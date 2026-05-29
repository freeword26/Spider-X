# 🕷️ Spider-X 蜘蛛群 — 使用说明

## 一、这是什么

Spider-X 是一个 **Worker 智能体集群引擎**。把它想象成一个"任务调度中心"：

```
你提交一个任务 → Spider-X 自动拆解 → 分配给最合适的 Worker 执行 → 全程审计追踪
```

**能做什么：**
- 提交任务（shell 命令、Python 代码、HTTP 请求、文件读写）
- 编排多步骤流水线（SOP）：比如"调研→编码→审查→测试→部署"
- 管理一群 Worker 智能体（注册、心跳、负载均衡）
- 技能图谱：发现哪些技能组合效果最好，哪些技能会冲突
- 插件系统：用容器/WASM/本地进程扩展新能力
- 桥接其他 Spider 系统（mini_spider、spider_max、spider_diary 等）

---

## 二、快速上手

### 1. 安装

```bash
cd Spider-X
pip install -e .                    # 基础安装
pip install -e ".[all]"            # 全部可选依赖（OTel + Neo4j + Redis）
pip install -e ".[dev]"            # 开发模式（含测试工具）
```

### 2. 启动服务

**方式一：Click CLI（推荐）**
```bash
spider-x serve --port 8006         # 启动 API 服务
```

**方式二：Python 脚本**
```bash
python run.py serve                 # 启动 API 服务
python run.py version               # 查看版本
```

**方式三：作为库使用**
```python
import spider_x
app = spider_x.create_app()
# 或用 TestClient 测试
from starlette.testclient import TestClient
client = TestClient(app)
print(client.get("/health").json())
```

### 3. 验证安装

```bash
curl http://localhost:8006/health
# 返回: {"status": "ok", "cluster": {...}, "scheduler": {...}}
```

---

## 三、命令行工具（CLI）

安装后，系统注册了 `spider-x` 命令：

| 命令 | 作用 | 常用参数 |
|------|------|----------|
| `serve` | 启动 API 服务器 | `--host 0.0.0.0 --port 8006 --reload` |
| `worker` | 启动 Worker 节点（从队列消费任务） | `--rabbitmq-url amqp://guest:guest@localhost:5672 --concurrency 4` |
| `init` | 初始化项目目录 | `spider-x init my-project` |
| `config` | 查看当前配置 JSON | — |
| `status` | 查询服务健康状态 | `--server-url http://localhost:8006` |
| `version` | 版本信息 | — |

**示例：**
```bash
# 启动热重载开发服务器
spider-x serve --port 8006 --reload

# 启动 Worker 连接到 RabbitMQ
spider-x worker --rabbitmq-url amqp://guest:guest@localhost:5672 --concurrency 8

# 初始化新项目
spider-x init ./my-project
```

---

## 四、HTTP API 接口

服务启动后，通过 HTTP 请求操作（默认端口 8006）：

### 基础
```
GET  /              服务信息
GET  /health        健康检查（含集群状态 + 调度器状态）
```

### 任务管理
```
POST /tasks/submit              提交任务
GET  /tasks/{id}                查询任务状态
GET  /tasks                     列出所有任务
```

### SOP 流水线
```
POST /api/v1/sop/pipelines       创建流水线
POST /api/v1/sop/execute/{id}    执行流水线
GET  /api/v1/sop/pipelines       列出流水线
GET  /api/v1/report/latest       最新执行报告
```

### 凭证链（审计）
```
GET  /api/v1/credentials/chains            列出所有凭证链
GET  /api/v1/credentials/chain/{id}        查看链详情
```

### Agent 管理
```
POST /api/v2/agents/register               注册 Agent
DELETE /api/v2/agents/{id}                 注销 Agent
POST /api/v2/agents/{id}/heartbeat         心跳上报
GET  /api/v2/agents                        列出所有 Agent
GET  /api/v2/agents/available              列出可用 Agent
GET  /api/v2/cluster/summary               集群概览
```

### 技能图谱
```
GET  /api/v3/gnn/discover                   GNN 技能组合发现
GET  /api/v3/gnn/recommend                  技能推荐
POST /api/v3/skills/check                   技能冲突检测
```

