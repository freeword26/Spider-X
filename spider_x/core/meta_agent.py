from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("spider_x.meta_agent")


class TaskStage(str, Enum):
    PARSE = "parse"
    DECOMPOSE = "decompose"
    DISPATCH = "dispatch"
    MONITOR = "monitor"
    AGGREGATE = "aggregate"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class SubTask:
    subtask_id: str
    parent_task_id: str
    agent_id: str
    action: str
    input_data: Dict[str, Any]
    status: str = "pending"
    result: Optional[Dict] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


@dataclass
class MetaTask:
    task_id: str
    raw_input: str
    task_type: str
    priority: str = "P1"
    max_retries: int = 3
    stage: TaskStage = TaskStage.PARSE
    subtasks: List[SubTask] = field(default_factory=list)
    results: List[Dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "priority": self.priority,
            "stage": self.stage.value,
            "subtask_count": len(self.subtasks),
            "completed_subtasks": sum(1 for s in self.subtasks if s.status == "completed"),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class TaskUnderstandingEngine:
    def __init__(self):
        self._intent_patterns: Dict[str, List[str]] = {
            "research": ["调研", "研究", "分析", "搜索", "查找", "了解", "research", "analyze", "search"],
            "code": ["编码", "开发", "实现", "写代码", "编程", "code", "develop", "implement", "build"],
            "review": ["审查", "评审", "检查", "review", "audit", "check", "inspect"],
            "deploy": ["部署", "发布", "上线", "deploy", "release", "publish"],
            "test": ["测试", "验证", "test", "verify", "validate"],
            "clean": ["清理", "整理", "clean", "organize", "tidy"],
            "data": ["数据", "统计", "分析", "data", "statistics", "metrics"],
            "notify": ["通知", "告警", "notify", "alert", "message"],
        }

    def understand(self, raw_input: str) -> Dict[str, Any]:
        raw_lower = raw_input.lower()
        matched_types = []
        for task_type, patterns in self._intent_patterns.items():
            if any(p.lower() in raw_lower for p in patterns):
                matched_types.append(task_type)
        if not matched_types:
            matched_types = ["research"]
        complexity = self._assess_complexity(raw_input)
        return {
            "task_types": matched_types,
            "primary_type": matched_types[0],
            "complexity": complexity,
            "requires_decomposition": complexity > 0.5,
            "raw_input": raw_input,
        }

    def _assess_complexity(self, text: str) -> float:
        factors = [
            len(text) > 100,
            len(text) > 300,
            any(kw in text for kw in ["并且", "然后", "接着", "同时"]),
            any(kw in text for kw in ["和", "与", "以及"]),
            text.count("。") + text.count(".") + text.count("；") > 2,
        ]
        return sum(factors) / len(factors)


class TaskDecomposer:
    def __init__(self):
        self._dag_templates: Dict[str, List[Dict]] = {
            "research": [
                {"name": "信息收集", "action": "research", "depends_on": []},
                {"name": "信息整理", "action": "review", "depends_on": ["信息收集"]},
                {"name": "报告生成", "action": "generate", "depends_on": ["信息整理"]},
            ],
            "code": [
                {"name": "需求分析", "action": "research", "depends_on": []},
                {"name": "编码实现", "action": "code", "depends_on": ["需求分析"]},
                {"name": "代码审查", "action": "review", "depends_on": ["编码实现"]},
                {"name": "测试验证", "action": "test", "depends_on": ["代码审查"]},
            ],
            "deploy": [
                {"name": "构建打包", "action": "code", "depends_on": []},
                {"name": "环境检查", "action": "research", "depends_on": []},
                {"name": "部署执行", "action": "deploy", "depends_on": ["构建打包", "环境检查"]},
                {"name": "部署验证", "action": "test", "depends_on": ["部署执行"]},
            ],
            "data": [
                {"name": "数据采集", "action": "research", "depends_on": []},
                {"name": "数据清洗", "action": "clean", "depends_on": ["数据采集"]},
                {"name": "数据分析", "action": "analyze", "depends_on": ["数据清洗"]},
                {"name": "报告输出", "action": "generate", "depends_on": ["数据分析"]},
            ],
        }

    def decompose(self, understanding: Dict[str, Any]) -> List[Dict]:
        primary_type = understanding.get("primary_type", "research")
        if understanding.get("requires_decomposition", False):
            template = self._dag_templates.get(primary_type, self._dag_templates["research"])
            return template
        return [{"name": "直接执行", "action": primary_type, "depends_on": []}]


class TaskDispatcher:
    def __init__(self):
        self._agent_capabilities: Dict[str, List[str]] = {}

    def register_agent(self, agent_id: str, capabilities: List[str]):
        self._agent_capabilities[agent_id] = capabilities

    def dispatch(self, subtask_def: Dict[str, Any]) -> str:
        action = subtask_def.get("action", "research")
        best_agent = None
        best_score = -1
        for agent_id, caps in self._agent_capabilities.items():
            score = sum(1 for c in caps if action in c.lower() or c.lower() in action)
            if score > best_score:
                best_score = score
                best_agent = agent_id
        if best_agent is None:
            best_agent = "system-manager"
        logger.info(f"  分发 '{subtask_def.get('name', action)}' → {best_agent} (匹配度: {best_score})")
        return best_agent


class ResultAggregator:
    def aggregate(self, subtask_results: List[Dict]) -> Dict[str, Any]:
        if not subtask_results:
            return {"status": "empty", "summary": "无子任务结果"}
        total = len(subtask_results)
        completed = sum(1 for r in subtask_results if r.get("status") == "completed")
        failed = sum(1 for r in subtask_results if r.get("status") == "failed")
        status = "completed" if failed == 0 else ("partial" if completed > 0 else "failed")
        summaries = [r.get("output", "") for r in subtask_results if r.get("output")]
        return {
            "status": status,
            "total_subtasks": total,
            "completed": completed,
            "failed": failed,
            "summary": " | ".join(summaries) if summaries else f"完成 {completed}/{total} 子任务",
            "results": subtask_results,
        }


class MetaAgent:
    def __init__(self, dispatcher: Optional[TaskDispatcher] = None, max_concurrent: int = 5):
        self.engine = TaskUnderstandingEngine()
        self.decomposer = TaskDecomposer()
        self.dispatcher = dispatcher or TaskDispatcher()
        self.aggregator = ResultAggregator()
        self.max_concurrent = max_concurrent
        self._active_tasks: Dict[str, MetaTask] = {}
        self._task_handlers: Dict[str, Any] = {}

    def register_task_handler(self, task_type: str, handler: Any):
        self._task_handlers[task_type] = handler

    async def submit_task(self, raw_input: str, task_type: str = "", priority: str = "P1") -> MetaTask:
        task_id = f"meta-{uuid.uuid4().hex[:12]}"
        meta_task = MetaTask(task_id=task_id, raw_input=raw_input, task_type=task_type, priority=priority)
        self._active_tasks[task_id] = meta_task
        logger.info(f"Meta-Agent 接收任务 [{task_id}]: {raw_input[:80]}")
        try:
            understanding = self.engine.understand(raw_input)
            if not meta_task.task_type:
                meta_task.task_type = understanding["primary_type"]
            meta_task.stage = TaskStage.DECOMPOSE
            subtask_defs = self.decomposer.decompose(understanding)
            meta_task.stage = TaskStage.DISPATCH
            for i, st_def in enumerate(subtask_defs):
                agent_id = self.dispatcher.dispatch(st_def)
                st = SubTask(
                    subtask_id=f"{task_id}-st{i:02d}",
                    parent_task_id=task_id,
                    agent_id=agent_id,
                    action=st_def["action"] if isinstance(st_def, dict) else st_def,
                    input_data={"description": st_def.get("name", ""), "raw_input": raw_input} if isinstance(st_def, dict) else {},
                )
                meta_task.subtasks.append(st)
            meta_task.stage = TaskStage.MONITOR
            meta_task = await self._execute_subtasks(meta_task)
            meta_task.stage = TaskStage.AGGREGATE
            meta_task.results = [s.result for s in meta_task.subtasks if s.result]
            aggregated = self.aggregator.aggregate(
                [{"status": s.status, "output": str(s.result)} for s in meta_task.subtasks]
            )
            meta_task.stage = TaskStage.COMPLETE
            meta_task.completed_at = datetime.now().isoformat()
            logger.info(f"Meta-Agent 任务完成 [{task_id}]: {aggregated.get('summary', '')}")
        except Exception as e:
            meta_task.stage = TaskStage.FAILED
            meta_task.error = str(e)
            meta_task.completed_at = datetime.now().isoformat()
            logger.error(f"Meta-Agent 任务失败 [{task_id}]: {e}")
        return meta_task

    async def _execute_subtasks(self, meta_task: MetaTask) -> MetaTask:
        completed_steps = set()
        pending = list(meta_task.subtasks)
        while pending:
            ready = []
            still_pending = []
            for st in pending:
                st_def = next((d for d in getattr(self.decomposer, '_dag_templates', {}).get(meta_task.task_type, [])
                               if isinstance(d, dict) and d.get("action") == st.action), {})
                deps = st_def.get("depends_on", []) if isinstance(st_def, dict) else []
                dep_actions = {meta_task.subtasks[i].action for i, d in enumerate(
                    self.decomposer._dag_templates.get(meta_task.task_type, [])
                ) if isinstance(d, dict) and d.get("name") in deps}
                if all(a in completed_steps for a in dep_actions) or not deps:
                    ready.append(st)
                else:
                    still_pending.append(st)
            if not ready and still_pending:
                logger.warning("  检测到循环依赖，强制执行剩余任务")
                ready = still_pending
                still_pending = []
            semaphore = asyncio.Semaphore(self.max_concurrent)
            async def run_subtask(st: SubTask):
                async with semaphore:
                    return await self._run_single_subtask(st)
            tasks = [run_subtask(st) for st in ready]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for st, result in zip(ready, results):
                if isinstance(result, Exception):
                    st.status = "failed"
                    st.error = str(result)
                    logger.error(f"  子任务失败 [{st.subtask_id}]: {result}")
                else:
                    st.status = "completed"
                    st.result = {"output": str(result)}
                    st.completed_at = datetime.now().isoformat()
                    completed_steps.add(st.action)
            pending = still_pending
        return meta_task

    async def _run_single_subtask(self, subtask: SubTask) -> Any:
        handler = self._task_handlers.get(subtask.action)
        if handler:
            if asyncio.iscoroutinefunction(handler):
                return await handler(subtask.input_data)
            return handler(subtask.input_data)
        return f"[模拟执行] {subtask.agent_id} 执行 {subtask.action}: {subtask.input_data.get('description', '')}"

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        task = self._active_tasks.get(task_id)
        return task.to_dict() if task else None

    def list_active_tasks(self) -> List[Dict]:
        return [t.to_dict() for t in self._active_tasks.values()]
