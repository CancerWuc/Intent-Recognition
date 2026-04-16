from flask import Blueprint, request, jsonify, current_app
from ..database import db, Scene, MultiAgent
import uuid
import json

scene_bp = Blueprint('scene', __name__, url_prefix='/api/scenes')

@scene_bp.route('', methods=['GET'])
def get_scenes():
    multi_agent_id = request.args.get('multi_agent_id')
    
    query = Scene.query
    if multi_agent_id:
        query = query.filter_by(multi_agent_id=multi_agent_id)
    
    scenes = query.order_by(Scene.sort_order.asc(), Scene.created_at.desc()).all()
    return jsonify({
        'success': True,
        'data': [scene.to_dict() for scene in scenes]
    })

@scene_bp.route('/<scene_id>', methods=['GET'])
def get_scene(scene_id):
    scene = Scene.query.get(scene_id)
    if not scene:
        return jsonify({
            'success': False,
            'error': '场景不存在'
        }), 404
    
    return jsonify({
        'success': True,
        'data': scene.to_dict()
    })

@scene_bp.route('', methods=['POST'])
def create_scene():
    data = request.json
    
    if not data.get('name'):
        return jsonify({
            'success': False,
            'error': '场景名称不能为空'
        }), 400
    
    multi_agent_id = data.get('multi_agent_id')
    if not multi_agent_id:
        return jsonify({
            'success': False,
            'error': '缺少multi_agent_id'
        }), 400
    
    multi_agent = MultiAgent.query.get(multi_agent_id)
    if not multi_agent:
        return jsonify({
            'success': False,
            'error': 'Multi-Agent不存在'
        }), 400
    
    scene_id = data.get('id') or str(uuid.uuid4())
    
    if Scene.query.get(scene_id):
        return jsonify({
            'success': False,
            'error': '场景ID已存在'
        }), 400
    
    scene = Scene()
    scene.id = scene_id
    scene.multi_agent_id = multi_agent_id
    scene.name = data.get('name')
    scene.description = data.get('description', '')
    scene.keywords = json.dumps(data.get('keywords', []))
    scene.examples = json.dumps(data.get('examples', []))
    scene.sort_order = data.get('sort_order', 0)
    
    db.session.add(scene)
    db.session.commit()
    
    current_app.config['ROUTER'].load_from_database(force=True)
    
    return jsonify({
        'success': True,
        'data': scene.to_dict()
    }), 201

@scene_bp.route('/<scene_id>', methods=['PUT'])
def update_scene(scene_id):
    scene = Scene.query.get(scene_id)
    if not scene:
        return jsonify({
            'success': False,
            'error': '场景不存在'
        }), 404
    
    data = request.json
    
    if data.get('name'):
        scene.name = data.get('name')
    if 'description' in data:
        scene.description = data.get('description')
    if 'keywords' in data:
        scene.keywords = json.dumps(data.get('keywords', []))
    if 'examples' in data:
        scene.examples = json.dumps(data.get('examples', []))
    
    db.session.commit()
    
    current_app.config['ROUTER'].load_from_database(force=True)
    
    return jsonify({
        'success': True,
        'data': scene.to_dict()
    })

@scene_bp.route('/<scene_id>', methods=['DELETE'])
def delete_scene(scene_id):
    from ..database import Intent
    from ..database.models import SceneVector, IntentVector
    scene = Scene.query.get(scene_id)
    if not scene:
        return jsonify({
            'success': False,
            'error': '场景不存在'
        }), 404
    
    intent_ids = [i.id for i in Intent.query.filter_by(scene_id=scene_id).all()]
    for iid in intent_ids:
        IntentVector.query.filter_by(intent_id=iid).delete()
    Intent.query.filter_by(scene_id=scene_id).delete()
    SceneVector.query.filter_by(scene_id=scene_id).delete()
    
    db.session.delete(scene)
    db.session.commit()
    
    current_app.config['ROUTER'].load_from_database(force=True)
    
    return jsonify({
        'success': True,
        'message': '场景已删除'
    })
