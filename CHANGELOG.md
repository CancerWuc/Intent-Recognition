# 更新日志

## [v2.2.0] - 2026-04-03

### Router 实例一致性修复 & 交互优化

本次更新修复了一个关键 Bug：Flask watchdog 重启后，管理后台的增删改操作无法即时生效的问题。

### 核心修复
- **Router 实例不一致问题**：Flask debug 模式下 watchdog 重启时，Blueprint 中 `from app import router` 获取的是旧模块缓存的 router 实例，而 `app.py` 中使用的是新创建的实例，导致增删改操作更新的是旧 router，识别请求使用的是新 router
  - **根因**：Python 模块级别导入在 Flask reloader 子进程中存在缓存不一致
  - **修复**：将 router 存入 `app.config['ROUTER']`，所有 Blueprint 通过 `current_app.config['ROUTER']` 获取，确保始终使用同一个实例
  - 涉及文件：`app.py`、`intent_routes.py`、`scene_routes.py`、`agent_routes.py`

### 功能优化
- **Qwen3 thinking 模式关闭**：`LLMClient.generate_stream()` 中添加 `enable_thinking: False`，禁用 Qwen3-8B 的思考模式，首 token 延迟从 ~5.5s 降至 ~0.6s
- **停止生成按钮**：前端新增「停止」按钮，支持流式输出时中断生成
  - 使用 `AbortController` + `ReadableStream.cancel()` 实现请求取消
  - 停止后在回复末尾追加 `[已停止]` 标记

### Bug 修复
- **新建意图无法匹配**：`load_from_database()` 中 `load_vectors_from_db()` 后未检测新意图的向量缺失，导致新意图没有向量可供匹配
- **删除意图后孤立向量**：删除意图/场景时未清理 `IntentVector` 和 `SceneVector` 记录，导致重载后旧向量被重新加载

---

## [v2.1.0] - 2026-04-03

### 向量持久化 & SSE 流式响应

本次更新主要解决了两个核心体验问题：
1. **意图识别速度**：通过向量持久化，将每次请求都要重新计算 embedding 的问题彻底解决，识别速度从 30+ 秒降至 **0.3 秒**
2. **Agent 响应体验**：通过 SSE 流式响应，将 Agent 回复从等待 50 秒一次性输出改为 **逐字流式显示**，大幅提升用户体验

### 向量持久化
- **新增数据库模型**：`SceneVector` 和 `IntentVector` 表，将 embedding 向量存储为 `LargeBinary`
  - 向量数据通过 `base64` 编码存储为二进制
  - `text_hash`（SHA256）字段检测场景/意图描述文本是否变更
  - `updated_at` 字段跟踪向量更新时间
- **智能向量构建**：`build_vectors()` 改为增量计算
  - 启动时从数据库加载已有向量（`load_vectors_from_db()`）
  - 仅对新增或文本变更的场景/意图计算 embedding
  - 计算后自动保存到数据库（`save_vectors_to_db()`）
- **Router 缓存优化**：`IntentRouter` 新增 `_loaded` 标志
  - 避免每次请求都重新加载场景/意图数据
  - 仅在数据变更时（create/update/delete）通过 `force=True` 重新加载

### SSE 流式响应
- **LLMClient.generate_stream()**：新增流式调用方法
  - 使用 `requests.post(stream=True)` + `iter_content(chunk_size=1)` 逐字节读取
  - bytes 层面按 `\n` 分割后整体 `decode("utf-8")`，避免 UTF-8 多字节字符被截断导致乱码
  - `json.dumps(ensure_ascii=False)` 保持中文原样输出
- **SSE 端点**：新增 `POST /api/recognize/execute/stream`
  - Generator 首行 yield `": connected\n\n"` SSE 注释，确保 Flask 立即发送 HTTP 200 header
  - `Response(direct_passthrough=True)` 避免 Werkzeug 缓冲
  - 每个 content token 实时 yield，前端到后端延迟仅 ~10ms
- **前端 ReadableStream 对接**：
  - 使用 `fetch` + `response.body.getReader()` + `TextDecoder` 逐块读取
  - Loading 动画持续显示到第一个文字 token 到达时才消失
  - 回复气泡先隐藏，第一个字到达后再显示，避免空白气泡

### 前端体验优化
- **Loading 动画优化**：识别意图 → 调用 Agent 的全过程持续显示加载动画
  - "正在识别意图..." → "识别完成 [Embedding, 置信度: 71%] → 正在调用 Agent: xxx..."
  - 直到流式文字到达时才消失，避免中间出现空白状态
