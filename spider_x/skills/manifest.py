"""Spider-X Skill Manifest."""
from __future__ import annotations
import json, logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List
logger = logging.getLogger("spider_x.skills")
__all__ = ["SkillManifest", "load_skill_manifest", "validate_manifest", "discover_skills"]

@dataclass
class SkillManifest:
    skill_id: str; name: str; version: str = "1.0.0"; category: str = "general"
    description: str = ""; author: str = ""; entry_point: str = ""
    dependencies: List[str] = field(default_factory=list)
    compatible_spiders: List[str] = field(default_factory=lambda: ["*"])
    config_schema: Dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> Dict: return {"skill_id": self.skill_id, "name": self.name, "category": self.category, "compatible_spiders": self.compatible_spiders}

def load_skill_manifest(path: str) -> SkillManifest:
    p = Path(path)
    if not p.exists(): raise FileNotFoundError(path)
    with open(p, "r", encoding="utf-8") as f: data = json.load(f)
    return SkillManifest(**{k: v for k, v in data.items() if k in SkillManifest.__dataclass_fields__})

def validate_manifest(m: SkillManifest) -> List[str]:
    e = []
    if not m.skill_id: e.append("skill_id required")
    if not m.name: e.append("name required")
    return e

def discover_skills(directory: str) -> List[SkillManifest]:
    ms = []; d = Path(directory)
    if not d.exists(): return ms
    for f in d.glob("**/*.json"):
        try:
            m = load_skill_manifest(str(f))
            if not validate_manifest(m): ms.append(m)
        except Exception as e: logger.warning(f"Failed {f}: {e}")
    return ms
