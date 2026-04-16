"""
意图识别系统

核心架构：
├── models/          # 数据模型
│   ├── scene.py     # 场景定义
│   ├── intent.py    # 意图定义
│   └── agent.py     # Agent基类
├── recognition/     # 意图识别
│   ├── llm_recognizer.py      # 基于大模型的识别器
│   └── embedding_recognizer.py # 基于向量的识别器
├── agents/          # Agent管理
│   ├── registry.py  # Agent注册中心
│   └── executor.py  # Agent执行器
├── router/          # 路由层
│   └── router.py    # 意图路由器
├── llm/             # 大模型集成
│   └── client.py    # 大模型客户端
├── api/             # Flask API路由
│   ├── scene_routes.py
│   ├── intent_routes.py
│   └── agent_routes.py
└── database/        # 数据库模型
    ├── models.py
    └── init_db.py
"""

from .models import (
    Scene, SceneStatus,
    Intent, IntentPriority, IntentStatus,
    BaseAgent, AgentResult, AgentInfo, AgentStatus
)
from .recognition import (
    LLMBasedRecognizer, LLMRecognitionResult,
    EmbeddingRecognizer
)
from .agents import (
    AgentRegistry, AgentRegistryItem,
    AgentExecutor, ExecutionResult
)
from .router import IntentRouter, RouterResult
from .llm import LLMClient

__all__ = [
    "Scene", "SceneStatus",
    "Intent", "IntentPriority", "IntentStatus",
    "BaseAgent", "AgentResult", "AgentInfo", "AgentStatus",
    "LLMBasedRecognizer", "LLMRecognitionResult",
    "EmbeddingRecognizer",
    "AgentRegistry", "AgentRegistryItem",
    "AgentExecutor", "ExecutionResult",
    "IntentRouter", "RouterResult",
    "LLMClient"
]
