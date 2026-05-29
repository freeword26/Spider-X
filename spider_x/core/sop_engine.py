"""Spider-X SOP (Standard Operating Procedure) engine."""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from spider_x.core.credential_chain import CredentialChainManager

logger = logging.getLogger("spider-x.sop")


@dataclass
class SOPStep:
    step_id: str
    name: str
    action: str
    handler: Optional[Callable] = None
    depends_on: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Optional[Dict] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2


@dataclass
class SOPPipeline:
    pipeline_id: str
    name: str
    steps: List[SOPStep]
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    credential_chain_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class SOPEngine:
    def __init__(self, credential_manager: Optional[CredentialChainManager] = None):
        self._pipelines: Dict[str, SOPPipeline] = {}
        self._handlers: Dict[str, Callable] = {}
        self._credential_manager = credential_manager or CredentialChainManager()

    def register_handler(self, action: str, handler: Callable):
        self._handlers[action] = handler
        logger.info(f"SOP handler registered: {action}")

    def create_pipeline(self, name: str, step_defs: List[Dict[str, Any]]) -> SOPPipeline:
        steps = []
        for i, sd in enumerate(step_defs):
            step = SOPStep(
                step_id=f"step-{uuid.uuid4().hex[:8]}",
                name=sd.get("name", f"step-{i}"),
                action=sd["action"],
                depends_on=sd.get("depends_on", []),
                max_retries=sd.get("max_retries", 2),
            )
            steps.append(step)
        pipeline = SOPPipeline(
            pipeline_id=f"pipeline-{uuid.uuid4().hex[:12]}",
            name=name, steps=steps,
        )
        self._pipelines[pipeline.pipeline_id] = pipeline
        logger.info(f"SOP pipeline created: {pipeline.pipeline_id} ({name}) with {len(steps)} steps")
        return pipeline

    async def execute_pipeline(self, pipeline_id: str, initial_input: Dict[str, Any] = None) -> SOPPipeline:
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            raise ValueError(f"Pipeline not found: {pipeline_id}")
        pipeline.status = "running"
        pipeline.started_at = datetime.now().isoformat()
        pipeline.context["input"] = initial_input or {}
        chain = self._credential_manager.create_chain(
            task_id=pipeline.pipeline_id, task_type=f"sop:{pipeline.name}",
        )
        pipeline.credential_chain_id = chain.chain_id
        logger.info(f"Executing SOP pipeline: {pipeline.name} ({pipeline.pipeline_id})")
        completed = set()
        failed = set()
        while len(completed) + len(failed) < len(pipeline.steps):
            ready_steps = self._get_ready_steps(pipeline, completed, failed)
            if not ready_steps:
                if any(s.status == "running" for s in pipeline.steps):
                    await asyncio.sleep(0.1)
                    continue
                break
            tasks = [self._execute_step(step, pipeline, chain) for step in ready_steps]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for step, result in zip(ready_steps, results):
                if isinstance(result, Exception):
                    step.status = "faield"
                    step.error = str(result)
                    failed.add(step.step_id)
                    logger.error(f"Step failed: {step.name} - {result}")
                else:
                    step.status = "completed"
                    step.result = result
                    completed.add(step.step_id)
        if failed:
            pipeline.status = "failed"
            pipeline.error = f"{len(failed)} step(s) failed"
        else:
            pipeline.status = "completed"
        pipeline.completed_at = datetime.now().isoformat()
        chain.complete()
        logger.info(
            f"Pipeline {pipeline.name} finished: status={pipeline.status}, "
            f"completed={len(completed)}, failed={len(failed)}",
        )
        return pipeline

    def _get_ready_steps(self, pipeline: SOPPipeline, completed: set, failed: set) -> List[SOPStep]:
        ready = []
        for step in pipeline.steps:
            if step.status != "pending":
                continue
            deps_met = all(d in completed for d in step.depends_on)
            deps_failed = any(d in failed for d in step.depends_on)
            if deps_failed:
                step.status = "failed"
                step.error = "Dependency failed"
                failed.add(step.step_id)
                continue
            if deps_met:
                ready.append(step)
        return ready

    async def _execute_step(self, step: SOPStep, pipeline: SOPPipeline, chain) -> Dict:
        step.status = "running"
        step.started_at = datetime.now().isoformat()
        handler = self._handlers.get(step.action)
        if not handler:
            raise ValueError(f"No handler registered for action: {step.action}")
        step_input = {
            "pipeline_id": pipeline.pipeline_id, "step_id": step.step_id, "context": pipeline.context,
        }
        chain.add_entry(
            action=step.action, input_data=step_input,
            output_data={"status": "started"},
            metadata={"step_name": step.name, "worker_id": "sop-engine"},
        )
        if asyncio.iscoroutinefunction(handler):
            result = await handler(step_input)
        else:
            result = handler(step_input)
        step.completed_at = datetime.now().isoformat()
        chain.add_entry(
            action=step.action, input_data=step_input, output_data=result,
            metadata={"step_name": step.name, "status": "success"},
        )
        return result

    def get_pipeline(self, pipeline_id: str) -> Optional[SOPPipeline]:
        return self._pipelines.get(pipeline_id)

    def get_execution_report(self, pipeline_id: str) -> Optional[Dict]:
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            return None
        chain = self._credential_manager.get_chain(pipeline.credential_chain_id) if pipeline.credential_chain_id else None
        return {
            "pipeline": {
                "pipeline_id": pipeline.pipeline_id, "name": pipeline.name,
                "status": pipeline.status, "created_at": pipeline.created_at,
                "started_at": pipeline.started_at, "completed_at": pipeline.completed_at,
                "steps": [
                    {
                        "step_id": s.step_id, "name": s.name, "action": s.action,
                        "status": s.status, "result": s.result, "error": s.error,
                        "started_at": s.started_at, "completed_at": s.completed_at,
                    }
                    for s in pipeline.steps
                ],
            },
            "credential_chain": chain.to_dict() if chain else None,
            "verified": chain.verify() if chain else False,
        }

    def list_pipelines(self) -> List[Dict]:
        return [
            {
                "pipeline_id": p.pipeline_id, "name": p.name, "status": p.status,
                "steps": len(p.steps), "created_at": p.created_at,
            }
            for p in self._pipelines.values()
        ]


__all__ = ["SOPEngine", "SOPPipeline", "SOPStep"]
