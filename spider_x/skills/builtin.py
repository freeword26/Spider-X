"""Spider-X Built-in Skills."""
from __future__ import annotations
import asyncio, logging
from datetime import datetime
from typing import Any, Dict
logger = logging.getLogger("spider_x.skills.builtin")
__all__ = ["BUILTIN_SKILLS", "register_builtin_skills"]

BUILTIN_SKILLS = [
    {"skill_id": "echo", "name": "Echo", "category": "utility", "compatible_spiders": ["*"]},
    {"skill_id": "shell", "name": "Shell", "category": "system", "compatible_spiders": ["*"]},
    {"skill_id": "python", "name": "Python", "category": "system", "compatible_spiders": ["*"]},
    {"skill_id": "http_request", "name": "HTTP Request", "category": "network", "compatible_spiders": ["*"]},
    {"skill_id": "file_write", "name": "File Write", "category": "file", "compatible_spiders": ["*"]},
    {"skill_id": "file_read", "name": "File Read", "category": "file", "compatible_spiders": ["*"]},
    {"skill_id": "research", "name": "Research", "category": "workflow", "compatible_spiders": ["*"]},
    {"skill_id": "code", "name": "Code", "category": "workflow", "compatible_spiders": ["*"]},
    {"skill_id": "review", "name": "Review", "category": "workflow", "compatible_spiders": ["*"]},
    {"skill_id": "test", "name": "Test", "category": "workflow", "compatible_spiders": ["*"]},
    {"skill_id": "clean", "name": "Clean", "category": "workflow", "compatible_spiders": ["*"]},
    {"skill_id": "deploy", "name": "Deploy", "category": "workflow", "compatible_spiders": ["*"]},
    {"skill_id": "notify", "name": "Notify", "category": "workflow", "compatible_spiders": ["*"]},
]

async def _echo(t): return {"echo": t.payload.get("message", ""), "time": datetime.now().isoformat()}
async def _shell(t):
    import subprocess; cmd = t.payload.get("command", "")
    if not cmd: raise ValueError("No command")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t.payload.get("timeout", 30))
    return {"rc": r.returncode, "out": r.stdout, "err": r.stderr}
async def _python(t):
    code = t.payload.get("code", "")
    if not code: raise ValueError("No code")
    lv = {}; exec(compile(code, "<t>", "exec"), {}, lv)
    return {"locals": {k: str(v) for k, v in lv.items()}}
async def _http(t):
    import httpx
    async with httpx.AsyncClient() as c:
        r = await c.request(t.payload.get("method","GET"), t.payload.get("url",""), headers=t.payload.get("headers",{}), json=t.payload.get("body"), timeout=t.payload.get("timeout",30))
        return {"status": r.status_code, "body": r.text[:10000]}
async def _fw(t):
    from pathlib import Path; p = Path(t.payload.get("path","")); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(t.payload.get("content",""),encoding="utf-8")
    return {"path": str(p)}
async def _fr(t):
    from pathlib import Path; p = Path(t.payload.get("path",""))
    if not p.exists(): raise FileNotFoundError(str(p))
    return {"path": str(p), "content": p.read_text(encoding="utf-8")[:10000]}
async def _stub(t): return {"status": "ok", "skill": t.task_type}

_HANDLERS = {"echo": _echo, "shell": _shell, "python": _python, "http_request": _http, "file_write": _fw, "file_read": _fr,
             "research": _stub, "code": _stub, "review": _stub, "test": _stub, "clean": _stub, "deploy": _stub, "notify": _stub}

def register_builtin_skills(reg: Any) -> int:
    for tt, h in _HANDLERS.items(): reg.register(tt)(h)
    logger.info(f"Registered {len(_HANDLERS)} skills")
    return len(_HANDLERS)