**提交任务示例：**
```bash
# 执行 echo 任务
curl -X POST http://localhost:8006/tasks/submit \
  -H "Content-Type: application/json" \
  -d '{"task_type": "echo", "payload": {"message": "Hello Spider-X!"}}'

# 执行 shell 命令
curl -X POST http://localhost:8006/tasks/submit \
  -H "Content-Type: application/json" \
  -d '{"task_type": "shell", "payload": {"command": "ls -la"}}'

# 执行 Python 代码
curl -X POST http://localhost:8006/tasks/submit \
  -H "Content-Type: application/json" \
  -d '{"task_type": "python", "payload": {"code": "print(2+2)"}}'
```

---

## 五、核心模块说明

### 5.1 任务系统（Task）

**是什么：** 任务的基本单元。每个任务有 ID、类型、内容、状态、优先级。

**内置任务类型（6 种）：**

| 类型 | 做什么 | 示例 |
|------|--------|------|
| `echo` | 回显测试 | `{"message": "hello"}` |
| `shell` | 执行系统命令 | `{"command": "ls -la"}` |
| `python` | 执行 Python 代码 | `{"code": "print(2+2)"}` |
| `http_request` | 发 HTTP 请求 | `{"method": "GET", "url": "https://..."}` |
| `file_write` | 写文件 | `{"path": "a.txt", "content": "hello"}` |
| `file_read` | 读文件 | `{"path": "a.txt"}` |

**注册自定义处理器：**
```python
from spider_x.core.registry import registry

@registry.register("my_task", description="我的自定义任务", version="1.0")
async def handle_my_task(payload):
    # payload 是任务携带的数据
    result = do_something(payload)
    return {"status": "ok", "result": result}
```

**任务状态流转：**
```
PENDING → RUNNING → COMPLETED
                   ↘ FAILED → (重试) → RUNNING
                   ↘ CANCELLED
```

### 5.2 SOP 流水线引擎

**是什么：** 把一系列步骤组合成自动化流水线，自动处理步骤间的依赖关系。

**使用场景：** "开发一个功能"可以拆成：需求分析 → 编码 → 代码审查 → 测试 → 部署。

**示例：**
```python
from spider_x.core.sop_engine import SOPEngine

engine = SOPEngine()

# 注册每个步骤的执行函数
engine.register_handler("research", do_research)
engine.register_handler("code", do_code)
engine.register_handler("review", do_review)
engine.register_handler("test", do_test)

# 创建流水线
pipeline = engine.create_pipeline("开发流水线", [
    {"name": "需求分析", "action": "research"},
    {"name": "编码", "action": "code", "depends_on": ["需求分析"]},
    {"name": "审查", "action": "review", "depends_on": ["编码"]},
    {"name": "测试", "action": "test", "depends_on": ["审查"]},
])

# 执行（自动按依赖顺序运行）
result = await engine.execute_pipeline(pipeline.pipeline_id)

# 查看报告
report = engine.get_execution_report(pipeline.pipeline_id)
# report 包含每步的状态、结果、耗时，以及完整的凭证链
```

**关键特性：**
- 没有依赖的步骤自动并行执行
- 某步失败会阻止依赖它的后续步骤执行
- 每步自动记录到凭证链（防篡改审计）
- 支持重试（`max_retries` 参数）

### 5.3 混沌调度器（Chaos Scheduler）

**是什么：** 智能任务分发器。有新任务来了，自动挑最合适的 Worker 执行。

**评分算法（三因子加权）：```
最终分数 = CPU/内存余量 × 0.3 + 能力匹配度 × 0.5 + 令牌桶余量 × 0.2
```

**竞价模式（可选）：** 开启后，Worker 根据自身能力和负载"出价"，价高者得。

