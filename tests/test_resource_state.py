import pytest
from spider_x.core.resource_state import ResourceStateService, AgentStatus, CapabilityVector, ResourceState


@pytest.fixture
def svc():
    return ResourceStateService()


class TestResourceStateService:
    def test_register_agent(self, svc):
        state = svc.register_agent("agent-1", {"roles": ["researcher"], "skills": ["search"]})
        assert state.agent_id == "agent-1"
        assert "researcher" in state.capabilities.roles

    def test_get_state(self, svc):
        svc.register_agent("agent-2")
        assert svc.get_state("agent-2") is not None
        assert svc.get_state("nonexistent") is None

    def test_update_state(self, svc):
        svc.register_agent("agent-3")
        svc.update_state("agent-3", {"cpu_percent": 42.0, "status": "busy"})
        s = svc.get_state("agent-3")
        assert s.resources.cpu_percent == 42.0
        assert s.status == "busy"

    def test_get_available_agents(self, svc):
        svc.register_agent("a1", {"roles": ["researcher"]})
        svc.register_agent("a2", {"roles": ["coder"]})
        svc.update_state("a2", {"status": "offline"})
        available = svc.get_available_agents()
        assert len(available) == 1
        assert available[0].agent_id == "a1"

    def test_get_available_by_role(self, svc):
        svc.register_agent("r1", {"roles": ["researcher"]})
        svc.register_agent("c1", {"roles": ["coder"]})
        researchers = svc.get_available_agents(required_role="researcher")
        assert len(researchers) == 1
        assert researchers[0].agent_id == "r1"

    def test_get_least_loaded(self, svc):
        svc.register_agent("l1", {"roles": ["researcher"]})
        svc.register_agent("l2", {"roles": ["researcher"]})
        svc.update_state("l1", {"active_tasks": 3})
        svc.update_state("l2", {"active_tasks": 1})
        best = svc.get_least_loaded(required_role="researcher")
        assert best.agent_id == "l2"

    def test_deregister(self, svc):
        svc.register_agent("d1")
        svc.deregister_agent("d1")
        s = svc.get_state("d1")
        assert s.status == AgentStatus.OFFLINE

    def test_cluster_summary(self, svc):
        svc.register_agent("s1", {"roles": ["researcher"], "skills": ["search"]})
        svc.register_agent("s2", {"roles": ["coder"], "skills": ["python"]})
        summary = svc.get_cluster_summary()
        assert summary["total_agents"] == 2
        assert "researcher" in summary["available_roles"]
        assert "python" in summary["available_skills"]

    def test_heartbeat(self, svc):
        svc.register_agent("h1")
        import time; time.sleep(0.01)
        svc.heartbeat("h1")
        s = svc.get_state("h1")
        assert s is not None

    def test_expired_agent(self, svc):
        state = svc.register_agent("e1")
        state.ttl_seconds = 0
        import time; time.sleep(0.05)
        s = svc.get_state("e1")
        assert s.status == AgentStatus.OFFLINE

