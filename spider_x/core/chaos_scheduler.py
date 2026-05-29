import asyncio
import heapq
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("spider_x.scheduler")


@dataclass(order=True)
class ScoredAgent:
    score: float
    agent_id: str = field(compare=False)
    tokens: float = field(default=0.0, compare=False)
    capacity_score: float = field(default=0.0, compare=False)
    capability_match: float = field(default=0.0, compare=False)


class TokenBucket:
    def __init__(self, rate: float = 10.0, capacity: float = 100.0):
        self.rate = rate
        self.capacity = capacity
        self.tokens: Dict[str, float] = {}
        self._last_refill: Dict[str, float] = {}

    def _refill(self, agent_id: str):
        now = time.monotonic()
        last = self._last_refill.get(agent_id, now)
        elapsed = now - last
        current = self.tokens.get(agent_id, self.capacity)
        self.tokens[agent_id] = min(self.capacity, current + elapsed * self.rate)
        self._last_refill[agent_id] = now

    def consume(self, agent_id: str, cost: float = 1.0) -> bool:
        self._refill(agent_id)
        current = self.tokens.get(agent_id, 0)
        if current >= cost:
            self.tokens[agent_id] = current - cost
            return True
        return False

    def get_tokens(self, agent_id: str) -> float:
        self._refill(agent_id)
        return self.tokens.get(agent_id, 0)

    def bid(self, agent_id: str, offer: float, cost: float = 1.0) -> bool:
        self._refill(agent_id)
        current = self.tokens.get(agent_id, 0)
        if current >= offer and offer >= cost:
            self.tokens[agent_id] = current - offer
            return True
        return False


