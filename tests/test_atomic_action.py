import pytest
from spider_x.core.atomic_action import TaskDecomposer, ActionStatus


@pytest.fixture
def decomposer():
    return TaskDecomposer()


class TestTaskDecomposer:
    def test_decompose_research(self, decomposer):
        result = decomposer.decompose("调研Rust异步运行时", pattern="research")
        assert result.task_id.startswith("task-")
        assert len(result.actions) > 0
        assert all(a.status == ActionStatus.PENDING for a in result.actions)

    def test_decompose_implement(self, decomposer):
        result = decomposer.decompose("实现一个HTTP服务", pattern="implement")
        assert len(result.actions) == 4
        action_types = [a.action_type for a in result.actions]
        assert "code" in action_types
        assert "review" in action_types

    def test_decompose_full_cycle(self, decomposer):
        result = decomposer.decompose("实现并部署用户系统", pattern="full_cycle")
        assert len(result.actions) == 6

    def test_auto_detect_research(self, decomposer):
        result = decomposer.decompose("搜索最新AI论文")
        assert len(result.actions) > 0

    def test_auto_detect_implement(self, decomposer):
        result = decomposer.decompose("开发一个API接口")
        action_types = [a.action_type for a in result.actions]
        assert "code" in action_types

    def test_dependency_graph(self, decomposer):
        result = decomposer.decompose("test", pattern="research")
        for action in result.actions:
            if action.depends_on:
                for dep in action.depends_on:
                    assert dep in result.dependency_graph

    def test_custom_pattern(self, decomposer):
        decomposer.register_pattern("custom", [
            {"name": "step1", "action_type": "custom", "required_roles": ["tester"]},
            {"name": "step2", "action_type": "custom"},
        ])
        result = decomposer.decompose("custom task", pattern="custom")
        assert len(result.actions) == 2

    def test_decompose_custom(self, decomposer):
        result = decomposer.decompose_custom("task-x", "desc", [
            {"name": "s1", "action_type": "a"},
            {"name": "s2", "action_type": "b"},
        ])
        assert len(result.actions) == 2
        assert result.task_id == "task-x"

    def test_action_fingerprint(self, decomposer):
        result = decomposer.decompose("test", pattern="research")
        fp = result.actions[0].fingerprint
        assert len(fp) == 12

    def test_get_ready_actions(self, decomposer):
        result = decomposer.decompose("test", pattern="research")
        ready = result.get_ready_actions(set())
        assert len(ready) >= 1
        assert all(not a.depends_on for a in ready)

