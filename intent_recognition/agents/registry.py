from typing import Dict, Optional, Type, Callable, Any
from dataclasses import dataclass, field
import logging

from ..models import BaseAgent, AgentResult, AgentStatus


logger = logging.getLogger(__name__)


@dataclass
class AgentRegistryItem:
    """Agent注册项"""
    agent_id: str
    agent_class: Type[BaseAgent]
    agent_instance: Optional[BaseAgent] = None
    factory: Optional[Callable] = None
    metadata: Dict = field(default_factory=dict)


class AgentRegistry:
    """
    Agent注册中心
    
    核心功能：
    - 管理所有Agent的注册和发现
    - 支持类注册和实例注册
    - 支持工厂函数创建Agent
    """
    
    def __init__(self):
        self._agents: Dict[str, AgentRegistryItem] = {}
        self._intent_agent_map: Dict[str, str] = {}
        self._scene_agent_map: Dict[str, list] = {}
    
    def register_agent_class(self, agent_id: str, agent_class: Type[BaseAgent],
                             intent_id: str = None, scene_id: str = None,
                             metadata: Dict = None) -> None:
        """
        注册Agent类
        
        Args:
            agent_id: Agent ID
            agent_class: Agent类
            intent_id: 关联的意图ID
            scene_id: 关联的场景ID
            metadata: 元数据
        """
        self._agents[agent_id] = AgentRegistryItem(
            agent_id=agent_id,
            agent_class=agent_class,
            metadata=metadata or {}
        )
        
        if intent_id:
            self._intent_agent_map[intent_id] = agent_id
        
        if scene_id:
            if scene_id not in self._scene_agent_map:
                self._scene_agent_map[scene_id] = []
            self._scene_agent_map[scene_id].append(agent_id)
        
        logger.info(f"注册Agent类: {agent_id}, 意图: {intent_id}, 场景: {scene_id}")
    
    def register_agent_instance(self, agent_id: str, agent_instance: BaseAgent,
                                intent_id: str = None, scene_id: str = None,
                                metadata: Dict = None) -> None:
        """
        注册Agent实例
        
        Args:
            agent_id: Agent ID
            agent_instance: Agent实例
            intent_id: 关联的意图ID
            scene_id: 关联的场景ID
            metadata: 元数据
        """
        self._agents[agent_id] = AgentRegistryItem(
            agent_id=agent_id,
            agent_class=type(agent_instance),
            agent_instance=agent_instance,
            metadata=metadata or {}
        )
        
        if intent_id:
            self._intent_agent_map[intent_id] = agent_id
        
        if scene_id:
            if scene_id not in self._scene_agent_map:
                self._scene_agent_map[scene_id] = []
            self._scene_agent_map[scene_id].append(agent_id)
        
        logger.info(f"注册Agent实例: {agent_id}, 意图: {intent_id}, 场景: {scene_id}")
    
    def register_agent_factory(self, agent_id: str, factory: Callable,
                               intent_id: str = None, scene_id: str = None,
                               metadata: Dict = None) -> None:
        """
        注册Agent工厂函数
        
        Args:
            agent_id: Agent ID
            factory: 工厂函数，返回Agent实例
            intent_id: 关联的意图ID
            scene_id: 关联的场景ID
            metadata: 元数据
        """
        self._agents[agent_id] = AgentRegistryItem(
            agent_id=agent_id,
            agent_class=None,
            factory=factory,
            metadata=metadata or {}
        )
        
        if intent_id:
            self._intent_agent_map[intent_id] = agent_id
        
        if scene_id:
            if scene_id not in self._scene_agent_map:
                self._scene_agent_map[scene_id] = []
            self._scene_agent_map[scene_id].append(agent_id)
        
        logger.info(f"注册Agent工厂: {agent_id}, 意图: {intent_id}, 场景: {scene_id}")
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """
        获取Agent实例
        
        Args:
            agent_id: Agent ID
            
        Returns:
            BaseAgent实例或None
        """
        item = self._agents.get(agent_id)
        if not item:
            logger.warning(f"Agent未找到: {agent_id}")
            return None
        
        if item.agent_instance:
            return item.agent_instance
        
        if item.factory:
            try:
                item.agent_instance = item.factory()
                return item.agent_instance
            except Exception as e:
                logger.error(f"工厂创建Agent失败: {agent_id}, 错误: {e}")
                return None
        
        if item.agent_class:
            try:
                item.agent_instance = item.agent_class()
                return item.agent_instance
            except Exception as e:
                logger.error(f"实例化Agent失败: {agent_id}, 错误: {e}")
                return None
        
        return None
    
    def get_agent_by_intent(self, intent_id: str) -> Optional[BaseAgent]:
        """通过意图ID获取Agent"""
        agent_id = self._intent_agent_map.get(intent_id)
        if agent_id:
            return self.get_agent(agent_id)
        return None
    
    def get_agents_by_scene(self, scene_id: str) -> list:
        """获取场景下的所有Agent"""
        agent_ids = self._scene_agent_map.get(scene_id, [])
        agents = []
        for agent_id in agent_ids:
            agent = self.get_agent(agent_id)
            if agent:
                agents.append(agent)
        return agents
    
    def list_agents(self) -> Dict[str, Dict]:
        """列出所有Agent信息"""
        result = {}
        for agent_id, item in self._agents.items():
            result[agent_id] = {
                "agent_id": agent_id,
                "has_instance": item.agent_instance is not None,
                "has_class": item.agent_class is not None,
                "has_factory": item.factory is not None,
                "metadata": item.metadata
            }
        return result
    
    def unregister_agent(self, agent_id: str) -> bool:
        """注销Agent"""
        if agent_id in self._agents:
            del self._agents[agent_id]
            
            for intent_id, aid in list(self._intent_agent_map.items()):
                if aid == agent_id:
                    del self._intent_agent_map[intent_id]
            
            for scene_id, aids in self._scene_agent_map.items():
                if agent_id in aids:
                    aids.remove(agent_id)
            
            logger.info(f"注销Agent: {agent_id}")
            return True
        return False
    
    def clear(self) -> None:
        """清空所有注册"""
        self._agents.clear()
        self._intent_agent_map.clear()
        self._scene_agent_map.clear()
        logger.info("清空所有Agent注册")
