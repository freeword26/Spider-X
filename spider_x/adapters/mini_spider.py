"""Spider-X Adapter for mini_spider."""
from __future__ import annotations
from typing import Any, Dict, List
__all__ = ["MiniSpiderAdapter"]

class MiniSpiderAdapter:
    def __init__(self, orchestrator: Any = None): self._orc, self._agents = orchestrator, {}
    @classmethod
    def from_mini_spider(cls, orc: Any) -> "MiniSpiderAdapter": return cls(orchestrator=orc)
    def register_agents(self, cfgs: List[Dict]) -> List[str]:
        ids = []
        for c in cfgs: aid = c.get("agent_id", f"agent-{len(self._agents)}"); self._agents[aid] = c; ids.append(aid)
        return ids
    def dispatch_task(self, task: Dict) -> str:
        tid = task.get("task_id", f"task-{id(task)}")
        if self._orc and hasattr(self._orc, "dispatch"): self._orc.dispatch(task)
        return tid
    def get_agent_status(self, aid: str) -> Dict: return self._agents.get(aid, {"agent_id": aid, "status": "unknown"})
    def list_agents(self) -> List[Dict]: return [{"agent_id": k, **v} for k, v in self._agents.items()]
    @staticmethod
    def to_spider_x_task(t: Dict) -> Dict:
        return {"task_id": t.get("id") or t.get("task_id"), "task_type": t.get("type", "custom"), "payload": t.get("payload", t.get("data", {})), "priority": t.get("priority", "P1")}
