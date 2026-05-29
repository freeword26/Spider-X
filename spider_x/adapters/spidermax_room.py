"""SpiderRoomAdapter for MAX ROOM v2.0 (Spider MAX ROOM) — 工作流注册/触发."""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
logger = logging.getLogger("spider_x.adapter.spidermax_room")
__all__ = ["SpiderRoomAdapter"]

class SpiderRoomAdapter:
    def __init__(self, room_app: Any = None): self._app, self._wfs = room_app, {}
    @classmethod
    def from_room(cls, app: Any) -> "SpiderRoomAdapter": return cls(room_app=app)
    def register_workflow(self, wd: Dict) -> str:
        wid = wd.get("workflow_id", f"wf-{len(self._wfs)}"); self._wfs[wid] = wd; return wid
    def trigger_workflow(self, wid: str) -> str: return f"exec-{wid}"
    def get_workflow_status(self, wid: str) -> Dict: return {"workflow_id": wid, "status": "registered"}
    def list_workflows(self) -> List[Dict]: return [{"workflow_id": k, **v} for k, v in self._wfs.items()]
