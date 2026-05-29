# 🕷️ Spider-X 蜘蛛群

**Worker智能体集群引擎** — 兼容全部Spider系列

[![Version](https://img.shields.io/badge/version-1.0.0-blue)](.)
[![Python](https://img.shields.io/badge/python-≥3.10-green)](.)
[![License](https://img.shields.io/badge/license-MIT-yellow)](.)

---

## 概述

Spider-X（蜘蛛群）是一个高性能的Worker智能体集群引擎，提供任务调度、SOP编排、技能图谱、插件管理等核心能力。设计为Spider系列生态的执行层，与所有Spider项目无缝集成。

```
                    spider.py (统一网关)
                   /    |     |      \       \
                  /     |     |       \       \
          spider_max    |     |        \     spider-x ◄── 蜘蛛群
         (大蜘蛛v3)     |     |         \   (Worker集群)
         Full-stack PM  |     |          \
                        |   小蜘蛛日历v1   mini_spider
                        |   (Spider Diary)  (小蜘蛛空间v3)
                        |
              大蜘蛛空间_V2.0
             (Spider MAX Room)
```

## 快速安装

```bash
# 从源码安装
cd Spider-X
pip install -e .

# 安装全部可选依赖
pip install -e ".[all]"

# 开发模式
pip install -e ".[dev]"
```

## 快速开始

### 作为库使用

```python
import spider_x

# 创建应用
app = spider_x.create_app()

# 或使用自定义配置
from spider_x.core.config import SpiderXConfig
config = SpiderXConfig(api={"port": 8080})
app = spider_x.create_app(config=config)
```

### 作为服务运行

```bash
# 启动API服务器
spider-x serve --port 8006

# 启动Worker节点
spider-x worker --rabbitmq-url amqp://guest:guest@localhost:5672

# 查看版本
spider-x version
```

### Docker运行

```bash
docker build -t spider-x .
docker run -p 8006:8006 spider-x
```

## 兼容Spider系列

| 系统 | 版本 | 中文说明 | 集成方式 |
|------|------|----------|----------|
| mini_spider | v3.0 | 小蜘蛛空间 - 多Agent框架 | `MiniSpiderAdapter` |
| spider_max | v3.0 | 大蜘蛛 - 全栈项目管理平台 | `SpiderMaxAdapter` |
| spider_max_room | v2.0 | 大蜘蛛空间 - 无人值守工作流 | `SpiderRoomAdapter` |
| spider_diary | v1.0 | 小蜘蛛日历 - 运维报告引擎 | `SpiderDiaryAdapter` |
| **spider-x** | **v1.0** | **蜘蛛群 - Worker智能体集群引擎** | **核心引擎** |

## 核心特性

### 🔗 凭证链 (Credential Chain)
- HMAC-SHA256签名防篡改
- 链式哈希链接（类似区块链结构）
- 支持完整性校验
- 每次SOP执行自动生成完整审计链

### 📋 SOP引擎
- 基于依赖图的顺序/并行执行
- 支持重试机制
- 失败传播与隔离
- 执行报告自动生成

### 🔄 混沌调度器 (Chaos Scheduler)
- Token Bucket流量控制
- 竞价机制（可选）
- 能力向量匹配
- 负载感知分配

### 🧠 技能图谱
- **GNN组合发现**: 基于图神经网络的技能组合路径发现
- **LOCKSS互锁检查**: 技能作用域冲突检测与解决
- **Neo4j知识图谱**: 支持持久化的技能关系图谱

### 📦 插件系统
- OCI容器部署
- WASI沙箱部署
- 本地进程部署
- 能力契约注册

### 📊 资源状态管理
- Agent注册与心跳
- 实时资源监控（CPU/内存/负载）
- 集群概览
- TTL过期自动下线

### 📡 可观测性
- OpenTelemetry集成（可选）
- 分布式链路追踪
- 指标收集
- Noop降级模式

## API端点

### 核心
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 服务信息 |
| GET | `/health` | 健康检查 |
| GET | `/handlers` | 列出任务处理器 |

### 任务管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/tasks/submit` | 提交任务 |
| GET | `/tasks/{id}` | 查询任务 |
| GET | `/tasks` | 列出任务 |

### 凭证链 (v1)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/report/latest` | 最新执行报告 |
| GET | `/api/v1/credentials/chains` | 凭证链列表 |
| GET | `/api/v1/credentials/chain/{id}` | 凭证链详情 |

### SOP流水线 (v1)
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/sop/pipelines` | 创建流水线 |
| POST | `/api/v1/sop/execute/{id}` | 执行流水线 |
| GET | `/api/v1/sop/pipelines` | 流水线列表 |

### Agent管理 (v2)
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v2/agents/register` | 注册Agent |
| DELETE | `/api/v2/agents/{id}` | 注销Agent |
| POST | `/api/v2/agents/{id}/heartbeat` | 心跳/状态更新 |
| GET | `/api/v2/agents` | Agent列表 |
| GET | `/api/v2/agents/available` | 可用Agent |
| GET | `/api/v2/cluster/summary` | 集群概览 |

### 技能图谱 (v3)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v3/gnn/discover` | GNN组合发现 |
| GET | `/api/v3/gnn/recommend` | 技能推荐 |
| POST | `/api/v3/skills/check` | 冲突检测 |

## 配置

通过环境变量或 `.env` 文件配置：

```env
# 基础
SPIDER_X_ENV=development
SPIDER_X_DEBUG=true
SPIDER_X_LOG_LEVEL=INFO

# API
SPIDER_X_API_HOST=0.0.0.0
SPIDER_X_API_PORT=8006
SPIDER_X_API_KEY=your-secret-key

# RabbitMQ
SPIDER_X_RABBITMQ_HOST=localhost
SPIDER_X_RABBITMQ_PORT=5672
SPIDER_X_RABBITMQ_USER=guest
SPIDER_X_RABBITMQ_PASSWORD=guest

# Neo4j
SPIDER_X_NEO4J_URI=bolt://localhost:7687
SPIDER_X_NEO4J_USER=neo4j
SPIDER_X_NEO4J_PASSWORD=password

# OpenTelemetry
SPIDER_X_OTEL_SERVICE_NAME=spider-x
SPIDER_X_OTEL_ENDPOINT=http://otel-collector:4318

# 安全
SPIDER_X_CREDIFICATE_SECRET=your-hmac-secret
```

## 架构

```
spider_x/
├── core/                    # 核心引擎
│   ├── app.py              # FastAPI应用工厂
│   ├── config.py           # 配置管理
│   ├── task.py             # 任务定义与注册表
│   ├── worker.py           # Worker节点与任务提交
│   ├── credential_chain.py # 凭证链
│   ├── sop_engine.py       # SOP流水线引擎
│   ├── observability.py    # OpenTelemetry集成
│   ├── resource_state.py   # Agent资源状态
│   ├── atomic_action.py    # 任务分解
│   ├── chaos_scheduler.py  # 混沌调度器
│   ├── subgraph.py         # 子图封装/VSA
│   ├── plugin.py           # 插件管理
│   ├── skill_lock.py       # LOCKSS互锁检查
│   ├── skill_gnn.py        # GNN技能组合
│   └── skill_kg.py         # 技能知识图谱
├── adapters/               # Spider系列适配器
│   ├── mini_spider.py      # 小蜘蛛空间适配器
│   ├── spider_max.py       # 大蜘蛛适配器
│   ├── spider_room.py      # 大蜘蛛空间适配器
│   └── spider_diary.py     # 小蜘蛛日历适配器
├── skills/                 # 技能系统
│   ├── manifest.py         # 技能清单
│   └── builtin.py          # 内置技能
└── cli.py                  # 命令行接口
```

## 开发

```bash
# 运行测试
pytest tests/ -v

# 代码检查
ruff check spider_x/

# 类型检查
mypy spider_x/
```

## 许可证

MIT License
