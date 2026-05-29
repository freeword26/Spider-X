# 🕷️ Spider-X 蜘蛛群

**Worker 智能体集群引擎** — 统一版

> 合并自 Spider-X + Spider-X-archive + 旧 Worker 智能体集群。一个项目，完整功能。

## 是什么

Spider-X 是 Spider 系列生态的**智能体集群调度引擎**：
- 接收任务 → 分解 → 调度 → 执行 → 审计
- 管理智能体集群（注册、心跳、负载均衡）
- 编排 SOP 流水线（顺序/并行/重试）
- 技能图谱（GNN 组合发现、知识图谱、冲突检测）
- 插件管理（OCI/WASI/本地三种部署）
- 桥接 mini_spider / spider_max / spidermax_room / spider_diary

## 快速开始

```bash
pip install -e ".[dev]"

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
