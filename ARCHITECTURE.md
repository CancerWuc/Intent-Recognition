# 意图识别系统 - 方案一实现

## 项目概述

本项目实现了**方案一：两层意图识别 + 直接调用Agent**的完整系统，采用中心化控制架构，无A2A依赖，具有响应速度快、调试简单、成本可控的特点。

## 核心架构

```
intent_recognition/
├── models/              # 数据模型层
│   ├── scene.py        # 场景定义
│   ├── intent.py       # 意图定义
│   └── agent.py        # Agent基类
├── recognition/         # 意图识别层
│   ├── scene_recognizer.py      # 场景识别器（规则引擎）
│   ├── intent_recognizer.py     # 意图识别器（规则引擎）
│   ├── two_layer_recognizer.py  # 两层识别协调器
│   └── llm_recognizer.py        # 基于大模型的识别器
├── agents/             # Agent管理层
│   ├── registry.py     # Agent注册中心
│   └── executor.py     # Agent执行器
├── router/             # 路由层（核心）
│   └── router.py       # 意图路由器
├── knowledge/          # 知识库同步
│   ├── adapters.py     # 知识库适配器
│   └── sync_service.py # 同步服务
├── llm/                # 大模型集成
│   └── client.py       # 大模型客户端（SiliconFlow API）
└── examples/           # 示例代码
    ├── sample_agents.py # 示例Agent实现
    ├── sample_config.py # 示例配置
    └── llm_demo.py     # 大模型集成示例
```

## 核心概念对齐

### 场景（Scene）
- **定义**：业务维度的大分类
- **示例**：电商客服、旅行规划、企业报销
- **属性**：
  - scene_id: 场景唯一标识
  - name: 场景名称
  - keywords: 关键词列表
  - examples: 示例句子
  - status: 状态（active/inactive/deprecated）

### 意图（Intent）
- **定义**：场景内的具体用户诉求
- **示例**：
  - 旅行规划场景：查机票、订酒店、查天气
  - 电商客服场景：订单查询、退款申请、商品咨询
- **属性**：
  - intent_id: 意图唯一标识
  - scene_id: 所属场景
  - keywords: 关键词列表
  - agent_id: 映射的Agent ID
  - parameters: 参数提取配置

### Agent
- **定义**：执行具体任务的单元
- **特点**：
  - 标准化接口（统一入参/出参）
  - 无状态设计（支持函数式调用）
  - 可观测性（内置日志和状态管理）
- **属性**：
  - agent_id: Agent唯一标识
  - name: Agent名称
  - scene_id: 所属场景
  - intent_id: 关联意图

## 两层意图识别流程

```
用户输入
    ↓
【第一层：场景识别】
    ├─ 关键词匹配
    ├─ 示例相似度计算
    └─ 置信度评估
    ↓
【第二层：意图识别】
    ├─ 场景内关键词匹配
    ├─ 参数提取
    └─ 置信度评估
    ↓
【Agent映射】
    └─ 意图 → Agent ID
    ↓
【Agent执行】
    ├─ 输入验证
    ├─ 预处理
    ├─ 执行
    └─ 后处理
    ↓
返回结果
```

## 核心特点

### 1. 中心化控制
- 所有意图识别逻辑集中在路由层
- Agent仅作为执行单元，无自主协作能力
- 逻辑简单清晰，易于理解和维护

### 2. 无A2A依赖
- Agent无需部署为独立服务
- 可作为函数/模块直接调用
- 无跨服务HTTP请求，延迟最低

### 3. 标准化接口
- 统一的Agent基类
- 标准化的入参/出参格式
- 支持预处理和后处理

### 4. 可观测性
- 执行统计（调用次数、成功率、耗时）
- 识别统计（场景/意图识别准确率）
- 错误追踪（失败阶段、错误信息）

## 使用示例

### 快速开始

```python
from intent_recognition import IntentRouter, BaseAgent, AgentResult
from intent_recognition.examples import create_sample_router

# 创建路由器
router = create_sample_router()

# 路由用户输入
result = router.route("我想查一下北京到上海的机票")

if result.success:
    print(f"场景: {result.scene_name}")
    print(f"意图: {result.intent_name}")
    print(f"响应: {result.final_response}")
```

### 自定义Agent

```python
class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="my_agent",
            name="我的Agent",
            description="自定义Agent",
            scene_id="my_scene",
            intent_id="my_intent"
        )
    
    def execute(self, user_input: str, context: dict) -> AgentResult:
        # 实现你的业务逻辑
        return AgentResult(
            success=True,
            data={"result": "处理成功"},
            message="执行成功"
        )

# 注册Agent
router = IntentRouter()
router.register_scene("my_scene", "我的场景", ["关键词"])
router.register_intent("my_intent", "my_scene", "我的意图", ["关键词"], "my_agent")
router.register_agent("my_agent", MyAgent(), "my_intent")
```

### 知识库同步

```python
from intent_recognition.knowledge import KnowledgeSyncService, FileKnowledgeBaseAdapter

# 创建文件适配器
adapter = FileKnowledgeBaseAdapter("config/knowledge_base.json")

# 创建同步服务
sync_service = KnowledgeSyncService(router, adapter)

# 执行同步
result = sync_service.sync_all()
print(f"同步成功: {result.success}")
print(f"场景添加: {result.scenes_added}")
print(f"意图添加: {result.intents_added}")
```

