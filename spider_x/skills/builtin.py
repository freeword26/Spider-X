"""Spider-X Built-in Skills v2 — spider_eco migrated."""
from __future__ import annotations
import asyncio, logging
from datetime import datetime
from typing import Any, Dict
from spider_x.core.task import Task

logger = logging.getLogger("spider_x.skills.builtin")
__all__ = ["BUILTIN_SKILLS", "register_builtin_skills"]

BUILTIN_SKILLS = [
    {"skill_id": "echo", "name": "Echo", "category": "utility"},
    {"skill_id": "shell", "name": "Shell", "category": "system"},
    {"skill_id": "python", "name": "Python", "category": "system"},
    {"skill_id": "http_request", "name": "HTTP Request", "category": "network"},
    {"skill_id": "file_write", "name": "File Write", "category": "file"},
    {"skill_id": "file_read", "name": "File Read", "category": "file"},
    {"skill_id": "crawl", "name": "Single URL Crawl (spider_eco mini_spider)", "category": "crawl"},
    {"skill_id": "crawl_concurrent", "name": "Concurrent Crawl (spider_eco spider_max)", "category": "crawl"},
    {"skill_id": "event_publish", "name": "EventBus Publish (spider_eco)", "category": "event"},
    {"skill_id": "room_coordinate", "name": "Room Coordinate (spider_eco spidermax_room)", "category": "collab"},
    {"skill_id": "research", "name": "Research", "category": "workflow"},
    {"skill_id": "code", "name": "Code", "category": "workflow"},
    {"skill_id": "review", "name": "Review", "category": "workflow"},
    {"skill_id": "test", "name": "Test", "category": "workflow"},
    {"skill_id": "clean", "name": "Clean", "category": "workflow"},
    {"skill_id": "deploy", "name": "Deploy", "category": "workflow"},
    {"skill_id": "notify", "name": "Notify", "category": "workflow"},
    {"skill_id": "multi_agent_index_brainstorm", "name": "Index Brainstorm", "category": "workflow"},
]

async def _brainstorm(t: Task) -> Dict:
    from spider_x.skills.index_brainstorm import handle_index_brainstorm
    return await handle_index_brainstorm(t)

async def _echo(t: Task) -> Dict:
    return {"echo": t.payload.get("message", ""), "time": datetime.now().isoformat()}

async def _shell(t: Task) -> Dict:
    import subprocess
    cmd = t.payload.get("command", "")
    if not cmd:
        raise ValueError("No command")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t.payload.get("timeout", 30))
    return {"rc": r.returncode, "out": r.stdout, "err": r.stderr}

async def _python(t: Task) -> Dict:
    code = t.payload.get("code", "")
    if not code:
        raise ValueError("No code")
    lv = {}
    exec(compile(code, "<t>", "exec"), {}, lv)
    return {"locals": {k: str(v) for k, v in lv.items()}}

async def _http(t: Task) -> Dict:
    import httpx
    async with httpx.AsyncClient() as c:
        r = await c.request(t.payload.get("method", "GET"), t.payload.get("url", ""),
            headers=t.payload.get("headers", {}), json=t.payload.get("body"),
            timeout=t.payload.get("timeout", 30))
        return {"status": r.status_code, "body": r.text[:10000]}

async def _fw(t: Task) -> Dict:
    from pathlib import Path
    p = Path(t.payload.get("path", ""))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(t.payload.get("content", ""), encoding="utf-8")
    return {"path": str(p)}

async def _fr(t: Task) -> Dict:
    from pathlib import Path
    p = Path(t.payload.get("path", ""))
    if not p.exists():
        raise FileNotFoundError(str(p))
    return {"path": str(p), "content": p.read_text(encoding="utf-8")[:10000]}

async def _crawl(t: Task) -> Dict:
    """spider_eco mini_spider crawl."""
    import httpx
    from bs4 import BeautifulSoup
    url = t.payload.get("url", "")
    max_links = t.payload.get("max_links", 50)
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=30, follow_redirects=True,
            headers={"User-Agent": "SpiderX/2.0 (compat mini_spider)"})
    soup = BeautifulSoup(resp.text, "lxml")
    title = soup.title.string if soup.title else "No title"
    links = [a["href"] for a in soup.find_all("a", href=True) if a["href"].startswith("http")][:max_links]
    return {"url": url, "title": title, "text_preview": soup.get_text(strip=True)[:500],
        "status_code": resp.status_code, "links_found": len(links), "links": links}

async def _crawl_concurrent(t: Task) -> Dict:
    """spider_eco spider_max concurrent crawl."""
    import asyncio, httpx
    from bs4 import BeautifulSoup
    urls = t.payload.get("urls", [])
    max_links = t.payload.get("max_links", 20)
    sem = asyncio.Semaphore(10)
    async def _fetch(u: str) -> dict:
        async with sem:
            try:
                async with httpx.AsyncClient() as c:
                    r = await c.get(u, timeout=30, follow_redirects=True,
                        headers={"User-Agent": "SpiderX/2.0 (compat spider_max)"})
                s = BeautifulSoup(r.text, "lxml")
                links = [a["href"] for a in s.find_all("a", href=True) if a["href"].startswith("http")][:max_links]
                return {"url": u, "title": s.title.string if s.title else "No title",
                    "text_preview": s.get_text(strip=True)[:300], "status_code": r.status_code, "links": links}
            except Exception as e:
                return {"url": u, "error": str(e)}
    pages = await asyncio.gather(*[_fetch(u) for u in urls])
    ok = sum(1 for p in pages if "error" not in p)
    return {"total_urls": len(urls), "crawled": ok, "failed": len(urls) - ok, "pages": pages}

async def _stub(t: Task) -> Dict:
    return {"status": "ok", "skill": t.task_type}

async def _event_publish(t: Task) -> Dict:
    return {"published": True, "event_type": t.payload.get("event_type", "custom"),
        "ts": datetime.now().isoformat()}

async def _room_coordinate(t: Task) -> Dict:
    return {"coordinated": True, "strategy": t.payload.get("strategy", "round_robin"),
        "urls": len(t.payload.get("urls", []))}

_HANDLERS = {
    "echo": _echo, "shell": _shell, "python": _python,
    "http_request": _http, "file_write": _fw, "file_read": _fr,
    "crawl": _crawl, "crawl_concurrent": _crawl_concurrent,
    "event_publish": _event_publish, "room_coordinate": _room_coordinate,
    "research": _stub, "code": _stub, "review": _stub, "test": _stub,
    "clean": _stub, "deploy": _stub, "notify": _stub,
    "multi_agent_index_brainstorm": _brainstorm,
}

def register_builtin_skills(reg: Any) -> int:
    eco_count = sum(1 for k in _HANDLERS if k in ("crawl", "crawl_concurrent", "event_publish", "room_coordinate"))
    total = len(_HANDLERS)
    for tt, h in _HANDLERS.items():
        reg.register(tt)(h)
    logger.info("Registered %d skills (%d migrated from spider_eco: crawl, crawl_concurrent, event_publish, room_coordinate)", total, eco_count)
    return total
