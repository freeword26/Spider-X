"""Spider-X 多Agent任务路由器 — CLI + HTTP 双模式入口.

用法:
    # 交互模式
    python router.py --config roles.yaml

    # HTTP API 模式
    python router.py --config roles.yaml --port 8006

    # 单次执行
    python router.py --config roles.yaml --task "帮我写一个Flask API"
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from spider_x.core.role_engine import RoleEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("spider_x.router")


async def interactive(engine: RoleEngine) -> None:
    """交互式任务路由."""
    print("\n🕷️ Spider-X 多Agent路由器 v2.0")
    print("=" * 50)
    s = engine.get_status()
    print(f"已加载 {s['total_roles']} 个角色: {s['local_count']} 本地 / {s['cloud_count']} 云端 / {s['builtin_count']} 内置")
    print("输入任务自动分配角色 | 'status' 查看状态 | 'quit' 退出")
    print("=" * 50 + "\n")

    while True:
        try:
            task = input("📝 任务> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见!")
            break
        if not task:
            continue
        if task.lower() in ("quit", "exit", "q"):
            break
        if task.lower() == "status":
            s = engine.get_status()
            print(f"\n  总角色: {s['total_roles']}")
            print(f"  本地: {', '.join(s['local_roles'])}")
            print(f"  云端: {', '.join(s['cloud_roles'])}\n")
            continue

        result = await engine.execute_task(task)
        if result["status"] == "ok":
            primary = result.get("primary_result", {})
            if primary:
                print(f"  ✅ [{primary.get('role', '?')} | {primary.get('type', '?')} | {primary.get('model', '?')}]")
                resp = primary.get("response", "")
                print(f"  {resp[:300]}{'...' if len(resp) > 300 else ''}")
            alts = result.get("alternative_results", [])
            if alts:
                names = [a.get("role", "?") for a in alts]
                print(f"  📎 辅助结果: {', '.join(names)}")
        else:
            print(f"  ❌ {result.get('error', '无匹配角色')}")
        print()


async def single_task(engine: RoleEngine, task: str) -> None:
    """单次任务执行."""
    result = await engine.execute_task(task)
    if result["status"] == "ok":
        primary = result.get("primary_result", {})
        if primary:
            print(f"[{primary.get('role')} | {primary.get('type')} | {primary.get('model')}]")
            print(primary.get("response", ""))
    else:
        print(f"Error: {result.get('error', 'unknown')}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Spider-X 多Agent路由器")
    parser.add_argument("--config", default="roles.yaml", help="角色配置文件")
    parser.add_argument("--port", type=int, default=0, help="HTTP端口(0=交互模式)")
    parser.add_argument("--task", type=str, default="", help="单次任务执行")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path

    logger.info("Loading roles from: %s", config_path)
    engine = RoleEngine(str(config_path))

    if args.task:
        asyncio.run(single_task(engine, args.task))
    elif args.port > 0:
        import uvicorn
        from spider_x.core.app import create_app
        app = create_app()
        logger.info("HTTP API :%d", args.port)
        uvicorn.run(app, host="0.0.0.0", port=args.port)
    else:
        asyncio.run(interactive(engine))


if __name__ == "__main__":
    main()
