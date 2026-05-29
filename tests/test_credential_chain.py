import asyncio
import pytest
from spider_x.core.credential_chain import CredentialChainManager, CredentialChain


@pytest.fixture
def manager():
    return CredentialChainManager(secret="test-secret")


@pytest.fixture
def chain(manager):
    return manager.create_chain("task-001", "echo")


class TestCredentialChain:
    def test_create_chain(self, chain):
        assert chain.chain_id.startswith("chain-")
        assert chain.task_id == "task-001"
        assert chain.task_type == "echo"
        assert chain.version == "1.0"
        assert len(chain.entries) == 0

    def test_add_entry(self, chain):
        entry = chain.add_entry("action1", {"data": "input"}, {"data": "output"})
        assert entry.step_index == 0
        assert entry.action == "action1"
        assert len(chain.entries) == 1

    def test_chain_linking(self, chain):
        e1 = chain.add_entry("a1", {"i": 1}, {"o": 1})
        e2 = chain.add_entry("a2", {"i": 2}, {"o": 2})
        assert e1.prev_hash is None
        assert e2.prev_hash == e1.compute_hash()

    def test_verify_valid_chain(self, chain):
        chain.add_entry("a1", {"i": 1}, {"o": 1})
        chain.add_entry("a2", {"i": 2}, {"o": 2})
        assert chain.verify() is True

    def test_verify_tampered_chain(self, chain):
        chain.add_entry("a1", {"i": 1}, {"o": 1})
        chain.add_entry("a2", {"i": 2}, {"o": 2})
        chain.entries[0].action = "tampered"
        assert chain.verify() is False

    def test_chain_hash(self, chain):
        chain.add_entry("a1", {"i": 1}, {"o": 1})
        h1 = chain.chain_hash
        chain.add_entry("a2", {"i": 2}, {"o": 2})
        h2 = chain.chain_hash
        assert h1 != h2

    def test_complete(self, chain):
        chain.complete()
        assert chain.completed_at is not None

    def test_summary(self, chain):
        chain.add_entry("a", {"i": 1}, {"o": 1})
        s = chain.summary()
        assert s["total_steps"] == 1
        assert s["verified"] is True


class TestCredentialChainManager:
    def test_create_and_get(self, manager):
        chain = manager.create_chain("t1", "echo")
        assert manager.get_chain(chain.chain_id) == chain

    def test_get_by_task(self, manager):
        chain = manager.create_chain("t2", "shell")
        found = manager.get_chain_by_task("t2")
        assert found == chain

    def test_list_chains(self, manager):
        manager.create_chain("t3", "echo")
        manager.create_chain("t4", "shell")
        chains = manager.list_chains()
        assert len(chains) == 2

    def test_verify_chain(self, manager):
        chain = manager.create_chain("t5", "echo")
        chain.add_entry("a", {"i": 1}, {"o": 1})
        assert manager.verify_chain(chain.chain_id) is True

    def test_verify_nonexistent(self, manager):
        assert manager.verify_chain("nonexistent") is False

