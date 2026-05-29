"""Spider-X credential chain for task audit trails."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

DEFAULT_SECRET = "worker-cluster-credential-secret-v1"


@dataclass
class CredentialEntry:
    entry_id: str
    step_index: int
    action: str
    input_hash: str
    output_digest: str
    timestamp: str
    signature: str
    prev_hash: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict:
        d = asdict(self)
        if d["metadata"] is None:
            del d["metadata"]
        if d["prev_hash"] is None:
            del d["prev_hash"]
        return d

    def compute_hash(self) -> str:
        payload = f"{self.entry_id}:{self.step_index}:{self.action}:{self.input_hash}:{self.output_digest}:{self.timestamp}"
        if self.prev_hash:
            payload += f":{self.prev_hash}"
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class CredentialChain:
    chain_id: str
    task_id: str
    task_type: str
    entries: List[CredentialEntry] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    _secret: str = field(default=DEFAULT_SECRET, repr=False)

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def chain_hash(self) -> str:
        if not self.entries:
            return hashlib.sha256(self.chain_id.encode()).hexdigest()
        return self.entries[-1].compute_hash()

    def add_entry(
        self,
        action: str,
        input_data: Any,
        output_data: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CredentialEntry:
        step_index = len(self.entries)
        entry_id = f"cred-{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now().isoformat()
        input_hash = hashlib.sha256(
            json.dumps(input_data, sort_keys=True, default=str).encode()
        ).hexdigest()
        output_str = json.dumps(output_data, sort_keys=True, default=str)[:200]
        output_digest = hashlib.sha256(output_str.encode()).hexdigest()
        prev_hash = self.entries[-1].compute_hash() if self.entries else None
        payload = f"{entry_id}:{step_index}:{action}:{input_hash}:{output_digest}:{timestamp}"
        if prev_hash:
            payload += f":{prev_hash}"
        signature = hmac.new(
            self._secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        entry = CredentialEntry(
            entry_id=entry_id, step_index=step_index, action=action,
            input_hash=input_hash, output_digest=output_digest, timestamp=timestamp,
            signature=signature, prev_hash=prev_hash, metadata=metadata,
        )
        self.entries.append(entry)
        return entry

    def verify(self) -> bool:
        for i, entry in enumerate(self.entries):
            payload = f"{entry.entry_id}:{entry.step_index}:{entry.action}:{entry.input_hash}:{entry.output_digest}:{entry.timestamp}"
            if entry.prev_hash:
                payload += f":{entry.prev_hash}"
            expected_sig = hmac.new(
                self._secret.encode(), payload.encode(), hashlib.sha256
            ).hexdigest()
            if entry.signature != expected_sig:
                return False
            if i > 0:
                expected_prev = self.entries[i - 1].compute_hash()
                if entry.prev_hash != expected_prev:
                    return False
        return True

    def complete(self):
        self.completed_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            "chain_id": self.chain_id, "version": self.version, "task_id": self.task_id,
            "task_type": self.task_type, "entries": [e.to_dict() for e in self.entries],
            "created_at": self.created_at, "completed_at": self.completed_at,
            "chain_hash": self.chain_hash,
        }

    def summary(self) -> Dict:
        return {
            "chain_id": self.chain_id, "task_id": self.task_id, "task_type": self.task_type,
            "total_steps": len(self.entries), "created_at": self.created_at,
            "completed_at": self.completed_at, "chain_hash": self.chain_hash,
            "verified": self.verify(),
        }


class CredentialChainManager:
    def __init__(self, secret: str = DEFAULT_SECRET):
        self._chains: Dict[str, CredentialChain] = {}
        self._secret = secret

    def create_chain(self, task_id: str, task_type: str) -> CredentialChain:
        chain_id = f"chain-{uuid.uuid4().hex[:12]}"
        chain = CredentialChain(
            chain_id=chain_id, task_id=task_id, task_type=task_type, _secret=self._secret,
        )
        self._chains[chain_id] = chain
        return chain

    def get_chain(self, chain_id: str) -> Optional[CredentialChain]:
        return self._chains.get(chain_id)

    def get_chain_by_task(self, task_id: str) -> Optional[CredentialChain]:
        for chain in self._chains.values():
            if chain.task_id == task_id:
                return chain
        return None

    def list_chains(self) -> List[Dict]:
        return [chain.summary() for chain in self._chains.values()]

    def verify_chain(self, chain_id: str) -> bool:
        chain = self._chains.get(chain_id)
        if not chain:
            return False
        return chain.verify()


__all__ = [
    "CredentialChainManager",
    "CredentialChain",
    "CredentialEntry",
    "DEFAULT_SECRET",
]
