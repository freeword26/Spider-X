"""Spider-X Subgraph."""
from __future__ import annotations
import logging, uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
logger = logging.getLogger("spider_x.subgraph")
__all__ = ["SubgraphEncapsulator", "VirtualSuperAgentManager", "CollaborationPattern"]

@dataclass
class CollaborationPattern:
    pattern_id: str; name: str; action_sequence: List[str]; frequency: int = 0
    def to_dict(self) -> Dict: return {"pattern_id": self.pattern_id, "name": self.name, "frequency": self.frequency}

class SubgraphEncapsulator:
    def __init__(self, min_frequency: int = 3): self._patterns, self._obs, self.min_freq = {}, [], min_frequency
    def record_observation(self, seq: List[str], success: bool = True, task_id: str = ""):
        self._obs.append(seq); key = "->".join(seq)
        if key in self._patterns: self._patterns[key].frequency += 1
        else: self._patterns[key] = CollaborationPattern(f"p-{uuid.uuid4().hex[:8]}", key, seq)
    def discover_patterns(self) -> List[CollaborationPattern]:
        return sorted([p for p in self._patterns.values() if p.frequency >= self.min_freq], key=lambda p: p.frequency, reverse=True)
    def get_pattern_by_sequence(self, seq: List[str]) -> Optional[CollaborationPattern]: return self._patterns.get("->".join(seq))
    def get_stats(self) -> Dict: return {"total": len(self._obs), "patterns": len(self._patterns)}

class VirtualSuperAgent:
    def __init__(self, pattern: CollaborationPattern):
        self.super_agent_id, self.pattern, self.created_at = f"vsa-{uuid.uuid4().hex[:8]}", pattern, datetime.now().isoformat()
    def to_dict(self) -> Dict: return {"id": self.super_agent_id, "name": self.pattern.name}
    def invoke(self) -> Dict: return {"id": self.super_agent_id, "status": "dispatched"}

class VirtualSuperAgentManager:
    def __init__(self, enc: Optional[SubgraphEncapsulator] = None): self._enc = enc or SubgraphEncapsulator(); self._agents: Dict[str, VirtualSuperAgent] = {}
    def create_from_pattern(self, p: CollaborationPattern) -> VirtualSuperAgent:
        vsa = VirtualSuperAgent(p); self._agents[vsa.super_agent_id] = vsa; return vsa
    def auto_discover_and_create(self) -> List[VirtualSuperAgent]:
        ex = {a.pattern.name for a in self._agents.values()}; created = []
        for p in self._enc.discover_patterns():
            if p.name not in ex: created.append(self.create_from_pattern(p)); ex.add(p.name)
        return created
    def get_super_agent(self, sid: str) -> Optional[VirtualSuperAgent]: return self._agents.get(sid)
    def find_super_agent_for(self, seq: List[str]) -> Optional[VirtualSuperAgent]:
        key = "->".join(seq)
        for a in self._agents.values():
            if a.pattern.name == key: return a
        return None
    def list_super_agents(self) -> List[Dict]: return [a.to_dict() for a in self._agents.values()]
    def get_encapsulator(self) -> SubgraphEncapsulator: return self._enc
