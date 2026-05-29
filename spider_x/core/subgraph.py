import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("worker-cluster.subgraph")


@dataclass
class CollaborationEdge:
    source_pattern: str
    target_pattern: str
    frequency: int = 0
    avg_latency_ms: float = 0.0
    success_rate: float = 1.0


@dataclass
class CollaborationPattern:
    pattern_id: str
    name: str
    action_sequence: List[str]
    frequency: int = 0
    avg_duration_ms: float = 0.0
    success_rate: float = 1.0
    example_tasks: List[str] = field(default_factory=list)


class SubgraphEncapsulator:
    def __init__(self, min_frequency: int = 3):
        self._patterns: Dict[str, CollaborationPattern] = {}
        self._edges: Dict[str, CollaborationEdge] = {}
        self._observations: List[List[str]] = []
        self.min_frequency = min_frequency

    def record_observation(self, action_sequence: List[str], duration_ms: float = 0, success: bool = True, task_id: str = ""):
        self._observations.append(action_sequence)
        key = "->".join(action_sequence)
        if key in self._patterns:
            p = self._patterns[key]
            p.frequency += 1
            total = p.avg_duration_ms * (p.frequency - 1) + duration_ms
            p.avg_duration_ms = total / p.frequency
            p.success_rate = (p.success_rate * (p.frequency - 1) + (1.0 if success else 0)) / p.frequency
            if task_id:
                p.example_tasks.append(task_id)
        else:
            self._patterns[key] = CollaborationPattern(
                pattern_id=f"pattern-{uuid.uuid4().hex[:8]}",
                name=key,
                action_sequence=action_sequence,
                frequency=1,
                avg_duration_ms=duration_ms,
                success_rate=1.0 if success else 0.0,
                example_tasks=[task_id] if task_id else [],
            )

        for i in range(len(action_sequence) - 1):
            edge_key = f"{action_sequence[i]}->{action_sequence[i+1]}"
            if edge_key in self._edges:
                e = self._edges[edge_key]
                e.frequency += 1
                e.avg_latency_ms = (e.avg_latency_ms * (e.frequency - 1) + duration_ms / max(1, len(action_sequence) - 1)) / e.frequency
            else:
                self._edges[edge_key] = CollaborationEdge(
                    source_pattern=action_sequence[i],
                    target_pattern=action_sequence[i + 1],
                    frequency=1,
                )

    def discover_patterns(self) -> List[CollaborationPattern]:
        return sorted(
            [p for p in self._patterns.values() if p.frequency >= self.min_frequency],
            key=lambda p: p.frequency,
            reverse=True,
        )

    def get_frequent_patterns(self, top_n: int = 5) -> List[CollaborationPattern]:
        patterns = self.discover_patterns()
        return patterns[:top_n]

    def get_pattern_by_sequence(self, sequence: List[str]) -> Optional[CollaborationPattern]:
        key = "->".join(sequence)
        return self._patterns.get(key)

    def get_stats(self) -> Dict:
        patterns = self.discover_patterns()
        return {
            "total_observations": len(self._observations),
            "total_patterns": len(self._patterns),
            "qualified_patterns": len(patterns),
            "top_patterns": [
                {
                    "name": p.name,
                    "frequency": p.frequency,
                    "success_rate": round(p.success_rate, 2),
                    "avg_duration_ms": round(p.avg_duration_ms, 1),
                }
                for p in patterns[:5]
            ],
        }


class VirtualSuperAgent:
    def __init__(self, pattern: CollaborationPattern):
        self.super_agent_id = f"vsa-{uuid.uuid4().hex[:8]}"
        self.pattern = pattern
        self.created_at = datetime.now().isoformat()
        self.invocation_count = 0
        self._wasm_module_name = f"wasm_{pattern.pattern_id}"

    def to_dict(self) -> Dict:
        return {
            "super_agent_id": self.super_agent_id,
            "pattern_id": self.pattern.pattern_id,
            "name": self.pattern.name,
            "action_sequence": self.pattern.action_sequence,
            "frequency": self.pattern.frequency,
            "success_rate": self.pattern.success_rate,
            "wasm_module": self._wasm_module_name,
            "created_at": self.created_at,
            "invocation_count": self.invocation_count,
        }

    def invoke(self) -> Dict:
        self.invocation_count += 1
        return {
            "super_agent_id": self.super_agent_id,
            "action_sequence": self.pattern.action_sequence,
            "status": "dispatched",
        }


class VirtualSuperAgentManager:
    def __init__(self, encapsulator: Optional[SubgraphEncapsulator] = None):
        self._encapsulator = encapsulator or SubgraphEncapsulator()
        self._super_agents: Dict[str, VirtualSuperAgent] = {}

    def create_from_pattern(self, pattern: CollaborationPattern) -> VirtualSuperAgent:
        vsa = VirtualSuperAgent(pattern)
        self._super_agents[vsa.super_agent_id] = vsa
        logger.info(f"Virtual super agent created: {vsa.super_agent_id} for pattern '{pattern.name}'")
        return vsa

    def auto_discover_and_create(self) -> List[VirtualSuperAgent]:
        patterns = self._encapsulator.discover_patterns()
        created = []
        for pattern in patterns:
            key = pattern.name
            if key not in {sa.pattern.name for sa in self._super_agents.values()}:
                vsa = self.create_from_pattern(pattern)
                created.append(vsa)
        return created

    def get_super_agent(self, super_agent_id: str) -> Optional[VirtualSuperAgent]:
        return self._super_agents.get(super_agent_id)

    def find_super_agent_for(self, action_sequence: List[str]) -> Optional[VirtualSuperAgent]:
        key = "->".join(action_sequence)
        for vsa in self._super_agents.values():
            if vsa.pattern.name == key:
                return vsa
        return None

    def list_super_agents(self) -> List[Dict]:
        return [vsa.to_dict() for vsa in self._super_agents.values()]

    def get_encapsulator(self) -> SubgraphEncapsulator:
        return self._encapsulator
