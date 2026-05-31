"""Spider-X Application Factory v2 — spider_eco integrated + AstrBot synergy."""
from __future__ import annotations
import logging, uuid
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from spider_x.core.config import SpiderXConfig
from spider_x.core.credential_chain import CredentialChainManager
from spider_x.core.sop_engine import SOPEngine
from spider_x.core.resource_state import ResourceStateService
from spider_x.core.atomic_action import TaskDecomposer
from spider_x.core.chaos_scheduler import ChaosScheduler
from spider_x.core.subgraph import SubgraphEncapsulator, VirtualSuperAgentManager
from spider_x.core.plugin import PluginManager
from spider_x.core.skill_lock import LOCKSSChecker
from spider_x.core.skill_gnn import SkillCombinatorGNN
from spider_x.core.skill_kg import SkillKnowledgeGraph
from spider_x.core.agent_registry import AgentRegistry
from spider_x.core.meta_agent import MetaAgent, TaskDispatcher as MetaTaskDispatcher
from spider_x.core.watchdog import WatchdogService, WatchdogConfig
from spider_x.core.event_bus import EventBus
from spider_x.core.role_engine import RoleEngine
from spider_x.core.task import registry, Task, TaskPriority, TaskStatus

logger = logging.getLogger("spider_x.app")


