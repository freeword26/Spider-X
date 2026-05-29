# Spider-X 模块速查

## 核心 (core/)

### app.py — 应用工厂
创建 FastAPI 实例，注册全部路由（30+），初始化所有核心服务。
- `create_app(config=None)` → FastAPI 实例

### cli.py — Click CLI
命令行入口，支持 serve/worker/init/config/status/version 子命令。
- `main()` — Click 组入口
- `serve` — 启动 API 服务（--host/--port/--reload）
- `worker` — 启动 Worker（--rabbitmq-url/--concurrency/--worker-id）
- `init` — 初始化项目目录
- `config` / `status` / `version`

### config.py — 配置管理
从环境变量 / .env 加载配置。Pydantic Settings，支持嵌套结构。
- `SpiderXConfig` — 全局配置（API/RabbitMQ/Neo4j/OTel/凭证密钥）
- `load_config(env_file=None)` → SpiderXConfig

### credential_chain.py — 凭证链（区块链式审计）
每次任务执行生成 HMAC-SHA256 签名的链式审计记录。
- `CredentialChainManager` — 管理多条链（创建/查询/校验/按任务查找）
- `CredentialChain` — 单条链（add_entry/verify/complete/summary/to_dict）
- `CredentialEntry` — 单条记录（input_hash/output_digest/signature/prev_hash）
- 默认 secret: `"worker-cluster-credential-secret-v1"`

### task.py — 任务模型
定义任务结构、状态流转、优先级。
- `Task` — 任务数据类（id/type/payload/status/priority/retry）
- `TaskStatus` — PENDING / RUNNING / COMPLETED / FAILED / CANCELLED
- `TaskPriority` — P0 / P1 / P2 / P3

### registry.py — 任务处理器注册表
通过装饰器注册/查询/执行任务处理器。
- `@registry.register("name", description, version)` — 装饰器
- `registry.get_handler(name)` → callable
- `registry.list_handlers()` → 所有已注册处理器
- `registry` — 全局单例

### sop_engine.py — SOP 流水线引擎
多步骤工作流编排。支持步骤状态跟踪、凭证链关联、重试策略。
- `SOPEngine` — 创建/执行流水线
- `SOPPipeline` — 流水线（name/steps/credential_chain）
- `SOPStep` — 步骤（name/action/status/retry）
- `execute_pipeline(pipeline_id, initial_input)` — 异步执行

### chaos_scheduler.py — 混沌调度器
智能任务分发。根据 CPU 余量、内存余量、能力匹配度评分，选择最优 Agent。
- `ChaosScheduler` — 注册 Agent、提交动作、竞价分配
- `TokenBucket` — 令牌桶限流（consume/bid）
- `ScoredAgent` — 评分后的 Agent（score/tokens/capacity_score/capability_match）
- 评分公式：`cpu×0.3 + capability×0.5 + token×0.2`
- `submit_actions(actions)` — 批量提交
- `dispatch(handlers)` — 异步调度循环（依赖感知）

### resource_state.py — 集群状态
跟踪所有 Agent 的在线状态、资源使用率、能力标签。
- `ResourceStateService` — 注册/心跳/查询/统计
- `AgentState` — 单个 Agent（roles/skills/cpu/mem/active_tasks）
- `CapabilityVector` — 能力向量
- `capacity_score` — 动态计算（使用 per-agent max_concurrency）
- `get_cluster_summary()` — 集群概览

### atomic_action.py — 任务分解
将复合任务拆解为带依赖关系的原子动作序列。
- `TaskDecomposer` — 模式匹配分解（implement/deploy/test/research/custom）
- `ActionType` — RESEARCH / CODE / REVIEW / CLEAN / TEST / DEPLOY / NOTIFY / CUSTOM
- `AtomicAction` — 单个原子动作