**示例：**
```python
from spider_x.core.chaos_scheduler import ChaosScheduler, TokenBucket

scheduler = ChaosScheduler(
    token_bucket_rate=10.0,          # 每秒恢复 10 个令牌
    token_bucket_capacity=100.0,     # 桶最多 100 个令牌
    enable_bidding=True,             # 开启竞价模式
)

# 注册 Worker 节点
scheduler.register_agent("worker-1", state={
    "capabilities": {"roles": ["coder"], "skills": ["python", "rust"]},
    "resources": {"cpu_percent": 20, "memory_percent": 30, "active_tasks": 2},
    "max_concurrency": 8,
})
scheduler.register_agent("worker-2", state={
    "capabilities": {"roles": ["researcher"], "skills": ["search", "writing"]},
    "resources": {"cpu_percent": 10, "memory_percent": 20, "active_tasks": 1},
    "max_concurrency": 4,
})

# 提交一个需要 Python 编程的任务
# 调度器会自动选 worker-1（能力匹配度更高）
scheduler.submit_action({
    "action_type": "code",
    "required_roles": ["coder"],
    "required_skills": ["python"],
})
```

### 5.4 凭证链（Credential Chain）

**是什么：** 任务执行的"区块链审计日志"。每步操作都生成一条不可篡改的记录，连成一条链。

**为什么重要：** 出了问题可以回溯每一步的输入输出，且无法事后篡改。

**示例：**
```python
from spider_x.core.credential_chain import CredentialChainManager

mgr = CredentialChainManager(secret="my-hmac-secret")

# 创建一个审计链
chain = mgr.create_chain("task-001", "data-pipeline")

# 每步操作自动记录
chain.add_entry("extract", {"source": "database"}, {"rows": 10000})
chain.add_entry("clean", {"rows": 10000}, {"rows": 9500, "removed": 500})
chain.add_entry("transform", {"rows": 9500}, {"rows": 9500, "fields": 12})
chain.add_entry("load", {"rows": 9500}, {"status": "done", "table": "dw.facts"})

# 验证完整性（检测是否被篡改）
assert chain.verify() is True

# 查看摘要
print(chain.summary())
# {"chain_id": "...", "total_steps": 4, "verified": True, "chain_hash": "..."}
```

### 5.5 集群资源状态管理

**是什么：** 实时监控所有 Worker 节点的 CPU、内存、负载、能力标签。

**示例：**
```python
from spider_x.core.resource_state import ResourceStateService

svc = ResourceStateService()

# Worker 注册
svc.register_agent("worker-1", capabilities={
    "roles": ["coder", "reviewer"],
    "skills": ["python", "rust", "sql"],
})

# Worker 上报心跳（带资源信息）
svc.update_state("worker-1", {
    "cpu_percent": 45.2,
    "memory_percent": 62.1,
    "active_tasks": 3,
})

# 获取集群概况
summary = svc.get_cluster_summary()
# {"total_agents": 1, "idle": 0, "busy": 1, "avg_cpu_percent": 45.2, ...}

# 查找能执行特定任务的 Worker
available = svc.get_available_agents(
    required_role="coder",
    required_skill="rust",
)
```

### 5.6 技能图谱（GNN + 知识图谱）

**是什么：** 技能之间的关系网络。GNN 发现好的组合，知识图谱记录冲突和互补关系。

**GNN — 技能组合推荐：**
```python
from spider_x.core.skill_gnn import SkillCombinatorGNN

gnn = SkillCombinatorGNN()

# 注册技能
gnn.register_skill("py", "Python", "language")
gnn.register_skill("rust", "Rust", "language")
gnn.register_skill("search", "搜索", "research")
gnn.register_skill("ml", "机器学习", "ai")

# 记录共现（哪些技能经常一起使用）
gnn.record_co_occurrence("py", "ml", weight=2.0)
gnn.record_co_occurrence("search", "ml", weight=1.5)

# 发现最佳组合
combinations = gnn.discover_combinations(top_k=5)
for combo in combinations:
    print(f"{combo.description} (置信度: {combo.confidence:.2f})")
# 输出: "从研究到实现: 搜索 → Python → 机器学习 (置信度: 0.85)"
```

**知识图谱 — 冲突检测：**
```python
from spider_x.core.skill_kg import SkillKnowledgeGraph

kg = SkillKnowledgeGraph(neo4j_uri="bolt://localhost:7687")

# 注册技能
kg.add_skill("py", "Python", {"category": "language"})
kg.add_skill("rust", "Rust", {"category": "language"})

# 记录关系
kg.register_complement("py", "ml", evidence="Python 是 ML 的主要语言")
kg.register_conflict("py", "rust", reason="同一项目不建议混用")

# 查询技能关系
print(kg.query_skill("py"))
# 返回: {"node": {...}, "relations": [{"target": "ml", "relation": "COMPLEMENT"}, ...]}

# 查找所有冲突
conflicts = kg.find_conflicts()
```