def create_app(config: Optional[SpiderXConfig] = None) -> FastAPI:
    cfg = config or SpiderXConfig(debug=True)
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
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
    agent_reg = AgentRegistry()
    meta_agent = MetaAgent(dispatcher=MetaTaskDispatcher())
    watchdog = WatchdogService(config=WatchdogConfig(
        heartbeat_timeout=30, check_interval=10, auto_restart=True))
    event_bus = EventBus(rabbitmq_url=cfg.rabbitmq_url)
    role_engine = RoleEngine()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Spider-X v2 starting (eco_integrated=True)")
        await watchdog.start()
        if cfg.rabbitmq_url:
            await event_bus.connect_rabbitmq(cfg.rabbitmq_url)
            logger.info("EventBus RabbitMQ connected")
        yield
        await watchdog.stop()
        sched.stop()
        logger.info("Spider-X v2 stopped")

    app = FastAPI(title="Spider-X v2", version="2.0.0",
        description="蜘蛛群 v2 — spider_eco 功能集成 + Agent Gateway 桥接", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)

    @app.get("/")
    async def root():
        return {"service": "Spider-X", "version": "2.0.0", "eco_integrated": True, "docs": "/docs"}

    @app.get("/health")
    async def health():
        return {"status": "ok", "cluster": res.get_cluster_summary(),
            "event_bus": event_bus.get_status(), "watchdog": watchdog.get_health_report()}

    @app.get("/handlers")
    async def handlers():
        return {"handlers": registry.list_handlers()}

    class TSubmit(BaseModel):
        task_type: str
        payload: dict = {}
        priority: str = "P1"
        max_retries: int = 3

    @app.post("/tasks/submit")
    async def submit(req: TSubmit):
        t = Task(f"task-{uuid.uuid4().hex[:12]}", req.task_type, req.payload, TaskPriority(req.priority), req.max_retries)
        chain = cred_mgr.create_chain(t.task_id, req.task_type)
        chain.add_entry("submit", {}, {"ok": True})
        registry.track_task(t)
        await event_bus.publish("task.created", task_id=t.task_id, task_type=req.task_type)
        return t.to_dict()

    @app.get("/tasks/{tid}")
    async def get_task(tid: str):
        t = registry.get_task(tid)
        if not t:
            raise HTTPException(404, "Not found")
        return t.to_dict()

    @app.get("/tasks")
    async def list_tasks(status: str = None):
        return [t.to_dict() for t in registry.get_all_tasks() if not status or t.status.value == status]

    @app.post("/tasks/{tid}/execute")
    async def execute_task(tid: str):
        t = registry.get_task(tid)
        if not t:
            raise HTTPException(404, "Task not found")
        handler = registry.get_handler(t.task_type)
        if not handler:
            raise HTTPException(400, f"No handler for: {t.task_type}")
        t.status = TaskStatus.RUNNING
        t.started_at = datetime.now().isoformat()
        result = await handler(t)
        t.status = TaskStatus.COMPLETED
        t.result = result
        t.completed_at = datetime.now().isoformat()
        await event_bus.publish("task.completed", task_id=tid, result=str(result)[:200])
        return t.to_dict()

    class EventPubReq(BaseModel):
        event_type: str
        payload: dict = {}

    @app.post("/api/v1/events/publish")
    async def publish_event(req: EventPubReq):
        results = await event_bus.publish(req.event_type, **req.payload)
        return {"event_type": req.event_type, "results": results}

    @app.get("/api/v1/events/status")
    async def event_status():
        return event_bus.get_status()

    @app.get("/api/v1/events/log")
    async def event_log():
        return event_bus.get_log()

    class ApiAdapterReq(BaseModel):
        name: str
        base_url: str
        api_key: str = ""
        endpoint_map: dict = {}

    class ApiCallReq(BaseModel):
        adapter_name: str
        endpoint: str = ""
        method: str = "GET"
        params: dict = {}
        data: dict = {}

    _api_adapters: Dict[str, dict] = {}

    @app.post("/api/v1/adapters/register")
    async def register_adapter(req: ApiAdapterReq):
        _api_adapters[req.name] = {"base_url": req.base_url.rstrip("/"), "api_key": req.api_key, "endpoint_map": req.endpoint_map}
        return {"registered": req.name}

    @app.post("/api/v1/adapters/call")
    async def call_adapter(req: ApiCallReq):
        import httpx
        adapter = _api_adapters.get(req.adapter_name)
        if not adapter:
            raise HTTPException(404, f"Adapter '{req.adapter_name}' not found")
        url = f"{adapter['base_url']}/{req.endpoint.lstrip('/')}"
        headers = {"Authorization": f"Bearer {adapter['api_key']}"} if adapter.get("api_key") else {}
        async with httpx.AsyncClient() as c:
            resp = await c.request(req.method, url, params=req.params, json=req.data, headers=headers, timeout=30)
        try:
            body = resp.json()
        except Exception:
            body = {"text": resp.text[:5000]}
        return {"status": resp.status_code, "adapter": req.adapter_name, "data": body}

    @app.get("/api/v1/adapters")
    async def list_adapters():
        return [{"name": k, "base_url": v["base_url"]} for k, v in _api_adapters.items()]

    _agents: Dict[str, dict] = {}
    _sessions: Dict[str, dict] = {}

    @app.post("/api/v1/room/agents/register")
    async def register_agent(body: dict):
        aid = body.get("agent_id", f"agent-{uuid.uuid4().hex[:8]}")
        _agents[aid] = {"agent_id": aid, "agent_type": body.get("agent_type", "worker"),
            "capabilities": body.get("capabilities", []), "status": "idle"}
        return {"registered": aid}

    @app.get("/api/v1/room/agents")
    async def list_agents():
        return list(_agents.values())

    @app.post("/api/v1/room/sessions")
    async def create_session(body: dict):
        sid = f"room-{uuid.uuid4().hex[:8]}"
        _sessions[sid] = {"session_id": sid, "name": body.get("name", ""),
            "task": body.get("task", ""), "agents": [], "status": "created"}
        return {"session_id": sid}

    @app.get("/api/v1/room/sessions")
    async def list_sessions():
        return list(_sessions.values())

    @app.post("/api/v1/room/coordinate")
    async def coordinate(body: dict):
        sid, urls, strategy = body.get("session_id", ""), body.get("urls", []), body.get("strategy", "round_robin")
        agents = [a for a, v in _agents.items() if v.get("status") in ("idle", "busy")]
        if not agents:
            raise HTTPException(400, "No available agents")
        dist: Dict[str, list] = {a: [] for a in agents}
        for i, url in enumerate(urls):
            if strategy == "round_robin":
                dist[agents[i % len(agents)]].append(url)
            elif strategy == "chunk":
                chunk = max(1, len(urls) // len(agents))
                for idx, a in enumerate(agents):
                    dist[a] = urls[idx*chunk:(idx+1)*chunk]
        return {"strategy": strategy, "assignments": [{"agent": a, "urls": len(u)} for a, u in dist.items() if u]}

    _diary: List[dict] = []

    @app.post("/api/v1/diary/log")
    async def diary_log(body: dict):
        entry = {"task_id": body.get("task_id", ""), "url": body.get("url", ""),
            "worker": body.get("worker", ""), "status": body.get("status", "success"),
            "notes": body.get("notes", ""), "ts": datetime.now().isoformat()}
        _diary.append(entry)
        return entry

    @app.get("/api/v1/diary/summary")
    async def diary_summary():
        from collections import Counter
        by_status = Counter(e.get("status") for e in _diary)
        by_worker = Counter(e.get("worker") for e in _diary)
        return {"total": len(_diary), "by_status": dict(by_status), "by_worker": dict(by_worker)}

    @app.get("/api/v1/diary/report")
    async def diary_report():
        total = len(_diary)
        if total == 0:
            return {"total": 0}
        ok = sum(1 for e in _diary if e.get("status") == "success")
        failed = sum(1 for e in _diary if e.get("status") in ("failed", "error"))
        lessons = [e.get("notes", "") for e in _diary if e.get("status") in ("failed", "error") and e.get("notes")]
        return {"total": total, "successful": ok, "failed": failed,
            "success_rate": f"{round(ok/total*100, 1)}%", "lessons": lessons[:20]}

    class SOPReq(BaseModel):
        name: str = "pipeline"
        steps: list = []

    @app.post("/api/v1/sop/pipelines")
    async def create_sop(req: SOPReq):
        p = sop.create_pipeline(req.name, req.steps)
        return {"pipeline_id": p.pipeline_id}

    @app.post("/api/v1/sop/execute/{pid}")
    async def exec_sop(pid: str, body: dict = None):
        return sop.get_execution_report(pid) or {}

    @app.get("/api/v1/sop/pipelines")
    async def list_sop():
        return sop.list_pipelines()

    @app.post("/api/v2/agents/register")
    async def reg_agent(body: dict):
        aid = body.get("agent_id", f"agent-{uuid.uuid4().hex[:8]}")
        st = res.register_agent(aid, body.get("capabilities", {}))
        sched.register_agent(aid, st)
        return st.to_dict()

    @app.delete("/api/v2/agents/{aid}")
    async def dereg_agent(aid: str):
        res.deregister_agent(aid)
        sched.deregister_agent(aid)
        return {"ok": True}

    @app.post("/api/v2/agents/{aid}/heartbeat")
    async def hb(aid: str, body: dict = None):
        st = res.update_state(aid, body or {})
        if not st:
            raise HTTPException(404)
        return st.to_dict()

    @app.get("/api/v2/agents")
    async def list_agents():
        return res.get_all_states()

    @app.get("/api/v2/cluster/summary")
    async def clus():
        return res.get_cluster_summary()

    @app.get("/api/v2/scheduler/status")
    async def sched_stat():
        return sched.get_status()

    @app.get("/api/v3/watchdog/health")
    async def wd_health():
        return watchdog.get_health_report()

    # ── Role Engine API ──
    @app.get("/api/v4/roles")
    async def list_roles(role_type: str = ""):
        if role_type:
            return [{"role_id": r.role_id, "type": r.type, "provider": r.provider,
                      "model": r.model, "agent_id": r.agent_id, "capabilities": r.capabilities,
                      "priority": r.priority, "cost_factor": r.cost_factor}
                     for r in role_engine.list_roles(role_type)]
        return [{"role_id": r.role_id, "type": r.type, "provider": r.provider,
                  "model": r.model, "agent_id": r.agent_id, "capabilities": r.capabilities,
                  "priority": r.priority, "cost_factor": r.cost_factor}
                 for r in role_engine.list_roles()]

    @app.get("/api/v4/roles/{role_id}")
    async def get_role(role_id: str):
        r = role_engine.get_role(role_id)
        if not r:
            raise HTTPException(404, f"Role '{role_id}' not found")
        return {"role_id": r.role_id, "type": r.type, "provider": r.provider,
                "model": r.model, "agent_id": r.agent_id, "capabilities": r.capabilities,
                "priority": r.priority, "cost_factor": r.cost_factor}

    @app.get("/api/v4/roles/by-agent/{agent_id}")
    async def get_role_by_agent(agent_id: str):
        r = role_engine.get_role_by_agent(agent_id)
        if not r:
            raise HTTPException(404, f"No role found for agent '{agent_id}'")
        return {"role_id": r.role_id, "type": r.type, "provider": r.provider,
                "model": r.model, "agent_id": r.agent_id, "capabilities": r.capabilities}

    @app.get("/api/v4/roles/by-capability/{capability}")
    async def find_roles_by_capability(capability: str):
        return [{"role_id": r.role_id, "type": r.type, "provider": r.provider, "model": r.model}
                for r in role_engine.find_by_capability(capability)]

    @app.post("/api/v4/roles/execute")
    async def execute_role(body: dict):
        role_id = body.get("role_id", "")
        prompt = body.get("prompt", "")
        context = body.get("context")
        if not role_id or not prompt:
            raise HTTPException(400, "role_id and prompt are required")
        result = await role_engine.execute(role_id, prompt, context)
        return result

    @app.get("/api/v4/roles/local")
    async def list_local_roles():
        return [{"role_id": r.role_id, "model": r.model, "provider": r.provider}
                for r in role_engine.list_roles("local")]

    @app.get("/api/v4/roles/cloud")
    async def list_cloud_roles():
        return [{"role_id": r.role_id, "provider": r.provider, "model": r.model,
                  "cost_factor": r.cost_factor}
                for r in role_engine.list_roles("cloud")]

    @app.post("/api/v4/roles/reload")
    async def reload_roles():
        count = role_engine.reload()
        return {"reloaded": count}

    @app.get("/api/v4/roles/status")
    async def role_status():
        return role_engine.get_status()

    return app


from datetime import datetime
