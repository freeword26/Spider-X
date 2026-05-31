"""Spider-X 实时监控面板.

端口: 9090
功能: 任务统计、角色监控、性能指标、成本分析
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("spider_x.dashboard")

SPIDER_X_API = os.environ.get("SPIDER_X_API_URL", "http://localhost:8006")
AGENT_GATEWAY = os.environ.get("AGENT_GATEWAY_URL", "http://localhost:9100")

app = FastAPI(title="Spider-X Monitor", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)


# ── WebSocket 连接管理 ────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, msg: dict):
        for ws in self.active[:]:
            try:
                await ws.send_json(msg)
            except Exception:
                self.active.remove(ws)


ws_mgr = ConnectionManager()


# ── Dashboard 页面 ────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard_page():
    return """
<!DOCTYPE html>
<html><head><title>Spider-X Monitor</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;padding:20px;background:#0f172a;color:#e2e8f0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.card{background:#1e293b;border-radius:12px;padding:20px;border:1px solid #334155}
.card h3{margin:0 0 12px;color:#60a5fa;font-size:14px;text-transform:uppercase;letter-spacing:1px}
.metric{font-size:2em;font-weight:70px;color:#f1f5f9}
.sub{color:#94a3b8;font:13px;margin-top:4px}
.badge{display:inline-block;padding:2px 8px;border-radius:99px;font:12px;margin:2px}
.local{background:#065f46;color:#6ee7b7}.cloud{background:#1e40af;color:#93c5fd}.builtin{background:#5b21b6;color:#c4b5fd}
canvas{width:100%;height:120px}
table{width:100%;border-collapse:collapse;font:13px}
th,td{padding:8px 12px;text-align:left;border-bottom:1px solid #334155}
th{color:#94a3b8;font-weight:600}
</style></head><body>
<h1 style="margin-bottom:24px">🕷️ Spider-X 多Agent监控面板</h1>
<div class="grid">
  <div class="card"><h3>📊 任务统计</h3>
    <div class="metric" id="total_tasks">-</div>
    <div class="sub">总任务数</div>
  </div>
  <div class="card"><h3>🏠 本地AI调用</h3>
    <div class="metric" id="local_calls" style="color:#6ee7b7">-</div>
    <div class="sub">成本: $0.00</div>
  </div>
  <div class="card"><h3>☁️ 云端AI调用</h3>
    <div class="metric" id="cloud_calls" style="color:#93c5fd">-</div>
    <div class="sub">按API计费</div>
  </div>
  <div class="card"><h3>💰 成本节省</h3>
    <div class="metric" id="savings" style="color:#fbbf24">-</div>
    <div class="sub">本地替代云端</div>
  </div>
</div>
<div class="grid" style="margin-top:16px">
  <div class="card"><h3>🤖 角色列表</h3><div id="role_list">加载中...</div></div>
  <div class="card"><h3>📈 调用分布</h3><table id="role_stats"><thead><tr><th>角色</th><th>类型</th><th>状态</th></tr></thead><tbody></tbody></table></div>
</div>
<div class="card" style="margin-top:16px"><h3>📝 实时日志</h3><div id="logs" style="max-height:200px;overflow-y:auto;font:12px monospace;color:#94a3b8"></div></div>
<script>
const ws=new WebSocket('ws://'+location.host+'/ws');
ws.onmessage=e=>{
  const d=JSON.parse(e.data);
  if(d.type==='stats'){
    document.getElementById('total_tasks').textContent=d.total||'-';
    document.getElementById('local_calls').textContent=d.local||'-';
    document.getElementById('cloud_calls').textContent=d.cloud||'-';
    document.getElementById('savings').textContent=d.savings||'-';
  }
  if(d.type==='roles'){
    const rl=document.getElementById('role_list');
    rl.innerHTML=d.roles.map(r=>`<span class="badge ${r.type}">${r.name}</span>`).join(' ');
    const tb=document.getElementById('role_stats').querySelector('tbody');
    tb.innerHTML=d.roles.map(r=>`<tr><td>${r.name}</td><td><span class="badge ${r.type}">${r.type}</span></td><td>${r.model}</td></tr>`).join('');
  }
  if(d.type==='log'){
    const l=document.getElementById('logs');
    l.innerHTML+=`<div>[${d.time}] ${d.msg}</div>`;
    l.scrollTop=l.scrollHeight;
  }
};
</script></body></html>
"""


# ── WebSocket 实时推送 ────────────────────────────────

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws_mgr.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
    except WebSocketDisconnect:
        ws_mgr.disconnect(ws)


# ── API 端点 ──────────────────────────────────────────

@app.get("/api/stats")
async def get_stats():
    """获取系统统计."""
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{SPIDER_X_API}/api/v4/roles/status")
            role_status = r.json() if r.status_code == 200 else {}
    except Exception:
        role_status = {}
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{AGENT_GATEWAY}/api/v1/stats")
            gw_stats = r.json() if r.status_code == 200 else {}
    except Exception:
        gw_stats = {}
    return {
        "role_engine": role_status,
        "gateway": gw_stats,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/roles")
async def get_roles():
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{SPIDER_X_API}/api/v4/roles")
            return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def main():
    port = int(os.environ.get("DASHBOARD_PORT", "9090"))
    logger.info("Dashboard starting on port %d", port)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
