from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import logging
import time

from ..recognition import LLMBasedRecognizer, LLMRecognitionResult, EmbeddingRecognizer
from ..llm import LLMClient
from ..agents import AgentRegistry, AgentExecutor, ExecutionResult
from ..models import AgentResult
from ..database import Scene, Intent, Agent as AgentModel


logger = logging.getLogger(__name__)


@dataclass
class RouterResult:
    """路由结果"""
    success: bool
    user_input: str
    llm_recognition_result: Optional[LLMRecognitionResult] = None
    execution_result: Optional[ExecutionResult] = None
    scene_id: Optional[str] = None
    scene_name: Optional[str] = None
    intent_id: Optional[str] = None
    intent_name: Optional[str] = None
    agent_id: Optional[str] = None
    final_response: Any = None
    total_time_ms: float = 0.0
    recognition_time_ms: float = 0.0
    execution_time_ms: float = 0.0
    error_message: str = ""
    error_stage: str = ""
    metadata: Dict = field(default_factory=dict)


class IntentRouter:
    """
    意图路由器 - 方案一核心组件

    核心功能：
    - 中心化控制：所有意图识别逻辑集中在此
    - 两层识别：场景识别 → 意图识别 → Agent执行
    - 直接调用：无A2A依赖，直接调用Agent函数

    特点：
    - 响应速度快：无跨服务调用
    - 调试简单：问题定位路径短
    - 成本可控：Agent按需调用
    """

    def __init__(self, llm_client: Optional[LLMClient] = None,
                 use_embedding: bool = True,
                 embedding_threshold: float = 0.5):
        self.llm_client = llm_client
        self.llm_recognizer = None
        self.embedding_recognizer = None
        self.use_embedding = use_embedding
        self.embedding_threshold = embedding_threshold

        if llm_client:
            self.llm_recognizer = LLMBasedRecognizer(llm_client)
            if use_embedding:
                self.embedding_recognizer = EmbeddingRecognizer(llm_client, confidence_threshold=embedding_threshold)

        self.registry = AgentRegistry()
        self.executor = AgentExecutor(self.registry, llm_client=llm_client)

        self._scene_names: Dict[str, str] = {}
        self._intent_names: Dict[str, str] = {}
        self._loaded = False
        self._current_multi_agent_id: Optional[str] = None
        self._router_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "recognition_failures": 0,
            "execution_failures": 0,
            "llm_usage": 0,
            "embedding_usage": 0,
            "llm_fallback": 0
        }
    
    def load_from_database(self, force: bool = False, multi_agent_id: str = None) -> 'IntentRouter':
        """
        从数据库加载场景、意图和智能体配置
        
        Args:
            force: 是否强制重新加载
            multi_agent_id: 只加载指定的Multi-Agent
        """
        if self._loaded and not force and self._current_multi_agent_id == multi_agent_id:
            return self

        from ..database import db
        from sqlalchemy.orm import Session

        if self.llm_recognizer:
            from ..recognition import LLMBasedRecognizer
            self.llm_recognizer = LLMBasedRecognizer(self.llm_recognizer.llm_client)

        if self.embedding_recognizer:
            self.embedding_recognizer.scenes.clear()
            self.embedding_recognizer.intents.clear()
            self.embedding_recognizer._scene_vectors.clear()
            self.embedding_recognizer._intent_vectors.clear()
            self.embedding_recognizer._vector_dirty = True

        self.registry = AgentRegistry()
        self.executor = AgentExecutor(self.registry, llm_client=self.llm_client)

        self._scene_names.clear()
        self._intent_names.clear()

        session = Session(db.engine)
        
        try:
            # 根据multi_agent_id过滤场景
            query = session.query(Scene)
            if multi_agent_id:
                query = query.filter_by(multi_agent_id=multi_agent_id)
            
            scenes = query.all()
            for scene in scenes:
                scene_dict = scene.to_dict()
                self.register_scene(
                    scene_id=scene_dict['id'],
                    name=scene_dict['name'],
                    keywords=scene_dict['keywords'],
                    examples=scene_dict['examples'],
                    description=scene_dict['description']
                )
            
            # 加载智能体
            agents = session.query(AgentModel).all()
            for agent in agents:
                agent_dict = agent.to_dict()
                # 创建一个动态智能体类
                from ..models import BaseAgent
                
                class DynamicAgent(BaseAgent):
                    def __init__(self, llm_client, config):
                        super().__init__(
                            agent_id=config['id'],
                            name=config['name'],
                            description=config['description'],
                            scene_id="",
                            intent_id=""
                        )
                        self.info.capabilities = config['capabilities']
                        self.llm_client = llm_client
                        self.prompt = config.get('prompt', '')
                        self.call_mode = config.get('call_mode', 'external_model')
                        self.agent_api_key = config.get('api_key')
                        self.agent_model_name = config.get('model_name')
                        self.agent_api_url = config.get('api_url')
                        self.agent_hi_agent_id = config.get('hi_agent_id')
                        params = config.get('parameters', {})
                        self.hi_agent_headers = params.get('hi_agent_headers', {}) if isinstance(params, dict) else {}

                    def execute(self, user_input: str, context: Dict[str, Any]) -> AgentResult:
                        if self.call_mode == 'hi_agent':
                            return self._execute_hi_agent(user_input)
                        return self._execute_external_model(user_input)

                    def _execute_external_model(self, user_input: str) -> AgentResult:
                        if self.agent_api_key:
                            from ..llm.client import LLMClient
                            client = LLMClient(api_key=self.agent_api_key)
                            response = client.generate(user_input, system_prompt=self.prompt, model=self.agent_model_name)
                        else:
                            response = self.llm_client.generate(user_input, system_prompt=self.prompt, model=self.agent_model_name)
                        if response:
                            return AgentResult(success=True, data=response, message=response)
                        return AgentResult(success=False, data="查询失败，请稍后重试。", message="查询失败，请稍后重试。")

                    def _execute_hi_agent(self, user_input: str) -> AgentResult:
                        if not self.agent_api_url or not self.agent_api_key:
                            return AgentResult(success=False, data="hi-agent模式需要配置API URL和API Key。", message="配置不完整。")
                        from ..llm.client import LLMClient
                        client = LLMClient(api_key=self.agent_api_key, base_url=self.agent_api_url)
                        response = client.call_hi_agent(
                            user_input=user_input,
                            api_url=self.agent_api_url,
                            agent_id=self.agent_hi_agent_id or self.info.agent_id,
                            system_prompt=self.prompt,
                            cap_user_name=self.hi_agent_headers.get('cap_user_name'),
                            real_name=self.hi_agent_headers.get('real_name'),
                            kk=self.hi_agent_headers.get('KK'),
                            oasis_access_token=self.hi_agent_headers.get('oasis_access_token'),
                            ua=self.hi_agent_headers.get('ua'),
                        )
                        if response:
                            return AgentResult(success=True, data=response, message=response)
                        return AgentResult(success=False, data="hi-agent调用失败，请稍后重试。", message="查询失败。")

                agent_instance = DynamicAgent(self.executor.llm_client, agent_dict)
                self.register_agent(
                    agent_id=agent_dict['id'],
                    agent_instance_or_class=agent_instance
                )
            
            # 根据场景过滤意图
            scene_ids = [s.id for s in scenes]
            query = session.query(Intent)
            if scene_ids:
                query = query.filter(Intent.scene_id.in_(scene_ids))
            
            intents = query.all()
            for intent in intents:
                intent_dict = intent.to_dict()
                self.register_intent(
                    intent_id=intent_dict['id'],
                    scene_id=intent_dict['scene_id'],
                    name=intent_dict['name'],
                    keywords=intent_dict['keywords'],
                    agent_id=intent_dict['agent_id'],
                    examples=intent_dict['examples'],
                    description=intent_dict['description']
                )
            
            logger.info(f"从数据库加载配置完成: {len(scenes)} 个场景, {len(intents)} 个意图, {len(agents)} 个智能体")

            if self.embedding_recognizer:
                loaded = self.embedding_recognizer.load_vectors_from_db()
                logger.info(f"从数据库加载 {loaded} 个已存储向量")
                if self.embedding_recognizer._vector_dirty:
                    self.embedding_recognizer.build_vectors()
            
            self._loaded = True
            self._current_multi_agent_id = multi_agent_id
        except Exception as e:
            logger.error(f"从数据库加载配置失败: {str(e)}")
        finally:
            session.close()

        return self
    
    def register_scene(self, scene_id: str, name: str, 
                       keywords: List[str], examples: List[str] = None,
                       description: str = None, metadata: Dict = None) -> 'IntentRouter':
        """
        注册场景
        
        Returns:
            self: 支持链式调用
        """
        if self.llm_recognizer:
            self.llm_recognizer.register_scene(
                scene_id=scene_id,
                name=name,
                keywords=keywords,
                examples=examples,
                description=description,
                metadata=metadata
            )
        
        if self.embedding_recognizer:
            self.embedding_recognizer.register_scene(
                scene_id=scene_id,
                name=name,
                keywords=keywords,
                examples=examples,
                description=description,
                metadata=metadata
            )
        
        self._scene_names[scene_id] = name
        logger.info(f"路由器注册场景: {scene_id} - {name}")
        return self
    
    def register_intent(self, intent_id: str, scene_id: str, name: str,
                        keywords: List[str], agent_id: str = None,
                        examples: List[str] = None, description: str = None,
                        parameters: Dict = None, metadata: Dict = None) -> 'IntentRouter':
        """
        注册意图
        
        Returns:
            self: 支持链式调用
        """
        if self.llm_recognizer:
            self.llm_recognizer.register_intent(
                intent_id=intent_id,
                scene_id=scene_id,
                name=name,
                keywords=keywords,
                examples=examples,
                description=description,
                agent_id=agent_id,
                parameters=parameters,
                metadata=metadata
            )
        
        if self.embedding_recognizer:
            self.embedding_recognizer.register_intent(
                intent_id=intent_id,
                scene_id=scene_id,
                name=name,
                keywords=keywords,
                examples=examples,
                description=description,
                agent_id=agent_id,
                parameters=parameters,
                metadata=metadata
            )
        
        self._intent_names[intent_id] = name
        logger.info(f"路由器注册意图: {intent_id} - {name}, 场景: {scene_id}")
        return self
    
    def register_agent(self, agent_id: str, agent_instance_or_class,
                       intent_id: str = None, scene_id: str = None,
                       metadata: Dict = None) -> 'IntentRouter':
        """
        注册Agent
        
        Returns:
            self: 支持链式调用
        """
        from ..models import BaseAgent
        
        if isinstance(agent_instance_or_class, BaseAgent):
            self.registry.register_agent_instance(
                agent_id=agent_id,
                agent_instance=agent_instance_or_class,
                intent_id=intent_id,
                scene_id=scene_id,
                metadata=metadata
            )
        elif isinstance(agent_instance_or_class, type):
            self.registry.register_agent_class(
                agent_id=agent_id,
                agent_class=agent_instance_or_class,
                intent_id=intent_id,
                scene_id=scene_id,
                metadata=metadata
            )
        else:
            raise ValueError("agent_instance_or_class 必须是 BaseAgent 实例或类")
        
        logger.info(f"路由器注册Agent: {agent_id}, 意图: {intent_id}")
        return self
    
    def recognize_only(self, user_input: str, context: Dict[str, Any] = None,
                       two_step: bool = False, multi_agent_id: str = None) -> RouterResult:
        """
        只做意图识别，不执行Agent
        
        Args:
            multi_agent_id: 指定使用的Multi-Agent
        """
        self.load_from_database(multi_agent_id=multi_agent_id)

        if not user_input:
            return RouterResult(
                success=False,
                user_input=user_input,
                error_message="用户输入为空",
                error_stage="validation"
            )

        recognition_result = None
        used_embedding = False

        if self.embedding_recognizer and self.use_embedding:
            emb_result = self.embedding_recognizer.recognize(user_input)
            logger.info(f"[recognize_only] Embedding识别: confidence={emb_result.get('confidence', 0):.3f}")

            if emb_result["success"] and emb_result.get("confidence", 0) >= self.embedding_threshold:
                used_embedding = True
                recognition_result = LLMRecognitionResult(
                    success=True,
                    scene_id=emb_result["scene_id"],
                    scene_name=emb_result["scene_name"],
                    intent_id=emb_result["intent_id"],
                    intent_name=emb_result["intent_name"],
                    agent_id=emb_result["agent_id"],
                    confidence=emb_result["confidence"],
                    reasoning=emb_result.get("reasoning", ""),
                    metadata={"method": "embedding", "raw_result": emb_result}
                )
            else:
                logger.info(f"[recognize_only] Embedding置信度不足，降级到LLM")
                self._router_stats["llm_fallback"] += 1

        if recognition_result is None and self.llm_recognizer:
            recognition_result = self.llm_recognizer.recognize(user_input, two_step=two_step)
            logger.info(f"[recognize_only] LLM识别完成")

        if recognition_result is None:
            return RouterResult(
                success=False,
                user_input=user_input,
                error_message="识别器未初始化",
                error_stage="init"
            )

        if not recognition_result.success:
            return RouterResult(
                success=False,
                user_input=user_input,
                llm_recognition_result=recognition_result,
                error_message="意图识别失败",
                error_stage="recognition"
            )

        agent_id = recognition_result.agent_id
        agent_name = ''
        if agent_id:
            agent = self.registry.get_agent(agent_id)
            if agent:
                agent_name = agent.info.name

        return RouterResult(
            success=True,
            user_input=user_input,
            llm_recognition_result=recognition_result,
            scene_id=recognition_result.scene_id,
            scene_name=recognition_result.scene_name,
            intent_id=recognition_result.intent_id,
            intent_name=recognition_result.intent_name,
            agent_id=agent_id,
            metadata={
                'agent_name': agent_name,
                'recognition_method': 'embedding' if used_embedding else 'llm'
            }
        )

    def execute_only(self, agent_id: str, user_input: str,
                     context: Dict[str, Any] = None) -> 'ExecutionResult':
        """
        只执行指定Agent，不做识别

        Returns:
            ExecutionResult: Agent执行结果
        """
        from ..agents.executor import ExecutionResult

        self.load_from_database()

        execution_context = {
            **(context or {}),
            "user_input": user_input
        }

        return self.executor.execute(
            agent_id=agent_id,
            user_input=user_input,
            context=execution_context
        )

    def route(self, user_input: str, context: Dict[str, Any] = None,
              two_step: bool = False,
              force_llm: bool = False,
              multi_agent_id: str = None) -> RouterResult:
        """
        路由用户输入到对应Agent

        核心流程：
        1. Embedding向量匹配（快速）
        2. 置信度不足时降级到LLM推理
        3. 获取Agent映射
        4. 直接调用Agent执行
        5. 返回结果
        
        Args:
            multi_agent_id: 指定使用的Multi-Agent
        """
        self.load_from_database(multi_agent_id=multi_agent_id)

        total_start = time.time()
        self._router_stats["total_requests"] += 1

        recognition_result = None
        recognition_time = 0.0
        used_embedding = False

        if not user_input:
            self._router_stats["failed_requests"] += 1
            return RouterResult(
                success=False,
                user_input=user_input,
                error_message="用户输入为空",
                error_stage="validation"
            )

        if self.embedding_recognizer and self.use_embedding and not force_llm:
            recognition_start = time.time()
            self._router_stats["embedding_usage"] += 1
            emb_result = self.embedding_recognizer.recognize(user_input)
            recognition_time = (time.time() - recognition_start) * 1000
            logger.info(f"Embedding识别完成: {recognition_time:.1f}ms, confidence={emb_result.get('confidence', 0):.3f}")

            if emb_result["success"] and emb_result.get("confidence", 0) >= self.embedding_threshold:
                used_embedding = True
                recognition_result = LLMRecognitionResult(
                    success=True,
                    scene_id=emb_result["scene_id"],
                    scene_name=emb_result["scene_name"],
                    intent_id=emb_result["intent_id"],
                    intent_name=emb_result["intent_name"],
                    agent_id=emb_result["agent_id"],
                    confidence=emb_result["confidence"],
                    reasoning=emb_result.get("reasoning", ""),
                    metadata={"method": "embedding", "raw_result": emb_result}
                )
            else:
                logger.info(f"Embedding置信度({emb_result.get('confidence', 0):.3f}) 低于阈值，降级到LLM推理")
                self._router_stats["llm_fallback"] += 1

        if recognition_result is None and self.llm_recognizer:
            recognition_start = time.time()
            self._router_stats["llm_usage"] += 1
            recognition_result = self.llm_recognizer.recognize(user_input, two_step=two_step)
            recognition_time = (time.time() - recognition_start) * 1000
            logger.info(f"LLM识别完成: {recognition_time:.1f}ms")

        if recognition_result is None:
            self._router_stats["failed_requests"] += 1
            return RouterResult(
                success=False,
                user_input=user_input,
                error_message="识别器未初始化",
                error_stage="init"
            )

        if not recognition_result.success:
            self._router_stats["failed_requests"] += 1
            self._router_stats["recognition_failures"] += 1
            return RouterResult(
                success=False,
                user_input=user_input,
                llm_recognition_result=recognition_result,
                recognition_time_ms=recognition_time,
                error_message="意图识别失败",
                error_stage="recognition",
                metadata={"recognition_result": recognition_result.metadata}
            )

        agent_id = recognition_result.agent_id
        scene_id = recognition_result.scene_id
        intent_id = recognition_result.intent_id
        scene_name = recognition_result.scene_name
        intent_name = recognition_result.intent_name
        confidence = recognition_result.confidence

        if not agent_id:
            self._router_stats["failed_requests"] += 1
            return RouterResult(
                success=False,
                user_input=user_input,
                scene_id=scene_id,
                intent_id=intent_id,
                recognition_time_ms=recognition_time,
                error_message="意图未映射到Agent",
                error_stage="agent_mapping"
            )

        execution_context = {
            **(context or {}),
            "scene_id": scene_id,
            "intent_id": intent_id,
            "confidence": confidence,
            "user_input": user_input
        }

        execution_result = self.executor.execute(
            agent_id=agent_id,
            user_input=user_input,
            context=execution_context
        )

        total_time = (time.time() - total_start) * 1000

        if not execution_result.success:
            self._router_stats["failed_requests"] += 1
            self._router_stats["execution_failures"] += 1
            return RouterResult(
                success=False,
                user_input=user_input,
                scene_id=scene_id,
                scene_name=scene_name,
                intent_id=intent_id,
                intent_name=intent_name,
                agent_id=agent_id,
                total_time_ms=total_time,
                recognition_time_ms=recognition_time,
                execution_time_ms=execution_result.execution_time_ms,
                error_message=execution_result.error_message,
                error_stage="execution"
            )

        self._router_stats["successful_requests"] += 1

        return RouterResult(
            success=True,
            user_input=user_input,
            llm_recognition_result=recognition_result,
            execution_result=execution_result,
            scene_id=scene_id,
            scene_name=scene_name,
            intent_id=intent_id,
            intent_name=intent_name,
            agent_id=agent_id,
            final_response=execution_result.agent_result.data if execution_result.agent_result else None,
            total_time_ms=total_time,
            recognition_time_ms=recognition_time,
            execution_time_ms=execution_result.execution_time_ms,
            metadata={
                "agent_metadata": execution_result.metadata,
                "recognition_metadata": getattr(recognition_result, "metadata", {}),
                "recognition_method": "embedding" if used_embedding else "llm"
            }
        )
    
    def route_batch(self, inputs: List[str], context: Dict[str, Any] = None, 
                   two_step: bool = False) -> List[RouterResult]:
        """批量路由"""
        return [self.route(user_input, context, two_step=two_step) for user_input in inputs]
    
    def get_stats(self) -> Dict:
        """获取路由统计"""
        return {
            "router_stats": self._router_stats.copy(),
            "agent_stats": self.executor.get_stats(),
            "scene_count": len(self._scene_names),
            "intent_count": len(self._intent_names),
            "agent_count": len(self.registry.list_agents()),
            "using_llm": self.llm_recognizer is not None
        }
    
    def reset_stats(self) -> None:
        """重置统计"""
        self._router_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "recognition_failures": 0,
            "execution_failures": 0,
            "llm_usage": 0
        }
        self.executor.reset_stats()
    
    def list_scenes(self) -> List[Dict]:
        """列出所有场景"""
        if self.llm_recognizer:
            return self.llm_recognizer.list_scenes()
        return []
    
    def list_intents(self, scene_id: str = None) -> List[Dict]:
        """列出所有意图"""
        if self.llm_recognizer:
            return self.llm_recognizer.list_intents(scene_id)
        return []
    
    def list_agents(self) -> Dict:
        """列出所有Agent"""
        return self.registry.list_agents()
