from flask import Flask, render_template, request, jsonify, Response, stream_with_context, current_app, session, after_this_request
from flask_session import Session
from flask_cors import CORS
from intent_recognition.llm.client import LLMClient
from intent_recognition.router.router import IntentRouter
from intent_recognition.database import db, init_db, load_initial_data
from intent_recognition.database.models import SessionHistory
from intent_recognition.api import api_bp
from intent_recognition.api.response import api_success, api_error, sse_content, sse_error, sse_done
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# 加载 .flaskenv 和 .env 文件中的环境变量
load_dotenv()

app = Flask(__name__)

# 配置数据库
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///intent_recognition.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 配置会话
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-this-in-production')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = 'flask_session'
app.config['SESSION_PERMANENT'] = False

# 初始化会话
Session(app)

# 启用 CORS 支持
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

API_KEY = os.getenv('SILICONFLOW_API_KEY', '')
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.siliconflow.cn/v1/chat/completions')

# 初始化数据库
init_db(app)

# 加载初始数据
with app.app_context():
    load_initial_data(app)

# 初始化 LLM 客户端和路由器
llm_client = LLMClient(api_key=API_KEY, base_url=LLM_BASE_URL)
router = IntentRouter(llm_client=llm_client)
app.config['ROUTER'] = router

with app.app_context():
    router.load_from_database()

# 注册API蓝图
app.register_blueprint(api_bp)

def _get_router():
    return current_app.config['ROUTER']

@app.route('/api/config')
def get_config():
    """返回前端所需的运行时配置"""
    api_base_url = os.getenv('API_BASE_URL', '')
    return api_success(
        data={'api_base_url': api_base_url},
        api_base_url=api_base_url
    )

@app.route('/frontend-config.js')
def frontend_config_js():
    """为前端页面注入运行时配置，通过 <script src="/frontend-config.js"> 引用"""
    api_base_url = os.getenv('API_BASE_URL', '')
    js = f'window.__API_BASE_URL__ = {json.dumps(api_base_url)};'
    return Response(js, mimetype='application/javascript')

@app.route('/')
def index():
    """首页 - API 文档和前端访问说明"""
    payload = {
        'message': 'Intent Recognition API',
        'description': '智能意图识别和 Agent 执行系统',
        'frontend_url': '请访问前端页面：frontend/index.html',
        'api_docs': {
            'recognize': 'POST /api/recognize - 意图识别',
            'recognize_execute': 'POST /api/recognize/execute/stream - 流式执行 Agent',
            'session_new': 'POST /api/session/new - 创建新会话',
            'session_list': 'GET /api/session/list - 获取会话列表',
            'session_history': 'GET /api/session/history - 获取会话历史',
            'session_clear': 'POST /api/session/clear - 清空会话'
        }
    }
    return api_success(data=payload, **payload)

@app.route('/api/recognize', methods=['POST'])
def recognize():
    """意图识别 API（只识别，不执行Agent）"""
    data = request.json or {}
    user_input = (data.get('input') or '').strip()
    multi_agent_id = data.get('multi_agent_id')

    if not user_input:
        return api_error('请输入内容', code=400)

    router = _get_router()
    result = router.recognize_only(user_input, multi_agent_id=multi_agent_id)

    response = {
        'user_input': user_input,
        'scene': result.scene_name,
        'intent': result.intent_name,
        'agent_id': result.agent_id,
        'confidence': getattr(result.llm_recognition_result, 'confidence', 0.0),
        'reasoning': getattr(result.llm_recognition_result, 'reasoning', ''),
        'agent_name': result.metadata.get('agent_name', '') if result.metadata else '',
        'recognition_method': result.metadata.get('recognition_method', 'llm') if result.metadata else 'llm'
    }

    if not result.success:
        return api_error(result.error_message or '意图识别失败', code=400, data=response, **response)

    return api_success(data=response, **response)


