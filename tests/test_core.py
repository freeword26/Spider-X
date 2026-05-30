import asyncio
import pytest
from spider_x.core.agent_registry import (
    AgentRegistry, AgentDescriptor, PermissionLevel, CollaborationMode,
    get_registry, find_agents_by_skill, find_agents_by_keyword,
)
from spider_x.core.meta_agent import (
    MetaAgent, MetaTask, TaskStage,
    TaskUnderstandingEngine, TaskDecomposer,
    TaskDispatcher, ResultAggregator,
)
from spider_x.core.watchdog import (
    WatchdogService, WatchdogConfig, HealthStatus, RecoveryAction,
)


# ── Agent Registry Tests ──

class TestAgentDescriptor:
    def test_create_descriptor(self):
        desc = AgentDescriptor(
            agent_id="test-agent",
            name="测试Agent",
            permission_level=PermissionLevel.L3_EXECUTE,
            description="测试用Agent",
            skills=["python", "research"],
            keywords=["测试", "开发"],
        )
        assert desc.agent_id == "test-agent"
        assert desc.permission_level == PermissionLevel.L3_EXECUTE

    def test_to_cline_tool(self):
        desc = AgentDescriptor(
            agent_id="test-agent",
            name="测试Agent",
            permission_level=PermissionLevel.L2_READ_WRITE,
            description="测试",
            skills=["code"],
            keywords=["测试"],
        )
        tool = desc.to_cline_tool()
        assert tool["name"] == "agent_test_agent"
        assert "action" in tool["parameters"]["properties"]
        assert "input" in tool["parameters"]["properties"]


class TestAgentRegistry:
    def test_get_agent(self):
        reg = AgentRegistry(router_url="http://localhost:9999")
        agent = reg.get_agent("system-manager")
        assert agent is not None
        assert agent.permission_level == PermissionLevel.L4_ADMIN

    def test_list_all_agents(self):
        reg = AgentRegistry(router_url="http://localhost:9999")
        agents = reg.list_agents()
        assert len(agents) == 25

    def test_list_by_permission_level(self):
        reg = AgentRegistry(router_url="http://localhost:9999")
        l4_agents = reg.list_agents(permission_level=4)
        # permission_level ≤ 4 包含 L4+L3+L2+L1，这里只验证包含 L4
        assert len(l4_agents) == 25  # 全部 Agent 权限都 ≤ 4

    def test_find_agents_by_keyword(self):
        reg = AgentRegistry(router_url="http://localhost:9999")
        results = reg.find_agents_by_keyword("安全")
        assert len(results) >= 1

    def test_find_agents_by_skill(self):
        reg = AgentRegistry(router_url="http://localhost:9999")
        results = reg.find_agents_by_skill("python")
        assert len(results) >= 1

    def test_call_agent_local_mode(self):
        reg = AgentRegistry(router_url="http://localhost:9999")
        result = reg.call_agent("system-manager", "analyze", "测试输入")
        assert result["status"] == "completed"
        assert result["agent_id"] == "system-manager"

    def test_route_request(self):
        reg = AgentRegistry(router_url="http://localhost:9999")
        result = reg.route_request("帮我分析系统架构")
        assert result["success"] is True
        assert result["agent_id"] is not None

    def test_route_request_default(self):
        reg = AgentRegistry(router_url="http://localhost:9999")
        result = reg.route_request("xyzabc123无意义输入")
        assert result["agent_id"] == "system-manager"

    def test_execute_workflow(self):
        reg = AgentRegistry(router_url="http://localhost:9999")
        result = reg.execute_workflow("sop", [
            {"agent_id": "system-manager", "action": "analyze"},
            {"agent_id": "tech-expert", "action": "review"},
        ])
        assert result["total_tasks"] == 2
        assert result["completed"] == 2

    def test_get_cline_tools(self):
        reg = AgentRegistry(router_url="http://localhost:9999")
        tools = reg.get_cline_tools()
        assert len(tools) == 25
        assert all("name" in t for t in tools)
        assert all("description" in t for t in tools)

    def test_get_status_summary(self):
        reg = AgentRegistry(router_url="http://localhost:9999")
        summary = reg.get_status_summary()
        assert summary["total_agents"] == 25
        assert "L4_ADMIN" in summary["levels"]


# ── Meta-Agent Tests ──

class TestTaskUnderstandingEngine:
    def test_understand_research(self):
        engine = TaskUnderstandingEngine()
        result = engine.understand("帮我调研最新的AI技术趋势")
        assert result["primary_type"] == "research"

    def test_understand_code(self):
        engine = TaskUnderstandingEngine()
        result = engine.understand("开发一个用户登录API")
        assert result["primary_type"] == "code"

    def test_understand_deploy(self):
        engine = TaskUnderstandingEngine()
        result = engine.understand("部署应用到生产环境")
        assert result["primary_type"] == "deploy"

    def test_complexity_scoring(self):
        engine = TaskUnderstandingEngine()
        simple = engine.understand("打印hello")
        long_text = ("开发一个完整的电商系统，包括用户管理、订单处理、支付集成、库存管理、物流跟踪、"
                      "客服系统、数据分析、推荐引擎，并且要部署到Kubernetes集群，配置CI/CD流水线，"
                      "还要做数据迁移和性能调优，同时需要实现多租户架构和分布式缓存，"
                      "并且要做安全审计和压力测试，以及实现国际化支持")
        complex_task = engine.understand(long_text)
        assert complex_task["complexity"] > simple["complexity"]
        assert complex_task["requires_decomposition"] is True

    def test_complexity_low(self):
        engine = TaskUnderstandingEngine()
        result = engine.understand("打印hello")
        assert result["complexity"] < 0.5


