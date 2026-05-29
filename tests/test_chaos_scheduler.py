import pytest
from spider_x.core.chaos_scheduler import ChaosScheduler, TokenBucket


class TestTokenBucket:
    def test_consume(self):
        tb = TokenBucket(rate=0, capacity=10)
        assert tb.consume("a1", 1.0) is True
        assert abs(tb.get_tokens("a1") - 9.0) < 0.01

    def test_consume_insufficient(self):
        tb = TokenBucket(rate=0, capacity=1)
        tb.consume("a1", 1.0)
        assert tb.consume("a1", 1.0) is False

    def test_refill(self):
        tb = TokenBucket(rate=100, capacity=10)
        tb.consume("a1", 5.0)
        import time; time.sleep(0.1)
        assert tb.get_tokens("a1") > 5.0

    def test_bid(self):
        tb = TokenBucket(rate=10, capacity=10)
        assert tb.bid("a1", offer=2.0, cost=1.0) is True

    def test_bid_insufficient(self):
        tb = TokenBucket(rate=0, capacity=0)
        assert tb.bid("a1", offer=1.0) is False


class MockAgentState:
    def __init__(self, status="idle"):
        self.status = status
        self.capabilities = type("C", (), {"roles": [], "skills": ()})()
        self.resources = type("R", (), {"cpu_percent": 30, "memory_percent": 40, "active_tasks": 0, "max_concurrency": 5})()


class TestChaosScheduler:
    def test_register_agent(self):
        cs = ChaosScheduler()
        cs.register_agent("a1")
        assert "a1" in cs._agent_states

    def test_submit_action(self):
        cs = ChaosScheduler()
        aid = cs.submit_action({"action_type": "test", "payload": {}})
        assert aid.startswith("action-")

    def test_submit_actions(self):
        cs = ChaosScheduler()
        ids = cs.submit_actions([
            {"action_type": "t1"},
            {"action_type": "t2"},
        ])
        assert len(ids) == 2

    def test_assign_action(self):
        cs = ChaosScheduler()
        cs.register_agent("a1", MockAgentState())
        aid = cs.submit_action({"action_type": "test", "required_roles": []})
        assigned = cs._broadcast_and_assign({"action_id": aid, "action_type": "test", "required_roles": [], "depends_on": []})
        assert assigned == "a1"

    def test_complete_action(self):
        cs = ChaosScheduler()
        aid = cs.submit_action({"action_type": "test"})
        cs.complete_action(aid, {"ok": True})
        assert aid in cs._completed

    def test_fail_action(self):
        cs = ChaosScheduler()
        aid = cs.submit_action({"action_type": "test"})
        cs.fail_action(aid, "error")
        assert aid in cs._failed

    def test_status(self):
        cs = ChaosScheduler()
        cs.submit_action({"action_type": "test"})
        status = cs.get_status()
        assert status["total_actions"] == 1
        assert status["pending"] == 1

    def test_no_available_agents(self):
        cs = ChaosScheduler()
        aid = cs.submit_action({"action_type": "test"})
        assigned = cs._broadcast_and_assign({"action_id": aid, "action_type": "test", "required_roles": [], "depends_on": []})
        assert assigned is None

    def test_deregister_agent(self):
        cs = ChaosScheduler()
        cs.register_agent("a1")
        cs.deregister_agent("a1")
        assert "a1" not in cs._agent_states

    def test_bidding_mode(self):
        cs = ChaosScheduler(enable_bidding=True)
        cs.register_agent("a1", MockAgentState())
        aid = cs.submit_action({"action_type": "test", "required_roles": []})
        assigned = cs._broadcast_and_assign({"action_id": aid, "action_type": "test", "required_roles": [], "depends_on": []})
        assert assigned is not None

