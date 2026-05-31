import json
import os
import tempfile
from pathlib import Path

import pytest

from spider_x.core.offline_skills import (
    OfflineSkillPack, SkillManifest, SandboxError, _safe_eval,
)


def _write_skill(path: Path, name: str, skill_type: str, rules: list, desc: str = ""):
    data = {"name": name, "version": "1.0", "type": skill_type,
            "description": desc, "rules": rules}
    import hashlib
    content = json.dumps(data, sort_keys=True).encode()
    data["signature"] = hashlib.sha256(content).hexdigest()[:16]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Sandbox Tests ──

class TestSafeEval:
    def test_basic_math(self):
        assert _safe_eval("1 + 2", {}) == 3

    def test_with_context(self):
        assert _safe_eval("x + y", {"x": 1, "y": 2}) == 3

    def test_comparison(self):
        assert _safe_eval("a > b", {"a": 5, "b": 3}) is True

    def test_disallowed_call(self):
        with pytest.raises(SandboxError):
            _safe_eval("__import__('os')", {})

    def test_disallowed_attribute(self):
        with pytest.raises(SandboxError):
            _safe_eval("().__class__", {})


# ── OfflineSkillPack Tests ──

class TestOfflineSkillPack:
    def test_init_creates_dir(self, tmp_path):
        pack = OfflineSkillPack(str(tmp_path / "skills"))
        assert (tmp_path / "skills").exists()

    def test_load_decision_tree_skill(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        rules = [
            {"condition": "score > 90", "action": "excellent"},
            {"condition": "score > 60", "action": "pass"},
            {"condition": "default", "action": "fail"},
        ]
        _write_skill(skill_dir / "grader.skill", "grader", "decision_tree", rules)
        pack = OfflineSkillPack(str(skill_dir))
        assert "grader" in pack.skills

    def test_execute_decision_tree(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        rules = [
            {"condition": "revenue_growth > 0.1", "action": "bullish"},
            {"condition": "revenue_growth > 0", "action": "neutral"},
            {"condition": "default", "action": "bearish"},
        ]
        _write_skill(skill_dir / "finance.skill", "finance", "decision_tree", rules)
        pack = OfflineSkillPack(str(skill_dir))
        result = pack.execute("finance", {"revenue_growth": 0.15})
        assert result["result"] == "bullish"
        assert result.get("_elapsed_ms", 0) > 0

    def test_decision_tree_default(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        rules = [
            {"condition": "score > 90", "action": "excellent"},
            {"condition": "default", "action": "fail"},
        ]
        _write_skill(skill_dir / "grader.skill", "grader", "decision_tree", rules)
        pack = OfflineSkillPack(str(skill_dir))
        result = pack.execute("grader", {"score": 30})
        assert result["result"] == "fail"

    def test_load_fsm_skill(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        states = {"start": {}, "processing": {}, "done": {}, "error": {}}
        transitions = [
            {"from": "start", "to": "processing", "on": "begin"},
            {"from": "processing", "to": "done", "on": "complete"},
            {"from": "processing", "to": "error", "on": "fail"},
        ]
        data = {"name": "workflow", "version": "1.0", "type": "finite_state_machine",
                "states": states, "transitions": transitions}
        import hashlib
        content = json.dumps(data, sort_keys=True).encode()
        data["signature"] = hashlib.sha256(content).hexdigest()[:16]
        (skill_dir / "workflow.skill").write_text(json.dumps(data), encoding="utf-8")

        pack = OfflineSkillPack(str(skill_dir))
        assert "workflow" in pack.skills

    def test_fsm_transitions(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        states = {"start": {}, "processing": {}, "done": {}}
        transitions = [
            {"from": "start", "to": "processing", "on": "begin"},
            {"from": "processing", "to": "done", "on": "complete"},
        ]
        data = {"name": "wf", "version": "1.0", "type": "finite_state_machine",
                "states": states, "transitions": transitions}
        import hashlib
        content = json.dumps(data, sort_keys=True).encode()
        data["signature"] = hashlib.sha256(content).hexdigest()[:16]
        (skill_dir / "wf.skill").write_text(json.dumps(data), encoding="utf-8")

        pack = OfflineSkillPack(str(skill_dir))
        result = pack.execute("wf", {"_event": "begin"})
        assert result["result"] == "processing"
        assert result["previous"] == "start"

    def test_fsm_no_match(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        transitions = [{"from": "start", "to": "done", "on": "finish"}]
        data = {"name": "wf", "version": "1.0", "type": "finite_state_machine",
                "states": {"start": {}, "done": {}}, "transitions": transitions}
        import hashlib
        content = json.dumps(data, sort_keys=True).encode()
        data["signature"] = hashlib.sha256(content).hexdigest()[:16]
        (skill_dir / "wf.skill").write_text(json.dumps(data), encoding="utf-8")
        pack = OfflineSkillPack(str(skill_dir))
        result = pack.execute("wf", {"_event": "unknown"})
        assert result["result"] == "start"  # 保持在当前状态

    def test_load_rule_engine_skill(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        rules = [
            {"name": "urgent", "pattern": "urgent|critical|asap", "action": "priority_high", "weight": 1.0},
            {"name": "code", "pattern": "code|debug|refactor", "action": "route_dev", "weight": 0.8},
        ]
        _write_skill(skill_dir / "router.skill", "router", "rule_engine", rules)
        pack = OfflineSkillPack(str(skill_dir))
        assert "router" in pack.skills

    def test_rule_engine_matching(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        rules = [
            {"name": "urgent", "pattern": "urgent|critical", "action": "priority_high", "weight": 1.0},
            {"name": "code", "pattern": "code|debug", "action": "route_dev", "weight": 0.8},
        ]
        _write_skill(skill_dir / "router.skill", "router", "rule_engine", rules)
        pack = OfflineSkillPack(str(skill_dir))
        result = pack.execute("router", {"text": "This is a critical bug"})
        assert result["result"] == "priority_high"
        assert len(result["matches"]) >= 1

    def test_rule_engine_no_match(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        rules = [
            {"name": "code", "pattern": "code|debug", "action": "route_dev", "weight": 0.8},
        ]
        _write_skill(skill_dir / "router.skill", "router", "rule_engine", rules)
        pack = OfflineSkillPack(str(skill_dir))
        result = pack.execute("router", {"text": "hello world"})
        assert result["result"] == "no_match"

    def test_execute_all(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        rules1 = [{"condition": "score > 50", "action": "pass"}, {"condition": "default", "action": "fail"}]
        rules2 = [{"name": "code", "pattern": "code", "action": "dev", "weight": 1.0}]
        _write_skill(skill_dir / "grader.skill", "grader", "decision_tree", rules1)
        _write_skill(skill_dir / "router.skill", "router", "rule_engine", rules2)
        pack = OfflineSkillPack(str(skill_dir))
        results = pack.execute_all({"score": 80, "text": "write code"})
        assert "grader" in results
        assert "router" in results

    def test_create_skill(self, tmp_path):
        pack = OfflineSkillPack(str(tmp_path / "skills"))
        path = pack.create_skill("my_skill", "decision_tree",
                                  [{"condition": "x > 0", "action": "pos"},
                                   {"condition": "default", "action": "neg"}],
                                  "测试技能")
        assert path.exists()
        assert "my_skill" in pack.skills

    def test_verify_skill(self, tmp_path):
        pack = OfflineSkillPack(str(tmp_path / "skills"))
        pack.create_skill("test", "decision_tree",
                          [{"condition": "x > 0", "action": "pos"},
                           {"condition": "default", "action": "neg"}])
        assert pack.verify_skill("test") is True

    def test_verify_tampered_skill(self, tmp_path):
        pack = OfflineSkillPack(str(tmp_path / "skills"))
        pack.create_skill("test", "decision_tree",
                          [{"condition": "x > 0", "action": "pos"}])
        assert pack.verify_skill("test") is True
        # 篡改文件但不更新签名
        skill_file = tmp_path / "skills" / "test.skill"
        data = json.loads(skill_file.read_text(encoding="utf-8"))
        data["rules"][0]["action"] = "tampered"
        skill_file.write_text(json.dumps(data), encoding="utf-8")
        # 重新加载后验证应失败
        pack.reload()
        assert pack.verify_skill("test") is False

    def test_delete_skill(self, tmp_path):
        pack = OfflineSkillPack(str(tmp_path / "skills"))
        pack.create_skill("temp", "decision_tree",
                          [{"condition": "x > 0", "action": "pos"}])
        assert "temp" in pack.skills
        pack.delete_skill("temp")
        assert "temp" not in pack.skills

    def test_get_manifest(self, tmp_path):
        pack = OfflineSkillPack(str(tmp_path / "skills"))
        pack.create_skill("info", "decision_tree",
                          [{"condition": "x > 0", "action": "pos"}],
                          "A test skill")
        m = pack.get_manifest("info")
        assert m is not None
        assert m.name == "info"
        assert m.description == "A test skill"

    def test_get_stats(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        rules = [{"condition": "x > 0", "action": "pos"}, {"condition": "default", "action": "neg"}]
        _write_skill(skill_dir / "counter.skill", "counter", "decision_tree", rules)
        pack = OfflineSkillPack(str(skill_dir))
        pack.execute("counter", {"x": 5})
        pack.execute("counter", {"x": -1})
        stats = pack.get_stats()
        assert stats["total_calls"] == 2
        assert stats["total_skills"] == 1

    def test_benchmark(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        rules = [{"condition": "x > 0", "action": "pos"}, {"condition": "default", "action": "neg"}]
        _write_skill(skill_dir / "bench.skill", "bench", "decision_tree", rules)
        pack = OfflineSkillPack(str(skill_dir))
        result = pack.benchmark("bench", {"x": 5}, iterations=50)
        assert result["avg_ms"] < 100  # 应该远低于100ms
        assert result["p95_ms"] < 200
        assert result["iterations"] == 50

    def test_performance_benchmarks_data(self):
        data = OfflineSkillPack.performance_benchmarks()
        assert "scenarios" in data
        assert "financial_report_analysis" in data["scenarios"]
        assert "key_insights" in data
        assert "skill_pack_sizes" in data

    def test_missing_skill_returns_error(self, tmp_path):
        pack = OfflineSkillPack(str(tmp_path / "skills"))
        result = pack.execute("nonexistent", {})
        assert result["status"] == "error"

    def test_skill_names(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        _write_skill(skill_dir / "a.skill", "a", "decision_tree",
                     [{"condition": "default", "action": "ok"}])
        _write_skill(skill_dir / "b.skill", "b", "rule_engine",
                     [{"name": "x", "pattern": "x", "action": "y", "weight": 1.0}])
        pack = OfflineSkillPack(str(skill_dir))
        names = pack.skill_names
        assert "a" in names
        assert "b" in names