### 5.7 技能锁（LOCKSS）

**是什么：** 检测多个并发任务是否会争抢同一资源，防止冲突。

**三种锁模式：**
- `READ`（读锁）：多个任务可以同时读
- `WRITE`（写锁）：读写互斥
- `EXCLUSIVE`（独占锁）：任何操作都互斥

**示例：**
```python
from spider_x.core.skill_lock import LOCKSSChecker, SkillScope, LockMode

checker = LOCKSSChecker()

# 注册两个会操作同一文件的技能
checker.register_skill(SkillScope(
    skill_id="write-config",
    scopes=[{"type": "file", "path": "/etc/app/config.yaml"}],
    lock_mode=LockMode.WRITE,
))
checker.register_skill(SkillScope(
    skill_id="read-config",
    scopes=[{"type": "file", "path": "/etc/app/config.yaml"}],
    lock_mode=LockMode.READ,
))

# 检查是否可以同时运行
ok, conflict = checker.check_compatibility("write-config", "read-config")
if not ok:
    print(f"冲突: {conflict.resolution}")
# "冲突: Incompatible lock modes: write vs read"

# 检查一个技能组合
ok, conflicts = checker.check_combination(["read-config", "backup-config"])
```

### 5.8 任务分解器（Atomic Action）

**是什么：** 把模糊的高层任务自动拆解为具体的原子动作。

**示例：**
```python
from spider_x.core.atomic_action import TaskDecomposer

decomposer = TaskDecomposer()

# 自动拆解
result = decomposer.decompose("实现一个用户注册的 REST API")
print(result.actions)
# [
#   Action(type=RESEARCH, name="调研需求"),
#   Action(type=CODE, name="编写代码", depends_on=["调研需求"]),
#   Action(type=REVIEW, name="代码审查", depends_on=["编写代码"]),
#   Action(type=TEST, name="测试验证", depends_on=["代码审查"]),
#   Action(type=DEPLOY, name="部署上线", depends_on=["测试验证"]),
# ]
```

### 5.9 子图封装（Subgraph / VSA）

**是什么：** 从历史执行数据中发现高频协作模式，封装成可复用的"虚拟超智能体"。

**示例：**
```python
from spider_x.core.subgraph import SubgraphEncapsulator, VirtualSuperAgentManager

enc = SubgraphEncapsulator(min_frequency=3)

# 记录历史执行序列
for _ in range(10):
    enc.record_observation(["research", "code", "test"], duration_ms=5000, success=True)
for _ in range(5):
    enc.record_observation(["code", "review", "fix"], duration_ms=3000, success=True)

# 发现高频模式
patterns = enc.discover_patterns()
for p in patterns:
    print(f"{p.name}: 执行了 {p.frequency} 次, 成功率 {p.success_rate:.0%}, 平均耗时 {p.avg_duration_ms:.0f}ms")

# 将高频模式封装为虚拟超智能体
mgr = VirtualSuperAgentManager(enc)
vsas = mgr.auto_discover_and_create()
for vsa in vsas:
    print(f"创建 VSA: {vsa.pattern.name} (调用入口: {vsa.super_agent_id})")
```

### 5.10 插件系统

**是什么：** 用插件扩展新的能力。支持三种部署方式：

| 方式 | 说明 | 适用场景 |
|------|------|----------|
| `oci` | Docker 容器 | 生产环境，隔离性最好 |
| `wasi` | WebAssembly 沙箱 | 轻量级，快速启动 |
| `local` | 本地进程 | 开发调试，零开销 |

**示例：**
```python
from spider_x.core.plugin import PluginManager, PluginManifest

mgr = PluginManager(plugin_dir="./plugins")

# 注册一个插件
manifest = PluginManifest(
    plugin_id="translator",
    name="翻译插件",
    version="1.0.0",
    agent_type="utility",
    entry_point="plugins.translator:main",
    capabilities=["translate", "detect_language"],
    deployment_mode="local",
)
mgr.register_plugin(manifest)

# 激活插件
await mgr.activate_plugin("translator")

# 按能力搜索
plugins = mgr.find_plugins_by_capability("translate")
```

