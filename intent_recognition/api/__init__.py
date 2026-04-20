from flask import Blueprint
from .scene_routes import scene_bp
from .intent_routes import intent_bp
from .agent_routes import agent_bp
from .multi_agent_routes import multi_agent_bp
from .multi_agent_mapping_routes import multi_agent_mapping_bp
from .external_recognize_routes import external_recognize_bp

api_bp = Blueprint('api', __name__)

# 注册所有子蓝图
api_bp.register_blueprint(scene_bp)
api_bp.register_blueprint(intent_bp)
api_bp.register_blueprint(agent_bp)
api_bp.register_blueprint(multi_agent_bp)
api_bp.register_blueprint(multi_agent_mapping_bp)
api_bp.register_blueprint(external_recognize_bp)

__all__ = ['api_bp']
