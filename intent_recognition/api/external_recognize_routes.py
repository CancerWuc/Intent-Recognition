import json

from flask import Blueprint, request, jsonify, current_app, Response

from ..database import db, MultiAgent, SessionHistory

external_recognize_bp = Blueprint('external_recognize', __name__, url_prefix='/multi/agent')


def _sse_payload(payload):
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _error_stream(message):
    def generate():
        yield b": connected\n\n"
        yield _sse_payload({'error': message}).encode('utf-8')
        yield b"data: [DONE]\n\n"

    return Response(generate(), mimetype='text/event-stream')


def _build_enhanced_prompt(app, session_id, prompt):
    if not session_id:
        return prompt

    db_history = SessionHistory.query.filter(
        SessionHistory.session_id == session_id,
        SessionHistory.user_input != ''
    ).order_by(SessionHistory.created_at.desc()).limit(5).all()
    db_history = list(reversed(db_history))

    app.logger.info(
        f'[External Stream Memory] session_id={session_id}, history_count={len(db_history)}'
    )

    if not db_history:
        return prompt

    history_text = "\n".join([
        f"用户: {history.user_input}\n系统: {history.response}"
        for history in db_history
    ])
    return f"{prompt}\n\n以下是当前会话的历史记录，请参考：\n{history_text}\n\n现在用户的新问题是："


def _build_stream_iterator(agent, router, user_input, enhanced_prompt):
    api_key = getattr(agent, 'agent_api_key', None)
    call_mode = getattr(agent, 'call_mode', 'external_model')
    api_url = getattr(agent, 'agent_api_url', None)
    hi_agent_id = getattr(agent, 'agent_hi_agent_id', None)
    hi_agent_headers = getattr(agent, 'hi_agent_headers', {})

    if api_key:
        from ..llm.client import LLMClient
        client = LLMClient(api_key=api_key)
    else:
        client = router.llm_client

    if call_mode == 'hi_agent':
        if not api_url or not api_key:
            return None, 'hi-agent模式需要配置API URL和API Key'
        return client.call_hi_agent_stream(
            user_input=user_input,
            api_url=api_url,
            agent_id=hi_agent_id or getattr(agent.info, 'agent_id', ''),
            system_prompt=enhanced_prompt,
            cap_user_name=hi_agent_headers.get('cap_user_name'),
            real_name=hi_agent_headers.get('real_name'),
            kk=hi_agent_headers.get('KK'),
            oasis_access_token=hi_agent_headers.get('oasis_access_token'),
            ua=hi_agent_headers.get('ua'),
        ), None

    return client.generate_stream(
        user_input,
        system_prompt=enhanced_prompt,
        model=getattr(agent, 'agent_model_name', None),
        max_tokens=getattr(agent, 'max_tokens', 1000)
    ), None


def _save_session_history(app, session_id, user_input, full_response, agent):
    if not session_id or not full_response:
        return

    try:
        with app.app_context():
            placeholder = SessionHistory.query.filter_by(
                session_id=session_id,
                user_input='',
                response='新会话'
            ).first()
            if placeholder:
                db.session.delete(placeholder)

            history = SessionHistory(
                session_id=session_id,
                user_input=user_input,
                response=full_response,
                agent_name=getattr(agent, 'name', '') or getattr(getattr(agent, 'info', None), 'name', '')
            )
            db.session.add(history)
            db.session.commit()
            app.logger.info(f'[External Stream] Saved history for session {session_id}')
    except Exception as exc:
        app.logger.error(f'[External Stream] Failed to save history: {exc}')


@external_recognize_bp.route('/recognize', methods=['POST'])
def external_recognize():
    """对外暴露的多智能体意图识别接口"""
    data = request.get_json(silent=True) or {}
    user_input = (data.get('input') or '').strip()
    multi_agent_id = (data.get('multi_agent_id') or '').strip() or None

    if not user_input:
        return jsonify({
            'success': False,
            'error': '请输入内容'
        }), 400

    if multi_agent_id and not MultiAgent.query.get(multi_agent_id):
        return jsonify({
            'success': False,
            'error': 'multi_agent_id对应的Multi-Agent不存在'
        }), 400

    result = current_app.config['ROUTER'].recognize_only(
        user_input,
        multi_agent_id=multi_agent_id
    )

    response = {
        'success': result.success,
        'user_input': user_input,
        'multi_agent_id': multi_agent_id,
        'scene': result.scene_name,
        'intent': result.intent_name,
        'agent_id': result.agent_id,
        'confidence': getattr(result.llm_recognition_result, 'confidence', 0.0),
        'reasoning': getattr(result.llm_recognition_result, 'reasoning', ''),
        'agent_name': result.metadata.get('agent_name', '') if result.metadata else '',
        'recognition_method': result.metadata.get('recognition_method', 'llm') if result.metadata else 'llm'
    }

    if not result.success:
        response['error'] = result.error_message

    return jsonify(response)


@external_recognize_bp.route('/recognize/execute', methods=['POST'])
def external_recognize_execute_stream():
    """对外暴露的多智能体意图识别并流式执行接口"""
    data = request.get_json(silent=True) or {}
    user_input = (data.get('input') or '').strip()
    multi_agent_id = (data.get('multi_agent_id') or '').strip() or None
    session_id = (data.get('session_id') or '').strip()

    if not user_input:
        return _error_stream('请输入内容')

    if multi_agent_id and not MultiAgent.query.get(multi_agent_id):
        return _error_stream('multi_agent_id对应的Multi-Agent不存在')

    app = current_app._get_current_object()
    router = current_app.config['ROUTER']
    result = router.recognize_only(user_input, multi_agent_id=multi_agent_id)

    if not result.success:
        return _error_stream(result.error_message or '意图识别失败')

    if not result.agent_id:
        return _error_stream('识别失败：未找到对应的智能体')

    agent = router.registry.get_agent(result.agent_id)
    if not agent:
        return _error_stream(f'Agent未找到: {result.agent_id}')

    prompt = getattr(agent, 'prompt', '')
    enhanced_prompt = _build_enhanced_prompt(app, session_id, prompt)
    stream_iter, stream_error = _build_stream_iterator(agent, router, user_input, enhanced_prompt)
    if stream_error:
        return _error_stream(stream_error)

    meta_payload = {
        'meta': {
            'scene': result.scene_name,
            'intent': result.intent_name,
            'agent_id': result.agent_id,
            'agent_name': result.metadata.get('agent_name', '') if result.metadata else '',
            'recognition_method': result.metadata.get('recognition_method', 'llm') if result.metadata else 'llm',
            'confidence': getattr(result.llm_recognition_result, 'confidence', 0.0),
            'multi_agent_id': multi_agent_id
        }
    }

    def generate():
        yield b": connected\n\n"
        yield _sse_payload(meta_payload).encode('utf-8')
        full_response = ""

        for chunk in stream_iter:
            if isinstance(chunk, str):
                if chunk.startswith('data: ') and not chunk.strip().endswith('[DONE]'):
                    try:
                        payload = chunk[6:].strip()
                        if payload:
                            chunk_data = json.loads(payload)
                            if 'content' in chunk_data:
                                full_response += chunk_data['content']
                    except json.JSONDecodeError:
                        pass
                yield chunk.encode('utf-8')
            else:
                yield chunk

        yield b"data: [DONE]\n\n"
        _save_session_history(app, session_id, user_input, full_response, agent)

    response = Response(generate(), mimetype='text/event-stream', direct_passthrough=True)
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    return response