### 5.11 适配器（Adapters）

**是什么：** 桥接其他 Spider 系统，让它们能和 Spider-X 互通。

| 适配器 | 桥接系统 | 能做什么 |
|--------|----------|----------|
| `MiniSpiderAdapter` | mini_spider v3 | Agent 注册、任务分发、格式转换 |
| `SpiderMaxAdapter` | spider_max | 项目同步、OKR 导入/导出、模块注册表 |
| `SpiderRoomAdapter` | spidermax_room v2 | 工作流注册/触发/状态查询 |
| `SpiderDiaryAdapter` | spider_diary | 报告生成、看板同步、定时调度 |

**示例 — 桥接 mini_spider：**
```python
from spider_x.adapters import MiniSpiderAdapter

# 从现有 mini_spider 实例创建适配器
adapter = MiniSpiderAdapter.from_mini_spider(mini_spider_orchestrator)

# 注册 Agent
adapter.register_agents([
    {"agent_id": "researcher-1", "roles": ["researcher"]},
    {"agent_id": "coder-1", "roles": ["coder"]},
])

# 把 mini_spider 任务转为 Spider-X 格式
task = adapter.to_spider_x_task({"id": "t1", "type": "research", "payload": {"query": "AI最新趋势"}})
```

### 5.12 可观测性（Observability）

**是什么：** 集成了 OpenTelemetry，自动追踪每个任务的执行链路和性能指标。

**只需配置环境变量即可启用：**
```env
SPIDER_X_OTEL_ENDPOINT=http://otel-collector:4318
```

**OTel Collector 配置（`config/otel-config.yaml`）：**
- 接收 OTLP 协议（gRPC 4317 + HTTP 4318）
- 批量处理 → 输出到日志 + Jaeger 链路追踪

**如果未安装 OTel：** 自动降级为 Noop（不影响任何功能）。

---

## 六、Docker 部署

### 一键启动完整栈

```bash
docker-compose up -d
```

**启动 4 个容器：**

| 容器 | 端口 | 作用 |
|------|------|------|
| `worker-api` | 8006 | API 服务器 |
| `worker-node` | — | Worker 节点（2 个副本） |
| `rabbitmq` | 5672, 15672 | 消息队列 + 管理面板 |
| `redis` | 6383 | 缓存 |

### 环境变量配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `RABBITMQ_HOST` | rabbitmq | RabbitMQ 地址 |
| `RABBITMQ_PORT` | 5672 | RabbitMQ 端口 |
| `REDIS_HOST` | redis | Redis 地址 |
| `REDIS_PORT` | 6383 | Redis 端口 |
| `API_PORT` | 8006 | API 服务端口 |

---

## 七、配置说明

### 环境变量（.env 文件）

```env
# 基础
SPIDER_X_ENV=development          # 环境: development / production
SPIDER_X_DEBUG=true               # 调试模式
SPIDER_X_LOG_LEVEL=INFO           # 日志级别

# API
SPIDER_X_API_HOST=0.0.0.0
SPIDER_X_API_PORT=8006

# 基础设施
SPIDER_X_RABBITMQ_HOST=localhost
SPIDER_X_RABBITMQ_PORT=5672
SPIDER_X_RABBITMQ_USER=guest
SPIDER_X_RABBITMQ_PASSWORD=guest
SPIDER_X_RABBITMQ_VHOST=/

SPIDER_X_REDIS_HOST=localhost
SPIDER_X_REDIS_PORT=6383

# 知识图谱
SPIDER_X_NEO4J_URI=bolt://localhost:7687
SPIDER_X_NEO4J_USER=neo4j
SPIDER_X_NEO4J_PASSWORD=password

# 可观测性
SPIDER_X_OTEL_ENDPOINT=http://otel-collector:4318

# 安全
SPIDER_X_CREDIFICATE_SECRET=your-hmac-secret
```

### YAML 配置（config/settings.yaml）

```yaml
service:
  name: Worker Cluster
  version: "1.0.0"
  debug: false

rabbitmq:
  host: localhost
  port: 5672

redis:
  host: localhost
  port: 6383

api:
  host: "0.0.0.0"
  port: 8006

worker:
  max_concurrency: 10
  prefetch_count: 1
```