## 性能特点

### 响应速度
- 无跨服务调用
- 无Host Agent中间编排
- 意图识别后直接调用Agent
- 平均响应时间 < 1ms

### 开发成本
- 无需学习A2A协议
- 无需部署多个Agent Server
- Agent可封装为普通函数/接口
- 运维只有"意图识别模型+Agent函数"两层

### 调试简单
- 问题定位路径短
- 无跨Agent通信问题
- 清晰的执行日志

### 成本可控
- Agent无需常驻服务
- 可按需调用（函数式）
- 无闲置资源占用

## 适用场景

### ✅ 推荐使用
- 场景/意图数量中等以下（≤10个场景，每个场景≤5个意图）
- 意图之间无协作需求（每个意图独立完成任务）
- 追求快速落地、低成本运维
- 对扩展性要求不高

### ❌ 不推荐使用
- 场景/意图数量多且持续增长
- 场景内意图需要协作（如"订机票+订酒店"）
- 追求长期扩展性、Agent复用、跨团队协作
- 需要动态调整能力（如Agent故障自动切换）

## 扩展方向

### 短期优化
1. **增强识别算法**
   - 集成BERT等预训练模型
   - 支持语义相似度计算
   - 多轮对话上下文理解

2. **优化参数提取**
   - 实体识别（NER）
   - 槽位填充
   - 多参数组合

3. **完善监控**
   - 性能监控
   - 准确率统计
   - 异常告警

4. **大模型集成**
   - 集成SiliconFlow等大模型API
   - 支持基于大模型的意图识别
   - 提高复杂意图的理解能力

### 长期演进
1. **迁移到方案二**
   - 将Agent封装为A2A服务
   - 引入Host Agent
   - 支持Agent协作

2. **混合架构**
   - 简单场景用方案一
   - 复杂场景用方案二
   - 按需选择架构

3. **智能路由**
   - 基于大模型的动态路由决策
   - 支持多模型协同推理
   - 自适应场景识别

## 项目文件说明

```
Intent Recognition/
├── intent_recognition/          # 核心代码
│   ├── __init__.py             # 包初始化
│   ├── models/                 # 数据模型
│   ├── recognition/            # 识别模块
│   ├── agents/                 # Agent管理
│   ├── router/                 # 路由层
│   ├── knowledge/              # 知识库同步
│   └── examples/               # 示例代码
├── tests/                      # 单元测试
│   └── test_intent_recognition.py
├── examples/                   # 演示代码
│   └── demo.py
├── config/                     # 配置文件
│   └── knowledge_base.json     # 知识库配置
├── requirements.txt            # 依赖包
├── quick_start.py             # 快速开始
└── ARCHITECTURE.md            # 架构文档（本文件）
```

## 测试结果

```
============================= test session starts ==============================
collected 22 items

tests/test_intent_recognition.py::TestSceneRecognizer::test_empty_input PASSED
tests/test_intent_recognition.py::TestSceneRecognizer::test_recognize_failure PASSED
tests/test_intent_recognition.py::TestSceneRecognizer::test_recognize_success PASSED
tests/test_intent_recognition.py::TestIntentRecognizer::test_parameter_extraction PASSED
tests/test_intent_recognition.py::TestIntentRecognizer::test_recognize_success PASSED
tests/test_intent_recognition.py::TestIntentRecognizer::test_recognize_wrong_scene PASSED
tests/test_intent_recognition.py::TestTwoLayerRecognizer::test_scene_not_found PASSED
tests/test_intent_recognition.py::TestTwoLayerRecognizer::test_two_layer_recognition PASSED
tests/test_intent_recognition.py::TestAgentRegistry::test_get_by_intent PASSED
tests/test_intent_recognition.py::TestAgentRegistry::test_register_class PASSED
tests/test_intent_recognition.py::TestAgentRegistry::test_register_instance PASSED
tests/test_intent_recognition.py::TestAgentRegistry::test_unregister PASSED
tests/test_intent_recognition.py::TestAgentExecutor::test_execute_agent_not_found PASSED
tests/test_intent_recognition.py::TestAgentExecutor::test_execute_success PASSED
tests/test_intent_recognition.py::TestAgentExecutor::test_stats PASSED
tests/test_intent_recognition.py::TestIntentRouter::test_batch_route PASSED
tests/test_intent_recognition.py::TestIntentRouter::test_route_failure PASSED
tests/test_intent_recognition.py::TestIntentRouter::test_route_success PASSED
tests/test_intent_recognition.py::TestIntentRouter::test_stats PASSED
tests/test_intent_recognition.py::TestSampleRouter::test_ecommerce_scene PASSED
tests/test_intent_recognition.py::TestSampleRouter::test_expense_scene PASSED
tests/test_intent_recognition.py::TestSampleRouter::test_travel_scene PASSED

======================== 22 passed, 1 warning in 0.03s =========================
```

## 总结

本实现完整地展示了**方案一：两层意图识别 + 直接调用Agent**的核心思想和实现细节，具有以下优势：

1. **架构清晰**：中心化控制，逻辑简单
2. **性能优异**：响应速度快，延迟低
3. **易于维护**：调试简单，问题定位快
4. **成本可控**：开发运维成本低，资源占用少

适合快速落地、小规模场景的意图识别需求，为后续演进到方案二打下坚实基础。