- **自动滚动**：流式输出时聊天容器自动滚动到底部

### 修复问题
- **中文乱码**：修复 SSE 流式输出中文乱码问题（bytes 层面分割避免 UTF-8 截断）
- **Flask 响应缓冲**：修复 Flask/Werkzeug 缓冲导致前端一次性收到所有数据的问题
  - 根因：generator 首次 yield 前 Flask 不发 HTTP 200 header
  - 解决：首行 yield SSE 注释 `": connected\n\n"` 触发 header 立即发送
- **向量重复计算**：修复每次请求都重新计算所有 embedding 向量的问题

### 性能对比

| 指标 | v2.0.0 | v2.1.0 |
|------|--------|--------|
| 意图识别速度 | 30+ 秒（每次重新计算向量） | **0.3 秒**（向量持久化） |
| Agent 响应体验 | 等待 50 秒一次性输出 | **逐字流式显示** |
| SSE 管线延迟 | - | **~10ms**（后端 yield 到前端收到） |

---

## [v2.0.0] - 2026-03-25 🎉 里程碑版本

### 项目概述
意图识别系统第一个正式发布版本，实现了完整的两层意图识别架构和Web管理后台。

### 核心特性
- **两层意图识别架构**：场景识别 → 意图识别 → Agent执行
- **LLM智能推理**：集成 Qwen3-8B 模型进行意图理解
- **意图识别与执行分离**：`recognize_only` + `execute_only` 灵活调用
- **Agent多模式调用**：支持 `external_model` 和 `hi_agent` 两种模式
- **完整Web管理后台**：场景/意图/智能体可视化管理 + 调试工具

### 技术栈
- Python 3.11 + Flask
- SiliconFlow API (Qwen3-8B)
- SQLite 数据库
- 响应式Web前端

### 版本演进
```
v1.0.0 → v1.1.0 → v1.2.0 → v1.3.0 → v1.4.0 → v1.5.0 → v1.6.0 → v2.0.0
```

---

## [v1.6.0] - 2026-03-25

### 架构优化：意图识别与Agent执行分离
- **recognize_only方法**：IntentRouter新增方法，只做意图识别不执行Agent
  - 返回识别结果（场景、意图、Agent ID、置信度等）
  - 适用于需要先展示识别结果再决定是否执行的场景

- **execute_only方法**：IntentRouter新增方法，直接执行指定Agent跳过识别
  - 接收 agent_id 和 user_input 参数
  - 适用于已确定Agent的直接调用场景

### API接口重构
- **POST /api/recognize**：新接口，调用 `recognize_only`，只返回识别结果
- **POST /api/recognize/execute/stream**：流式执行 Agent，实时返回结果
- **用户体验提升**：用户可清晰看到识别和执行两个阶段的状态变化

### 优势
- API更灵活，支持单独调用识别或执行接口
- 识别和执行解耦，便于独立测试和维护
- 可在两步之间插入其他逻辑（权限校验、日志记录等）

## [v1.5.0] - 2026-03-25

### Agent多模式调用支持
- **DynamicAgent重构**：智能体现在支持两种调用模式
  - `external_model`：外部模型模式，调用SiliconFlow等外部API
  - `hi_agent`：Hi-Agent模式，调用自研的Hi-Agent服务
  - 通过数据库中的 `call_mode` 字段配置调用方式

- **Agent配置扩展**：智能体支持更多自定义配置字段
  - `api_key`：自定义API密钥，支持每个Agent使用不同的模型服务
  - `model_name`：自定义模型名称，灵活切换不同模型
  - `api_url`：自定义API地址，支持私有化部署
  - `hi_agent_id`：Hi-Agent服务的智能体ID

### LLMClient增强
- **generate方法增强**：新增可选 `model` 参数，支持动态指定模型
- **call_hi_agent方法**：新增专门调用Hi-Agent服务的方法
  - 支持传递 agent_id 和 system_prompt
  - 统一的错误处理和日志记录

### 前端体验优化
- **首页加载动画重构**：加载状态改为内联在聊天消息中显示
  - 新增 `addLoadingMessage`、`updateLoadingText`、`removeLoadingMessage` 方法
  - 加载动画与消息气泡风格一致，视觉更协调
  - 移除了独立的加载容器，减少DOM层级

