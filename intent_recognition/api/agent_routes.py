from flask import Blueprint, request, current_app
from ..database import db, Agent
from ..llm.client import LLMClient
from .response import api_success, api_error
import uuid
import json

agent_bp = Blueprint('agent', __name__, url_prefix='/api/agents')

@agent_bp.route('', methods=['GET'])
def get_agents():
    agents = Agent.query.all()
    return api_success(data=[agent.to_dict() for agent in agents])

@agent_bp.route('/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    agent = Agent.query.get(agent_id)
    if not agent:
        return api_error('智能体不存在', code=404)
    
    return api_success(data=agent.to_dict())

@agent_bp.route('', methods=['POST'])
def create_agent():
    data = request.json
    
    if not data.get('name'):
        return api_error('智能体名称不能为空', code=400)
    
    agent_id = data.get('id') or str(uuid.uuid4())
    
    if Agent.query.get(agent_id):
        return api_error('智能体ID已存在', code=400)
    
    agent = Agent()
    agent.id = agent_id
    agent.name = data.get('name')
    agent.description = data.get('description', '')
    agent.prompt = data.get('prompt', '')
    agent.capabilities = json.dumps(data.get('capabilities', []))
    agent.parameters = json.dumps(data.get('parameters', {}))
    agent.call_mode = data.get('call_mode', 'external_model')
    agent.api_key = data.get('api_key')
    agent.model_name = data.get('model_name')
    agent.api_url = data.get('api_url')
    agent.hi_agent_id = data.get('hi_agent_id')
    agent.max_tokens = data.get('max_tokens', 1000)

    db.session.add(agent)
    db.session.commit()
    
    current_app.config['ROUTER'].load_from_database(force=True)
    
    return api_success(data=agent.to_dict())

@agent_bp.route('/<agent_id>', methods=['PUT'])
def update_agent(agent_id):
    agent = Agent.query.get(agent_id)
    if not agent:
        return api_error('智能体不存在', code=404)
    
    data = request.json
    
    if data.get('name'):
        agent.name = data.get('name')
    if 'description' in data:
        agent.description = data.get('description')
    if 'prompt' in data:
        agent.prompt = data.get('prompt')
    if 'capabilities' in data:
        agent.capabilities = json.dumps(data.get('capabilities', []))
    if 'parameters' in data:
        agent.parameters = json.dumps(data.get('parameters', {}))
    if 'call_mode' in data:
        agent.call_mode = data.get('call_mode')
    if 'api_key' in data:
        agent.api_key = data.get('api_key')
    if 'model_name' in data:
        agent.model_name = data.get('model_name')
    if 'api_url' in data:
        agent.api_url = data.get('api_url')
    if 'hi_agent_id' in data:
        agent.hi_agent_id = data.get('hi_agent_id')
    if 'max_tokens' in data:
        agent.max_tokens = data.get('max_tokens')

    db.session.commit()
    
    current_app.config['ROUTER'].load_from_database(force=True)
    
    return api_success(data=agent.to_dict())

@agent_bp.route('/<agent_id>', methods=['DELETE'])
def delete_agent(agent_id):
    agent = Agent.query.get(agent_id)
    if not agent:
        return api_error('智能体不存在', code=404)
    
    db.session.delete(agent)
    db.session.commit()
    
    current_app.config['ROUTER'].load_from_database(force=True)
    
    return api_success(data=None, msg='智能体已删除')

@agent_bp.route('/<agent_id>/test', methods=['POST'])
def test_agent(agent_id):
    agent = Agent.query.get(agent_id)
    if not agent:
        return api_error('智能体不存在', code=404)
    
    data = request.json
    test_input = data.get('input', '')
    
    if not test_input:
        return api_error('测试输入不能为空', code=400)
    
    try:
        agent_dict = agent.to_dict()
        call_mode = agent_dict.get('call_mode', 'external_model')

        if call_mode == 'hi_agent':
            api_url = agent_dict.get('api_url')
            api_key = agent_dict.get('api_key')
            hi_agent_id = agent_dict.get('hi_agent_id')

            if not api_url or not api_key:
                return api_error('hi-agent模式需要配置API URL和API Key', code=400)

            client = LLMClient(api_key=api_key, base_url=api_url)
            response = client.call_hi_agent(
                user_input=test_input,
                api_url=api_url,
                agent_id=hi_agent_id or agent_id,
                system_prompt=agent.prompt
            )
        else:
            api_key = agent_dict.get('api_key')
            model_name = agent_dict.get('model_name')

            if api_key:
                client = LLMClient(api_key=api_key)
                response = client.generate(test_input, system_prompt=agent.prompt, model=model_name)
            else:
                from app import llm_client
                response = llm_client.generate(test_input, system_prompt=agent.prompt, model=model_name)

        return api_success(data={
            'input': test_input,
            'response': response
        })
    except Exception as e:
        return api_error(f'测试失败: {str(e)}', code=500)
