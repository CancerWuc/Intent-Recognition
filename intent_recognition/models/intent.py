from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum


class IntentPriority(Enum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class IntentStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


@dataclass
class Intent:
    """
    意图定义 - 场景内的具体用户诉求
    
    示例（旅行规划场景下）：
    - 查机票
    - 订酒店
    - 查天气
    """
    intent_id: str
    scene_id: str
    name: str
    description: str
    keywords: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    agent_id: Optional[str] = None
    priority: IntentPriority = IntentPriority.MEDIUM
    status: IntentStatus = IntentStatus.ACTIVE
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "intent_id": self.intent_id,
            "scene_id": self.scene_id,
            "name": self.name,
            "description": self.description,
            "keywords": self.keywords,
            "examples": self.examples,
            "agent_id": self.agent_id,
            "priority": self.priority.value,
            "status": self.status.value,
            "parameters": self.parameters,
            "metadata": self.metadata
        }
