from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum


class AgentStatus(Enum):
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


@dataclass
class AgentResult:
    """Agent执行结果"""
    success: bool
    data: Any = None
    message: str = ""
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class AgentInfo:
    """Agent信息"""
    agent_id: str
    name: str
    description: str
    scene_id: str
    intent_id: str
    version: str = "1.0.0"
    status: AgentStatus = AgentStatus.READY
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


from ..llm.client import LLMClient


class BaseAgent(ABC):
    """
    Agent基类 - 所有Agent必须继承此类
    
    核心特点：
    - 标准化接口：统一的入参/出参格式
    - 无状态设计：支持函数式调用
    - 可观测性：内置日志和状态管理
    """
    
    def __init__(self, agent_id: str, name: str, description: str, 
                 scene_id: str, intent_id: str):
        self.info = AgentInfo(
            agent_id=agent_id,
            name=name,
            description=description,
            scene_id=scene_id,
            intent_id=intent_id
        )
        self._status = AgentStatus.READY
        self.llm_client = None  # 大模型客户端
    
    def set_llm_client(self, llm_client: LLMClient):
        """设置大模型客户端"""
        self.llm_client = llm_client
    
    @abstractmethod
    def execute(self, user_input: str, context: Dict[str, Any]) -> AgentResult:
        """
        执行Agent任务
        
        Args:
            user_input: 用户输入
            context: 上下文信息（包含场景、意图识别结果等）
            
        Returns:
            AgentResult: 执行结果
        """
        pass
    
    def validate_input(self, user_input: str, context: Dict[str, Any]) -> bool:
        """验证输入参数"""
        return bool(user_input and isinstance(user_input, str))
    
    def pre_process(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """预处理"""
        return {"processed_input": user_input, "context": context}
    
    def post_process(self, result: AgentResult, context: Dict[str, Any]) -> AgentResult:
        """后处理"""
        return result
    
    def get_status(self) -> AgentStatus:
        """获取Agent状态"""
        return self._status
    
    def set_status(self, status: AgentStatus) -> None:
        """设置Agent状态"""
        self._status = status
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "agent_id": self.info.agent_id,
            "name": self.info.name,
            "description": self.info.description,
            "scene_id": self.info.scene_id,
            "intent_id": self.info.intent_id,
            "version": self.info.version,
            "status": self._status.value,
            "capabilities": self.info.capabilities
        }
