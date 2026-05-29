"""Spider-X Adapter for spider_max."""
from __future__ import annotations
from typing import Any, Dict, List
__all__ = ["SpiderMaxAdapter"]

class SpiderMaxAdapter:
    def __init__(self, app: Any = None): self._app, self._mods = app, {}
    @classmethod
    def from_spider_max(cls, app: Any) -> "SpiderMaxAdapter": return cls(app=app)
    def sync_projects(self) -> List[Dict]: return []
    def import_okr(self, data: Dict) -> str: return data.get("id", f"okr-{id(data)}")
    def export_report(self, rt: str) -> Dict: return {"type": rt, "data": []}
    def get_module_registry(self) -> Dict:
        if self._app and hasattr(self._app, "state"): return dict(getattr(self._app.state, "components", {}))
        return self._mods
    @staticmethod
    def to_spider_x_skill(s: Dict) -> Dict:
        return {"skill_id": s.get("id") or s.get("skill_id"), "name": s.get("name", ""), "version": s.get("version", "1.0.0"), "compatible_spiders": ["*"]}
