"""Spider-X atomic action decomposition module."""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("spider-x.atomic_action")


class ActionType(str, Enum):
    RESEARCH = "research"
    CODE = "code"
    REVIEW = "review"
    CLEAN = "clean"
    TEST = "test"
    DEPLOY = "deploy"
    NOTIFY = "notify"
    CUSTOM = "custom"


class ActionStatus(str, Enum):
    PENDING = "pending"
    DECOMPOSING = "decomposing"
    DECOMPOSED = "decomposed"
    BROADCASTING = "broadcasting"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AtomicAction:
    action_id: str
    action_type: str
    name: str
    payload: Dict[str, Any]
    status: str = ActionStatus.PENDING
    parent_task_id: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    required_roles: List[str] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)
    priority: int = 1
    assigned_agent: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict:
        d = asdict(self)
        for k in ["result", "error", "started_at", "completed_at", "assigned_agent", "parent_task_id"]:
            if d[k] is None:
                del d[k]
        return d

    @property
    def fingerprint(self) -> str:
        content = f"{self.action_type}:{self.name}:{json.dumps(self.payload, sort_keys=True, default=str)}"
        return hashlib.md5(content.encode()).hexdigest()[:12]


@dataclass
class DecompositionResult:
    task_id: str
    original_description: str
    actions: List[AtomicAction]
    dependency_graph: Dict[str, List[str]]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id, "original_description": self.original_description,
            "actions": [a.to_dict() for a in self.actions],
            "dependency_graph": self.dependency_graph, "created_at": self.created_at,
        }

    def get_ready_actions(self, completed: Set[str]) -> List[AtomicAction]:
        ready = []
        for action in self.actions:
            if action.status != ActionStatus.PENDING:
                continue
            if all(dep in completed for dep in action.depends_on):
                ready.append(action)
        return ready


class TaskDecomposer:
    def __init__(self):
        self._patterns: Dict[str, List[Dict]] = {}
        self._register_default_patterns()

    def _register_default_patterns(self):
        self._patterns["research"] = [
            {"name": "信息检索", "action_type": "research", "required_roles": ["researcher"]},
            {"name": "结果整理", "action_type": "research", "required_roles": ["researcher"]},
        ]
        self._patterns["implement"] = [
            {"name": "代码实现", "action_type": "code", "required_roles": ["coder"]},
            {"name": "代码审查", "action_type": "review", "required_roles": ["reviewer"]},
            {"name": "测试验证", "action_type": "test", "required_roles": ["tester"]},
            {"name": "清理优化", "action_type": "clean", "required_roles": ["cleaner"]},
        ]
        self._patterns["full_cycle"] = [
            {"name": "需求分析", "action_type": "research", "required_roles": ["researcher"]},
            {"name": "代码实现", "action_type": "code", "required_roles": ["coder"]},
            {"name": "代码审查", "action_type": "review", "required_roles": ["reviewer"]},
            {"name": "测试验证", "action_type": "test", "required_roles": ["tester"]},
            {"name": "清理优化", "action_type": "clean", "required_roles": ["cleaner"]},
            {"name": "部署通知", "action_type": "deploy", "required_roles": ["deployer"]},
        ]

    def register_pattern(self, name: str, steps: List[Dict]):
        self._patterns[name] = steps

    def decompose(self, task_description: str, pattern: str = "auto", context: Optional[Dict] = None) -> DecompositionResult:
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        if pattern == "auto":
            pattern = self._detect_pattern(task_description)
        step_defs = self._patterns.get(pattern, self._patterns.get("research", []))
        actions = []
        dep_graph: Dict[str, List[str]] = {}
        for i, sd in enumerate(step_defs):
            action_id = f"action-{uuid.uuid4().hex[:8]}"
            deps = [actions[-1].action_id] if actions else []
            action = AtomicAction(
                action_id=action_id, action_type=sd.get("action_type", "custom"),
                name=sd.get("name", f"step-{i}"),
                payload={"description": task_description, "step_index": i, **(context or {})},
                parent_task_id=task_id, depends_on=deps,
                required_roles=sd.get("required_roles", []),
                required_skills=sd.get("required_skills", []),
                priority=sd.get("priority", 1),
            )
            actions.append(action)
            dep_graph[action_id] = deps
        result = DecompositionResult(
            task_id=task_id, original_description=task_description,
            actions=actions, dependency_graph=dep_graph,
        )
        logger.info(f"Task decomposed: {task_id} -> {len(actions)} actions (pattern={pattern})")
        return result

    def _detect_pattern(self, description: str) -> str:
        desc_lower = description.lower()
        if any(kw in desc_lower for kw in ["实现", "开发", "编码", "implement", "code", "build"]):
            if any(kw in desc_lower for kw in ["测试", "test", "部署", "deploy"]):
                return "full_cycle"
            return "implement"
        if any(kw in desc_lower for kw in ["研究", "调研", "搜索", "research", "search"]):
            return "research"
        return "research"

    def decompose_custom(self, task_id: str, description: str, steps: List[Dict]) -> DecompositionResult:
        actions = []
        dep_graph: Dict[str, List[str]] = {}
        for i, sd in enumerate(steps):
            action_id = f"action-{uuid.uuid4().hex[:8]}"
            deps = [actions[-1].action_id] if actions else []
            action = AtomicAction(
                action_id=action_id, action_type=sd.get("action_type", "custom"),
                name=sd.get("name", f"step-{i}"),
                payload={"description": description, "step_index": i},
                parent_task_id=task_id, depends_on=sd.get("depends_on", deps),
                required_roles=sd.get("required_roles", []),
                required_skills=sd.get("required_skills", []),
            )
            actions.append(action)
            dep_graph[action_id] = action.depends_on
        return DecompositionResult(
            task_id=task_id, original_description=description,
            actions=actions, dependency_graph=dep_graph,
        )


__all__ = [
    "TaskDecomposer",
    "AtomicAction",
    "ActionStatus",
    "ActionType",
    "DecompositionResult",
]