---

## 八、运行测试

```bash
pip install -e ".[dev]"
pytest tests/ -v              # 详细输出
pytest tests/ -q              # 简洁输出
pytest tests/ --tb=short      # 短 traceback

# 81 个测试，全部通过
```

**测试覆盖：**
- `test_imports.py` — 15 个：模块导入 + 基础功能验证
- `test_atomic_action.py` — 10 个：任务分解器
- `test_chaos_scheduler.py` — 13 个：调度器 + 令牌桶
- `test_credential_chain.py` — 11 个：凭证链 + 审计
- `test_resource_state.py` — 9 个：集群状态管理
- `test_skill_lock.py` — 11 个：技能锁 + 冲突检测
- `test_sop_engine.py` — 6 个：SOP 流水线

---

## 九、项目结构

```
Spider-X/
├── spider_x/                    # 主包
│   ├── __init__.py              # 公开 API 导出
│   ├── cli.py                   # Click CLI（6 个命令）
│   ├── core/                    # 核心模块（16 个）
│   │   ├── app.py               # FastAPI 应用工厂
│   │   ├── cli.py               # （同 spider_x/cli.py）
│   │   ├── config.py            # 配置管理
│   │   ├── credential_chain.py  # 凭证链审计
│   │   ├── task.py              # 任务模型 + 内置处理器
│   │   ├── registry.py          # 任务处理器注册表
│   │   ├── sop_engine.py        # SOP 流水线引擎
│   │   ├── chaos_scheduler.py   # 混沌调度器
│   │   ├── resource_state.py    # 集群状态管理
│   │   ├── atomic_action.py     # 任务分解器
│   │   ├── subgraph.py          # 子图封装 + VSA
│   │   ├── plugin.py            # 插件管理器
│   │   ├── skill_lock.py        # 技能锁检测
│   │   ├── skill_gnn.py         # GNN 技能组合发现
│   │   ├── skill_kg.py          # 技能知识图谱
│   │   ├── worker.py            # Worker 节点
│   │   └── observability.py     # OpenTelemetry
│   ├── adapters/                # 外部系统适配器（5 个）
│   │   ├── mini_spider.py
│   │   ├── spider_max.py
│   │   ├── spider_room.py
│   │   ├── spidermax_room.py
│   │   └── spider_diary.py
│   └── skills/                  # 技能系统
│       ├── builtin.py           # 14 个内置技能
│       ├── manifest.py          # 技能清单加载器
│       └── index_brainstorm.py  # 多智能体头脑风暴
├── tests/                       # 测试（81 个）
├── docs/                        # 文档
│   ├── MODULES.md               # 模块速查
│   ├── QUICKSTART.md            # 快速入门
│   ├── WHITEPAPER.md            # 技术白皮书
│   └── requirements.md          # 需求文档模板
├── webui/                       # Web 控制台
│   ├── dashboard.html
│   └── report.html
├── shared/schemas/              # JSON Schema
│   ├── agent_state_v2.json
│   ├── credential_v1.json
│   └── skill_scope_v3.json
├── config/                      # 配置文件
│   ├── settings.yaml
│   └── otel-config.yaml
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
└── run.py                       # 入口脚本
```

---

## 十、依赖说明

### 核心依赖（必须）

| 包 | 用途 |
|----|------|
| `fastapi` | Web 框架 |
| `uvicorn` | ASGI 服务器 |
| `pydantic` | 数据验证 + 配置 |
| `pydantic-settings` | 环境变量配置 |
| `aio-pika` | RabbitMQ 客户端 |
| `httpx` | HTTP 客户端 |
| `click` | CLI 框架 |
| `python-dotenv` | .env 文件加载 |

### 可选依赖

| 组 | 包 | 用途 |
|----|----|------|
| `otel` | opentelemetry-* | 链路追踪 + 指标 |
| `neo4j` | neo4j | 知识图谱存储 |
| `redis` | redis | 缓存 |
| `dev` | pytest, ruff | 测试 + 代码检查 |

```bash
pip install -e ".[otel,neo4j,redis,dev]"   # 全部
```
