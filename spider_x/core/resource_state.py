"""Spider-X resource state management for agent cluster."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("spider-x.resource_state")


@dataclass
class CapabilityVector:
    roles: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    max_concurrency: int = 5
    specializations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict) -> CapabilityVector:
        return CapabilityVector(**{k: v for k, v in d.items() if k in CapabilityVector.__dataclass_fields__})


@dataclass
class ResourceState:
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_mb: float = 0.0
    load_avg: float = 0.0
    active_tasks: int = 0
    queued_tasks: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)

    @property
    def is_healthy(self) -> bool:
        return self.cpu_percent < 90 and self.memory_percent < 90

    @property
    def capacity_score(self) -> float:
        cpu_headroom = max(0, 100 - self.cpu_percent)
        mem_headroom = max(0, 100 - self.memory_percent)
        load_factor = max(0, 1.0 - self.active_tasks / max(1, getattr(self, 'max_concurrency', 5)))
        return (cpu_headroom * 0.4 + mem_headroom * 0.4 + load_factor * 20 * 0.2)

    @staticmethod
    def from_dict(d: Dict) -> ResourceState:
        return ResourceState(**{k: v for k, v in d.items() if k in ResourceState.__dataclass_fields__})


class AgentStatus:
    IDLE = "idle"
    BUSY = "busy"
    DRAINING = "draining"
    OFFLINE = "offline"


@dataclass
class AgentState:
    agent_id: str
    status: str = AgentStatus.IDLE
    capabilities: CapabilityVector = field(default_factory=CapabilityVector)
    resources: ResourceState = field(default_factory=ResourceState)
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ttl_seconds: int = 30
    _version: str = "2.0"

    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id, "version": self._version, "status": self.status,
            "capabilities": self.capabilities.to_dict(), "resources": self.resources.to_dict(),
            "updated_at": self.updated_at, "ttl_seconds": self.ttl_seconds,
        }

    def is_expired(self) -> bool:
        try:
            updated = datetime.fromisoformat(self.updated_at)
            return (datetime.now() - updated).total_seconds() > self.ttl_seconds
        except (ValueError, TypeError):
            return True

    @staticmethod
    def from_dict(d: Dict) -> AgentState:
        caps = CapabilityVector.from_dict(d.get("capabilities", {}))
        res = ResourceState.from_dict(d.get("resources", {}))
        return AgentState(
            agent_id=d["agent_id"], status=d.get("status", AgentStatus.IDLE),
            capabilities=caps, resources=res,
            updated_at=d.get("updated_at", datetime.now().isoformat()),
            ttl_seconds=d.get("ttl_seconds", 30),
        )


class ResourceStateService:
    def __init__(self):
        self._states: Dict[str, AgentState] = {}
        self._listeners: List[callable] = []

    def register_listener(self, callback: callable):
        self._listeners.append(callback)

    async def _notify_listeners(self, event: str, agent_id: str, state: AgentState):
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, agent_id, state)
                else:
                    listener(event, agent_id, state)
            except Exception as e:
                logger.error(f"Listener error: {e}")

    def register_agent(self, agent_id: str, capabilities: Optional[Dict] = None) -> AgentState:
        caps = CapabilityVector.from_dict(capabilities) if capabilities else CapabilityVector()
        state = AgentState(agent_id=agent_id, capabilities=caps)
        self._states[agent_id] = state
        logger.info(f"Agent registered: {agent_id}")
        return state

    def deregister_agent(self, agent_id: str):
        if agent_id in self._states:
            self._states[agent_id].status = AgentStatus.OFFLINE
            logger.info(f"Agent deregistered: {agent_id}")

    def update_state(self, agent_id: str, updates: Dict[str, Any]) -> Optional[AgentState]:
        state = self._states.get(agent_id)
        if not state:
            logger.warning(f"Update for unknown agent: {agent_id}")
            return None
        if "status" in updates:
            state.status = updates["status"]
        if "cpu_percent" in updates:
            state.resources.cpu_percent = updates["cpu_percent"]
        if "memory_percent" in updates:
            state.resources.memory_percent = updates["memory_percent"]
        if "memory_mb" in updates:
            state.resources.memory_mb = updates["memory_mb"]
        if "load_avg" in updates:
            state.resources.load_avg = updates["load_avg"]
        if "active_tasks" in updates:
            state.resources.active_tasks = updates["active_tasks"]
        if "queued_tasks" in updates:
            state.resources.queued_tasks = updates["queued_tasks"]
        if "capabilities" in updates:
            state.capabilities = CapabilityVector.from_dict(updates["capabilities"])
        state.updated_at = datetime.now().isoformat()
        return state

    def heartbeat(self, agent_id: str) -> Optional[AgentState]:
        state = self._states.get(agent_id)
        if state:
            state.updated_at = datetime.now().isoformat()
        return state

    def get_state(self, agent_id: str) -> Optional[AgentState]:
        state = self._states.get(agent_id)
        if state and state.is_expired():
            state.status = AgentStatus.OFFLINE
        return state

    def get_all_states(self) -> List[AgentState]:
        result = []
        for agent_id, state in list(self._states.items()):
            if state.is_expired():
                state.status = AgentStatus.OFFLINE
            result.append(state)
        return result

    def get_available_agents(self, required_role: Optional[str] = None, required_skill: Optional[str] = None) -> List[AgentState]:
        available = []
        for state in self._states.values():
            if state.status not in (AgentStatus.IDLE, AgentStatus.BUSY):
                continue
            if state.is_expired():
                continue
            if required_role and required_role not in state.capabilities.roles:
                continue
            if required_skill and required_skill not in state.capabilities.skills:
                continue
            available.append(state)
        return available

    def get_least_loaded(self, required_role: Optional[str] = None) -> Optional[AgentState]:
        available = self.get_available_agents(required_role=required_role)
        if not available:
            return None
        return min(available, key=lambda s: s.resources.active_tasks)

    def get_cluster_summary(self) -> Dict:
        states = self.get_all_states()
        total = len(states)
        idle = sum(1 for s in states if s.status == AgentStatus.IDLE)
        busy = sum(1 for s in states if s.status == AgentStatus.BUSY)
        draining = sum(1 for s in states if s.status == AgentStatus.DRAINING)
        offline = sum(1 for s in states if s.status == AgentStatus.OFFLINE)
        total_active = sum(s.resources.active_tasks for s in states)
        total_queued = sum(s.resources.queued_tasks for s in states)
        avg_cpu = sum(s.resources.cpu_percent for s in states) / max(1, total)
        avg_mem = sum(s.resources.memory_percent for s in states) / max(1, total)
        all_roles = set()
        all_skills = set()
        for s in states:
            all_roles.update(s.capabilities.roles)
            all_skills.update(s.capabilities.skills)
        return {
            "total_agents": total, "idle": idle, "busy": busy, "draining": draining,
            "offline": offline, "total_active_tasks": total_active,
            "total_queued_tasks": total_queued, "avg_cpu_percent": round(avg_cpu, 1),
            "avg_memory_percent": round(avg_mem, 1), "available_roles": sorted(all_roles),
            "available_skills": sorted(all_skills), "timestamp": datetime.now().isoformat(),
        }


__all__ = [
    "ResourceStateService",
    "AgentState",
    "AgentStatus",
    "CapabilityVector",
    "ResourceState",
]
