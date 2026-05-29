import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("worker-cluster.skill_lock")


class LockMode:
    READ = "read"
    WRITE = "write"
    EXCLUSIVE = "exclusive"


COMPATIBILITY_MATRIX = {
    (LockMode.READ, LockMode.READ): True,
    (LockMode.READ, LockMode.WRITE): False,
    (LockMode.READ, LockMode.EXCLUSIVE): False,
    (LockMode.WRITE, LockMode.READ): False,
    (LockMode.WRITE, LockMode.WRITE): False,
    (LockMode.WRITE, LockMode.EXCLUSIVE): False,
    (LockMode.EXCLUSIVE, LockMode.READ): False,
    (LockMode.EXCLUSIVE, LockMode.WRITE): False,
    (LockMode.EXCLUSIVE, LockMode.EXCLUSIVE): False,
}


@dataclass
class SkillScope:
    skill_id: str
    scopes: List[Dict[str, str]]
    lock_mode: str = LockMode.READ
    compatible_with: List[str] = field(default_factory=list)
    conflicts_with: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

    def scope_paths(self) -> Set[str]:
        return {s.get("path", "") for s in self.scopes}

    def scope_types(self) -> Set[str]:
        return {s.get("type", "") for s in self.scopes}


@dataclass
class LockConflict:
    skill_a: str
    skill_b: str
    conflict_type: str
    overlapping_scopes: List[str]
    resolution: str = ""


class LOCKSSChecker:
    def __init__(self):
        self._skills: Dict[str, SkillScope] = {}
        self._active_locks: Dict[str, str] = {}

    def register_skill(self, skill: SkillScope):
        self._skills[skill.skill_id] = skill
        logger.info(f"Skill registered for lock checking: {skill.skill_id}")

    def check_compatibility(self, skill_a_id: str, skill_b_id: str) -> Tuple[bool, Optional[LockConflict]]:
        skill_a = self._skills.get(skill_a_id)
        skill_b = self._skills.get(skill_b_id)
        if not skill_a or not skill_b:
            return True, None

        if skill_b_id in skill_a.compatible_with:
            return True, None
        if skill_b_id in skill_a.conflicts_with:
            conflict = LockConflict(
                skill_a=skill_a_id, skill_b=skill_b_id,
                conflict_type="declared",
                overlapping_scopes=[],
                resolution=f"Explicit conflict declared between {skill_a_id} and {skill_b_id}",
            )
            return False, conflict

        mode_a = skill_a.lock_mode
        mode_b = skill_b.lock_mode
        modes_compatible = COMPATIBILITY_MATRIX.get((mode_a, mode_b), False)
        if not modes_compatible:
            conflict = LockConflict(
                skill_a=skill_a_id, skill_b=skill_b_id,
                conflict_type="lock_mode",
                overlapping_scopes=[],
                resolution=f"Incompatible lock modes: {mode_a} vs {mode_b}",
            )
            return False, conflict

        paths_a = skill_a.scope_paths()
        paths_b = skill_b.scope_paths()
        overlap = self._check_path_overlap(paths_a, paths_b)
        if overlap and mode_a != LockMode.READ:
            conflict = LockConflict(
                skill_a=skill_a_id, skill_b=skill_b_id,
                conflict_type="scope_overlap",
                overlapping_scopes=list(overlap),
                resolution=f"Scope overlap with {mode_a}/{mode_b} lock modes",
            )
            return False, conflict
        if overlap and mode_b != LockMode.READ:
            conflict = LockConflict(
                skill_a=skill_a_id, skill_b=skill_b_id,
                conflict_type="scope_overlap",
                overlapping_scopes=list(overlap),
                resolution="Scope overlap with non-read lock",
            )
            return False, conflict

        return True, None

    def _check_path_overlap(self, paths_a: Set[str], paths_b: Set[str]) -> Set[str]:
        overlap = set()
        for pa in paths_a:
            for pb in paths_b:
                if self._paths_overlap(pa, pb):
                    overlap.add(f"{pa} ∩ {pb}")
        return overlap

    def _paths_overlap(self, path_a: str, path_b: str) -> bool:
        if path_a == path_b:
            return True
        if path_a == "*" or path_b == "*":
            return True
        norm_a = path_a.rstrip("/")
        norm_b = path_b.rstrip("/")
        if norm_a.startswith(norm_b + "/") or norm_b.startswith(norm_a + "/"):
            return True
        parts_a = norm_a.split("/")
        parts_b = norm_b.split("/")
        for i in range(min(len(parts_a), len(parts_b))):
            if parts_a[i] != parts_b[i] and parts_a[i] != "*" and parts_b[i] != "*":
                return False
        return True

    def check_combination(self, skill_ids: List[str]) -> Tuple[bool, List[LockConflict]]:
        conflicts = []
        for i in range(len(skill_ids)):
            for j in range(i + 1, len(skill_ids)):
                compatible, conflict = self.check_compatibility(skill_ids[i], skill_ids[j])
                if not compatible and conflict:
                    conflicts.append(conflict)
        return len(conflicts) == 0, conflicts

    def resolve_conflicts(self, conflicts: List[LockConflict]) -> List[Dict]:
        resolutions = []
        for c in conflicts:
            if c.conflict_type == "scope_overlap":
                resolutions.append({
                    "conflict": f"{c.skill_a} ↔ {c.skill_b}",
                    "strategy": "serialize",
                    "detail": "Serialize access to overlapping scopes",
                })
            elif c.conflict_type == "lock_mode":
                resolutions.append({
                    "conflict": f"{c.skill_a} ↔ {c.skill_b}",
                    "strategy": "upgrade",
                    "detail": "Downgrade write locks to read where possible",
                })
            elif c.conflict_type == "declared":
                resolutions.append({
                    "conflict": f"{c.skill_a} ↔ {c.skill_b}",
                    "strategy": "forbid",
                    "detail": "Explicitly declared conflict — these skills cannot coexist",
                })
        return resolutions

    def get_skill_scopes(self) -> Dict[str, Dict]:
        return {sid: skill.to_dict() for sid, skill in self._skills.items()}

    def get_stats(self) -> Dict:
        n = len(self._skills)
        max_pairs = n * (n - 1) // 2 if n > 1 else 0
        conflicts = 0
        for i, sid_a in enumerate(self._skills):
            for sid_b in list(self._skills.keys())[i + 1:]:
                ok, _ = self.check_compatibility(sid_a, sid_b)
                if not ok:
                    conflicts += 1
        return {
            "total_skills": n,
            "max_pairs": max_pairs,
            "conflicts": conflicts,
            "compatible_pairs": max_pairs - conflicts,
        }
