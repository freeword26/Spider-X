import asyncio
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from spider_x.core.role_engine import (
    RoleEngine, AIRouter, Role, AIType,
    CodeLlamaClient, QwenClient, ClaudeProxy, OpenAIProxy,
)


def _write_roles(path: Path, roles: dict):
    path.write_text(yaml.dump({"roles": roles}), encoding="utf-8")


# ── Role / AIType Tests ──

class TestAIType:
    def test_enum_values(self):
        assert AIType.LOCAL == "local"
        assert AIType.CLOUD == "cloud"
        assert AIType.BUILTIN == "builtin"


class TestRole:
    def test_priority_rank(self):
        r = Role(name="t", type=AIType.LOCAL, provider="ollama", model="m", agent_id="a", priority="high")
        assert r.priority_rank == 1
        r2 = Role(name="t", type=AIType.LOCAL, provider="ollama", model="m", agent_id="a", priority="low")
        assert r2.priority_rank == 3

    def test_type_checks(self):
        local = Role(name="l", type=AIType.LOCAL, provider="ollama", model="m", agent_id="a")
        cloud = Role(name="c", type=AIType.CLOUD, provider="openai", model="gpt-4", agent_id="a")
        builtin = Role(name="b", type=AIType.BUILTIN, provider="builtin", model="s", agent_id="a")
        assert local.is_local and not local.is_cloud
        assert cloud.is_cloud and not cloud.is_local
        assert not builtin.is_local and not builtin.is_cloud


# ── AIRouter Tests ──

class TestAIRouter:
    def test_load_and_match(self, tmp_path):
        f = tmp_path / "roles.yaml"
        _write_roles(f, {
            "code_engineer": {"type": "local", "provider": "ollama", "model": "codellama:7b",
                              "agent_id": "dev", "capabilities": ["code_generation", "debugging"],
                              "priority": "high", "cost_factor": 0.0},
            "researcher": {"type": "cloud", "provider": "anthropic", "model": "claude-3-opus",
                           "agent_id": "analyst", "capabilities": ["web_research", "analysis"],
                           "priority": "high", "cost_factor": 1.0},
        })
        router = AIRouter(str(f))
        assert len(router.roles) == 2

    def test_match_code_task(self, tmp_path):
        f = tmp_path / "roles.yaml"
        _write_roles(f, {
            "code_engineer": {"type": "local", "provider": "ollama", "model": "codellama:7b",
                              "agent_id": "dev", "capabilities": ["code_generation", "debugging"],
                              "priority": "high", "cost_factor": 0.0},
            "researcher": {"type": "cloud", "provider": "anthropic", "model": "claude-3-opus",
                           "agent_id": "analyst", "capabilities": ["web_research"],
                              "priority": "high", "cost_factor": 1.0},
        })
        router = AIRouter(str(f))
        matched = router.match_role("帮我写一个Python排序算法")
        assert len(matched) >= 1
        assert matched[0].name == "code_engineer"

    def test_match_research_task(self, tmp_path):
        f = tmp_path / "roles.yaml"
        _write_roles(f, {
            "code_engineer": {"type": "local", "provider": "ollama", "model": "codellama:7b",
                              "agent_id": "dev", "capabilities": ["code_generation"],
                              "priority": "high", "cost_factor": 0.0},
            "researcher": {"type": "cloud", "provider": "anthropic", "model": "claude-3-opus",
                           "agent_id": "analyst", "capabilities": ["web_research", "analysis"],
                           "priority": "high", "cost_factor": 1.0},
        })
        router = AIRouter(str(f))
        matched = router.match_role("帮我研究搜索最新的AI技术趋势")
        names = [r.name for r in matched]
        assert "researcher" in names

    def test_priority_sorting(self, tmp_path):
        f = tmp_path / "roles.yaml"
        _write_roles(f, {
            "low_cost": {"type": "cloud", "provider": "openai", "model": "gpt-4",
                         "agent_id": "a1", "capabilities": ["content_creation"],
                         "priority": "low", "cost_factor": 0.3},
            "high_priority": {"type": "cloud", "provider": "anthropic", "model": "claude-3-opus",
                              "agent_id": "a2", "capabilities": ["content_creation"],
                              "priority": "high", "cost_factor": 1.0},
        })
        router = AIRouter(str(f))
        matched = router.match_role("帮我写一篇营销文案")
        assert len(matched) >= 1
        assert matched[0].name == "high_priority"

    def test_no_match_returns_empty(self, tmp_path):
        f = tmp_path / "roles.yaml"
        _write_roles(f, {
            "code_engineer": {"type": "local", "provider": "ollama", "model": "codellama:7b",
                              "agent_id": "dev", "capabilities": ["code_generation"],
                              "priority": "high", "cost_factor": 0.0},
        })
        router = AIRouter(str(f))
        matched = router.match_role("今天天气怎么样")
        assert matched == []

    def test_builtin_excluded_from_match(self, tmp_path):
        f = tmp_path / "roles.yaml"
        _write_roles(f, {
            "orch": {"type": "builtin", "provider": "builtin", "model": "scheduler",
                     "agent_id": "system-manager", "capabilities": ["task_decomposition"],
                     "priority": "critical", "cost_factor": 0.0},
        })
        router = AIRouter(str(f))
        matched = router.match_role("分解任务")
        assert matched == []

    def test_reload(self, tmp_path):
        f = tmp_path / "roles.yaml"
        _write_roles(f, {"r1": {"type": "local", "provider": "ollama", "model": "m1", "agent_id": "a1",
                                  "capabilities": ["code"], "priority": "high", "cost_factor": 0.0}})
        router = AIRouter(str(f))
        assert len(router.roles) == 1
        _write_roles(f, {
            "r1": {"type": "local", "provider": "ollama", "model": "m1", "agent_id": "a1",
                   "capabilities": ["code"], "priority": "high", "cost_factor": 0.0},
            "r2": {"type": "cloud", "provider": "openai", "model": "gpt-4", "agent_id": "a2",
                   "capabilities": ["research"], "priority": "medium", "cost_factor": 0.8},
        })
        router.reload()
        assert len(router.roles) == 2


