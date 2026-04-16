from flask import Blueprint, request, jsonify, current_app
from ..database import db, Scene, Intent, MultiAgent
import uuid
import json

multi_agent_bp = Blueprint('multi_agent', __name__, url_prefix='/api/multi-agents')


@multi_agent_bp.route('', methods=['GET'])
def get_multi_agents():
    multi_agents = MultiAgent.query.order_by(MultiAgent.created_at.desc()).all()
    result = []
    for ma in multi_agents:
        ma_dict = ma.to_dict()
        scene_count = Scene.query.filter_by(multi_agent_id=ma.id).count()
        intent_count = Intent.query.filter(
            Intent.scene.has(Scene.multi_agent_id == ma.id)
        ).count()
        ma_dict['scene_count'] = scene_count
        ma_dict['intent_count'] = intent_count
        result.append(ma_dict)
    
    return jsonify({
        'success': True,
        'data': result
    })


@multi_agent_bp.route('/<multi_agent_id>', methods=['GET'])
def get_multi_agent(multi_agent_id):
    multi_agent = MultiAgent.query.get(multi_agent_id)
    if not multi_agent:
        return jsonify({
            'success': False,
            'error': 'Multi-Agent不存在'
        }), 404
    
    scene_count = Scene.query.filter_by(multi_agent_id=multi_agent_id).count()
    intent_count = Intent.query.filter(
        Intent.scene.has(Scene.multi_agent_id == multi_agent_id)
    ).count()
    
    result = multi_agent.to_dict()
    result['scene_count'] = scene_count
    result['intent_count'] = intent_count
    return jsonify({'success': True, 'data': result})


@multi_agent_bp.route('', methods=['POST'])
def create_multi_agent():
    data = request.json
    
    if not data.get('name'):
        return jsonify({
            'success': False,
            'error': 'Multi-Agent名称不能为空'
        }), 400
    
    multi_agent_id = data.get('id') or str(uuid.uuid4())
    
    if MultiAgent.query.get(multi_agent_id):
        return jsonify({
            'success': False,
            'error': 'Multi-Agent ID已存在'
        }), 400
    
    multi_agent = MultiAgent()
    multi_agent.from_dict(data)
    db.session.add(multi_agent)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'data': multi_agent.to_dict()
    }), 201


@multi_agent_bp.route('/<multi_agent_id>', methods=['PUT'])
def update_multi_agent(multi_agent_id):
    multi_agent = MultiAgent.query.get(multi_agent_id)
    if not multi_agent:
        return jsonify({
            'success': False,
            'error': 'Multi-Agent不存在'
        }), 404
    
    multi_agent.from_dict(request.json)
    db.session.commit()
    
    current_app.config['ROUTER'].load_from_database(force=True)
    
    return jsonify({
        'success': True,
        'data': multi_agent.to_dict()
    })


@multi_agent_bp.route('/<multi_agent_id>', methods=['DELETE'])
def delete_multi_agent(multi_agent_id):
    multi_agent = MultiAgent.query.get(multi_agent_id)
    if not multi_agent:
        return jsonify({
            'success': False,
            'error': 'Multi-Agent不存在'
        }), 404
    
    from ..database.models import SceneVector, IntentVector
    
    scenes = Scene.query.filter_by(multi_agent_id=multi_agent_id).all()
    for scene in scenes:
        intents = Intent.query.filter_by(scene_id=scene.id).all()
        for intent in intents:
            IntentVector.query.filter_by(intent_id=intent.id).delete()
            db.session.delete(intent)
        SceneVector.query.filter_by(scene_id=scene.id).delete()
        db.session.delete(scene)
    
    db.session.delete(multi_agent)
    db.session.commit()
    
    current_app.config['ROUTER'].load_from_database(force=True)
    
    return jsonify({
        'success': True,
        'message': '删除成功'
    })


@multi_agent_bp.route('/<multi_agent_id>/set-default', methods=['POST'])
def set_default_multi_agent(multi_agent_id):
    MultiAgent.query.update({'is_default': False})
    multi_agent = MultiAgent.query.get(multi_agent_id)
    if multi_agent:
        multi_agent.is_default = True
        db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '设置成功'
    })
