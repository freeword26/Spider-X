"""Spider-X Agent Gateway — IDE集成路由网关.

对外暴露统一入口，内部路由到 Spider-X 角色引擎。
支持 VS Code / IntelliJ 插件连接。

端口: 9100
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("spider_x.gateway")

SPIDER_X_API = os.environ.get("SPIDER_X_API_URL", "http://localhost:8006")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

app = FastAPI(title="Spider-X Agent Gateway", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)

# ── 统计 ──────────────────────────────────────────────
_task_count = 0
_local_calls = 0
_cloud_calls = 0
_cache: Dict[str, Dict] = {}
CACHE_MAX = 1000
CACHE_TTL = 86400  # 24h

# ── 请求模型 ──────────────────────────────────────────

class ExecuteReq(BaseModel):
    task: str
    context: Optional[Dict[str, Any]] = None
    max_parallel: int = 3
    prefer_local: bool = False
    timeout: int = 120

class ExecuteOneReq(BaseModel):
    role_id: str
    prompt: str
    context: Optional[Dict[str, Any]] = None
    timeout: int = 120


# ── 健康检查 ──────────────────────────────────────────

@app.get("/health")
async def health():
    """网关健康检查."""
    status = {"status": "ok", "gateway": "spider-x-gateway"}
    # 检查 Spider-X API 连通性
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(f"{SPIDER_X_API}/health")
            status["spider_x_api"] = "up" if resp.status_code == 200 else "down"
    except Exception:
        status["spider_x_api"] = "down"
    # 检查 Ollama 连通性
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(f"{OLLAMA_HOST}/api/tags")
            status["ollama"] = "up" if resp.status_code == 200 else "down"
    except Exception:
        status["ollama"] = "unknown"
    return status


# ── 任务执行（IDE调用入口）──────────────────────────────

@app.post("/api/v1/execute")
async def execute_task(req: ExecuteReq):
    """IDE插件统一调用入口 → 自动路由到最优角色."""
    global _task_count
    _task_count += 1
    logger.info("Task #%d: %s", _task_count, req.task[:80])
    async with httpx.AsyncClient(timeout=req.timeout) as c:
        resp = await c.post(
            f"{SPIDER_X_API}/api/v4/roles/execute",
            json=req.dict(),
        )
        return resp.json()


@app.post("/api/v1/execute/{role_id}")
async def execute_one(req: ExecuteOneReq, role_id: str):
    """指定角色执行."""
    async with httpx.AsyncClient(timeout=req.timeout) as c:
        resp = await c.post(
            f"{SPIDER_X_API}/api/v4/roles/execute",
            json={"role_id": role_id, "prompt": req.prompt, "context": req.context},
        )
        return resp.json()


# ── 角色管理 ──────────────────────────────────────────

@app.get("/api/v1/roles")
async def list_roles(type: str = ""):
    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.get(f"{SPIDER_X_API}/api/v4/roles", params={"role_type": type})
        return resp.json()


@app.get("/api/v1/roles/{role_id}")
async def get_role(role_id: str):
    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.get(f"{SPIDER_X_API}/api/v4/roles/{role_id}")
        if resp.status_code == 404:
            raise HTTPException(404, f"Role '{role_id}' not found")
        return resp.json()


@app.get("/api/v1/roles/by-capability/{capability}")
async def find_by_cap(capability: str):
    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.get(f"{SPIDER_X_API}/api/v4/roles/by-capability/{capability}")
        return resp.json()


# ── 监控统计 ──────────────────────────────────────────

@app.get("/api/v1/stats")
async def stats():
    s = _local_calls + _cloud_calls
    return {
        "total_tasks": _task_count,
        "local_calls": _local_calls,
        "cloud_calls": _cloud_calls,
        "cache_hit_rate": f"{len(_cache)}/{CACHE_MAX}",
        "avg_response_time": "N/A",
        "cost_savings": f"${_local_calls * 0.01:.2f} (local vs cloud estimate)",
    }


@app.get("/dashboard")
async def dashboard():
    """简化的监控面板数据."""
    return {
        "gateway": "spider-x-gateway",
        "version": "2.0.0",
        "endpoints": {
            "health": "/health",
            "execute": "POST /api/v1/execute",
            "roles": "/api/v1/roles",
            "stats": "/api/v1/stats",
        },
        "stats": await stats(),
    }


def main():
    port = int(os.environ.get("GATEWAY_PORT", "9100"))
    logger.info("Agent Gateway starting on port %d", port)
    logger.info("Spider-X API: %s", SPIDER_X_API)
    logger.info("Ollama: %s", OLLAMA_HOST)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
