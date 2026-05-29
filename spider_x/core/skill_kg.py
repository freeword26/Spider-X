"""Spider-X Skill Knowledge Graph."""
from __future__ import annotations
import json, logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional
logger = logging.getLogger("spider_x.skill_kg")
__all__ = ["SkillKnowledgeGraph", "KGNode", "KGEdge"]

@dataclass
class KGNode:
    node_id: str; label: str; name: str; properties: Dict = field(default_factory=dict)

@dataclass
class KGEdge:
    source_id: str; target_id: str; relation: str; properties: Dict = field(default_factory=dict); weight: float = 1.0

class SkillKnowledgeGraph:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", pwd="password"):
        self.uri, self.user, self.pwd, self._neo4j = uri, user, pwd, False
        self._nodes, self._edges, self._adj = {}, [], defaultdict(list)
        try:
            from neo4j import GraphDatabase; self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.pwd)); self._neo4j = True
        except (ImportError, Exception) as e: logger.info(f"Neo4j not available: {e}")
    def add_skill(self, sid, name, props=None) -> KGNode:
        n = KGNode(sid, "Skill", name, props or {}); self._nodes[sid] = n
        if self._neo4j:
            try:
                with self._driver.session() as s: s.run("MERGE (n:Skill {id: $id}) SET n.name = $name", id=sid, name=name)
            except Exception: pass
        return n
    def register_complement(self, a, b, ev=""): e=KGEdge(a,b,"COMPLEMENT",{"evidence":ev}); self._edges.append(e); self._adj[a].append(e)
    def register_conflict(self, a, b, r=""): e=KGEdge(a,b,"CONFLICT",{"reason":r}); self._edges.append(e); self._adj[a].append(e)
    def query_skill(self, sid):
        n = self._nodes.get(sid)
        if not n: return None
        rs = [{"target":e.target_id,"target_name":self._nodes.get(e.target_id,KGNode(e.target_id,"Unknown","unknown")).name,"relation":e.relation} for e in self._adj.get(sid,[])]
        return {"node":{"id":n.node_id,"name":n.name},"relations":rs}
    def find_conflicts(self) -> List[Dict]:
        return [{"a":self._nodes.get(e.source_id,KGNode(e.source_id,"","")).name or e.source_id,"b":self._nodes.get(e.target_id,KGNode(e.target_id,"","")).name or e.target_id,"reason":e.properties.get("reason","")} for e in self._edges if e.relation=="CONFLICT"]
    def find_complements(self) -> List[Dict]:
        return [{"a":self._nodes.get(e.source_id,KGNode(e.source_id,"","")).name or e.source_id,"b":self._nodes.get(e.target_id,KGNode(e.target_id,"","")).name or e.target_id} for e in self._edges if e.relation=="COMPLEMENT"]
    def get_stats(self) -> Dict:
        return {"nodes":len(self._nodes),"edges":len(self._edges),"conflicts":sum(1 for e in self._edges if e.relation=="CONFLICT"),"complements":sum(1 for e in self._edges if e.relation=="COMPLEMENT")}
    def export_cypher(self) -> List[str]:
        return [f"CREATE (n:{n.label} {{id: '{n.node_id}', name: '{n.name}'}})" for n in self._nodes.values()] + [f"MATCH (a {{id: '{e.source_id}'}}), (b {{id: '{e.target_id}'}}) CREATE (a)-[:{e.relation}]->(b)" for e in self._edges]
    def close(self):
        if hasattr(self,"_driver") and self._driver: self._driver.close()