class TestTaskDecomposer:
    def test_decompose_research(self):
        decomposer = TaskDecomposer()
        result = decomposer.decompose({"primary_type": "research", "requires_decomposition": True})
        assert len(result) >= 3

    def test_decompose_code(self):
        decomposer = TaskDecomposer()
        result = decomposer.decompose({"primary_type": "code", "requires_decomposition": True})
        assert len(result) == 4

    def test_decompose_simple(self):
        decomposer = TaskDecomposer()
        result = decomposer.decompose({"primary_type": "research", "requires_decomposition": False})
        assert len(result) == 1


class TestResultAggregator:
    def test_all_completed(self):
        agg = ResultAggregator()
        result = agg.aggregate([
            {"status": "completed", "output": "ok1"},
            {"status": "completed", "output": "ok2"},
        ])
        assert result["status"] == "completed"
        assert result["completed"] == 2

    def test_partial(self):
        agg = ResultAggregator()
        result = agg.aggregate([
            {"status": "completed", "output": "ok"},
            {"status": "failed", "output": "fail"},
        ])
        assert result["status"] == "partial"

    def test_empty(self):
        agg = ResultAggregator()
        result = agg.aggregate([])
        assert result["status"] == "empty"


class TestMetaAgent:
    @pytest.mark.asyncio
    async def test_submit_simple_task(self):
        agent = MetaAgent()
        result = await agent.submit_task("帮我调研Python异步编程")
        assert result.task_id is not None
        assert result.stage == TaskStage.COMPLETE
        assert len(result.subtasks) > 0

    @pytest.mark.asyncio
    async def test_submit_code_task(self):
        agent = MetaAgent()
        result = await agent.submit_task("实现一个REST API")
        assert result.stage == TaskStage.COMPLETE
        assert any(st.action == "code" for st in result.subtasks)

    def test_get_task_status(self):
        agent = MetaAgent()
        agent._active_tasks["t1"] = MetaTask(task_id="t1", raw_input="test", task_type="research")
        status = agent.get_task_status("t1")
        assert status is not None
        assert status["task_id"] == "t1"


# ── Watchdog Tests ──

class TestWatchdogService:
    def test_register_and_heartbeat(self):
        w = WatchdogService()
        w.register_agent("agent-1")
        w.record_heartbeat("agent-1", cpu=50, memory=60, active_tasks=2)
        report = w.get_health_report()
        assert report["total_monitored"] == 1
        assert report["records"]["agent-1"]["cpu"] == 50.0

    def test_task_failure_tracking(self):
        w = WatchdogService()
        w.register_agent("agent-1")
        w.record_task_failure("agent-1")
        w.record_task_failure("agent-1")
        report = w.get_health_report()
        assert report["records"]["agent-1"]["failed_tasks"] == 2

    def test_task_success_resets_failures(self):
        w = WatchdogService()
        w.register_agent("agent-1")
        w.record_task_failure("agent-1")
        w.record_task_success("agent-1")
        assert w._health_records["agent-1"].consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_auto_restart_recovery(self):
        w = WatchdogService(config=WatchdogConfig(
            heartbeat_timeout=30, check_interval=5,
            auto_restart=True, max_consecutive_failures=2,
        ))
        w.register_agent("agent-1")
        w._health_records["agent-1"].consecutive_failures = 999
        w._health_records["agent-1"].last_heartbeat = 0
        await w._run_health_check()
        assert len(w._recovery_events) >= 1

    @pytest.mark.asyncio
    async def test_recovery_hook_called(self):
        w = WatchdogService(config=WatchdogConfig(auto_restart=True, auto_reassign=False))
        w.register_agent("agent-1")
        called = []
        w.on_recovery(RecoveryAction.RESTART_AGENT, lambda aid, r: called.append(aid))
        w._health_records["agent-1"].consecutive_failures = 999
        w._health_records["agent-1"].last_heartbeat = 0
        await w._run_health_check()
        assert len(called) >= 1

    @pytest.mark.asyncio
    async def test_alert_callback(self):
        w = WatchdogService(config=WatchdogConfig(auto_restart=False, auto_reassign=False))
        w.register_agent("agent-1")
        alerts = []
        w.on_alert(lambda aid, status, reason: alerts.append((aid, status)))
        w._health_records["agent-1"].consecutive_failures = 999
        w._health_records["agent-1"].last_heartbeat = 0
        await w._run_health_check()
        assert len(alerts) >= 1