### subgraph.py — 子图封装
从历史协作数据中发现高频动作组合，封装为可复用虚拟超智能体。
- `SubgraphEncapsulator` — 记录观测/发现模式/滚动统计
- `VirtualSuperAgentManager` — 管理虚拟超智能体
- `VirtualSuperAgent` — VSA（invocation_count/wasm_module/invoke）
- `CollaborationPattern` — 协作模式（频率/平均耗时/成功率/示例任务）
- `CollaborationEdge` — 协作边（频率/平均延迟/成功率）

### plugin.py — 插件管理
注册、激活、停用插件。支持三种部署模式。
- `PluginManager` — 插件生命周期管理
- `PluginManifest` — 插件清单（resource_limits/env_vars/deployment_mode）
- `CapabilityContract` — 能力契约（from_dict/to_dict）
- `PluginState` — 7 种状态：REGISTERED → LOADING → ACTIVE / DEGRADED → UNLOADING → UNLOADED / FAILED
- 部署模式：OCI 容器 / WASI 沙箱 / 本地进程

### skill_lock.py — 技能锁
检测并发执行的技能之间是否存在资源冲突。
- `LOCKSSChecker` — 注册作用域/检查冲突/解决冲突/统计
- `SkillScope` — 技能作用域（id/scopes/lock_mode/compatible_with/conflicts_with）
- `LockMode` — READ / WRITE / EXCLUSIVE
- 完整 9 种组合兼容矩阵

### skill_gnn.py — GNN 技能组合发现
技能图上的路径搜索 + 组合推荐。
- `SkillCombinatorGNN` — 技能图 + 组合发现 + 推荐
- `SkillGraph` — 邻接表图 + DFS 路径搜索 + 余弦相似度
- `CombinationPath` — 组合路径（skills/confidence/path_type/description）
- Category diversity bonus（跨类别 +0.1）
- 5 种路径分类（specialization/research_implementation/development_pipeline/cross_language/general）

### skill_kg.py — 技能知识图谱
技能间关系的图数据库存储（Neo4j 后端，缺失时降级为内存）。
- `SkillKnowledgeGraph` — 节点/关系 CRUD + 子图提取 + 反向查询 + Cypher 导出
- `add_combination_path` — 注册组合路径
- `add_overlap` — 注册作用域重叠
- `register_redundancy` — 注册冗余关系
- `get_subgraph(skill_ids)` — 提取子图
- `export_cypher()` — 完整 Cypher 导出

### worker.py — Worker 节点
从消息队列取任务、路由到 handler 执行、上报结果。
- `WorkerNode` — Worker 实例
- `TaskSubmitter` — 任务提交

### observability.py — 可观测性
OpenTelemetry 封装。无 OTel 包时自动降级为 Noop。
- `init_otel(service_name, endpoint)` — 初始化
- `get_tracer()` / `get_meter()` — 获取 tracer/meter
- `record_task_start()` / `record_task_complete()` — 任务级 Span

## 适配器 (adapters/)

| 模块 | 桥接目标 | 关键功能 |
|------|----------|----------|
| `mini_spider.py` | mini_spider v3 | Agent 注册/任务分发/状态查询 |
| `spider_max.py` | spider_max | OKR 导入/报告导出/模块注册表 |
| `spider_room.py` | spidermax_room | 工作流注册/触发/状态查询（精简版） |
| `spidermax_room.py` | MAX ROOM v2 | 工作流管理完整版（含依赖检查） |
| `spider_diary.py` | spider_diary | 报告生成/看板同步/健康检查 |

## 技能系统 (skills/)

| 模块 | 技能数 | 说明 |
|------|--------|------|
| `builtin.py` | 14 | echo/shell/python/http/file_read/file_write/research/code/review/test/clean/deploy/notify/multi_agent_index_brainstorm |
| `manifest.py` | — | 技能清单 JSON/YAML 加载、校验、自动发现 |
| `index_brainstorm.py` | 1 | 多智能体索引头脑风暴（25 个 Agent，5 层架构，3 种索引策略） |
