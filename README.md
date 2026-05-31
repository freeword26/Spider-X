# 🕷️ Spider-X 蜘蛛群

**多Agent协同引擎 + 本地/.cloud AI调度 + 离线能力包**

> 合并自 Spider-X + Spider-X-archive + 旧 Worker 智能体集群 + Spider Meta。一个项目，完整功能。

## 是什么

Spider-X 是 Spider 系列生态的**多Agent智能体集群调度引擎**：

**核心能力：**
- **任务路由** — 关键词匹配 + 中英文同义词，自动分配到最优角色
- **本地AI** — Ollama 本地模型（codellama/qwen/llama3），零成本执行
- **云端AI** — Claude/GPT-4/OpenAI，按需调用，质量优先
- **离线能力包** — 预编译决策树/状态机，<50ms响应，无需模型
- **混合调度** — 本地预处理 + 云端深度分析，1.2秒 vs 纯云端2.8秒
- **全Agent并行** — 最多3个角色同时执行，结果智能聚合
- **审计追踪** — HMAC-SHA256 区块链式凭证链

**架构优势（典型场景：分析10页财报PDF）：**

| 架构 | 延迟 | 说明 |
|------|------|------|
| 纯本地 | OOM崩溃 | 内存溢出 |
| 纯云端 | 2.8秒 | 网络延迟主导 |
| **Spider-X 混合** | **1.2秒** | 本地预处理 + 云端深度分析 |
| **Spider-X 离线** | **3.5秒** | 离线能力包，零网络依赖 |

**关键结论：**
- 本地基础能力：所有设备都能运行1B-3B模型（Phi-3-mini, Gemma-2B）
- 智能卸载：复杂任务自动拆解，仅关键部分上云
- 离线保障：90%高频任务通过能力包本地完成
- 低带宽优化：差分同步减少95%+数据传输

## 快速开始

```bash
pip install -e ".[dev]"

# 一键启动（推荐）
./start_ai_system.sh

# 或分步启动
docker-compose up -d --build
```

**端口说明：**

| 服务 | 端口 | 用途 |
|------|------|------|
| Spider-X API | 8006 | FastAPI 完整接口 |
| Agent Gateway | 9100 | IDE 集成入口 /api/v1/execute |
| Dashboard | 9090 | 实时监控面板 + WebSocket |

# Click CLI（推荐）
spider-x serve --port 8006
spider-x worker --rabbitmq-url amqp://guest:guest@localhost:5672
spider-x init my-project
spider-x config
spider-x status
spider-x version

# 或 Python 入口
python run.py serve
python run.py worker
python run.py version
```

## 模块说明

### 核心层 (`spider_x/core/`)

| 模块 | 作用 |
|------|------|
| `app.py` | FastAPI 应用工厂，注册全部路由（30+） |
| `cli.py` | Click CLI（serve/worker/init/config/status/version） |
| `config.py` | 配置加载（Pydantic Settings，支持 .env） |
| `credential_chain.py` | 区块链式凭证链（HMAC-SHA256 签名、链式哈希、完整性校验） |
| `task.py` | 任务模型（状态/优先级/重试） |
| `registry.py` | 任务处理器注册表（装饰器模式） |
| `sop_engine.py` | SOP 流水线引擎（DAG 编排、凭证链集成） |
| `chaos_scheduler.py` | 混沌调度器（CPU/内存/能力 三因子评分 + bidding 竞价） |
| `resource_state.py` | 智能体集群状态管理（注册/心跳/TTL 过期） |
| `atomic_action.py` | 任务分解（复合任务 → 原子动作序列） |
| `subgraph.py` | 子图封装（协作模式发现 → 虚拟超智能体） |
| `plugin.py` | 插件管理（7 种状态、OCI/WASI/本地部署） |
| `skill_lock.py` | 技能锁（并发冲突检测、兼容矩阵） |
| `skill_gnn.py` | GNN 技能组合发现（category bonus、中文描述） |
| `skill_kg.py` | 技能知识图谱（Neo4j 持久化、子图提取、反向查询） |
| `worker.py` | Worker 节点与任务提交 |
| `observability.py` | OpenTelemetry 链路追踪（Noop 降级） |

### 适配器 (`spider_x/adapters/`)

| 模块 | 桥接目标 |
|------|----------|
| `mini_spider.py` | mini_spider v3 多智能体框架 |
| `spider_max.py` | spider_max 项目管理平台 |
| `spider_room.py` | spidermax_room 工作流引擎 |
| `spidermax_room.py` | MAX ROOM v2 无人值守工作流（完整版） |
| `spider_diary.py` | spider_diary 运维报告引擎 |

### 技能系统 (`spider_x/skills/`)

| 模块 | 作用 |
|------|------|
| `builtin.py` | 14 个内置技能（echo/shell/python/http/file/research/code/review/test/clean/deploy/notify/brainstorm） |
| `manifest.py` | 技能清单加载/校验/发现 |
| `index_brainstorm.py` | 多智能体索引头脑风暴（25 个 Agent，5 层架构） |

## API 一览

| 端点 | 作用 |
|------|------|
| `GET /health` | 健康检查（含集群状态） |
| `POST /tasks/submit` | 提交任务 |
| `GET /tasks/{id}` | 查询任务 |
| `POST /api/v1/sop/pipelines` | 创建 SOP 流水线 |
| `POST /api/v1/sop/execute/{id}` | 执行流水线 |
| `POST /api/v2/agents/register` | 注册智能体 |
| `GET /api/v2/agents` | 查看集群 |
| `GET /api/v2/cluster/summary` | 集群概览 |
| `GET /api/v3/gnn/discover` | GNN 技能组合发现 |
| `POST /api/v3/skills/check` | 技能冲突检测 |

## 配置

```env
SPIDER_X_API_PORT=8006
SPIDER_X_DEBUG=true
SPIDER_X_RABBITMQ_HOST=localhost
SPIDER_X_RABBITMQ_PORT=5672
SPIDER_X_NEO4J_URI=bolt://localhost:7687
SPIDER_X_OTEL_ENDPOINT=http://otel-collector:4318
SPIDER_X_CREDIFICATE_SECRET=your-hmac-secret
```

## 运行测试

```bash
pytest tests/ -v
# 81 tests, all passing
```

## Docker 部署

```bash
docker-compose up -d
# 包含: API 服务 + Worker 节点 + RabbitMQ + Redis
```

## 架构

```
外部系统                  Spider-X
─────────                ──────────
mini_spider       ──┐
spider_max        ──┼──  adapters  ──→  core  ──→  FastAPI  ──→  WebUI
spidermax_room    ──┤                  │
spider_diary      ──┘                  └──  RabbitMQ  ←──  Worker 节点
```

## 许可证

MIT
