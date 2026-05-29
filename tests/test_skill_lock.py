import pytest
from spider_x.core.skill_lock import LOCKSSChecker, SkillScope, LockMode


@pytest.fixture
def checker():
    return LOCKSSChecker()


class TestLOCKSSChecker:
    def test_register_skill(self, checker):
        skill = SkillScope(skill_id="s1", scopes=[{"type": "file", "path": "/data"}], lock_mode=LockMode.READ)
        checker.register_skill(skill)
        assert "s1" in checker._skills

    def test_compatible_read_read(self, checker):
        checker.register_skill(SkillScope(skill_id="r1", scopes=[{"type": "file", "path": "/data"}], lock_mode=LockMode.READ))
        checker.register_skill(SkillScope(skill_id="r2", scopes=[{"type": "file", "path": "/data"}], lock_mode=LockMode.READ))
        ok, conflict = checker.check_compatibility("r1", "r2")
        assert ok is True

    def test_incompatible_write_write(self, checker):
        checker.register_skill(SkillScope(skill_id="w1", scopes=[{"type": "file", "path": "/data"}], lock_mode=LockMode.WRITE))
        checker.register_skill(SkillScope(skill_id="w2", scopes=[{"type": "file", "path": "/data"}], lock_mode=LockMode.WRITE))
        ok, conflict = checker.check_compatibility("w1", "w2")
        assert ok is False
        assert conflict.conflict_type == "lock_mode"

    def test_scope_overlap_conflict(self, checker):
        checker.register_skill(SkillScope(skill_id="o1", scopes=[{"type": "file", "path": "/data"}], lock_mode=LockMode.WRITE))
        checker.register_skill(SkillScope(skill_id="o2", scopes=[{"type": "file", "path": "/data"}], lock_mode=LockMode.WRITE))
        ok, conflict = checker.check_compatibility("o1", "o2")
        assert ok is False

    def test_declared_conflict(self, checker):
        checker.register_skill(SkillScope(skill_id="c1", scopes=[], conflicts_with=["c2"]))
        checker.register_skill(SkillScope(skill_id="c2", scopes=[]))
        ok, conflict = checker.check_compatibility("c1", "c2")
        assert ok is False
        assert conflict.conflict_type == "declared"

    def test_declared_compatible(self, checker):
        checker.register_skill(SkillScope(skill_id="cp1", scopes=[], compatible_with=["cp2"]))
        checker.register_skill(SkillScope(skill_id="cp2", scopes=[]))
        ok, conflict = checker.check_compatibility("cp1", "cp2")
        assert ok is True

    def test_check_combination(self, checker):
        checker.register_skill(SkillScope(skill_id="x1", scopes=[{"type": "file", "path": "/a"}], lock_mode=LockMode.READ))
        checker.register_skill(SkillScope(skill_id="x2", scopes=[{"type": "file", "path": "/b"}], lock_mode=LockMode.READ))
        checker.register_skill(SkillScope(skill_id="x3", scopes=[{"type": "file", "path": "/c"}], lock_mode=LockMode.READ))
        ok, conflicts = checker.check_combination(["x1", "x2", "x3"])
        assert ok is True
        assert len(conflicts) == 0

    def test_check_combination_with_conflict(self, checker):
        checker.register_skill(SkillScope(skill_id="y1", scopes=[{"type": "file", "path": "/same"}], lock_mode=LockMode.WRITE))
        checker.register_skill(SkillScope(skill_id="y2", scopes=[{"type": "file", "path": "/same"}], lock_mode=LockMode.WRITE))
        ok, conflicts = checker.check_combination(["y1", "y2"])
        assert ok is False
        assert len(conflicts) > 0

    def test_resolve_conflicts(self, checker):
        checker.register_skill(SkillScope(skill_id="z1", scopes=[{"type": "file", "path": "/s"}], lock_mode=LockMode.WRITE))
        checker.register_skill(SkillScope(skill_id="z2", scopes=[{"type": "file", "path": "/s"}], lock_mode=LockMode.WRITE))
        _, conflicts = checker.check_combination(["z1", "z2"])
        resolutions = checker.resolve_conflicts(conflicts)
        assert len(resolutions) > 0

    def test_stats(self, checker):
        checker.register_skill(SkillScope(skill_id="st1", scopes=[], lock_mode=LockMode.READ))
        checker.register_skill(SkillScope(skill_id="st2", scopes=[], lock_mode=LockMode.READ))
        stats = checker.get_stats()
        assert stats["total_skills"] == 2
        assert stats["max_pairs"] == 1

    def test_path_overlap_wildcard(self, checker):
        checker.register_skill(SkillScope(skill_id="wc1", scopes=[{"type": "file", "path": "/data/*"}], lock_mode=LockMode.WRITE))
        checker.register_skill(SkillScope(skill_id="wc2", scopes=[{"type": "file", "path": "/data/file.txt"}], lock_mode=LockMode.WRITE))
        ok, conflict = checker.check_compatibility("wc1", "wc2")
        assert ok is False

    def test_unknown_skill_compatible(self, checker):
        checker.register_skill(SkillScope(skill_id="u1", scopes=[]))
        ok, conflict = checker.check_compatibility("u1", "nonexistent")
        assert ok is True

