from flask import Blueprint, request, current_app
from ..database import db, Intent, Scene
from .response import api_success, api_error
import uuid
import json

intent_bp = Blueprint('intent', __name__, url_prefix='/api/intents')

@intent_bp.route('', methods=['GET'])
def get_intents():
    scene_id = request.args.get('scene_id')
    if scene_id:
        intents = Intent.query.filter_by(scene_id=scene_id).all()
    else:
        intents = Intent.query.all()
    
    return api_success(data=[intent.to_dict() for intent in intents])

@intent_bp.route('/<intent_id>', methods=['GET'])
def get_intent(intent_id):
    intent = Intent.query.get(intent_id)
    if not intent:
        return api_error('意图不存在', code=404)
    
    return api_success(data=intent.to_dict())

@intent_bp.route('/scene/<scene_id>', methods=['GET'])
def get_intents_by_scene(scene_id):
    if not Scene.query.get(scene_id):
        return api_error('场景不存在', code=404)
    
    intents = Intent.query.filter_by(scene_id=scene_id).all()
    return api_success(data=[intent.to_dict() for intent in intents])

@intent_bp.route('', methods=['POST'])
def create_intent():
    data = request.json
    
    if not data.get('name'):
        return api_error('意图名称不能为空', code=400)
    
    if not data.get('scene_id'):
        return api_error('场景ID不能为空', code=400)
    
    if not Scene.query.get(data.get('scene_id')):
        return api_error('场景不存在', code=400)
    
    intent_id = data.get('id') or str(uuid.uuid4())
    
    if Intent.query.get(intent_id):
        return api_error('意图ID已存在', code=400)
    
    intent = Intent()
    intent.id = intent_id
    intent.scene_id = data.get('scene_id')
    intent.name = data.get('name')
    intent.description = data.get('description', '')
    intent.keywords = json.dumps(data.get('keywords', []))
    intent.examples = json.dumps(data.get('examples', []))
    intent.agent_id = data.get('agent_id')

    db.session.add(intent)
    db.session.commit()
    
    current_app.config['ROUTER'].load_from_database(force=True)
    
    return api_success(data=intent.to_dict())

@intent_bp.route('/<intent_id>', methods=['PUT'])
def update_intent(intent_id):
    intent = Intent.query.get(intent_id)
    if not intent:
        return api_error('意图不存在', code=404)
    
    data = request.json
    
    if data.get('name'):
        intent.name = data.get('name')
    if 'description' in data:
        intent.description = data.get('description')
    if 'keywords' in data:
        intent.keywords = json.dumps(data.get('keywords', []))
    if 'examples' in data:
        intent.examples = json.dumps(data.get('examples', []))
    if 'agent_id' in data:
        intent.agent_id = data.get('agent_id')
    
    db.session.commit()
    
    current_app.config['ROUTER'].load_from_database(force=True)
    
    return api_success(data=intent.to_dict())

@intent_bp.route('/<intent_id>', methods=['DELETE'])
def delete_intent(intent_id):
    intent = Intent.query.get(intent_id)
    if not intent:
        return api_error('意图不存在', code=404)
    
    from ..database.models import IntentVector
    IntentVector.query.filter_by(intent_id=intent_id).delete()
    
    db.session.delete(intent)
    db.session.commit()
    
    current_app.config['ROUTER'].load_from_database(force=True)
    
    return api_success(data=None, msg='意图已删除')
