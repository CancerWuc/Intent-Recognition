from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import logging
import time

from ..models import BaseAgent, AgentResult, AgentStatus
from .registry import AgentRegistry
from ..llm.client import LLMClient


logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    agent_id: Optional[str] = None
    agent_result: Optional[AgentResult] = None
    execution_time_ms: float = 0.0
    error_message: str = ""
    metadata: Dict = field(default_factory=dict)


class AgentExecutor:
    """
    Agent执行器
    
    核心功能：
    - 直接调用Agent（无A2A依赖）
    - 执行前后处理
    - 性能监控
    """
    
    def __init__(self, registry: AgentRegistry, llm_client: Optional[LLMClient] = None):
        self.registry = registry
        self.llm_client = llm_client
        self._execution_stats: Dict[str, Dict] = {}
    
    def execute(self, agent_id: str, user_input: str, 
                context: Dict[str, Any] = None) -> ExecutionResult:
        """
        执行Agent
        
        Args:
            agent_id: Agent ID
            user_input: 用户输入
            context: 上下文信息
            
        Returns:
            ExecutionResult: 执行结果
        """
        start_time = time.time()
        
        agent = self.registry.get_agent(agent_id)
        if not agent:
            return ExecutionResult(
                success=False,
                agent_id=agent_id,
                error_message=f"Agent未找到: {agent_id}"
            )
        
        # 设置大模型客户端
        if self.llm_client:
            agent.set_llm_client(self.llm_client)
        
        if not agent.validate_input(user_input, context or {}):
            return ExecutionResult(
                success=False,
                agent_id=agent_id,
                error_message="输入验证失败"
            )
        
        try:
            agent.set_status(AgentStatus.BUSY)
            
            preprocessed = agent.pre_process(user_input, context or {})
            processed_input = preprocessed.get("processed_input", user_input)
            processed_context = preprocessed.get("context", context or {})
            
            agent_result = agent.execute(processed_input, processed_context)
            
            final_result = agent.post_process(agent_result, processed_context)
            
            agent.set_status(AgentStatus.READY)
            
            execution_time = (time.time() - start_time) * 1000
            self._update_stats(agent_id, execution_time, final_result.success)
            
            return ExecutionResult(
                success=True,
                agent_id=agent_id,
                agent_result=final_result,
                execution_time_ms=execution_time,
                metadata={
                    "agent_name": agent.info.name,
                    "scene_id": agent.info.scene_id,
                    "intent_id": agent.info.intent_id
                }
            )
            
        except Exception as e:
            agent.set_status(AgentStatus.ERROR)
            execution_time = (time.time() - start_time) * 1000
            
            logger.error(f"Agent执行失败: {agent_id}, 错误: {e}", exc_info=True)
            
            return ExecutionResult(
                success=False,
                agent_id=agent_id,
                execution_time_ms=execution_time,
                error_message=str(e),
                metadata={"exception_type": type(e).__name__}
            )
    
    def execute_by_intent(self, intent_id: str, user_input: str,
                          context: Dict[str, Any] = None) -> ExecutionResult:
        """通过意图ID执行Agent"""
        agent = self.registry.get_agent_by_intent(intent_id)
        if agent:
            return self.execute(agent.info.agent_id, user_input, context)
        
        return ExecutionResult(
            success=False,
            error_message=f"意图未映射到Agent: {intent_id}"
        )
    
    def _update_stats(self, agent_id: str, execution_time: float, success: bool) -> None:
        """更新执行统计"""
        if agent_id not in self._execution_stats:
            self._execution_stats[agent_id] = {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_time_ms": 0.0,
                "avg_time_ms": 0.0
            }
        
        stats = self._execution_stats[agent_id]
        stats["total_calls"] += 1
        stats["total_time_ms"] += execution_time
        stats["avg_time_ms"] = stats["total_time_ms"] / stats["total_calls"]
        
        if success:
            stats["successful_calls"] += 1
        else:
            stats["failed_calls"] += 1
    
    def get_stats(self, agent_id: str = None) -> Dict:
        """获取执行统计"""
        if agent_id:
            return self._execution_stats.get(agent_id, {})
        return self._execution_stats.copy()
    
    def reset_stats(self) -> None:
        """重置统计"""
        self._execution_stats.clear()
