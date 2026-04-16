# 意图识别系统

基于 Flask + LLM 的智能意图识别与 Agent 执行系统。支持 Embedding 向量匹配 + LLM 推理双引擎，可快速将用户输入路由到对应的智能体执行。

## 功能特性

- **双引擎识别**：Embedding（快速）+ LLM（准确），自动降级
- **动态 Agent**：运行时从数据库加载配置，支持 external_model / hi_agent 模式
- **会话记忆**：支持多轮对话上下文
- **流式输出**：SSE 流式响应，提升用户体验
- **前后端分离**：独立的前端和后端服务，支持独立部署
- **Web 管理后台**：场景、意图、智能体可视化管理
- **REST API**：完整的 CRUD 接口

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
export SILICONFLOW_API_KEY="your-api-key-here"
```

或在 `app.py` 中直接设置（不推荐生产环境）。

### 3. 启动服务

**启动后端**：
```bash
python app.py
```

后端 API 地址：http://127.0.0.1:5001

**启动前端**：
直接在浏览器中打开 `frontend/index.html`，或使用简单的 HTTP 服务器：
```bash
# Python 3
cd frontend
python -m http.server 8000

# 或使用 Node.js
cd frontend
npx serve -p 8000
```

前端访问地址：http://127.0.0.1:8000

**启动后台管理**：
后台管理页面已迁移到前端，与用户界面使用相同的架构。访问地址：
- 管理首页：http://127.0.0.1:8000/admin/index.html
- 智能体管理：http://127.0.0.1:8000/admin/agents.html
- 场景意图管理：http://127.0.0.1:8000/admin/scene-intent.html
- 意图识别调试：http://127.0.0.1:8000/admin/debug.html

**注意**：前端默认配置的 API 地址是 `http://localhost:5001`，如果后端地址不同，请修改：
- 用户端：`frontend/js/app.js` 中的 `API_BASE_URL` 常量
- 管理端：`frontend/admin/admin.js` 中的 `API_BASE_URL` 常量

## 项目结构

```
intent_recognition/
├── models/              # 数据模型（Scene, Intent, Agent）
├── recognition/         # 识别引擎
│   ├── llm_recognizer.py        # LLM 推理识别
│   └── embedding_recognizer.py  # 向量匹配识别
├── agents/              # Agent 管理
│   ├── registry.py      # 注册中心
│   └── executor.py      # 执行器
├── router/              # 路由层
│   └── router.py        # 意图路由器
├── llm/                 # LLM 客户端
│   └── client.py        # 统一 API 封装
├── api/                 # Flask API 路由
│   ├── scene_routes.py
│   ├── intent_routes.py
│   └── agent_routes.py
└── database/            # 数据库模型
    ├── models.py
    └── init_db.py

frontend/                # 前端项目（独立部署）
├── index.html           # 用户端主页面
├── admin/               # 管理端页面
│   ├── index.html       # 管理首页
│   ├── agents.html      # 智能体管理
│   ├── scene-intent.html # 场景意图管理
│   ├── debug.html       # 意图识别调试
│   ├── admin.css        # 管理端样式
│   └── admin.js        # 管理端逻辑
├── css/
│   └── style.css        # 通用样式文件
└── js/
    └── app.js           # 用户端逻辑

app.py                   # Flask 应用入口
templates/               # 已弃用，前端已分离到 frontend/
```

## 核心流程

```
用户输入
    ↓
Embedding 识别（<100ms）
    ├─ 置信度 >= 阈值 → 返回结果
    └─ 置信度 < 阈值 → LLM 识别
    ↓
识别结果：场景 + 意图 + AgentID
    ↓
Agent 执行（调用外部模型 / Hi-Agent）
    ↓
最终响应
```

## 前后端分离架构

本项目采用前后端分离架构，前端和后端可以独立部署和扩展。

### 架构说明

- **后端**：Flask 应用，提供 REST API 和 SSE 流式接口
- **前端**：纯 HTML/CSS/JavaScript，通过 Fetch API 与后端通信
- **通信协议**：HTTP/HTTPS，支持 CORS 跨域访问

