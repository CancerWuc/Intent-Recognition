import uuid

from flask import Blueprint, request
from ..database import db, MultiAgent, MultiAgentsMapping
from .response import api_success, api_error

multi_agent_mapping_bp = Blueprint('multi_agent_mapping', __name__, url_prefix='/multi/agent')


def _get_request_data():
    return request.get_json(silent=True) or {}


def _parse_status(status_value):
    try:
        return int(status_value), None
    except (TypeError, ValueError):
        return None, 'status必须为整数'


@multi_agent_mapping_bp.route('', methods=['GET'])
def get_multi_agent_mappings():
    multi_agents_key = request.args.get('multi_agents_key')

    query = MultiAgentsMapping.query
    if multi_agents_key:
        query = query.filter_by(multi_agents_key=multi_agents_key)

    mappings = query.order_by(MultiAgentsMapping.multi_agents_id.asc()).all()
    return api_success(data=[mapping.to_dict() for mapping in mappings])


@multi_agent_mapping_bp.route('/<multi_agents_id>', methods=['GET'])
def get_multi_agent_mapping(multi_agents_id):
    mapping = MultiAgentsMapping.query.get(multi_agents_id)
    if not mapping:
        return api_error('multi_agents_mapping不存在', code=404)

    return api_success(data=mapping.to_dict())


@multi_agent_mapping_bp.route('', methods=['POST'])
def create_multi_agent_mapping():
    data = _get_request_data()

    multi_agents_id = (data.get('multi_agents_id') or '').strip() or str(uuid.uuid4())
    multi_agents_key = (data.get('multi_agents_key') or '').strip()

    if MultiAgentsMapping.query.get(multi_agents_id):
        return api_error('multi_agents_id已存在', code=400)

    if not multi_agents_key:
        return api_error('multi_agents_key不能为空', code=400)

    if not MultiAgent.query.get(multi_agents_key):
        return api_error('multi_agents_key关联的Multi-Agent不存在', code=400)

    if 'status' not in data:
        return api_error('status不能为空', code=400)

    status, error = _parse_status(data.get('status'))
    if error:
        return api_error(error, code=400)

    mapping = MultiAgentsMapping()
    mapping.from_dict({
        'multi_agents_id': multi_agents_id,
        'multi_agents_key': multi_agents_key,
        'status': status,
        'description': data.get('description')
    })

    db.session.add(mapping)
    db.session.commit()

    return api_success(data=mapping.to_dict())


@multi_agent_mapping_bp.route('/<multi_agents_id>/update', methods=['POST'])
def update_multi_agent_mapping(multi_agents_id):
    mapping = MultiAgentsMapping.query.get(multi_agents_id)
    if not mapping:
        return api_error('multi_agents_mapping不存在', code=404)

    data = _get_request_data()

    if 'multi_agents_id' in data and data.get('multi_agents_id') != multi_agents_id:
        return api_error('不允许修改multi_agents_id', code=400)

    if 'multi_agents_key' in data:
        multi_agents_key = (data.get('multi_agents_key') or '').strip()
        if not multi_agents_key:
            return api_error('multi_agents_key不能为空', code=400)
        if not MultiAgent.query.get(multi_agents_key):
            return api_error('multi_agents_key关联的Multi-Agent不存在', code=400)
        mapping.multi_agents_key = multi_agents_key

    if 'status' in data:
        status, error = _parse_status(data.get('status'))
        if error:
            return api_error(error, code=400)
        mapping.status = status

    if 'description' in data:
        mapping.description = data.get('description')

    db.session.commit()

    return api_success(data=mapping.to_dict())


@multi_agent_mapping_bp.route('/<multi_agents_id>/delete', methods=['POST'])
def delete_multi_agent_mapping(multi_agents_id):
    mapping = MultiAgentsMapping.query.get(multi_agents_id)
    if not mapping:
        return api_error('multi_agents_mapping不存在', code=404)

    db.session.delete(mapping)
    db.session.commit()

    return api_success(data=None, msg='删除成功')
