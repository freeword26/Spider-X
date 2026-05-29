import hashlib
import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("spider_x.skill_gnn")


@dataclass
class SkillNode:
    skill_id: str
    name: str
    category: str
    embedding: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillEdge:
    source_id: str
    target_id: str
    edge_type: str
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CombinationPath:
    path_id: str
    skills: List[str]
    confidence: float
    path_type: str
    description: str
    discovery_method: str = "gnn"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return asdict(self) if hasattr(self, "__dataclass_fields__") else {
            "path_id": self.path_id, "skills": self.skills,
            "confidence": self.confidence, "path_type": self.path_type,
            "description": self.description, "discovery_method": self.discovery_method,
            "created_at": self.created_at,
        }


class SkillGraph:
    def __init__(self):
        self.nodes: Dict[str, SkillNode] = {}
        self.edges: List[SkillEdge] = []
        self._adjacency: Dict[str, List[Tuple[str, float]]] = defaultdict(list)

    def add_skill(self, skill: SkillNode):
        self.nodes[skill.skill_id] = skill

    def add_edge(self, edge: SkillEdge):
        self.edges.append(edge)
        self._adjacency[edge.source_id].append((edge.target_id, edge.weight))
        self._adjacency[edge.target_id].append((edge.source_id, edge.weight * 0.5))

    def get_neighbors(self, skill_id: str) -> List[Tuple[str, float]]:
        return self._adjacency.get(skill_id, [])

    def find_paths(self, start_id: str, max_depth: int = 3) -> List[List[str]]:
        paths = []
        self._dfs(start_id, [start_id], {start_id}, paths, max_depth)
        return paths

    def _dfs(self, current: str, path: List[str], visited: Set[str], paths: List[List[str]], max_depth: int):
        if len(path) >= 2:
            paths.append(list(path))
        if len(path) >= max_depth:
            return
        for neighbor_id, weight in self._adjacency.get(current, []):
            if neighbor_id not in visited and weight > 0.1:
                visited.add(neighbor_id)
                path.append(neighbor_id)
                self._dfs(neighbor_id, path, visited, paths, max_depth)
                path.pop()
                visited.remove(neighbor_id)

    def compute_similarity(self, skill_a_id: str, skill_b_id: str) -> float:
        node_a = self.nodes.get(skill_a_id)
        node_b = self.nodes.get(skill_b_id)
        if not node_a or not node_b:
            return 0.0
        if node_a.embedding and node_b.embedding:
            return self._cosine_similarity(node_a.embedding, node_b.embedding)
        if node_a.category == node_b.category:
            return 0.5
        return 0.1

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(x * x for x in b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)


