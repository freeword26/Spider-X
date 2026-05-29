"""Spider-X Application Factory."""
from __future__ import annotations
import logging, uuid
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from spider_x.core.config import SpiderXConfig
from spider_x.core.credential_chain import CredentialChainManager
from spider_x.core.sop_engine import SOPEngine
from spider_x.core.resource_state import ResourceStateService
from spider_x.core.atomic_action import TaskDecomposer
from spider_x.core.chaos_scheduler import ChaosScheduler
from spider_x.core.subgraph import SubgraphEncapsulator, VirtualSuperAgentManager
from spider_x.core.plugin import PluginManager, PluginManifest
from spider_x.core.skill_lock import LOCKSSChecker, SkillScope
from spider_x.core.skill_gnn import SkillCombinatorGNN
from spider_x.core.skill_kg import SkillKnowledgeGraph
logger = logging.getLogger("spider_x.app")

def create_app(config: Optional[SpiderXConfig] = None) -> FastAPI:
    cfg = config or SpiderXConfig()
    logging.basicConfig(level=getattr(logging, cfg.log_level.upper(), logging.INFO), format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    cred_mgr = CredentialChainManager(secret=cfg.credential_secret or "")
    sop = SOPEngine(credential_manager=cred_mgr)
    res = ResourceStateService()
    dec = TaskDecomposer()
    sched = ChaosScheduler(enable_bidding=cfg.enable_bidding)
    subg = SubgraphEncapsulator()
    vsa = VirtualSuperAgentManager(subg)
    plug = PluginManager(plugin_dir=cfg.plugin_dir)
    slock = LOCKSSChecker()
    sgnn = SkillCombinatorGNN()
    skg = SkillKnowledgeGraph(neo4j_uri=cfg.neo4j_uri, neo4j_user=cfg.neo4j_user, neo4j_password=cfg.neo4j_password)
    import os
    wuip = cfg.webui_path if cfg.webui_path and os.path.isdir(cfg.webui_path) else None
    from spider_x.core.task import registry, Task, TaskPriority, TaskStatus

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Spider-X starting"); yield; sched.stop(); logger.info("Spider-X stopped")

    app = FastAPI(title="Spider-X", version="1.0.0", description="蜘蛛群 - Worker智能体集群引擎", lifespan=lifespan)

    if wuip:
        from fastapi.staticfiles import StaticFiles
        app.mount("/webui", StaticFiles(directory=wuip), name="webui")

    @app.get("/")
    async def root(): return {"service":"Spider-X","version":"1.0.0","docs":"/docs"}

    @app.get("/health")
    async def health(): return {"status":"ok","cluster":res.get_cluster_summary(),"scheduler":sched.get_status()}

    @app.get("/handlers")
    async def handlers(): return {"handlers": registry.list_handlers()}

    class TSubmit(BaseModel):
        task_type: str; payload: dict = {}; priority: str = "P1"; max_retries: int = 3

    @app.post("/tasks/submit")
    async def submit(req: TSubmit):
        t = Task(f"task-{uuid.uuid4().hex[:12]}", req.task_type, req.payload, TaskPriority(req.priority), req.max_retries)
        c = cred_mgr.create_chain(t.task_id, req.task_type); c.add_entry("submit",{},{"ok":True}); registry.track_task(t); return t.to_dict()

    @app.get("/tasks/{tid}")
    async def get_task(tid: str):
        t = registry.get_task(tid)
        if not t: raise HTTPException(404, "Not found")
        return t.to_dict()

    @app.get("/tasks")
    async def list_tasks(status: str = None):
        return [t.to_dict() for t in registry.get_all_tasks() if not status or t.status.value == status]

    @app.get("/api/v1/report/latest")
    async def latest_report():
        for cid in reversed(list(cred_mgr._chains.keys())):
            ch = cred_mgr.get_chain(cid)
            if ch and ch.entries: return {"chain": ch.to_dict(), "verified": ch.verify()}
        return {"chain": None}

    @app.get("/api/v1/credentials/chains")
    async def list_chains(): return cred_mgr.list_chains()

    @app.get("/api/v1/credentials/chain/{cid}")
    async def get_chain(cid: str):
        ch = cred_mgr.get_chain(cid)
        if not ch: raise HTTPException(404)
        return ch.to_dict()

    class SOPReq(BaseModel): name: str = "pipeline"; steps: list = []

    @app.post("/api/v1/sop/pipelines")
    async def create_sop(req: SOPReq):
        p = sop.create_pipeline(req.name, [s.dict() if hasattr(s,"dict") else s for s in req.steps])
        return {"pipeline_id": p.pipeline_id}

    @app.post("/api/v1/sop/execute/{pid}")
    async def exec_sop(pid: str, body: dict = None): return sop.get_execution_report(pid) or {}

    @app.get("/api/v1/sop/pipelines")
    async def list_sop(): return sop.list_pipelines()

    @app.get("/api/v1/sop/report/{pid}")
    async def sop_report(pid: str): return sop.get_execution_report(pid) or {}

    @app.post("/api/v2/agents/register")
    async def reg_agent(body: dict):
        aid = body.get("agent_id", f"agent-{uuid.uuid4().hex[:8]}")
        st = res.register_agent(aid, body.get("capabilities", {})); sched.register_agent(aid, st); return st.to_dict()

    @app.delete("/api/v2/agents/{aid}")
    async def dereg_agent(aid: str): res.deregister_agent(aid); sched.deregister_agent(aid); return {"ok": True}

    @app.post("/api/v2/agents/{aid}/heartbeat")
    async def hb(aid: str, body: dict = None):
        st = res.update_state(aid, body or {}) if body else res.heartbeat(aid)
        if not st: raise HTTPException(404)
        return st.to_dict()

    @app.get("/api/v2/agents")
    async def list_agents(): return res.get_all_states()

    @app.get("/api/v2/agents/available")
    async def avail(role: str = None, skill: str = None): return [s.to_dict() for s in res.get_available_agents(role, skill)]

    @app.get("/api/v2/cluster/summary")
    async def clus(): return res.get_cluster_summary()

    @app.post("/api/v2/tasks/decompose")
    async def decomp(body: dict): return dec.decompose(body.get("description",""),body.get("pattern","auto"),body.get("context",{})).to_dict()

    @app.post("/api/v2/scheduler/actions")
    async def sched_act(body: dict): return {"action_id": sched.submit_action(body)}

    @app.get("/api/v2/scheduler/status")
    async def sched_stat(): return sched.get_status()

    @app.get("/api/v3/skills/check")
    async def check(body: dict):
        ids = body.get("skill_ids", []); ok, cs = slock.check_combination(ids)
        return {"compatible": ok, "conflicts": [c.to_dict() for c in cs], "resolutions": slock.resolve_conflicts(cs)}

    @app.get("/api/v3/skills/stats")
    async def sk_stat(): return slock.get_stats()

    @app.get("/api/v3/gnn/discover")
    async def gnn_disc(seed: str = None, top_k: int = 10): return {"combinations": [p.to_dict() for p in sgnn.discover_combinations(seed, top_k)]}

    @app.get("/api/v3/gnn/recommend")
    async def gnn_rec(skill_id: str, top_k: int = 5): return {"recommendations": sgnn.get_recommendations(skill_id, top_k)}

    @app.get("/api/v3/gnn/stats")
    async def gnn_stat(): return sgnn.get_stats()

    @app.get("/api/v3/kg/query/{sid}")
    async def kgq(sid: str):
        r = skg.query_skill(sid)
        if not r: raise HTTPException(404)
        return r

    @app.get("/api/v3/kg/conflicts")
    async def kgc(): return {"conflicts": skg.find_conflicts()}

    @app.get("/api/v3/kg/complements")
    async def kgcomp(): return {"complements": skg.find_complements()}

    @app.get("/api/v3/kg/stats")
    async def kgs(): return skg.get_stats()

    return app
