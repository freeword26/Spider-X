# Spider-X 模块速查

## 核心 (core/)

### app.py — 应用工厂
创建 FastAPI 实例，注册全部路由，初始化所有核心服务。
- `create_app(config=None)` → FastAPI 实例

### config.py — 配置管理
从环境变量 / .env 加载配置。使用 Pydantic Settings，支持嵌套结构。
- `SpiderXConfig` — 全局配置数据类
- `load_config(env_file=None)` → SpiderXConfig

### credential_chain.py — 凭证链
为每次任务执行生成防篡改审计链。类似区块链：每条记录包含前一条的哈希值。
- `CredentialChainManager` — 管理多条凭证链
- `CredentialEntry` — 单条凭证（input/output/HMAC签名/prev_hash）
- `verify()` — 校验链完整性

### task.py — 任务模型
定义任务结构、状态流转、优先级。
- `Task` — 任务数据类（id/type/payload/status/priority/retry）
- `TaskStatus` — 枚举：PENDING → RUNNING → COMPLETED / FAILED / CANCELLED
- `TaskPriority` — 枚举：P0(紧急) / P1(高) / P2(中) / P3(低)

### sop_engine.py — SOP 流水线
按 DAG（有向无环图）编排多步骤工作流。支持顺序执行、并行分支、重试、失败隔离。
- `SOPEngine` — 创建和执行流水线
- `SOPPipeline` — 流水线定义（含步骤列表和依赖关系）
- `SOPStep` — 单步定义（名称/action/重试次数/超时）

### chaos_scheduler.py — 混沌调度器
智能任务分发。根据 CPU 余量、内存余量、能力匹配度评分，选择最优 Agent 执行。
- `ChaosScheduler` — 注册 Agent、提交动作、分配执行
- `TokenBucket` — 令牌桶限流（防止 Agent 过载）
- 评分公式：capacity×0.3 + capability_match×0.5 + token×0.2

### resource_state.py — 集群状态
跟踪所有 Agent 的在线状态、资源使用率、能力标签。
- `ResourceStateService` — 注册/心跳/查询/自动过期
- `AgentState` — 单个 Agent 状态（角色/技能/CPU/内存/活跃任务数）
- `AgentStatus` — 枚举：IDLE / BUSY / DRAINING / OFFLINE

### atomic_action.py — 任务分解
将复合任务（"实现一个 HTTP 服务"）拆解为原子动作序列（设计→编码→测试→部署）。
- `TaskDecomposer` — 按关键词模式匹配或自定义规则分解
- `ActionType` — 枚举：RESEARCH / CODE / REVIEW / CLEAN / TEST / DEPLOY / NOTIFY / CUSTOM
- `DecompositionResult` — 分解结果（原子动作列表 + 依赖图）

### subgraph.py — 子图封装
从历史协作数据中发现高频动作组合，封装为可复用的"虚拟超智能体"。
- `SubgraphEncapsulator` — 记录协作观测、发现模式
- `VirtualSuperAgentManager` — 管理虚拟超智能体
- `VirtualSuperAgent` — 封装的协作模式（名称/成员/成功率/调用入口）

### plugin.py — 插件管理
注册、激活、停用插件。支持三种部署模式。
- `PluginManager` — 插件生命周期管理
- `PluginManifest` — 插件清单（名称/版本/入口/能力/部署模式）
- `PluginState` — 枚举：REGISTERED → ACTIVE / DEGRADED / UNLOADING / UNLOADED
- 部署模式：OCI 容器 / WASI 沙箱 / 本地进程

### skill_lock.py — 技能锁
检测并发执行的技能之间是否存在资源冲突（如同时写同一文件）。
- `LOCKSSChecker` — 注册技能作用域、检查兼容性
- `SkillScope` — 技能作用域（读/写/执行 + 资源路径）
- `LockMode` — 锁模式：READ / WRITE / EXCLUSIVE
- `check_compatibility(s1, s2)` → (bool, conflict_detail)

### skill_gnn.py — GNN 技能组合
用图神经网络建模技能共现关系，发现高频技能组合路径。
- `SkillCombinatorGNN` — 技能图 + 组合发现
- `SkillGraph` — 技能拓扑图（节点=技能，边=共现权重）
- `discover_combinations(start_skill, max_depth)` → 推荐路径列表

### skill_kg.py — 技能知识图谱
用 Neo4j 存储技能间的冲突、互补、依赖关系。支持复杂图查询。
- `SkillKnowledgeGraph` — 节点/关系 CRUD + Cypher 查询
- `KGNode` — 知识图谱节点（id/name/label/properties）
- `KGEdge` — 关系边（source/target/relation/properties）

### worker.py — Worker 节点
从消息队列取任务、调用 handler 执行、上报结果。
- `WorkerNode` — Worker 实例（连接 RabbitMQ/消费/调度）
- `TaskSubmitter` — 任务提交（发布到队列）

### observability.py — 可观测性
OpenTelemetry 封装。无 OTel 包时自动降级为 Noop（不影响运行）。
- `init_otel(service_name, endpoint)` — 初始化
- `get_tracer()` / `get_meter()` — 获取 tracer/meter
- `record_task_start(task_id)` / `record_task_complete(task_id)` — 任务级 Span

## 适配器 (adapters/)

| 模块 | 桥接系统 | 关键功能 |
|------|----------|----------|
| `mini_spider.py` | mini_spider v3 | Agent 注册/任务分发/状态查询 |
| `spider_max.py` | spider_max | OKR 导入/报告导出/模块注册表 |
| `spider_room.py` | spidermax_room | 工作流注册/触发/状态查询 |
| `spider_diary.py` | spider_diary | 报告生成/看板同步/健康检查 |

## 技能系统 (skills/)

| 模块 | 技能数 | 说明 |
|------|--------|------|
| `builtin.py` | 14 | echo/shell/python/http/file_read/file_write/research/code/review/test/clean/deploy/notify/multi_agent_index_brainstorm |
| `manifest.py` | — | 技能清单 JSON/YAML 加载、校验、自动发现 |
| `index_brainstorm.py` | 1 | 多智能体索引头脑风暴（25 个 Agent，5 层架构） |
