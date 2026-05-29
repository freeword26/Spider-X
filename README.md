# 🕷️ Spider-X 蜘蛛群

**Worker 智能体集群引擎** — 服务端完整版

> 提供完整 REST API、WebUI 控制台、三因子调度、技能图谱。适合部署为中央调度服务。

## 是什么

Spider-X 是 Spider 系列生态的**中央调度引擎**，负责：
- 接收任务 → 分解 → 调度 → 执行 → 审计
- 管理智能体集群（注册、心跳、负载均衡）
- 编排 SOP 流水线（顺序/并行/重试）
- 桥接 mini_spider / spider_max / spidermax_room / spider_diary

## 快速开始

```bash
pip install -e .
spider-x serve --port 8006
```

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

## 模块说明

### 核心层 (`spider_x/core/`)

| 模块 | 作用 |
|------|------|
| `app.py` | FastAPI 应用工厂，注册全部路由 |
| `config.py` | 配置加载（Pydantic Settings，支持 .env） |
| `credential_chain.py` | 凭证链（HMAC-SHA256 防篡改审计） |
| `task.py` | 任务模型（状态/优先级/重试） |
| `sop_engine.py` | SOP 流水线引擎（DAG 编排） |
| `chaos_scheduler.py` | 混沌调度器（CPU/内存/能力 三因子评分 + bidding） |
| `resource_state.py` | 智能体集群状态管理（注册/心跳/TTL 过期） |
| `atomic_action.py` | 任务分解（复合任务 → 原子动作序列） |
| `subgraph.py` | 子图封装（协作模式发现 → 虚拟超智能体） |
| `plugin.py` | 插件管理（OCI/WASI/本地三种部署） |
| `skill_lock.py` | 技能锁（并发技能冲突检测） |
| `skill_gnn.py` | GNN 技能组合推荐 |
| `skill_kg.py` | 技能知识图谱（Neo4j 持久化） |
| `worker.py` | Worker 节点与任务提交 |
| `observability.py` | OpenTelemetry 链路追踪 |

### 适配器 (`spider_x/adapters/`)

| 模块 | 桥接目标 |
|------|----------|
| `mini_spider.py` | mini_spider v3 多智能体框架 |
| `spider_max.py` | spider_max 项目管理平台 |
| `spider_room.py` | spidermax_room 工作流引擎 |
| `spider_diary.py` | spider_diary 运维报告引擎 |

### 技能系统 (`spider_x/skills/`)

| 模块 | 作用 |
|------|------|
| `builtin.py` | 14 个内置技能（echo/shell/python/http/file/research/code/review/test/clean/deploy/notify/brainstorm） |
| `manifest.py` | 技能清单加载与校验 |
| `index_brainstorm.py` | 多智能体索引头脑风暴（25 个 Agent 协作） |

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
pip install -e ".[dev]"
pytest tests/ -v
```

## 配套项目

- **spider-x-worker** (`Spider-X-archive`) — 轻量 Worker 节点版，无 Pydantic 依赖，含 Click CLI、RabbitMQ 消费、区块链审计链。适合边缘部署。

## 架构

```
外部系统                  Spider-X (服务端)
─────────                ──────────────────
mini_spider       ──┐
spider_max        ──┼──  adapters  ──→  core  ──→  FastAPI  ──→  WebUI
spidermax_room    ──┤                  │
spider_diary      ──┘                  └──  RabbitMQ  ←──  spider-x-worker
```

## 许可证

MIT