@app.route('/api/recognize/execute/stream', methods=['POST'])
def recognize_execute_stream():
    """流式执行Agent API"""
    data = request.json or {}
    agent_id = (data.get('agent_id') or '').strip()
    user_input = (data.get('input') or '').strip()

    if not agent_id or not user_input:
        def error_gen():
            yield sse_error('缺少 agent_id 或 input', code=400).encode('utf-8')
            yield sse_done().encode('utf-8')
        return Response(error_gen(), mimetype='text/event-stream')

    agent = _get_router().registry.get_agent(agent_id)
    if not agent:
        def error_gen():
            yield sse_error(f'Agent未找到: {agent_id}', code=404).encode('utf-8')
            yield sse_done().encode('utf-8')
        return Response(error_gen(), mimetype='text/event-stream')

    prompt = getattr(agent, 'prompt', '')
    model_name = getattr(agent, 'agent_model_name', None)
    api_key = getattr(agent, 'agent_api_key', None)
    call_mode = getattr(agent, 'call_mode', 'external_model')
    api_url = getattr(agent, 'agent_api_url', None)
    hi_agent_id = getattr(agent, 'agent_hi_agent_id', None)
    hi_agent_headers = getattr(agent, 'hi_agent_headers', {})

    if api_key:
        client = LLMClient(api_key=api_key)
    else:
        client = llm_client

    session_id = data.get('session_id', '')
    db_history = SessionHistory.query.filter(
        SessionHistory.session_id == session_id,
        SessionHistory.user_input != ''
    ).order_by(SessionHistory.created_at.desc()).limit(5).all()
    db_history = list(reversed(db_history))

    app.logger.info(f'[Stream Memory] session_id={session_id}, history_count={len(db_history)}, call_mode={call_mode}')

    if db_history:
        history_text = "\n".join([
            f"用户: {h.user_input}\n系统: {h.response}"
            for h in db_history
        ])
        enhanced_prompt = f"{prompt}\n\n以下是当前会话的历史记录，请参考：\n{history_text}\n\n现在用户的新问题是："
    else:
        enhanced_prompt = prompt

    app.logger.info(f'[Stream Memory] enhanced_prompt length: {len(enhanced_prompt)} chars')

    def generate():
        yield b": connected\n\n"
        full_response = ""

        if call_mode == 'hi_agent':
            if not api_url or not api_key:
                yield sse_error('hi-agent模式需要配置API URL和API Key', code=400).encode('utf-8')
                yield sse_done().encode('utf-8')
                return
            stream_iter = client.call_hi_agent_stream(
                user_input=user_input,
                api_url=api_url,
                agent_id=hi_agent_id or agent_id,
                system_prompt=enhanced_prompt,
                cap_user_name=hi_agent_headers.get('cap_user_name'),
                real_name=hi_agent_headers.get('real_name'),
                kk=hi_agent_headers.get('KK'),
                oasis_access_token=hi_agent_headers.get('oasis_access_token'),
                ua=hi_agent_headers.get('ua'),
            )
        else:
            stream_iter = client.generate_stream(
                user_input,
                system_prompt=enhanced_prompt,
                model=model_name,
                max_tokens=getattr(agent, 'max_tokens', 1000)
            )

        for chunk in stream_iter:
            if isinstance(chunk, str):
                if chunk.startswith('data: ') and not chunk.strip().endswith('[DONE]'):
                    try:
                        payload = chunk[6:].strip()
                        if payload:
                            chunk_data = json.loads(payload)
                            if 'content' in chunk_data:
                                full_response += chunk_data['content']
                                yield sse_content(chunk_data['content']).encode('utf-8')
                            elif 'error' in chunk_data:
                                yield sse_error(chunk_data['error'], code=500).encode('utf-8')
                    except json.JSONDecodeError:
                        yield chunk.encode('utf-8')
            else:
                yield chunk
        yield sse_done().encode('utf-8')
        
        if session_id and full_response:
            try:
                with app.app_context():
                    placeholder = SessionHistory.query.filter_by(session_id=session_id, user_input='', response='新会话').first()
                    if placeholder:
                        db.session.delete(placeholder)
                    history = SessionHistory(
                        session_id=session_id,
                        user_input=user_input,
                        response=full_response,
                        agent_name=getattr(agent, 'name', '')
                    )
                    db.session.add(history)
                    db.session.commit()
                    app.logger.info(f'[Stream] Saved history for session {session_id}')
            except Exception as e:
                app.logger.error(f'[Stream] Failed to save history: {e}')

    resp = Response(generate(), mimetype='text/event-stream', direct_passthrough=True)
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['X-Accel-Buffering'] = 'no'
    resp.headers['Connection'] = 'keep-alive'
    return resp

@app.route('/api/debug/recognize', methods=['POST'])
def debug_recognize():
    """调试意图识别 API"""
    data = request.json or {}
    user_input = (data.get('input') or '').strip()
    multi_agent_id = data.get('multi_agent_id')
    
    if not user_input:
        return api_error('请输入内容', code=400)
    
    result = _get_router().recognize_only(user_input, multi_agent_id=multi_agent_id)
    
    response = {
        'user_input': user_input,
        'scene_name': result.scene_name,
        'intent_name': result.intent_name,
        'agent_id': result.agent_id,
        'agent_name': result.metadata.get('agent_name', ''),
        'confidence': getattr(result.llm_recognition_result, 'confidence', 0.0),
        'recognition_method': result.metadata.get('recognition_method', 'llm')
    }
    
    if not result.success:
        return api_error(result.error_message or '意图识别失败', code=400, data=response, **response)

    return api_success(data=response, **response)

