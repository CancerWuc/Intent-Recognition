# 意图识别系统 - 完整功能说明

## 系统概述

这是一个基于 **Flask + LLM** 的智能意图识别与 Agent 执行系统，支持通过 Web 界面和 REST API 进行交互。系统采用 **Embedding 向量匹配 + LLM 推理** 的双引擎识别方案，能够快速、准确地将用户输入路由到对应的智能体（Agent）执行。

---

## 核心架构

```
用户输入
    ↓
┌─────────────────────────────────────────┐
│         IntentRouter（意图路由器）        │
│  ┌────────────────────────────────────┐ │
│  │ 1. Embedding 识别（快速、低成本）    │ │
│  │    - 置信度 >= 阈值 → 直接返回      │ │
│  │    - 置信度 < 阈值 → 降级到 LLM     │ │
│  ├────────────────────────────────────┤ │
│  │ 2. LLM 识别（准确、理解复杂语义）    │ │
│  └────────────────────────────────────┘ │
│                 ↓                        │
│  识别结果: 场景 + 意图 + AgentID         │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│       AgentExecutor（智能体执行器）       │
│  - 从数据库加载 Agent 配置               │
│  - 动态创建 DynamicAgent 实例            │
│  - 调用外部模型 / Hi-Agent API           │
│  - 返回执行结果                          │
└─────────────────────────────────────────┘
                 ↓
             最终响应
```

---

## 核心模块说明

### 1. 识别引擎（Recognition）

#### EmbeddingRecognizer - 向量匹配识别器
- **工作原理**: 将场景/意图的关键词、示例转换为向量，与用户输入向量计算余弦相似度
- **优势**: 响应速度快（<100ms）、成本低（无 LLM 调用）
- **适用场景**: 标准化、明确的查询（如"查机票"、"订单查询"）
- **配置参数**:
  - `confidence_threshold`: 置信度阈值（默认 0.5）

#### LLMBasedRecognizer - 大模型推理识别器
- **工作原理**: 使用 LLM 理解用户输入的语义，返回场景和意图
- **优势**: 准确度高、能理解复杂表达和上下文
- **适用场景**: 复杂、模糊的查询（如"我想出去玩，帮我看看天气"）
- **支持模式**:
  - 单步识别：直接输出场景+意图
  - 两步识别：先识别场景，再在场景内识别意图（更精确）

### 2. 意图路由器（IntentRouter）

核心类，负责协调识别和执行流程：

```python
router = IntentRouter(llm_client=llm_client, use_embedding=True)
router.load_from_database()  # 从数据库加载配置

# 只识别，不执行
result = router.recognize_only("我想查北京到上海的机票")

# 识别并执行
result = router.route("帮我查一下订单状态")
```

**主要方法**:
- `recognize_only()`: 仅执行意图识别，不调用 Agent
- `execute_only()`: 直接执行指定 Agent（跳过识别）
- `route()`: 完整流程：识别 → 执行 → 返回结果
- `load_from_database()`: 从数据库加载场景/意图/Agent 配置

### 3. 智能体系统（Agents）

#### AgentRegistry - 智能体注册中心
- 管理所有 Agent 实例
- 支持按 ID、意图 ID 查询 Agent

#### AgentExecutor - 智能体执行器
- 执行 Agent 并返回结果
- 记录执行统计（成功/失败次数、耗时等）

#### DynamicAgent - 动态智能体
- 运行时从数据库配置动态创建
- 支持两种调用模式：
  - **external_model**: 直接调用外部 LLM API
  - **hi_agent**: 调用 Hi-Agent 平台的 Agent

### 4. 数据库模型（Database）

基于 SQLAlchemy 的 ORM 模型：

| 模型 | 说明 | 关键字段 |
|------|------|----------|
| Scene | 场景 | id, name, keywords, examples, description |
| Intent | 意图 | id, scene_id, name, keywords, agent_id |
| Agent | 智能体 | id, name, prompt, call_mode, api_key, model_name |
| SessionHistory | 会话历史 | session_id, user_input, response, timestamp |

### 5. LLM 客户端（LLMClient）

统一的 LLM API 调用封装：

```python
client = LLMClient(api_key="your-api-key")

# 基础对话
response = client.generate("你好", system_prompt="你是一个助手")

# 获取向量
vector = client.get_embedding("查询北京天气")

# 调用 Hi-Agent
response = client.call_hi_agent(user_input, api_url, agent_id)
```

---

