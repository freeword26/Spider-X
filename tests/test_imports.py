"""Test that all Spider-X modules can be imported successfully."""

import pytest
import os


def test_core_imports():
    from spider_x.core.config import SpiderXConfig, load_config
    from spider_x.core.credential_chain import CredentialChainManager
    from spider_x.core.task import Task, TaskStatus, TaskPriority
    from spider_x.core.sop_engine import SOPEngine
    from spider_x.core.resource_state import ResourceStateService, AgentStatus
    from spider_x.core.atomic_action import TaskDecomposer, ActionStatus
    from spider_x.core.chaos_scheduler import ChaosScheduler, TokenBucket
    from spider_x.core.subgraph import SubgraphEncapsulator, VirtualSuperAgentManager
    from spider_x.core.plugin import PluginManager, PluginState
    from spider_x.core.skill_lock import LOCKSSChecker, LockMode
    from spider_x.core.skill_gnn import SkillCombinatorGNN
    from spider_x.core.skill_kg import SkillKnowledgeGraph


def test_package_imports():
    import spider_x
    assert spider_x.__version__ == "2.0.0"
    assert hasattr(spider_x, "create_app")
    # 验证核心模块可通过子包导入
    from spider_x.core.credential_chain import CredentialChainManager
    from spider_x.core.sop_engine import SOPEngine
    from spider_x.core.chaos_scheduler import ChaosScheduler
    from spider_x.core.skill_lock import LOCKSSChecker
    from spider_x.core.skill_gnn import SkillCombinatorGNN
    from spider_x.adapters import MiniSpiderAdapter, SpiderMaxAdapter
    from spider_x.adapters.spider_eco_diary import SpiderEcoDiaryAdapter


def test_config_defaults():
    from spider_x.core.config import SpiderXConfig
    cfg = SpiderXConfig()
    assert cfg.api_port == 8006
    assert cfg.api_host == "0.0.0.0"
    assert cfg.log_level == "INFO"


def test_config_from_env():
    import os
    os.environ["SPIDER_ECO_API_PORT"] = "9090"
    from spider_x.core.config import load_config
    cfg = load_config(env_file="/nonexistent/.env")
    assert cfg.api_port == 9090
    del os.environ["SPIDER_ECO_API_PORT"]


def test_adapters_import():
    from spider_x.adapters import MiniSpiderAdapter, SpiderMaxAdapter
    from spider_x.adapters import SpiderRoomAdapter, SpiderDiaryAdapter


def test_skills_import():
    from spider_x.skills import SkillManifest, BUILTIN_SKILLS, register_builtin_skills
    assert len(BUILTIN_SKILLS) > 0


def test_credential_chain():
    from spider_x.core.credential_chain import CredentialChainManager
    mgr = CredentialChainManager(secret="test-secret")
    chain = mgr.create_chain("task-1", "test")
    chain.add_entry("action1", {"input": 1}, {"output": 2})
    chain.add_entry("action2", {"input": 2}, {"output": 3})
    assert chain.verify() is True
    assert len(chain.entries) == 2


def test_task_creation():
    from spider_x.core.task import Task, TaskStatus, TaskPriority
    t = Task(task_id="t1", task_type="echo", payload={"msg": "hello"})
    assert t.status == TaskStatus.PENDING
    assert t.priority == TaskPriority.P1


def test_sop_engine():
    from spider_x.core.sop_engine import SOPEngine
    engine = SOPEngine()
    pipeline = engine.create_pipeline("test", [
        {"name": "step1", "action": "echo"},
        {"name": "step2", "action": "echo"},
    ])
    assert pipeline.name == "test"
    assert len(pipeline.steps) == 2


def test_chaos_scheduler():
    from spider_x.core.chaos_scheduler import ChaosScheduler, TokenBucket
    tb = TokenBucket(rate=10, capacity=100)
    assert tb.consume("a1", 1.0) is True
    assert tb.get_tokens("a1") > 0

    cs = ChaosScheduler()
    cs.register_agent("agent-1")
    aid = cs.submit_action({"action_type": "test"})
    assert aid.startswith("action-")


def test_resource_service():
    from spider_x.core.resource_state import ResourceStateService, AgentStatus
    svc = ResourceStateService()
    state = svc.register_agent("a1", {"roles": ["researcher"]})
    assert state.agent_id == "a1"
    assert state.status == AgentStatus.IDLE
    assert "researcher" in state.capabilities.roles


def test_skill_lock():
    from spider_x.core.skill_lock import LOCKSSChecker, SkillScope, LockMode
    checker = LOCKSSChecker()
    checker.register_skill(SkillScope(skill_id="s1", scopes=[{"type": "file", "path": "/data"}], lock_mode=LockMode.READ))
    checker.register_skill(SkillScope(skill_id="s2", scopes=[{"type": "file", "path": "/data"}], lock_mode=LockMode.READ))
    ok, conflict = checker.check_compatibility("s1", "s2")
    assert ok is True


def test_subgraph():
    from spider_x.core.subgraph import SubgraphEncapsulator
    enc = SubgraphEncapsulator(min_frequency=1)
    for _ in range(3):
        enc.record_observation(["research", "code", "test"], success=True)
    patterns = enc.discover_patterns()
    assert len(patterns) >= 1


def test_plugin_manager():
    from spider_x.core.plugin import PluginManager, PluginManifest, PluginState
    mgr = PluginManager()
    manifest = PluginManifest(
        plugin_id="p1", name="Test", version="1.0.0",
        agent_type="test", entry_point="test:main", capabilities=["test"],
    )
    pid = mgr.register_plugin(manifest)
    assert pid == "p1"
    assert mgr.get_plugin(pid)["state"] == PluginState.REGISTERED


def test_task_decomposer():
    from spider_x.core.atomic_action import TaskDecomposer
    dec = TaskDecomposer()
    result = dec.decompose("实现一个HTTP服务", pattern="implement")
    assert len(result.actions) == 4
