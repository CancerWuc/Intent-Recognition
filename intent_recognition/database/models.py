from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import base64
import numpy as np

db = SQLAlchemy()

class MultiAgent(db.Model):
    __tablename__ = 'multi_agents'
    
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    color = db.Column(db.String(20))
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'color': self.color,
            'is_default': self.is_default,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def from_dict(self, data):
        if 'id' in data and data['id'] is not None:
            self.id = data['id']
        self.name = data.get('name')
        self.description = data.get('description', '')
        self.icon = data.get('icon', '')
        self.color = data.get('color', '')
        self.is_default = data.get('is_default', False)
        self.is_active = data.get('is_active', True)

class Scene(db.Model):
    __tablename__ = 'scenes'
    
    id = db.Column(db.String(50), primary_key=True)
    multi_agent_id = db.Column(db.String(50), db.ForeignKey('multi_agents.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    keywords = db.Column(db.Text)
    examples = db.Column(db.Text)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    multi_agent = db.relationship('MultiAgent', backref=db.backref('scenes', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'multi_agent_id': getattr(self, 'multi_agent_id', None),
            'name': self.name,
            'description': self.description,
            'keywords': json.loads(self.keywords) if self.keywords else [],
            'examples': json.loads(self.examples) if self.examples else [],
            'sort_order': getattr(self, 'sort_order', 0),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def from_dict(self, data):
        self.id = data.get('id')
        self.multi_agent_id = data.get('multi_agent_id')
        self.name = data.get('name')
        self.description = data.get('description', '')
        self.keywords = json.dumps(data.get('keywords', []))
        self.examples = json.dumps(data.get('examples', []))
        self.sort_order = data.get('sort_order', 0)


class Intent(db.Model):
    __tablename__ = 'intents'

    id = db.Column(db.String(50), primary_key=True)
    scene_id = db.Column(db.String(50), db.ForeignKey('scenes.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    keywords = db.Column(db.Text)
    examples = db.Column(db.Text)
    agent_id = db.Column(db.String(50), db.ForeignKey('agents.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scene = db.relationship('Scene', backref=db.backref('intents', lazy=True))
    agent = db.relationship('Agent', backref=db.backref('intents', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'scene_id': self.scene_id,
            'name': self.name,
            'description': self.description,
            'keywords': json.loads(self.keywords) if self.keywords else [],
            'examples': json.loads(self.examples) if self.examples else [],
            'agent_id': self.agent_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def from_dict(self, data):
        self.id = data.get('id')
        self.scene_id = data.get('scene_id')
        self.name = data.get('name')
        self.description = data.get('description', '')
        self.keywords = json.dumps(data.get('keywords', []))
        self.examples = json.dumps(data.get('examples', []))
        self.agent_id = data.get('agent_id')


class Agent(db.Model):
    __tablename__ = 'agents'
    
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    prompt = db.Column(db.Text)
    capabilities = db.Column(db.Text)
    parameters = db.Column(db.Text)
    call_mode = db.Column(db.String(20), default='external_model')
    api_key = db.Column(db.String(200))
    model_name = db.Column(db.String(100))
    api_url = db.Column(db.String(500))
    hi_agent_id = db.Column(db.String(100))
    max_tokens = db.Column(db.Integer, default=1000)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'prompt': self.prompt,
            'capabilities': json.loads(self.capabilities) if self.capabilities else [],
            'parameters': json.loads(self.parameters) if self.parameters else {},
            'call_mode': self.call_mode or 'external_model',
            'api_key': self.api_key,
            'model_name': self.model_name,
            'api_url': self.api_url,
            'hi_agent_id': self.hi_agent_id,
            'max_tokens': self.max_tokens,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def from_dict(self, data):
        self.id = data.get('id')
        self.name = data.get('name')
        self.description = data.get('description', '')
        self.prompt = data.get('prompt', '')
        self.capabilities = json.dumps(data.get('capabilities', []))
        self.parameters = json.dumps(data.get('parameters', {}))
        self.call_mode = data.get('call_mode', 'external_model')
        self.api_key = data.get('api_key')
        self.model_name = data.get('model_name')
        self.api_url = data.get('api_url')
        self.hi_agent_id = data.get('hi_agent_id')
        self.max_tokens = data.get('max_tokens', 1000)


def vector_to_bytes(vector: np.ndarray) -> bytes:
    return base64.b64encode(vector.astype(np.float32).tobytes())


def bytes_to_vector(data: bytes) -> np.ndarray:
    return np.frombuffer(base64.b64decode(data), dtype=np.float32)


class SceneVector(db.Model):
    __tablename__ = 'scene_vectors'

    scene_id = db.Column(db.String(50), db.ForeignKey('scenes.id'), primary_key=True)
    vector_data = db.Column(db.LargeBinary, nullable=False)
    text_hash = db.Column(db.String(64), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scene = db.relationship('Scene', backref=db.backref('vector', uselist=False))

    def set_vector(self, vector: np.ndarray):
        self.vector_data = vector_to_bytes(vector)

    def get_vector(self) -> np.ndarray:
        return bytes_to_vector(self.vector_data)


class IntentVector(db.Model):
    __tablename__ = 'intent_vectors'

    intent_id = db.Column(db.String(50), db.ForeignKey('intents.id'), primary_key=True)
    vector_data = db.Column(db.LargeBinary, nullable=False)
    text_hash = db.Column(db.String(64), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    intent = db.relationship('Intent', backref=db.backref('vector', uselist=False))

    def set_vector(self, vector: np.ndarray):
        self.vector_data = vector_to_bytes(vector)

    def get_vector(self) -> np.ndarray:
        return bytes_to_vector(self.vector_data)


class SessionHistory(db.Model):
    __tablename__ = 'session_histories'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    user_input = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    agent_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_input': self.user_input,
            'response': self.response,
            'agent_name': self.agent_name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
