"""Spider-X Skill Lock."""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
logger = logging.getLogger("spider_x.skill_lock")
__all__ = ["LOCKSSChecker", "SkillScope", "LockMode", "LockConflict"]

class LockMode:
    READ = "read"; WRITE = "write"; EXCLUSIVE = "exclusive"

_COMPAT = {(LockMode.READ, LockMode.READ): True}
for a in [LockMode.READ, LockMode.WRITE, LockMode.EXCLUSIVE]:
    for b in [LockMode.WRITE, LockMode.EXCLUSIVE]: _COMPAT[(a,b)] = False; _COMPAT[(b,a)] = False
_COMPAT[(LockMode.WRITE, LockMode.WRITE)] = False; _COMPAT[(LockMode.EXCLUSIVE, LockMode.EXCLUSIVE)] = False

@dataclass
class SkillScope:
    skill_id: str; scopes: List[Dict[str, str]]; lock_mode: str = LockMode.READ
    compatible_with: List[str] = field(default_factory=list); conflicts_with: List[str] = field(default_factory=list)
    def to_dict(self) -> Dict: return {"skill_id": self.skill_id, "lock_mode": self.lock_mode}
    def scope_paths(self) -> Set[str]: return {s.get("path", "") for s in self.scopes}

@dataclass
class LockConflict:
    skill_a: str; skill_b: str; conflict_type: str; overlapping_scopes: List[str]; resolution: str = ""
    def to_dict(self) -> Dict: return {"skill_a": self.skill_a, "skill_b": self.skill_b, "conflict_type": self.conflict_type}

class LOCKSSChecker:
    def __init__(self): self._skills: Dict[str, SkillScope] = {}
    def register_skill(self, s: SkillScope): self._skills[s.skill_id] = s
    def check_compatibility(self, a: str, b: str) -> Tuple[bool, Optional[LockConflict]]:
        sa, sb = self._skills.get(a), self._skills.get(b)
        if not sa or not sb: return True, None
        if b in sa.compatible_with: return True, None
        if b in sa.conflicts_with: return False, LockConflict(a, b, "declared", [])
        if not _COMPAT.get((sa.lock_mode, sb.lock_mode), False): return False, LockConflict(a, b, "lock_mode", [])
        ov = self._overlap(sa.scope_paths(), sb.scope_paths())
        if ov and sa.lock_mode != LockMode.READ: return False, LockConflict(a, b, "scope_overlap", list(ov))
        return True, None
    def _overlap(self, a: Set[str], b: Set[str]) -> Set[str]: return {f"{x} ∩ {y}" for x in a for y in b if self._po(x, y)}
    def _po(self, a: str, b: str) -> bool:
        if a == b or a == "*" or b == "*": return True
        na, nb = a.rstrip("/"), b.rstrip("/")
        if na.startswith(nb+"/") or nb.startswith(na+"/"): return True
        pa, pb = na.split("/"), nb.split("/")
        return all(pa[i] == pb[i] or pa[i] == "*" or pb[i] == "*" for i in range(min(len(pa), len(pb))))
    def check_combination(self, ids: List[str]) -> Tuple[bool, List[LockConflict]]:
        cs = []
        for i in range(len(ids)):
            for j in range(i+1, len(ids)):
                ok, c = self.check_compatibility(ids[i], ids[j])
                if not ok and c: cs.append(c)
        return len(cs) == 0, cs
    def resolve_conflicts(self, cs: List[LockConflict]) -> List[Dict]:
        return [{"conflict": f"{c.skill_a} ↔ {c.skill_b}", "strategy": "serialize" if c.conflict_type == "scope_overlap" else "upgrade" if c.conflict_type == "lock_mode" else "forbid"} for c in cs]
    def get_stats(self) -> Dict:
        n = len(self._skills); ids = list(self._skills.keys())
        return {"total_skills": n, "conflicts": sum(1 for i in range(n) for j in range(i+1,n) if not self.check_compatibility(ids[i],ids[j])[0])}