# 管理员端路由（已迁移到前端，保留路由以便重定向）
@app.route('/admin')
def admin_index():
    """管理员首页 - 重定向到前端"""
    payload = {
        'message': '管理后台首页已迁移到前端',
        'frontend_url': 'frontend/admin/index.html'
    }
    return api_success(data=payload, **payload)

@app.route('/admin/agents')
def admin_agents():
    """智能体管理页面 - 重定向到前端"""
    payload = {
        'message': '智能体管理页面已迁移到前端',
        'frontend_url': 'frontend/admin/agents.html'
    }
    return api_success(data=payload, **payload)

@app.route('/admin/scene-intent')
def admin_scene_intent():
    """场景和意图管理 - 重定向到前端"""
    payload = {
        'message': '场景和意图管理页面已迁移到前端',
        'frontend_url': 'frontend/admin/scene-intent.html'
    }
    return api_success(data=payload, **payload)

@app.route('/admin/scene-intent/detail')
def admin_scene_intent_detail():
    """场景详情页面 - 重定向到前端"""
    payload = {
        'message': '场景详情页面已迁移到前端',
        'frontend_url': 'frontend/admin/scene-detail.html'
    }
    return api_success(data=payload, **payload)

@app.route('/admin/debug')
def admin_debug():
    """意图识别调试 - 重定向到前端"""
    payload = {
        'message': '意图识别调试页面已迁移到前端',
        'frontend_url': 'frontend/admin/debug.html'
    }
    return api_success(data=payload, **payload)



@app.route('/api/session/history', methods=['GET'])
def get_session_history():
    session_id = request.args.get('session_id')
    if not session_id:
        return api_error('缺少 session_id 参数', code=400)
    history = SessionHistory.query.filter_by(session_id=session_id).order_by(SessionHistory.created_at).all()
    history_data = [h.to_dict() for h in history]
    response_data = {
        'session_id': session_id,
        'history': history_data
    }
    return api_success(data=response_data, **response_data)

@app.route('/api/session/clear', methods=['POST'])
def clear_session():
    data = request.json or {}
    session_id = data.get('session_id')
    if not session_id:
        return api_error('缺少 session_id 参数', code=400)
    SessionHistory.query.filter_by(session_id=session_id).delete()
    db.session.commit()
    return api_success(data=None, msg='会话历史已清空')

@app.route('/api/session/new', methods=['POST'])
def create_new_session():
    import uuid
    session_id = str(uuid.uuid4())
    empty_history = SessionHistory(
        session_id=session_id,
        user_input='',
        response='新会话',
        agent_name=''
    )
    db.session.add(empty_history)
    db.session.commit()
    response_data = {
        'session_id': session_id,
        'message': '新会话已创建'
    }
    return api_success(data=response_data, session_id=session_id, message='新会话已创建')

@app.route('/api/session/list', methods=['GET'])
def get_session_list():
    try:
        session_ids = db.session.query(SessionHistory.session_id).distinct().all()
        session_ids = [s[0] for s in session_ids]
        sessions = []
        for sid in session_ids:
            latest_history = SessionHistory.query.filter(
                SessionHistory.session_id == sid,
                SessionHistory.user_input != ''
            ).order_by(SessionHistory.created_at.desc()).first()
            if latest_history:
                if latest_history.user_input:
                    latest_message = latest_history.user_input
                else:
                    latest_message = '新会话'
            else:
                latest_message = '空会话'
            sessions.append({
                'session_id': sid,
                'latest_message': latest_message,
                'created_at': latest_history.created_at.isoformat() if latest_history else None
            })
        sessions.sort(key=lambda x: x['created_at'] if x['created_at'] else '', reverse=True)
        return api_success(data={'sessions': sessions}, sessions=sessions)
    except Exception as e:
        return api_error(str(e), code=500)

@app.route('/api/session/save_history', methods=['POST'])
def save_session_history():
    data = request.json
    user_input = data.get('user_input', '')
    response_text = data.get('response', '')
    agent_name = data.get('agent_name', '')
    session_id = data.get('session_id')
    if not session_id:
        return api_error('缺少 session_id 参数', code=400)
    if not user_input or not response_text:
        return api_error('缺少必要参数', code=400)
    placeholder = SessionHistory.query.filter_by(session_id=session_id, user_input='', response='新会话').first()
    if placeholder:
        db.session.delete(placeholder)
    history = SessionHistory(
        session_id=session_id,
        user_input=user_input,
        response=response_text,
        agent_name=agent_name
    )
    db.session.add(history)
    db.session.commit()
    return api_success(data=None, msg='会话历史已保存')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
