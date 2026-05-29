"""Spider-X Skill GNN."""
from __future__ import annotations
import hashlib, logging, uuid, random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
logger = logging.getLogger("spider_x.skill_gnn")
__all__ = ["SkillCombinatorGNN", "SkillGraph", "CombinationPath"]

@dataclass
class SkillNode:
    skill_id: str; name: str; category: str; embedding: List[float] = field(default_factory=list)

@dataclass
class SkillEdge:
    source_id: str; target_id: str; weight: float = 1.0

@dataclass
class CombinationPath:
    path_id: str; skills: List[str]; confidence: float; path_type: str; description: str
    discovery_method: str = "gnn"; created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    def to_dict(self) -> Dict: return {"path_id": self.path_id, "skills": self.skills, "confidence": self.confidence, "path_type": self.path_type, "description": self.description}

class SkillGraph:
    def __init__(self): self.nodes, self.edges, self._adj = {}, [], defaultdict(list)
    def add_skill(self, s: SkillNode): self.nodes[s.skill_id] = s
    def add_edge(self, e: SkillEdge): self.edges.append(e); self._adj[e.source_id].append((e.target_id, e.weight)); self._adj[e.target_id].append((e.target_id, e.weight*0.5))
    def get_neighbors(self, sid: str) -> List[tuple]: return self._adj.get(sid, [])
    def find_paths(self, start: str, max_d: int = 3) -> List[List[str]]: ps = []; self._dfs(start, [start], {start}, ps, max_d); return ps
    def _dfs(self, cur, path, vis, ps, md):
        if len(path) >= 2: ps.append(list(path))
        if len(path) >= md: return
        for nid, w in self._adj.get(cur, []):
            if nid not in vis and w > 0.1: vis.add(nid); path.append(nid); self._dfs(nid, path, vis, ps, md); path.pop(); vis.remove(nid)
    def compute_similarity(self, a: str, b: str) -> float:
        na, nb = self.nodes.get(a), self.nodes.get(b)
        if not na or not nb: return 0.0
        if na.embedding and nb.embedding:
            d = sum(x*y for x,y in zip(na.embedding,nb.embedding)); ma=sum(x*x for x in na.embedding)**0.5; mb=sum(x*x for x in nb.embedding)**0.5
            return d/(ma*mb) if ma and mb else 0.0
        return 0.5 if na.category == nb.category else 0.1

class SkillCombinatorGNN:
    def __init__(self): self.graph=SkillGraph(); self._paths, self._hist = [], []
    def register_skill(self, sid, name, cat, emb=None, meta=None):
        if emb is None: seed=int(hashlib.md5(f"{sid}:{name}:{cat}".encode()).hexdigest()[:8],16); rng=random.Random(seed); emb=[rng.gauss(0,1) for _ in range(16)]
        self.graph.add_skill(SkillNode(sid, name, cat, emb))
    def record_co_occurrence(self, a, b, w=1.0): self.graph.add_edge(SkillEdge(a, b, w))
    def record_combination_result(self, ids, ok, ctx=""):
        self._hist.append({"skills":ids,"success":ok})
        for i in range(len(ids)):
            for j in range(i+1,len(ids)): self.record_co_occurrence(ids[i],ids[j],1.0 if ok else -0.5)
    def discover_combinations(self, seed=None, top_k=10):
        ps=[]
        for sid in ([seed] if seed else list(self.graph.nodes.keys())):
            if sid not in self.graph.nodes: continue
            for p in self.graph.find_paths(sid, 4):
                if len(p)<2: continue
                c=self._score(p)
                if c>0.2:
                    ns=[self.graph.nodes.get(s,SkillNode(s,s,"unknown")).name for s in p]; pt=self._classify(p)
                    ps.append(CombinationPath(f"combo-{uuid.uuid4().hex[:8]}",p,c,pt," → ".join(ns)))
        ps.sort(key=lambda x:x.confidence,reverse=True); self._paths=ps; return ps[:top_k]
    def _score(self, p):
        if len(p)<2: return 0.0
        t=sum(self.graph.compute_similarity(p[i],p[i+1]) for i in range(len(p)-1)); return min(1.0,t/(len(p)-1)+min(0.3,len(p)*0.05))
    def _classify(self, p):
        c=set(self.graph.nodes[s].category for s in p if s in self.graph.nodes)
        if len(c)==1: return "specialization"
        if "research" in c and "code" in c: return "research_implementation"
        if "code" in c and "test" in c: return "development_pipeline"
        return "general_combination"
    def get_recommendations(self, sid, top_k=5):
        if sid not in self.graph.nodes: return []
        s=[{"skill_id":n,"name":self.graph.nodes[n].name,"score":self.graph.compute_similarity(sid,n)*w} for n,w in self.graph.get_neighbors(sid) if n in self.graph.nodes]
        s.sort(key=lambda x:x["score"],reverse=True); return s[:top_k]
    def get_stats(self) -> Dict: return {"skills":len(self.graph.nodes),"edges":len(self.graph.edges),"paths":len(self._paths)}
