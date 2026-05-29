# Spider-X 快速入门指南

## 5分钟上手

### 1. 安装

```bash
cd Spider-X
pip install -e .
```

### 2. 启动服务

```bash
# 方式一：命令行
spider-x serve --port 8006

# 方式二：Python
python -c "from spider_x.cli import main; main()" serve
```

### 3. 验证

```bash
curl http://localhost:8006/health
```

## 基础用法

### 提交任务

```bash
curl -X POST http://localhost:8006/tasks/submit \
  -H "Content-Type: application/json" \
  -d '{"task_type": "echo", "payload": {"message": "Hello Spider-X!"}}'
```

### Python API

```python
import spider_x

# 创建应用
app = spider_x.create_app()

# 使用TestClient测试
from starlette.testclient import TestClient
client = TestClient(app)

# 提交任务
resp = client.post("/tasks/submit", json={
    "task_type": "echo",
    "payload": {"message": "Hello"}
})
print(resp.json())

# 健康检查
resp = client.get("/health")
print(resp.json())
```

### 注册Agent

```bash
curl -X POST http://localhost:8006/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "worker-01",
    "capabilities": {
      "roles": ["researcher", "coder"],
      "skills": ["python", "search"],
      "max_concurrency": 5
    }
  }'
```

### 创建SOP流水线

```bash
curl -X POST http://localhost:8006/api/v1/sop/pipelines \
  -H "Content-Type: application/json" \
  -d '{
    "name": "开发流水线",
    "steps": [
      {"name": "需求分析", "action": "research"},
      {"name": "代码实现", "action": "code"},
      {"name": "代码审查", "action": "review"},
      {"name": "测试验证", "action": "test"}
    ]
  }'
```

## 与Spider系列集成

### mini_spider集成

```python
from spider_x.adapters import MiniSpiderAdapter

# 从现有mini_spider编排器创建
adapter = MiniSpiderAdapter.from_mini_spider(orchestrator)

# 注册Agent
adapter.register_agents([
    {"agent_id": "researcher-1", "roles": ["researcher"]},
    {"agent_id": "coder-1", "roles": ["coder"]},
])

# 转换任务格式
spider_x_task = MiniSpiderAdapter.to_spider_x_task(mini_spider_task)
```

### spider_max集成

```python
from spider_x.adapters import SpiderMaxAdapter

adapter = SpiderMaxAdapter.from_spider_max(spider_max_app)
projects = adapter.sync_projects()
```

## 配置

创建 `.env` 文件：

```env
SPIDER_X_ENV=development
SPIDER_X_DEBUG=true
SPIDER_X_API_PORT=8006
SPIDER_X_RABBITMQ_HOST=localhost
SPIDER_X_RABBITMQ_PORT=5672
SPIDER_X_API_KEY=my-secret-key
```

## 下一步

- 阅读 [技术白皮书](WHITEPAPER.md) 了解架构设计
- 查看 [API文档](http://localhost:8006/docs) (Swagger UI)
- 探索 [技能系统](../spider_x/skills/) 扩展能力
