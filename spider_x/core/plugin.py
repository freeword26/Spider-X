"""Spider-X Plugin."""
from __future__ import annotations
import hashlib, logging, uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
logger = logging.getLogger("spider_x.plugin")
__all__ = ["PluginManager", "PluginManifest", "PluginState", "CapabilityContract"]

class PluginState:
    REGISTERED = "registered"; LOADING = "loading"; ACTIVE = "active"; FAILED = "failed"; UNLOADED = "unloaded"

@dataclass
class CapabilityContract:
    contract_id: str; agent_type: str; version: str; capabilities: Dict[str, Any]; endpoints: Dict[str, str]
    registered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    def to_dict(self) -> Dict: return {"contract_id": self.contract_id, "agent_type": self.agent_type, "version": self.version}

@dataclass
class PluginManifest:
    plugin_id: str; name: str; version: str; agent_type: str; entry_point: str; capabilities: List[str]
    deployment_mode: str = "oci"; image: Optional[str] = None
    def to_dict(self) -> Dict: return {"plugin_id": self.plugin_id, "name": self.name, "version": self.version, "agent_type": self.agent_type, "capabilities": self.capabilities}
    def fingerprint(self) -> str: return hashlib.sha256(f"{self.plugin_id}:{self.version}:{self.entry_point}".encode()).hexdigest()[:16]

class PluginManager:
    def __init__(self, plugin_dir: str = "/var/lib/spider-x/plugins"): self._plugins, self._contracts = {}, {}
    def register_plugin(self, m: PluginManifest) -> str: self._plugins[m.plugin_id] = {"manifest": m.to_dict(), "state": PluginState.REGISTERED}; return m.plugin_id
    async def activate_plugin(self, pid: str) -> bool:
        p = self._plugins.get(pid)
        if not p: return False
        p["state"] = PluginState.LOADING
        try:
            m = p["manifest"]; c = CapabilityContract(f"c-{uuid.uuid4().hex[:8]}", m["agent_type"], m["version"], {c: True for c in m["capabilities"]}, {"main": f"/plugins/{pid}/invoke"})
            self._contracts[c.contract_id] = c; p["state"] = PluginState.ACTIVE; return True
        except Exception: p["state"] = PluginState.FAILED; return False
    async def deactivate_plugin(self, pid: str) -> bool:
        p = self._plugins.get(pid)
        if not p: return False
        cid = p.get("contract_id")
        if cid: self._contracts.pop(cid, None)
        p["state"] = PluginState.UNLOADED; return True
    def get_plugin(self, pid: str) -> Optional[Dict]: return self._plugins.get(pid)
    def get_contract(self, cid: str) -> Optional[CapabilityContract]: return self._contracts.get(cid)
    def list_plugins(self, state: str = None) -> List[Dict]: return [{"plugin_id": pid, "name": p["manifest"]["name"], "state": p["state"]} for pid, p in self._plugins.items() if not state or p["state"] == state]
    def list_contracts(self) -> List[Dict]: return [c.to_dict() for c in self._contracts.values()]
    def find_plugins_by_capability(self, cap: str) -> List[Dict]: return [{"plugin_id": pid, "manifest": p["manifest"]} for pid, p in self._plugins.items() if p["state"] == PluginState.ACTIVE and cap in p["manifest"].get("capabilities", [])]
    def get_status(self) -> Dict: return {"total_plugins": len(self._plugins), "active_contracts": len(self._contracts)}
