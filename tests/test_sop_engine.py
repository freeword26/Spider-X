import asyncio
import pytest
from spider_x.core.credential_chain import CredentialChainManager
from spider_x.core.sop_engine import SOPEngine, SOPStatus


@pytest.fixture
def engine():
    mgr = CredentialChainManager(secret="test-secret")
    eng = SOPEngine(credential_manager=mgr)
    eng.register_handler("step_a", lambda ctx: {"result": "a"})
    eng.register_handler("step_b", lambda ctx: {"result": "b"})
    eng.register_handler("step_c", lambda ctx: {"result": "c"})
    return eng


class TestSOPEngine:
    def test_create_pipeline(self, engine):
        pipeline = engine.create_pipeline("test", [
            {"name": "s1", "action": "step_a"},
            {"name": "s2", "action": "step_b"},
        ])
        assert pipeline.name == "test"
        assert len(pipeline.steps) == 2

    @pytest.mark.asyncio
    async def test_execute_linear_pipeline(self, engine):
        pipeline = engine.create_pipeline("linear", [
            {"name": "s1", "action": "step_a"},
            {"name": "s2", "action": "step_b", "depends_on": []},
        ])
        result = await engine.execute_pipeline(pipeline.pipeline_id)
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_execution_report(self, engine):
        pipeline = engine.create_pipeline("report_test", [
            {"name": "s1", "action": "step_a"},
        ])
        await engine.execute_pipeline(pipeline.pipeline_id)
        report = engine.get_execution_report(pipeline.pipeline_id)
        assert report is not None
        assert report["pipeline"]["status"] == "completed"
        assert report["verified"] is True
        assert report["credential_chain"] is not None

    @pytest.mark.asyncio
    async def test_pipeline_failure(self, engine):
        engine.register_handler("fail_step", lambda ctx: (_ for _ in ()).throw(ValueError("fail")))
        pipeline = engine.create_pipeline("fail", [
            {"name": "s1", "action": "step_a"},
            {"name": "s2", "action": "fail_step"},
        ])
        result = await engine.execute_pipeline(pipeline.pipeline_id)
        assert result.status == "failed"

    def test_list_pipelines(self, engine):
        engine.create_pipeline("p1", [{"name": "s1", "action": "step_a"}])
        engine.create_pipeline("p2", [{"name": "s1", "action": "step_a"}])
        pipelines = engine.list_pipelines()
        assert len(pipelines) == 2

    @pytest.mark.asyncio
    async def test_concurrent_independent_steps(self, engine):
        pipeline = engine.create_pipeline("concurrent", [
            {"name": "s1", "action": "step_a"},
            {"name": "s2", "action": "step_b"},
            {"name": "s3", "action": "step_c"},
        ])
        result = await engine.execute_pipeline(pipeline.pipeline_id)
        assert result.status == "completed"
        for step in result.steps:
            assert step.status == "completed"

