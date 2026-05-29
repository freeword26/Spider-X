# Spider-X 蜘蛛群 — 技术白皮书

## 1. 概述

Spider-X（蜘蛛群）是Spider系列生态的**Worker智能体集群引擎**，负责任务执行、资源调度、技能编排和插件管理。它填补了Spider系列中"执行层"的空白：

- **mini_spider** 提供多Agent协作框架
- **spider_max** 提供项目管理平台
- **spider_max_room** 提供无人值守工作流
- **spider_diary** 提供运维报告引擎
- **spider-x** 提供**任务执行与集群调度引擎**

## 2. 架构设计

### 2.1 三层架构

```
┌─────────────────────────────────────────────────────────┐
│                    应用层 (Application)                   │
│  spider_max │ spider_max_room │ spider_diary │ mini_spider│
├─────────────────────────────────────────────────────────┤
│                    适配层 (Adapters)                      │
│  SpiderMaxAdapter │ SpiderRoomAdapter │ SpiderDiaryAdapter│
│  MiniSpiderAdapter                                        │
├─────────────────────────────────────────────────────────┤
│                    核心层 (Spider-X Core)                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ 凭证链   │ │ SOP引擎  │ │ 混沌调度 │ │ 技能图谱 │   │
│  │Credential│ │   SOP    │ │  Chaos   │ │  Skill   │   │
│  │  Chain   │ │  Engine  │ │Scheduler │ │  Graph   │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ 资源状态 │ │ 原子动作 │ │ 子图封装 │ │ 插件管理 │   │
│  │ Resource │ │  Atomic  │ │ Subgraph │ │  Plugin  │   │
│  │  State   │ │  Action  │ │  Agent   │ │ Manager  │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
├─────────────────────────────────────────────────────────┤
│                    基础设施层 (Infrastructure)             │
│  FastAPI │ RabbitMQ │ Redis │ Neo4j │ OpenTelemetry     │
└─────────────────────────────────────────────────────────┘
```

### 2.2 核心模块说明

#### 凭证链 (Credential Chain)
借鉴区块链的链式哈希结构，为每次任务执行生成防篡改的审计链。每个凭证条目包含：
- 输入数据的SHA-256哈希
- 输出内容的摘要
- 时间戳
- HMAC-SHA256签名
- 前一条目的哈希（链式链接）

```
Entry_0 → Entry_1 → Entry_2 → ... → Entry_N
  ↓         ↓         ↓               ↓
Hash_0    Hash_1    Hash_2          Hash_N
```

#### SOP引擎 (Standard Operation Procedure)
基于DAG（有向无环图）的流程编排引擎，支持：
- 顺序执行
- 并行执行（无依赖的步骤）
- 重试机制
- 失败传播隔离
- 执行报告自动生成

#### 混沌调度器 (Chaos Scheduler)
结合Token Bucket和竞价机制的智能调度器：
- **Token Bucket**: 控制每个Agent的任务消费速率
- **竞价机制**: Agent根据能力和负载出价，价高者得
- **能力匹配**: 基于角色和技能的向量匹配
- **负载感知**: 实时监控CPU/内存/活跃任务数

#### 技能图谱 (Skill Graph)
三层技能知识管理：
1. **SkillGraph**: 技能拓扑图，支持路径发现和相似度计算
2. **GNN Combinator**: 基于图神经网络的组合路径发现
3. **LOCKSS Checker**: 技能作用域互锁冲突检测

## 3. 数据流

```
任务提交 → 凭证链创建 → 任务分解(原子动作) → 混沌调度 → Agent执行
    ↓                                                    ↓
    └──────────── 凭证链记录每一步 ←──────────────────────┘
                         ↓
                  执行报告生成
                         ↓
                  技能图谱更新
```

## 4. API设计

### 4.1 RESTful API
所有API遵循RESTful设计，版本化路径：
- `/api/v1/*` — 凭证链、SOP
- `/api/v2/*` — Agent管理、任务分解、调度、子图、插件
- `/api/v3/*` — 技能图谱、GNN、知识图谱

### 4.2 消息队列
通过RabbitMQ实现异步任务处理：
- `task_queue`: 持久化任务队列
- `result_exchange`: 结果发布（Topic模式）

## 5. 安全设计

- **API Key认证**: 通过`X-API-Key`请求头
- **凭证链签名**: HMAC-SHA256防篡改
- **技能互锁**: LOCKSS算法防止冲突技能并发执行
- **插件隔离**: OCI/WASI沙箱部署

## 6. 扩展性

### 6.1 插件系统
支持三种部署模式：
- **OCI**: 标准容器部署
- **WASI**: WebAssembly沙箱部署
- **本地**: 本地进程部署

### 6.2 技能系统
- 内置13种技能（echo/shell/python/http/file/research/code/review/test/clean/deploy/notify）
- 支持通过清单文件扩展
- 技能清单支持JSON/YAML格式
- 自动发现技能目录

### 6.3 Spider适配器
通过适配器模式与所有Spider系列项目集成：
- 懒加载导入（无硬依赖）
- 双向数据格式转换
- 独立降级运行

## 7. 性能考量

- **无状态设计**: 所有状态可外置到Redis/数据库
- **异步IO**: 基于asyncio的全异步架构
- **Token Bucket**: 防止Agent过载
- **TTL过期**: 自动清理离线Agent
- **Noop降级**: 可选依赖（OTel/Neo4j）缺失时自动降级
