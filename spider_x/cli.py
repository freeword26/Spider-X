"""Spider-X CLI."""
from __future__ import annotations
import json, logging, os, sys
__all__ = ["main"]

def main():
    args = sys.argv[1:]; cmd = args[0] if args else "serve"
    if cmd in ("version","--version","-v"): _ver()
    elif cmd == "serve": _serve(args[1:])
    elif cmd == "worker": _worker(args[1:])
    elif cmd == "config": _config()
    elif cmd == "init": _init(args[1:])
    elif cmd == "status": _status()
    else: print(f"Unknown: {cmd}"); sys.exit(1)

def _ver():
    from spider_x import __version__; print(f"Spider-X v{__version__}")

def _serve(a):
    h, p, rl = None, None, False; i = 0
    while i < len(a):
        if a[i]=="--host" and i+1<len(a): h=a[i+1]; i+=1
        elif a[i]=="--port" and i+1<len(a): p=int(a[i+1]); i+=1
        elif a[i]=="--reload": rl=True
        i+=1
    from spider_x.core.config import load_config; cfg=load_config(); h=h or cfg.api_host; p=p or cfg.api_port
    import uvicorn; uvicorn.run("spider_x.core.app:create_app",host=h,port=p,reload=rl or cfg.debug,factory=True)

def _worker(a):
    url, conc, wid = None, None, None; i = 0
    while i < len(a):
        if a[i]=="--rabbitmq-url" and i+1<len(a): url=a[i+1]; i+=1
        elif a[i]=="--concurrency" and i+1<len(a): conc=int(a[i+1]); i+=1
        elif a[i]=="--worker-id" and i+1<len(a): wid=a[i+1]; i+=1
        i+=1
    import asyncio; from spider_x.core.config import load_config; from spider_x.core.worker import WorkerNode
    cfg=load_config(); wid=wid or os.getenv("SPIDER_X_WORKER_ID",f"worker-{os.getpid()}"); url=url or cfg.rabbitmq_url; conc=conc or cfg.max_concurrency
    asyncio.run(WorkerNode(wid,url,conc).start())

def _config():
    from spider_x.core.config import load_config; cfg=load_config()
    print(json.dumps({"api":{"host":cfg.api_host,"port":cfg.api_port},"rabbitmq":cfg.rabbitmq_url},indent=2))

def _init(a):
    t = a[0] if a else "."; os.makedirs(t,exist_ok=True)
    ep = os.path.join(t,".env")
    if not os.path.exists(ep):
        with open(ep,"w") as f: f.write("SPIDER_X_API_PORT=8006\nSPIDER_X_DEBUG=true\n")
    for d in ["skills","plugins","workflows"]: os.makedirs(os.path.join(t,d),exist_ok=True)
    print(f"Initialized in {os.path.abspath(t)}")

def _status():
    import urllib.request
    try:
        with urllib.request.urlopen("http://localhost:8006/health",timeout=5) as r: print(json.dumps(json.loads(r.read()),indent=2))
    except Exception as e: print(f"Cannot connect: {e}")