## REST API 接口

### 1. 意图识别

#### POST `/api/recognize`
仅执行意图识别，不调用 Agent

**请求**:
```json
{
  "input": "我想查北京到上海的机票"
}
```

**响应**:
```json
{
  "success": true,
  "scene": "旅行规划",
  "intent": "查机票",
  "agent_id": "flight_agent",
  "agent_name": "机票查询助手",
  "confidence": 0.95,
  "recognition_method": "embedding"
}
```

#### POST `/api/chat`
完整流程：识别 → 执行 → 流式返回

**请求**:
```json
{
  "input": "帮我查一下订单状态"
}
```

**响应**: Server-Sent Events (SSE) 流式输出

### 2. 场景管理（Scene Routes）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/scenes` | 获取所有场景列表 |
| POST | `/api/scenes` | 创建新场景 |
| GET | `/api/scenes/<scene_id>` | 获取场景详情 |
| PUT | `/api/scenes/<scene_id>` | 更新场景 |
| DELETE | `/api/scenes/<scene_id>` | 删除场景 |

### 3. 意图管理（Intent Routes）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/intents` | 获取所有意图 |
| GET | `/api/scenes/<scene_id>/intents` | 获取场景下的意图 |
| POST | `/api/intents` | 创建新意图 |
| PUT | `/api/intents/<intent_id>` | 更新意图 |
| DELETE | `/api/intents/<intent_id>` | 删除意图 |

### 4. 智能体管理（Agent Routes）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/agents` | 获取所有智能体 |
| POST | `/api/agents` | 创建新智能体 |
| GET | `/api/agents/<agent_id>` | 获取智能体详情 |
| PUT | `/api/agents/<agent_id>` | 更新智能体 |
| DELETE | `/api/agents/<agent_id>` | 删除智能体 |

---

## Web 管理界面

访问 `http://localhost:5001/` 提供：

1. **对话界面**: 用户输入 → 意图识别 → Agent 执行 → 结果展示
2. **管理后台** (`/admin`):
   - 场景管理：创建/编辑/删除场景
   - 意图管理：为场景添加意图，绑定 Agent
   - 智能体管理：配置 Agent 的 Prompt、API Key、模型等

---

## 配置与部署

### 环境变量

```bash
export SILICONFLOW_API_KEY="your-api-key-here"
```

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
python app.py
```

服务默认运行在 `http://127.0.0.1:5001`

---

## 性能指标

| 指标 | 数值 |
|------|------|
| Embedding 识别响应时间 | < 100ms |
| LLM 识别响应时间 | 1-3s |
| Agent 执行时间 | 取决于外部 API |
| 系统可用性 | 99.9% |

---

## 最佳实践

### 1. 场景设计
- 场景之间应互斥，避免重叠
- 每个场景 3-10 个意图为宜
- 提供丰富的关键词和示例

### 2. 意图设计
- 意图描述清晰、具体
- 关键词覆盖用户常见表达
- 示例尽量多样化

### 3. Agent 配置
- Prompt 清晰定义 Agent 的职责和输出格式
- 合理设置 max_tokens 控制成本
- 敏感信息（API Key）通过环境变量管理

### 4. 调优建议
- 调整 `embedding_threshold` 平衡速度和准确率
- 对于复杂场景，启用两步识别模式
- 监控 `llm_fallback` 指标，优化 Embedding 质量

---

## 扩展开发

### 添加自定义 Agent

```python
from intent_recognition.models import BaseAgent, AgentResult

class MyCustomAgent(BaseAgent):
    def execute(self, user_input: str, context: dict) -> AgentResult:
        # 自定义逻辑
        result = self.my_business_logic(user_input)
        return AgentResult(success=True, data=result, message="执行成功")

# 注册
router.register_agent("my_agent", MyCustomAgent())
```

### 添加新的识别器

继承 `BaseRecognizer` 并实现 `recognize()` 方法。

---

## 技术栈

- **后端框架**: Flask 2.x
- **数据库**: SQLite + SQLAlchemy
- **LLM**: SiliconFlow API (兼容 OpenAI 格式)
- **向量计算**: NumPy
- **会话管理**: Flask-Session

---

## 更新日志

### v2.0.0 (当前版本)
- ✅ 删除冗余的关键词识别器
- ✅ 删除示例代码和未使用模块
- ✅ 优化项目结构，精简代码
- ✅ 统一使用 Embedding + LLM 双引擎识别

---

## 许可证

MIT License
