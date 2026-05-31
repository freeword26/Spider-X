#!/bin/bash
# start_ai_system.sh — Spider-X 多Agent协同系统一键启动
set -e

echo "🕷️ Spider-X 多Agent协同系统启动中..."
echo "========================================"

# 1. 启动 Docker 容器
echo ""
echo "📦 [1/5] 启动Docker容器..."
docker-compose down -v --remove-orphans 2>/dev/null || true
docker-compose up -d --build

# 2. 等待服务就绪
echo ""
echo "⏳ [2/5] 等待服务就绪 (15s)..."
sleep 15

# 3. 验证服务状态
echo ""
echo "✅ [3/5] 服务状态验证..."
docker-compose ps

# 4. 检查 API 健康
echo ""
echo "🏥 [4/5] API健康检查..."
for i in $(seq 1 5); do
    if curl -sf http://localhost:8006/health > /dev/null 2>&1; then
        echo "   ✅ Spider-X API 正常"
        break
    fi
    if [ $i -eq 5 ]; then
        echo "   ⚠️ API 未就绪，请检查日志: docker-compose logs worker-api"
    fi
    sleep 3
done

# 5. 启动交互模式
echo ""
echo "🚀 [5/5] 系统就绪！"
echo ""
echo "========================================"
echo "  API 文档:   http://localhost:8006/docs"
echo "  角色列表:   http://localhost:8006/api/v4/roles"
echo "  路由状态:   http://localhost:8006/api/v4/roles/status"
echo "  健康检查:   http://localhost:8006/health"
echo "========================================"
echo ""
echo "交互模式启动 (输入任务，自动分配AI角色)"
echo ""

cd "$(dirname "$0")"
python router.py --config roles.yaml --interactive