class SkillCombinatorGNN:
    def __init__(self):
        self.graph = SkillGraph()
        self._combination_paths: List[CombinationPath] = []
        self._training_history: List[Dict] = []

    def register_skill(self, skill_id: str, name: str, category: str,
                       embedding: Optional[List[float]] = None, metadata: Optional[Dict] = None):
        if embedding is None:
            embedding = self._generate_embedding(skill_id, name, category)
        node = SkillNode(skill_id=skill_id, name=name, category=category, embedding=embedding, metadata=metadata or {})
        self.graph.add_skill(node)
        logger.info(f"Skill registered in GNN graph: {skill_id} ({name})")

    def _generate_embedding(self, skill_id: str, name: str, category: str, dim: int = 16) -> List[float]:
        seed_str = f"{skill_id}:{name}:{category}"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
        import random
        rng = random.Random(seed)
        return [rng.gauss(0, 1) for _ in range(dim)]

    def record_co_occurrence(self, skill_a_id: str, skill_b_id: str, weight: float = 1.0):
        edge = SkillEdge(source_id=skill_a_id, target_id=skill_b_id, edge_type="co_occurrence", weight=weight)
        self.graph.add_edge(edge)

    def record_combination_result(self, skill_ids: List[str], success: bool, context: str = ""):
        self._training_history.append({
            "skills": skill_ids, "success": success, "context": context,
            "timestamp": datetime.now().isoformat(),
        })
        for i in range(len(skill_ids)):
            for j in range(i + 1, len(skill_ids)):
                w = 1.0 if success else -0.5
                self.record_co_occurrence(skill_ids[i], skill_ids[j], w)

    def discover_combinations(self, seed_skill_id: Optional[str] = None, top_k: int = 10) -> List[CombinationPath]:
        paths = []
        seed_nodes = [seed_skill_id] if seed_skill_id else list(self.graph.nodes.keys())
        for sid in seed_nodes:
            if sid not in self.graph.nodes:
                continue
            raw_paths = self.graph.find_paths(sid, max_depth=4)
            for p in raw_paths:
                if len(p) < 2:
                    continue
                confidence = self._score_path(p)
                if confidence > 0.2:
                    path_type = self._classify_path(p)
                    skills_names = [self.graph.nodes.get(s, SkillNode(s, s, "unknown")).name for s in p]
                    desc = self._generate_description(p, skills_names, path_type)
                    combo = CombinationPath(
                        path_id=f"combo-{uuid.uuid4().hex[:8]}",
                        skills=p, confidence=confidence,
                        path_type=path_type, description=desc,
                    )
                    paths.append(combo)
        paths.sort(key=lambda x: x.confidence, reverse=True)
        self._combination_paths = paths
        return paths[:top_k]

    def _score_path(self, path: List[str]) -> float:
        if len(path) < 2:
            return 0.0
        total_sim = 0.0
        count = 0
        for i in range(len(path) - 1):
            sim = self.graph.compute_similarity(path[i], path[i + 1])
            total_sim += sim
            count += 1
        avg_sim = total_sim / max(1, count)
        length_bonus = min(0.3, len(path) * 0.05)
        categories = set()
        for sid in path:
            node = self.nodes.get(sid)
            if node:
                categories.add(node.category)
        category_bonus = 0.1 if len(categories) > 1 else 0.0
        return min(1.0, avg_sim + length_bonus + category_bonus)

    def _classify_path(self, path: List[str]) -> str:
        categories = []
        for sid in path:
            node = self.nodes.get(sid)
            if node:
                categories.append(node.category)
        unique = set(categories)
        if len(unique) == 1:
            return "specialization"
        if "research" in unique and "code" in unique:
            return "research_implementation"
        if "code" in unique and "test" in unique:
            return "development_pipeline"
        if "research" in unique and "language" in unique:
            return "cross_language"
        return "general_combination"

    def _generate_description(self, path: List[str], names: List[str], path_type: str) -> str:
        templates = {
            "specialization": f"深度专业化的 {' → '.join(names)} 组合",
            "research_implementation": f"从研究到实现: {' → '.join(names)}",
            "development_pipeline": f"开发流水线: {' → '.join(names)}",
            "cross_language": f"跨领域组合: {' → '.join(names)}",
            "general_combination": f"技能组合: {' → '.join(names)}",
        }
        return templates.get(path_type, f"组合: {' → '.join(names)}")

    def get_recommendations(self, base_skill_id: str, top_k: int = 5) -> List[Dict]:
        if base_skill_id not in self.graph.nodes:
            return []
        neighbors = self.graph.get_neighbors(base_skill_id)
        scored = []
        for nid, weight in neighbors:
            node = self.nodes.get(nid)
            if node:
                sim = self.graph.compute_similarity(base_skill_id, nid)
                scored.append({"skill_id": nid, "name": node.name, "score": sim * weight})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def get_stats(self) -> Dict:
        return {
            "total_skills": len(self.graph.nodes),
            "total_edges": len(self.graph.edges),
            "discovered_paths": len(self._combination_paths),
            "training_records": len(self._training_history),
            "categories": list(set(n.category for n in self.graph.nodes.values())),
        }
