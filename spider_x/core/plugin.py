import asyncio
import hashlib
import json
import logging
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("spider_x.plugin")


class PluginState(str, Enum):
    REGISTERED = "registered"
    LOADING = "loading"
    ACTIVE = "active"
    DEGRADED = "degraded"
    UNLOADING = "unloading"
    UNLOADED = "unloaded"
    FAILED = "failed"


@dataclass
class CapabilityContract:
    contract_id: str
    agent_type: str
    version: str
    capabilities: Dict[str, Any]
    endpoints: Dict[str, str]
    health_check_path: str = "/health"
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict) -> "CapabilityContract":
        return CapabilityContract(**{k: v for k, v in d.items() if k in CapabilityContract.__dataclass_fields__})


@dataclass
class PluginManifest:
    plugin_id: str
    name: str
    version: str
    agent_type: str
    entry_point: str
    capabilities: List[str]
    resource_limits: Dict[str, Any] = field(default_factory=lambda: {"cpu_cores": 1, "memory_mb": 512})
    deployment_mode: str = "oci"
    image: Optional[str] = None
    env_vars: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

    def fingerprint(self) -> str:
        content = f"{self.plugin_id}:{self.version}:{self.entry_point}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class PluginManager:
    def __init__(self, plugin_dir: str = "/var/lib/spider-x/plugins"):
        self._plugins: Dict[str, Dict] = {}
        self._contracts: Dict[str, CapabilityContract] = {}
        self._plugin_dir = plugin_dir

    def register_plugin(self, manifest: PluginManifest) -> str:
        plugin_id = manifest.plugin_id
        self._plugins[plugin_id] = {
            "manifest": manifest.to_dict(),
            "state": PluginState.REGISTERED,
            "registered_at": datetime.now().isoformat(),
            "health_check_failures": 0,
        }
        logger.info(f"Plugin registered: {plugin_id} v{manifest.version} ({manifest.agent_type})")
        return plugin_id

    async def activate_plugin(self, plugin_id: str) -> bool:
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            logger.error(f"Plugin not found: {plugin_id}")
            return False
        plugin["state"] = PluginState.LOADING
        try:
            manifest_dict = plugin["manifest"]
            manifest = PluginManifest(**{k: v for k, v in manifest_dict.items() if k in PluginManifest.__dataclass_fields__})
            if manifest.deployment_mode == "oci":
                logger.info(f"Activating OCI plugin: {plugin_id}")
            elif manifest.deployment_mode == "wasi":
                logger.info(f"Activating WASI plugin: {plugin_id}")
            elif manifest.deployment_mode == "local":
                logger.info(f"Activating local plugin: {plugin_id}")
            contract = CapabilityContract(
                contract_id=f"contract-{uuid.uuid4().hex[:8]}",
                agent_type=manifest.agent_type,
                version=manifest.version,
                capabilities={c: True for c in manifest.capabilities},
                endpoints={"main": f"/plugins/{plugin_id}/invoke"},
                metadata={"fingerprint": manifest.fingerprint()},
            )
            self._contracts[contract.contract_id] = contract
            plugin["contract_id"] = contract.contract_id
            plugin["state"] = PluginState.ACTIVE
            plugin["activated_at"] = datetime.now().isoformat()
            logger.info(f"Plugin activated: {plugin_id} (contract={contract.contract_id})")
            return True
        except Exception as e:
            plugin["state"] = PluginState.FAILED
            plugin["error"] = str(e)
            logger.error(f"Plugin activation failed: {plugin_id} - {e}")
            return False

    async def deactivate_plugin(self, plugin_id: str) -> bool:
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        plugin["state"] = PluginState.UNLOADING
        contract_id = plugin.get("contract_id")
        if contract_id:
            self._contracts.pop(contract_id, None)
        plugin["state"] = PluginState.UNLOADED
        logger.info(f"Plugin deactivated: {plugin_id}")
        return True

    def get_plugin(self, plugin_id: str) -> Optional[Dict]:
        return self._plugins.get(plugin_id)

    def get_contract(self, contract_id: str) -> Optional[CapabilityContract]:
        return self._contracts.get(contract_id)

    def list_plugins(self, state: Optional[str] = None) -> List[Dict]:
        results = []
        for pid, p in self._plugins.items():
            if state and p["state"] != state:
                continue
            results.append({
                "plugin_id": pid,
                "name": p["manifest"]["name"],
                "version": p["manifest"]["version"],
                "state": p["state"],
                "agent_type": p["manifest"]["agent_type"],
            })
        return results

    def list_contracts(self) -> List[Dict]:
        return [c.to_dict() for c in self._contracts.values()]

    def find_plugins_by_capability(self, capability: str) -> List[Dict]:
        results = []
        for pid, p in self._plugins.items():
            if p["state"] != PluginState.ACTIVE:
                continue
            if capability in p["manifest"].get("capabilities", []):
                results.append({"plugin_id": pid, "manifest": p["manifest"]})
        return results

    def get_status(self) -> Dict:
        states = {}
        for p in self._plugins.values():
            s = p["state"]
            states[s] = states.get(s, 0) + 1
        return {
            "total_plugins": len(self._plugins),
            "active_contracts": len(self._contracts),
            "states": states,
        }