### 代码重构
- **DynamicAgent类优化**：将配置参数通过构造函数传入，避免闭包问题
- **执行逻辑分离**：`_execute_external_model` 和 `_execute_hi_agent` 方法独立处理不同模式

## [v1.4.0] - 2026-03-25

### 模型升级
- **LLM模型升级**：将默认模型从 `Qwen/Qwen2-0.5B-Instruct` 升级至 `Qwen/Qwen3-8B`
  - 模型参数量从5亿提升至80亿，推理能力和理解精度大幅增强
  - 对模糊输入和复杂意图的识别效果显著改善

### Prompt优化
- **意图识别Prompt增强**：在场景和意图的Prompt中新增示例（examples）信息
  - 一步推理的 `_build_recognition_prompt` 方法中，场景和意图描述均增加了示例字段
  - 两步推理的 `_recognize_scene` 和 `_recognize_intent` 方法同样增加了示例字段
  - 为模型提供了更多参考上下文，提高匹配准确度

### Bug修复
- **Agent测试接口修复**：修复了 `agent_routes.py` 中测试Agent时每次都新建 `LLMClient()` 的问题
  - 改为从 `app` 模块导入共享的 `llm_client` 实例
  - 避免了重复初始化，确保使用统一的模型配置

### UI重构
- **管理后台主题重构**：所有前端页面统一为红色主题风格
  - 主色调从紫色渐变（`#667eea` → `#764ba2`）更换为红色（`#C41230`）
  - 涉及页面：首页、调试页面、管理员首页、智能体管理、场景和意图管理、场景详情
  - 统一了按钮、输入框、加载动画等组件的视觉风格
  - 优化了间距、圆角、字号等细节，提升整体一致性

### 代码格式
- 微调了 `intent_routes.py` 和 `models.py` 中的空白格式

## [v1.3.0] - 2026-03-24

### 管理后台重构
- **场景和意图管理优化**：完全重构了场景和意图管理界面
  - 删除了单独的场景管理和意图管理页面
  - 创建了新的场景和意图管理页面，采用卡片式布局
  - 实现了场景详情页面，支持场景内意图的创建和管理
  - 添加了场景和意图的删除和编辑功能

- **导航栏优化**：统一了所有管理后台页面的导航栏
  - 删除了重复的场景管理和意图管理链接
  - 添加了新的场景和意图管理入口
  - 确保所有页面的导航一致

- **UI/UX改进**：优化了管理后台的视觉设计
  - 统一了颜色和样式
  - 改进了响应式布局
  - 添加了更清晰的操作提示

### 功能增强
- **场景和意图关联**：实现了场景和意图的关联管理
  - 场景可以包含多个意图
  - 意图必须属于一个场景
  - 提供了场景详情页面，显示场景下的所有意图

- **调试功能优化**：改进了意图识别调试功能
  - 优化了调试页面的UI设计
  - 添加了详细的识别结果展示
  - 提供了更直观的错误信息

### 代码优化
- **API路由重构**：重构了场景和意图管理的API
  - 删除了原有的scenes.html和intents.html
  - 创建了新的scene_intent_management.html和scene_detail.html
  - 优化了路由处理逻辑

- **数据库操作**：改进了数据库操作的稳定性
  - 添加了cleanup.py脚本用于数据清理
  - 优化了数据库连接和事务处理
  - 确保数据一致性

### 修复问题
- **配置同步问题**：修复了场景和意图更新后的配置同步问题
- **变量命名冲突**：修复了场景详情页面中变量命名冲突问题
- **API调用错误**：优化了API调用的错误处理

### 新增测试文件
- 添加了多个测试文件，包括：
  - 场景和意图管理测试
  - API测试
  - 数据库操作测试
  - 意图识别功能测试

### 当前场景和意图
- **股票查询和分析**（5个意图）
- **基金查询和分析**（9个意图）
- **客服**（3个意图）
- **通用**（1个意图）
- **测试场景**（新增）
  - 测试python（原测试场景）
  - 代码测试场景（新增，包含Java代码测试、Python代码测试、C++代码测试）

### 技术栈
- Python 3.11
- Flask (网页框架)
- SiliconFlow API (大模型服务)
- Qwen/Qwen3-8B (当前使用的模型)

## [v1.2.0] - 2026-03-24

### 界面优化
- **聊天界面重构**：将用户端界面完全重构为聊天对话模式
  - 添加了消息气泡样式，区分用户和系统消息
  - 实现了滚动聊天容器和自动滚动到底部功能
  - 新增消息发送时间显示
  - 优化了输入框和发送按钮布局

