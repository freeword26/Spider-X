import asyncio
import pytest
from spider_x.core.agent_registry import (
    AgentRegistry, AgentDescriptor, PermissionLevel, CollaborationMode,
    get_registry, find_agents_by_skill, find_agents_by_keyword,
)
from spider_x.core.meta_agent import MetaTask, TaskStage, ResultAggregator
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

class TestResultAggregator:
    def test_all_completed(self):
        agg = ResultAggregator()
        result = agg.aggregate([
            {"status": "ok", "response": "ok1"},
            {"status": "ok", "response": "ok2"},
        ])
        assert result["status"] == "completed"
        assert result["completed"] == 2

    def test_partial(self):
        agg = ResultAggregator()
        result = agg.aggregate([
            {"status": "ok", "response": "ok"},
            {"status": "error", "response": "fail"},
        ])
        assert result["status"] == "partial"

    def test_empty(self):
        agg = ResultAggregator()
        result = agg.aggregate([])
        assert result["status"] == "empty"

    def test_all_completed(self):
        agg = ResultAggregator()
        result = agg.aggregate([
            {"status": "ok", "response": "ok1"},
            {"status": "ok", "response": "ok2"},
        ])
        assert result["status"] == "completed"
        assert result["completed"] == 2

    def test_partial(self):
        agg = ResultAggregator()
        result = agg.aggregate([
            {"status": "ok", "response": "ok"},
            {"status": "error", "response": "fail"},
        ])
        assert result["status"] == "partial"


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
