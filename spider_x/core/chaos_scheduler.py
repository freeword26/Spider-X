"""Spider-X Chaos Scheduler."""
from __future__ import annotations
import asyncio, logging, time, uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
logger = logging.getLogger("spider_x.scheduler")
__all__ = ["ChaosScheduler", "TokenBucket", "ScoredAgent"]

@dataclass(order=True)
class ScoredAgent:
    score: float
    agent_id: str = field(compare=False)

class TokenBucket:
    def __init__(self, rate: float = 10.0, capacity: float = 100.0):
        self.rate, self.capacity = rate, capacity
        self.tokens: Dict[str, float] = {}
        self._last_refill: Dict[str, float] = {}
    def _refill(self, aid: str):
        now = time.monotonic()
        self.tokens[aid] = min(self.capacity, self.tokens.get(aid, self.capacity) + (now - self._last_refill.get(aid, now)) * self.rate)
        self._last_refill[aid] = now
    def consume(self, aid: str, cost: float = 1.0) -> bool:
        self._refill(aid)
        if self.tokens.get(aid, 0) >= cost: self.tokens[aid] -= cost; return True
        return False
    def get_tokens(self, aid: str) -> float: self._refill(aid); return self.tokens.get(aid, 0)
    def bid(self, aid: str, offer: float, cost: float = 1.0) -> bool:
        self._refill(aid)
        if self.tokens.get(aid, 0) >= offer >= cost: self.tokens[aid] -= offer; return True
        return False

class ChaosScheduler:
    def __init__(self, token_bucket_rate: float = 10.0, enable_bidding: bool = False):
        self.token_bucket = TokenBucket(rate=token_bucket_rate)
        self.enable_bidding, self._running = enable_bidding, False
        self._agent_states: Dict[str, Any] = {}
        self._action_queue: List[Dict] = []
        self._completed, self._failed = set(), set()
    def register_agent(self, aid: str, state: Any = None):
        self._agent_states[aid] = state; self.token_bucket.tokens[aid] = self.token_bucket.capacity / 2; self.token_bucket._last_refill[aid] = time.monotonic()
    def deregister_agent(self, aid: str): self._agent_states.pop(aid, None)
    def submit_action(self, action: Dict) -> str:
        aid = action.get("action_id", f"action-{uuid.uuid4().hex[:8]}"); action["action_id"] = aid; action["status"] = "pending"; self._action_queue.append(action); return aid
    def _score_agent(self, aid: str, action: Dict) -> float:
        state = self._agent_states.get(aid)
        return min(1.0, self.token_bucket.get_tokens(aid) / max(1, self.token_bucket.capacity)) * 0.5 + (0.5 if state else 0.3)
    def _broadcast_and_assign(self, action: Dict) -> Optional[str]:
        cands = [ScoredAgent(score=self._score_agent(aid, action), agent_id=aid) for aid, s in self._agent_states.items() if s is not None and getattr(s, "status", None) not in ("offline","draining")]
        if not cands: return None
        best = max(cands, key=lambda c: c.score)
        return best.agent_id if self.token_bucket.consume(best.agent_id, 1.0) else None
    async def dispatch(self, handlers: Optional[Dict] = None):
        self._running = True
        while self._running:
            for a in self._action_queue:
                if a.get("status") != "pending": continue
                deps = a.get("depends_on", [])
                if not all(d in self._completed for d in deps): continue
                if any(d in self._failed for d in deps): a["status"] = "failed"; self._failed.add(a["action_id"]); continue
                assigned = self._broadcast_and_assign(a)
                if assigned: a["status"] = "assigned"; a["assigned_agent"] = assigned
            await asyncio.sleep(0.05)
    def complete_action(self, aid: str, result: Any = None):
        for a in self._action_queue:
            if a.get("action_id") == aid: a["status"] = "completed"; self._completed.add(aid); return
    def fail_action(self, aid: str, error: str):
        for a in self._action_queue:
            if a.get("action_id") == aid: a["status"] = "failed"; self._failed.add(aid); return
    def stop(self): self._running = False
    def get_status(self) -> Dict:
        return {"total_actions": len(self._action_queue), "completed": len(self._completed), "failed": len(self._failed), "running": self._running}
