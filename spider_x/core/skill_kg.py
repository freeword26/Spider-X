import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("worker-cluster.skill_kg")


@dataclass
class KGNode:
    node_id: str
    label: str
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class KGEdge:
    source_id: str
    target_id: str
    relation: str
    properties: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0


class SkillKnowledgeGraph:
    def __init__(self, neo4j_uri: str = "bolt://neo4j:7687"):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = "neo4j"
        self.neo4j_password = "password"
        self._nodes: Dict[str, KGNode] = {}
        self._edges: List[KGEdge] = []
        self._adjacency: Dict[str, List[KGEdge]] = defaultdict(list)
        self._neo4j_available = False
        self._try_connect()

    def _try_connect(self):
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
            )
            self._neo4j_available = True
            logger.info("Neo4j connected")
        except ImportError:
            logger.info("Neo4j driver not installed, using in-memory mode")
        except Exception as e:
            logger.warning(f"Neo4j connection failed: {e}, using in-memory mode")

    def add_skill(self, skill_id: str, name: str, properties: Optional[Dict] = None) -> KGNode:
        node = KGNode(node_id=skill_id, label="Skill", name=name, properties=properties or {})
        self._nodes[skill_id] = node
        self._persist_node(node)
        return node

    def add_combination_path(self, path_id: str, skill_ids: List[str], path_type: str,
                             confidence: float, description: str = "") -> KGNode:
        node = KGNode(
            node_id=path_id, label="CombinationPath",
            name=f"combo-{path_id}",
            properties={"path_type": path_type, "confidence": confidence, "description": description},
        )
        self._nodes[path_id] = node
        for sid in skill_ids:
            if sid in self._nodes:
                edge = KGEdge(source_id=path_id, target_id=sid, relation="CONTAINS")
                self._edges.append(edge)
                self._adjacency[path_id].append(edge)
        self._persist_node(node)
        return node

    def add_overlap(self, skill_a_id: str, skill_b_id: str, overlap_type: str,
                    shared_scopes: Optional[List[str]] = None, weight: float = 1.0):
        edge = KGEdge(
            source_id=skill_a_id, target_id=skill_b_id,
            relation=f"OVERLAP_{overlap_type.upper()}",
            properties={"shared_scopes": shared_scopes or [], "overlap_type": overlap_type},
            weight=weight,
        )
        self._edges.append(edge)
        self._adjacency[skill_a_id].append(edge)
        self._persist_edge(edge)

    def register_complement(self, skill_a_id: str, skill_b_id: str, evidence: str = ""):
        edge = KGEdge(
            source_id=skill_a_id, target_id=skill_b_id,
            relation="COMPLEMENT",
            properties={"evidence": evidence},
        )
        self._edges.append(edge)
        self._adjacency[skill_a_id].append(edge)

    def register_redundancy(self, skill_a_id: str, skill_b_id: str, overlap_degree: float = 0.5):
        edge = KGEdge(
            source_id=skill_a_id, target_id=skill_b_id,
            relation="REDUNDANT",
            properties={"overlap_degree": overlap_degree},
        )
        self._edges.append(edge)
        self._adjacency[skill_a_id].append(edge)

    def register_conflict(self, skill_a_id: str, skill_b_id: str, reason: str = ""):
        edge = KGEdge(
            source_id=skill_a_id, target_id=skill_b_id,
            relation="CONFLICT",
            properties={"reason": reason},
        )
        self._edges.append(edge)
        self._adjacency[skill_a_id].append(edge)

    def query_skill(self, skill_id: str) -> Optional[Dict]:
        node = self._nodes.get(skill_id)
        if not node:
            return None
        edges = self._adjacency.get(skill_id, [])
        relations = []
        for e in edges:
            relations.append({
                "target": e.target_id,
                "target_name": self._nodes.get(e.target_id, KGNode(e.target_id, "Unknown", "unknown")).name,
                "relation": e.relation,
                "weight": e.weight,
            })
        reverse_targets = [e for e in self._edges if e.target_id == skill_id]
        for e in reverse_targets:
            relations.append({
                "source": e.source_id,
                "source_name": self._nodes.get(e.source_id, KGNode(e.source_id, "Unknown", "unknown")).name,
                "relation": f"REVERSE_{e.relation}",
                "weight": e.weight,
            })
        return {
            "node": {"id": node.node_id, "name": node.name, "label": node.label, "properties": node.properties},
            "relations": relations,
        }

    def find_combinations_containing(self, skill_id: str) -> List[Dict]:
        results = []
        for edge in self._edges:
            if edge.target_id == skill_id and edge.relation == "CONTAINS":
                node = self._nodes.get(edge.source_id)
                if node:
                    results.append({
                        "combination_id": node.node_id,
                        "name": node.name,
                        "path_type": node.properties.get("path_type", "unknown"),
                        "confidence": node.properties.get("confidence", 0),
                    })
        return results

    def find_conflicts(self) -> List[Dict]:
        conflicts = []
        for edge in self._edges:
            if edge.relation == "CONFLICT":
                source = self._nodes.get(edge.source_id)
                target = self._nodes.get(edge.target_id)
                conflicts.append({
                    "skill_a": source.name if source else edge.source_id,
                    "skill_b": target.name if target else edge.target_id,
                    "reason": edge.properties.get("reason", ""),
                })
        return conflicts

    def find_complements(self) -> List[Dict]:
        complements = []
        for edge in self._edges:
            if edge.relation == "COMPLEMENT":
                source = self._nodes.get(edge.source_id)
                target = self._nodes.get(edge.target_id)
                complements.append({
                    "skill_a": source.name if source else edge.source_id,
                    "skill_b": target.name if target else edge.target_id,
                    "evidence": edge.properties.get("evidence", ""),
                })
        return complements

    def get_subgraph(self, skill_ids: List[str]) -> Dict:
        nodes = []
        edges = []
        for sid in skill_ids:
            node = self._nodes.get(sid)
            if node:
                nodes.append({"id": node.node_id, "name": node.name, "label": node.label})
        for e in self._edges:
            if e.source_id in skill_ids or e.target_id in skill_ids:
                edges.append({
                    "source": e.source_id, "target": e.target_id,
                    "relation": e.relation, "weight": e.weight,
                })
        return {"nodes": nodes, "edges": edges}

    def get_stats(self) -> Dict:
        skill_count = sum(1 for n in self._nodes.values() if n.label == "Skill")
        combo_count = sum(1 for n in self._nodes.values() if n.label == "CombinationPath")
        conflict_count = sum(1 for e in self._edges if e.relation == "CONFLICT")
        complement_count = sum(1 for e in self._edges if e.relation == "COMPLEMENT")
        redundancy_count = sum(1 for e in self._edges if e.relation == "REDUNDANT")
        return {
            "total_nodes": len(self._nodes),
            "skill_nodes": skill_count,
            "combination_nodes": combo_count,
            "total_edges": len(self._edges),
            "conflicts": conflict_count,
            "complements": complement_count,
            "redundancies": redundancy_count,
        }

    def export_cypher(self) -> List[str]:
        statements = []
        for node in self._nodes.values():
            props = json.dumps(node.properties, ensure_ascii=False)
            statements.append(
                f"CREATE (n:{node.label} {{id: '{node.node_id}', name: '{node.name}', properties: '{props}'}})"
            )
        for edge in self._edges:
            props = json.dumps(edge.properties, ensure_ascii=False)
            statements.append(
                f"MATCH (a {{id: '{edge.source_id}'}}), (b {{id: '{edge.target_id}'}}) "
                f"CREATE (a)-[:{edge.relation} {{weight: {edge.weight}, properties: '{props}'}}]->(b)"
            )
        return statements

    def _persist_node(self, node: KGNode):
        if not self._neo4j_available or not hasattr(self, "_driver"):
            return
        try:
            with self._driver.session() as session:
                session.run(
                    f"MERGE (n:{node.label} {{id: $id}}) SET n.name = $name, n.properties = $props",
                    id=node.node_id, name=node.name, props=json.dumps(node.properties),
                )
        except Exception as e:
            logger.error(f"Neo4j persist node failed: {e}")

    def _persist_edge(self, edge: KGEdge):
        if not self._neo4j_available or not hasattr(self, "_driver"):
            return
        try:
            with self._driver.session() as session:
                session.run(
                    f"MATCH (a {{id: $sid}}), (b {{id: $tid}}) "
                    f"MERGE (a)-[r:{edge.relation}]->(b) SET r.weight = $w, r.properties = $p",
                    sid=edge.source_id, tid=edge.target_id, w=edge.weight,
                    p=json.dumps(edge.properties),
                )
        except Exception as e:
            logger.error(f"Neo4j persist edge failed: {e}")

    def close(self):
        if hasattr(self, "_driver") and self._driver:
            self._driver.close()

