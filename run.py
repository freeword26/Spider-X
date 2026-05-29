#!/usr/bin/env python3
"""Spider-X 蜘蛛群 - 启动入口"""

import sys


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "serve"

    if cmd == "version":
        from spider_x import __version__
        print(f"Spider-X v{__version__}")
        print("蜘蛛群 — Worker智能体集群引擎")
        print("兼容: mini_spider | spider_max | spider_max_room | spider_diary")
        return

    if cmd == "serve":
        from spider_x.core.config import load_config
        import uvicorn
        config = load_config()
        print(f"Spider-X v1.0.0 starting on {config.api.host}:{config.api.port}")
        uvicorn.run(
            "spider_x.core.app:create_app",
            host=config.api.host, port=config.api.port,
            factory=True, log_level=config.log_level.lower(),
        )
        return

    if cmd == "worker":
        import asyncio
        from spider_x.core.config import load_config
        from spider_x.core.worker import WorkerNode
        import os
        config = load_config()
        worker_id = os.getenv("SPIDER_X_WORKER_ID", f"worker-{os.getpid()}")
        print(f"Spider-X Worker {worker_id} starting")
        worker = WorkerNode(worker_id=worker_id, rabbitmq_url=config.rabbitmq.url, concurrency=config.max_concurrency)
        try:
            asyncio.run(worker.start())
        except KeyboardInterrupt:
            print("Worker stopped")
        return

    if cmd == "init":
        import os
        target = args[1] if len(args) > 1 else "."
        os.makedirs(target, exist_ok=True)
        env_path = os.path.join(target, ".env")
        if not os.path.exists(env_path):
            with open(env_path, "w") as f:
                f.write("SPIDER_X_API_PORT=8006\nSPIDER_X_DEBUG=true\n")
        for d in ["skills", "plugins", "workflows"]:
            os.makedirs(os.path.join(target, d), exist_ok=True)
        print(f"Spider-X project initialized in {os.path.abspath(target)}")
        return

    print(f"Unknown command: {cmd}")
    print("Usage: python run.py [serve|worker|version|init]")
    sys.exit(1)


if __name__ == "__main__":
    main()