- **加载动画改进**：创建了全新的加载动画系统
  - 添加了旋转加载图标
  - 实现了分阶段加载提示（正在识别 → 正在分析意图 → 正在分配Agent）
  - 优化了加载状态的用户体验

### 功能增强
- **场景和意图描述优化**：在LLMBasedRecognizer中添加了场景和意图描述字段
  - 重写了场景和意图的注册方法，支持description参数
  - 优化了recognize方法中的场景和意图信息构建
  - 在_build_recognition_prompt中添加了对场景和意图描述的支持
  - 在_tow_step_recognition和_step_recognition_intent中同样添加了描述支持

- **数据加载优化**：改进了IntentRouter中的数据加载过程
  - 在load_from_database方法中添加了场景和意图描述的加载支持
  - 优化了register_scene和register_intent方法的参数传递
  - 确保数据库查询和场景意图描述的一致性

- **响应内容优化**：修改了前端处理响应的方式
  - 删除了原有的结果展示区域
  - 添加了addMessage函数，用于动态添加消息到聊天界面
  - 优化了错误处理和用户反馈
  - 添加了欢迎消息初始化功能

### 代码改进
- **路由优化**：在IntentRouter中添加了场景和意图描述的支持
  - 在register_scene方法中添加description参数
  - 在register_intent方法中添加description参数
  - 确保从数据库加载场景和意图时描述信息正确传递

- **识别器改进**：增强了LLMBasedRecognizer的功能
  - 在_scene_recognizer方法中优化了场景信息展示
  - 在_intent_recognizer方法中优化了意图信息展示
  - 确保两步推理过程中使用描述信息

### 用户体验提升
- **输入优化**：添加了按Enter键发送消息的功能
- **消息管理**：实现了用户输入后的自动清空功能
- **视觉反馈**：改进了聊天界面的视觉层次和交互效果

## [v1.1.0] - 2026-03-20

### 新增功能
- **网页端界面**：新增Flask网页应用，提供友好的用户交互界面
  - 支持用户输入问题并实时显示识别结果
  - 显示场景、意图、Agent、置信度和响应内容
  - 响应内容支持自然语言格式显示

### 重大改进
- **Agent大模型集成**：所有Agent类现在都通过大模型生成自然语言回复
  - 移除了硬编码的JSON格式返回
  - Agent回复更加智能和自然
  - 支持更丰富的上下文理解

- **Agent结果优化**：AgentResult现在同时设置data和message字段
  - 确保router能正确获取final_response
  - 提高数据传递的一致性

### 代码优化
- **删除冗余Agent**：移除了不再使用的Agent类
  - 删除FlightQueryAgent、HotelBookingAgent、WeatherQueryAgent
  - 删除OrderQueryAgent、RefundApplyAgent、ProductConsultAgent
  - 删除ExpenseSubmitAgent、ApprovalQueryAgent

- **简化配置**：优化了sample_config.py中的Agent注册逻辑
  - 所有Agent实例化时传递llm_client参数
  - 确保Agent能正确调用大模型

### 修复问题
- **修复返回值问题**：解决了Agent返回None的问题
- **修复导入错误**：修复了llm_demo.py中的模块导入问题

### 当前场景和意图
- **股票查询和分析**（5个意图）
  - 个股-信息查询
  - 个股-个股诊断
  - 指数-指数分析
  - 个股或指数-多股对比
  - 选股-综合选股

- **基金查询和分析**（9个意图）
  - 个基-公募基金信息查询
  - 个基-公募基金分析
  - 个基-场内ETF信息查询
  - 个基-场内ETF分析
  - 基金经理-信息查询
  - 基金经理-信息分析
  - 基金诊断-多基金对比
  - 选基-综合选基
  - 选基-选基金经理

- **客服**（3个意图）
  - 客服-客服FAQ
  - 客服-业务办理
  - 客服-转人工

- **通用**（1个意图）
  - 闲聊-闲聊陪伴

### 技术栈
- Python 3.11
- Flask (网页框架)
- SiliconFlow API (大模型服务)
- Qwen/Qwen3-8B (当前使用的模型)

---

## [v1.0.0] - 2026-03-19

### 初始版本
- 实现了两层意图识别 + 直接调用Agent的架构
- 集成了大模型进行意图识别
- 支持一步推理和两步推理两种模式
- 实现了知识库同步模块
- 完成了单元测试