class ChaosScheduler:
    def __init__(
        self,
        token_bucket_rate: float = 10.0,
        token_bucket_capacity: float = 100.0,
        enable_bidding: bool = False,
    ):
        self.token_bucket = TokenBucket(rate=token_bucket_rate, capacity=token_bucket_capacity)
        self.enable_bidding = enable_bidding
        self._agent_states: Dict[str, Any] = {}
        self._action_queue: List[Dict] = []
        self._assignments: Dict[str, str] = {}
        self._completed: Set[str] = set()
        self._failed: Set[str] = set()
        self._running = False

    def register_agent(self, agent_id: str, state: Any = None):
        self._agent_states[agent_id] = state
        self.token_bucket.tokens[agent_id] = self.token_bucket.capacity / 2
        self.token_bucket._last_refill[agent_id] = time.monotonic()
        logger.info(f"Agent registered: {agent_id}")

    def deregister_agent(self, agent_id: str):
        self._agent_states.pop(agent_id, None)

    def submit_action(self, action: Dict) -> str:
        action_id = action.get("action_id", f"action-{uuid.uuid4().hex[:8]}")
        action["action_id"] = action_id
        action["status"] = "pending"
        action["submitted_at"] = datetime.now().isoformat()
        self._action_queue.append(action)
        logger.info(f"Action submitted: {action_id}")
        return action_id

    def submit_actions(self, actions: List[Dict]) -> List[str]:
        return [self.submit_action(a) for a in actions]

    def _compute_capability_match(self, agent_state: Any, action: Dict) -> float:
        if not agent_state:
            return 0.5
        required_roles = set(action.get("required_roles", []))
        required_skills = set(action.get("required_skills", []))
        if not required_roles and not required_skills:
            return 1.0
        agent_roles = set()
        agent_skills = set()
        if hasattr(agent_state, "capabilities"):
            caps = agent_state.capabilities
            agent_roles = set(getattr(caps, "roles", []))
            agent_skills = set(getattr(caps, "skills", []))
        elif isinstance(agent_state, dict):
            caps = agent_state.get("capabilities", {})
            agent_roles = set(caps.get("roles", []))
            agent_skills = set(caps.get("skills", []))
        role_match = len(required_roles & agent_roles) / max(1, len(required_roles)) if required_roles else 1.0
        skill_match = len(required_skills & agent_skills) / max(1, len(required_skills)) if required_skills else 1.0
        return role_match * 0.6 + skill_match * 0.4

    def _compute_capacity_score(self, agent_state: Any) -> float:
        if not agent_state:
            return 0.5
        if hasattr(agent_state, "resources"):
            res = agent_state.resources
            cpu_h = max(0, 100 - getattr(res, "cpu_percent", 50))
            mem_h = max(0, 100 - getattr(res, "memory_percent", 50))
            active = getattr(res, "active_tasks", 0)
            max_c = getattr(agent_state, "max_concurrency", 5)
            load_f = max(0, 1.0 - active / max(1, max_c))
            return (cpu_h * 0.35 + mem_h * 0.35 + load_f * 30 * 0.3) / 100
        if isinstance(agent_state, dict):
            res = agent_state.get("resources", {})
            cpu_h = max(0, 100 - res.get("cpu_percent", 50))
            mem_h = max(0, 100 - res.get("memory_percent", 50))
            return (cpu_h + mem_h) / 200
        return 0.5

    def _score_agent(self, agent_id: str, action: Dict) -> float:
        state = self._agent_states.get(agent_id)
        cap_score = self._compute_capacity_score(state)
        cap_match = self._compute_capability_match(state, action)
        token_factor = min(1.0, self.token_bucket.get_tokens(agent_id) / max(1, self.token_bucket.capacity))
        return cap_score * 0.3 + cap_match * 0.5 + token_factor * 0.2

    def _broadcast_and_assign(self, action: Dict) -> Optional[str]:
        candidates = []
        for agent_id, state in self._agent_states.items():
            if state is None:
                continue
            status = getattr(state, "status", None)
            if isinstance(state, dict):
                status = state.get("status")
            if status in ("offline", "draining"):
                continue
            score = self._score_agent(agent_id, action)
            candidates.append(ScoredAgent(
                score=score, agent_id=agent_id,
                tokens=self.token_bucket.get_tokens(agent_id),
                capacity_score=self._compute_capacity_score(state),
                capability_match=self._compute_capability_match(state, action),
            ))
        if not candidates:
            return None
        candidates.sort(key=lambda c: c.score, reverse=True)
        if self.enable_bidding:
            for c in candidates:
                offer = min(c.score * 2, self.token_bucket.get_tokens(c.agent_id))
                if self.token_bucket.bid(c.agent_id, offer=offer, cost=1.0):
                    return c.agent_id
            best = candidates[0]
        else:
            best = candidates[0]
        if self.token_bucket.consume(best.agent_id, 1.0):
            return best.agent_id
        return None

    async def dispatch(self, handlers: Optional[Dict[str, Callable]] = None):
        self._running = True
        while self._running:
            pending = [a for a in self._action_queue if a.get("status") == "pending"]
            if not pending:
                await asyncio.sleep(0.1)
                continue
            for action in pending:
                action_id = action["action_id"]
                deps = action.get("depends_on", [])
                if not all(d in self._completed for d in deps):
                    continue
                failed_deps = [d for d in deps if d in self._failed]
                if failed_deps:
                    action["status"] = "failed"
                    action["error"] = f"Dependency failed: {failed_deps}"
                    self._failed.add(action_id)
                    continue
                assigned = self._broadcast_and_assign(action)
                if assigned:
                    action["status"] = "assigned"
                    action["assigned_agent"] = assigned
                    action["assigned_at"] = datetime.now().isoformat()
                    self._assignments[action_id] = assigned
                else:
                    await asyncio.sleep(0.05)
            await asyncio.sleep(0.05)

    def complete_action(self, action_id: str, result: Any = None):
        for a in self._action_queue:
            if a.get("action_id") == action_id:
                a["status"] = "completed"
                a["result"] = result
                a["completed_at"] = datetime.now().isoformat()
                self._completed.add(action_id)
                return

    def fail_action(self, action_id: str, error: str):
        for a in self._action_queue:
            if a.get("action_id") == action_id:
                a["status"] = "failed"
                a["error"] = error
                self._failed.add(action_id)
                return

    def stop(self):
        self._running = False

    def get_status(self) -> Dict:
        total = len(self._action_queue)
        pending = sum(1 for a in self._action_queue if a.get("status") == "pending")
        assigned = sum(1 for a in self._action_queue if a.get("status") == "assigned")
        return {
            "total_actions": total,
            "pending": pending,
            "assigned": assigned,
            "completed": len(self._completed),
            "failed": len(self._failed),
            "running": self._running,
            "agents": list(self._agent_states.keys()),
            "bidding_enabled": self.enable_bidding,
        }
