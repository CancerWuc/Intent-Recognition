from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class SceneStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


@dataclass
class Scene:
    """
    场景定义 - 业务维度的大分类
    
    示例：
    - 电商客服
    - 旅行规划
    - 企业报销
    """
    scene_id: str
    name: str
    description: str
    keywords: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    intents: Dict[str, 'Intent'] = field(default_factory=dict)
    status: SceneStatus = SceneStatus.ACTIVE
    metadata: Dict = field(default_factory=dict)
    
    def add_intent(self, intent: 'Intent') -> None:
        self.intents[intent.intent_id] = intent
    
    def get_intent(self, intent_id: str) -> Optional['Intent']:
        return self.intents.get(intent_id)
    
    def to_dict(self) -> Dict:
        return {
            "scene_id": self.scene_id,
            "name": self.name,
            "description": self.description,
            "keywords": self.keywords,
            "examples": self.examples,
            "intent_count": len(self.intents),
            "status": self.status.value,
            "metadata": self.metadata
        }
