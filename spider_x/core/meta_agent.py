"""Spider-X Meta Agent — 多Agent聚合层.

职责：聚合多个Agent的执行结果。
任务理解/拆解/分发 → 由 role_engine.py 负责（AIRouter）。
"""
from __future__ import annotations

import logging
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
    stage: TaskStage = TaskStage.PARSE
    subtasks: List[SubTask] = field(default_factory=list)
    results: List[Dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    error: Optional[str] = None


class ResultAggregator:
    """多Agent结果聚合器.

    支持多种聚合策略:
      - priority: 按优先级选择（默认）
      - voting: 投票表决（适用于分类任务）
      - merge: 合并拼接（适用于生成任务）
      - ranking: 加权排序（适用于推荐任务）
    """

    def aggregate(self, subtask_results: List[Dict],
                  strategy: str = "priority") -> Dict[str, Any]:
        """聚合子任务结果."""
        if not subtask_results:
            return {"status": "empty", "summary": "无子任务结果"}

        valid = [r for r in subtask_results if r.get("status") == "ok"]
        failed = [r for r in subtask_results if r.get("status") == "error"]
        total = len(subtask_results)

        if strategy == "priority":
            return self._aggregate_by_priority(valid, failed, total)
        elif strategy == "voting":
            return self._aggregate_by_voting(valid, failed, total)
        elif strategy == "merge":
            return self._aggregate_by_merge(valid, failed, total)
        elif strategy == "ranking":
            return self._aggregate_by_ranking(valid, failed, total)
        return self._aggregate_by_priority(valid, failed, total)

    def _aggregate_by_priority(self, valid: list, failed: list, total: int) -> Dict:
        """按优先级选择最优结果."""
        if not valid:
            return {
                "status": "failed",
                "total_subtasks": total,
                "completed": 0,
                "failed": len(failed),
                "summary": "所有子任务均失败",
                "errors": [f.get("error", "") for f in failed],
            }
        # 选择最高优先级结果
        best = valid[0]
        return {
            "status": "completed" if not failed else "partial",
            "total_subtasks": total,
            "completed": len(valid),
            "failed": len(failed),
            "summary": best.get("summary", best.get("result", "")),
            "best_result": best,
            "alternative_results": valid[1:],
            "all_results": valid,
        }

    def _aggregate_by_voting(self, valid: list, failed: list, total: int) -> Dict:
        """投票表决."""
        votes: Dict[str, int] = {}
        for r in valid:
            result = str(r.get("result", r.get("response", "")))
            votes[result] = votes.get(result, 0) + 1
        if not votes:
            return {"status": "failed", "summary": "无有效投票"}
        winner = max(votes, key=votes.get)
        return {
            "status": "ok",
            "total_subtasks": total,
            "completed": len(valid),
            "winner": winner,
            "votes": votes,
            "confidence": votes[winner] / len(valid),
            "summary": f"投票结果: {winner} ({votes[winner]}/{len(valid)} 票)",
        }

    def _aggregate_by_merge(self, valid: list, failed: list, total: int) -> Dict:
        """合并拼接结果."""
        merged = []
        sources = []
        for r in valid:
            content = r.get("response", r.get("result", ""))
            if content and content not in ("no_match", ""):
                merged.append(content)
                sources.append(r.get("role", r.get("agent_id", "?")))
        return {
            "status": "ok" if merged else "empty",
            "total_subtasks": total,
            "completed": len(valid),
            "summary": "\n\n".join(merged),
            "sources": sources,
            "merged_parts": len(merged),
        }

    def _aggregate_by_ranking(self, valid: list, failed: list, total: int) -> Dict:
        """加权排序."""
        ranked = []
        for r in valid:
            score = r.get("confidence", r.get("weight", 0.5))
            ranked.append((score, r))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return {
            "status": "ok",
            "total_subtasks": total,
            "completed": len(valid),
            "ranked_results": [
                {"score": s, "result": r.get("response", r.get("result", ""))}
                for s, r in ranked
            ],
            "best_score": ranked[0][0] if ranked else 0,
            "summary": ranked[0][1].get("summary", "") if ranked else "",
        }