# ── RoleEngine Tests ──

class TestRoleEngine:
    def _make_engine(self, tmp_path, roles=None):
        f = tmp_path / "roles.yaml"
        default_roles = {
            "code_engineer": {"type": "local", "provider": "ollama", "model": "codellama:7b",
                              "agent_id": "dev", "capabilities": ["code_generation", "debugging"],
                              "priority": "high", "cost_factor": 0.0},
            "data_analyst": {"type": "local", "provider": "ollama", "model": "qwen:14b",
                             "agent_id": "data-scientist", "capabilities": ["data_analysis", "visualization"],
                             "priority": "medium", "cost_factor": 0.0},
            "research_assistant": {"type": "cloud", "provider": "anthropic", "model": "claude-3-opus",
                                   "agent_id": "analyst", "capabilities": ["web_research", "analysis"],
                                   "priority": "high", "cost_factor": 1.0},
            "creative_writer": {"type": "cloud", "provider": "openai", "model": "gpt-4-turbo",
                                "agent_id": "humanities-scholar", "capabilities": ["content_creation", "copywriting"],
                                "priority": "medium", "cost_factor": 0.8},
            "orchestrator": {"type": "builtin", "provider": "builtin", "model": "dag_scheduler",
                             "agent_id": "system-manager", "capabilities": ["task_decomposition"],
                             "priority": "critical", "cost_factor": 0.0},
        }
        _write_roles(f, roles or default_roles)
        return RoleEngine(str(f))

    def test_load(self, tmp_path):
        eng = self._make_engine(tmp_path)
        assert len(eng.list_roles()) == 5

    def test_get_role(self, tmp_path):
        eng = self._make_engine(tmp_path)
        r = eng.get_role("code_engineer")
        assert r is not None
        assert r.model == "codellama:7b"
        assert r.is_local

    def test_list_by_type(self, tmp_path):
        eng = self._make_engine(tmp_path)
        assert len(eng.list_roles("local")) == 2
        assert len(eng.list_roles("cloud")) == 2

    def test_find_by_capability(self, tmp_path):
        eng = self._make_engine(tmp_path)
        results = eng.find_by_capability("code_generation")
        assert len(results) == 1
        assert results[0].name == "code_engineer"

    def test_get_status(self, tmp_path):
        eng = self._make_engine(tmp_path)
        status = eng.get_status()
        assert status["total_roles"] == 5
        assert status["local_count"] == 2
        assert status["cloud_count"] == 2
        assert status["builtin_count"] == 1

    @pytest.mark.asyncio
    async def test_execute_builtin(self, tmp_path):
        eng = self._make_engine(tmp_path)
        result = await eng.execute("orchestrator", "test prompt")
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_execute_local_connection_error(self, tmp_path):
        eng = self._make_engine(tmp_path)
        eng._ollama_host = "http://localhost:19999"
        result = await eng.execute("code_engineer", "write a function")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_execute_cloud_no_key(self, tmp_path):
        eng = self._make_engine(tmp_path)
        # 没有 API key 时返回提示信息而非抛异常
        result = await eng.execute("research_assistant", "analyze trends")
        assert result["status"] == "ok"
        assert "not set" in result.get("response", "")

    @pytest.mark.asyncio
    async def test_execute_task_auto_route(self, tmp_path):
        eng = self._make_engine(tmp_path)
        result = await eng.execute_task("帮我写一个Python Flask API")
        assert "primary_result" in result
        assert "sources" in result

    @pytest.mark.asyncio
    async def test_execute_task_no_match(self, tmp_path):
        eng = self._make_engine(tmp_path)
        result = await eng.execute_task("今天天气怎么样xyz123")
        assert result.get("status") == "error"

    @pytest.mark.asyncio
    async def test_execute_task_max_parallel(self, tmp_path):
        eng = self._make_engine(tmp_path)
        result = await eng.execute_task("分析数据并生成报告", max_parallel=2)
        assert len(result.get("sources", [])) <= 2
        assert "primary_result" in result

    def test_reload(self, tmp_path):
        eng = self._make_engine(tmp_path)
        assert len(eng.list_roles()) == 5
        # 修改 roles.yaml
        _write_roles(tmp_path / "roles.yaml", {
            "new_role": {"type": "local", "provider": "ollama", "model": "llama3:8b",
                         "agent_id": "new", "capabilities": ["test"],
                         "priority": "low", "cost_factor": 0.0},
        })
        eng.load()
        assert len(eng.list_roles()) == 1
        assert eng.get_role("new_role") is not None


# ── Client Tests (connection error handling) ──

class TestLocalClients:
    @pytest.mark.asyncio
    async def test_codellama_connection_error(self):
        client = CodeLlamaClient("http://localhost:19999")
        with pytest.raises(Exception):
            await client.generate("test")

    @pytest.mark.asyncio
    async def test_qwen_connection_error(self):
        client = QwenClient("http://localhost:19999")
        with pytest.raises(Exception):
            await client.generate("test")


class TestCloudProxies:
    def test_claude_no_key(self):
        proxy = ClaudeProxy()
        proxy.api_key = ""
        result = asyncio.run(proxy.call("claude-3-opus", "test"))
        assert "not set" in result

    def test_openai_no_key(self):
        proxy = OpenAIProxy()
        proxy.api_key = ""
        result = asyncio.run(proxy.call("gpt-4", "test"))
        assert "not set" in result