### 部署方式

**开发环境**：
- 后端：`python app.py` 运行在 5001 端口
- 前端：`python -m http.server 8000` 运行在 8000 端口

**生产环境**：
- 后端：使用 Gunicorn/uWSGI + Nginx 反向代理
- 前端：部署到 CDN 或静态服务器（如 Nginx、Apache）
- 安全配置：启用 HTTPS，配置 CORS 白名单

### 配置说明

前端配置文件：`frontend/js/app.js`

```javascript
const API_BASE_URL = 'http://localhost:5001';  // 修改为实际的后端地址
```

**生产环境配置**：
```javascript
const API_BASE_URL = 'https://api.yourdomain.com';  // 生产环境 API 地址
```

### CORS 配置

后端已配置 CORS 支持（`app.py`）：

```python
CORS(app, resources={
    r"/api/*": {
        "origins": "*",  # 生产环境建议改为具体域名
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})
```

**生产环境安全建议**：
- 将 `origins` 改为具体的域名列表
- 启用 HTTPS
- 添加认证和授权机制

## REST API

### 意图识别

**POST /api/recognize**
```json
// 请求
{"input": "我想查北京到上海的机票"}

// 响应
{
  "success": true,
  "scene": "旅行规划",
  "intent": "查机票",
  "agent_id": "flight_agent",
  "confidence": 0.95,
  "recognition_method": "embedding"
}
```

**POST /api/recognize/execute/stream**

流式输出（SSE），支持实时响应。

### 管理接口

| 接口 | 说明 |
|------|------|
| GET/POST /api/scenes | 场景列表/创建 |
| GET/PUT/DELETE /api/scenes/{id} | 场景详情/更新/删除 |
| GET/POST /api/intents | 意图列表/创建 |
| GET/PUT/DELETE /api/intents/{id} | 意图详情/更新/删除 |
| GET/POST /api/agents | 智能体列表/创建 |
| GET/PUT/DELETE /api/agents/{id} | 智能体详情/更新/删除 |

## 数据库模型

### Scene（场景）
- id, name, description
- keywords, examples

### Intent（意图）
- id, scene_id, name, description
- keywords, examples, agent_id

### Agent（智能体）
- id, name, description, prompt
- call_mode（external_model / hi_agent）
- api_key, model_name, api_url
- capabilities, max_tokens

### SessionHistory（会话历史）
- session_id, user_input, response
- agent_name, created_at

## 配置说明

### Agent 调用模式

1. **external_model**：直接调用外部 LLM API
   - 配置：api_key, model_name, api_url（可选）
   
2. **hi_agent**：调用 Hi-Agent 平台
   - 配置：api_url, api_key, hi_agent_id

### 识别器配置

```python
router = IntentRouter(
    llm_client=client,
    use_embedding=True,          # 启用 Embedding 识别
    embedding_threshold=0.5      # 置信度阈值
)
```

## Web 界面

- `/` - 首页（对话界面）
- `/admin` - 管理后台
- `/admin/scene_detail/{id}` - 场景详情
- `/debug` - 调试页面

## 扩展开发

### 添加自定义 Agent

```python
from intent_recognition.models import BaseAgent, AgentResult

class MyAgent(BaseAgent):
    def execute(self, user_input: str, context: dict) -> AgentResult:
        result = self.process(user_input)
        return AgentResult(success=True, data=result)

router.register_agent("my_agent", MyAgent())
```

## 性能指标

| 指标 | 数值 |
|------|------|
| Embedding 识别 | < 100ms |
| LLM 识别 | 1-3s |
| Agent 执行 | 取决于外部 API |

## 技术栈

- Flask 2.x
- SQLAlchemy + SQLite
- SiliconFlow API（兼容 OpenAI）
- NumPy（向量计算）
- Flask-Session（会话管理）

## 更新日志

### v2.0.0
- 删除冗余代码（旧识别器、示例代码、未使用模块）
- 统一 Embedding + LLM 双引擎识别
- 优化项目结构

## 许可证

MIT License
