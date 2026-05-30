from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import click
import uvicorn

from spider_x import __version__
from spider_x.core.app import create_app
from spider_x.core.config import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__, prog_name="Spider-X")
def main():
    """Spider-X v2: Spider Swarm Worker Agent Cluster Engine (spider_eco integrated)."""
    pass


@main.command()
@click.option("--host", "-h", default="0.0.0.0", show_default=True)
@click.option("--port", "-p", default=8006, type=int, show_default=True)
@click.option("--config", "-c", "config_path", default=None, type=click.Path())
@click.option("--reload", "-r", is_flag=True, default=False)
def serve(host: str, port: int, config_path: Optional[str], reload: bool):
    """Start the Spider-X API server."""
    config = load_config(config_path)
    logger.info("Spider-X v%s starting on %s:%d (eco_integrated=True)", __version__, host, port)
    uvicorn.run("spider_x.cli:_get_app", host=host, port=port, reload=reload, factory=True)


def _get_app():
    return create_app()


@main.command()
@click.option("--rabbitmq-url", "-q", default=None)
@click.option("--concurrency", "-c", default=4, type=int, show_default=True)
@click.option("--worker-id", "-w", default=None)
def worker(rabbitmq_url: Optional[str], concurrency: int, worker_id: Optional[str]):
    """Start a Spider-X worker node (RabbitMQ consumer)."""
    config = load_config()
    url = rabbitmq_url or str(config.rabbitmq_url)
    wid = worker_id or f"worker-{os.getpid()}"
    logger.info("Worker %s starting (concurrency=%d, rmq=%s)", wid, concurrency, url)
    if not url:
        logger.error("No RabbitMQ URL. Set SPIDER_ECO_RABBITMQ_HOST or pass --rabbitmq-url.")
        sys.exit(1)
    asyncio.run(_run_worker(wid, concurrency, url))


async def _run_worker(worker_id: str, concurrency: int, rabbitmq_url: str):
    from spider_x.core.worker import WorkerNode
    w = WorkerNode(worker_id=worker_id, rabbitmq_url=rabbitmq_url, concurrency=concurrency)
    try:
        await w.start()
    except KeyboardInterrupt:
        logger.info("Worker '%s' stopped", worker_id)


@main.command()
def version():
    click.echo(f"Spider-X v{__version__} — spider_eco integrated")
    click.echo(f"Python {sys.version}")


@main.command()
@click.option("--config", "-c", "config_path", default=None, type=click.Path())
def config(config_path: Optional[str]):
    cfg = load_config(config_path)
    data = {
        "env": cfg.env,
        "api": {"host": cfg.api_host, "port": cfg.api_port},
        "rabbitmq": {"host": cfg.rabbitmq_host, "port": cfg.rabbitmq_port, "vhost": cfg.rabbitmq_vhost},
        "max_concurrency": cfg.max_concurrency, "bidding": cfg.enable_bidding,
    }
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


@main.command()
@click.argument("project_dir", default=".", type=click.Path())
@click.option("--force", "-f", is_flag=True, default=False)
def init(project_dir: str, force: bool):
    base = Path(project_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)
    env_path = base / ".env"
    if not env_path.exists() or force:
        env_path.write_text(
            "SPIDER_ECO_API_PORT=8006\n"
            "SPIDER_ECO_RABBITMQ_HOST=localhost\n"
            "SPIDER_ECO_RABBITMQ_PORT=5672\n"
            "SPIDER_ECO_RABBITMQ_USER=admin\n"
            "SPIDER_ECO_RABBITMQ_PASSWORD=admin123\n"
            "SPIDER_ECO_RABBITMQ_VHOST=/\n",
            encoding="utf-8",
        )
    for d in ("skills", "plugins", "workflows", "data/diary"):
        (base / d).mkdir(parents=True, exist_ok=True)
    click.echo(f"Spider-X project initialized at {base}")


@main.command()
@click.option("--server-url", "-u", default="http://localhost:8006", show_default=True)
def status(server_url: str):
    try:
        import urllib.request
        req = urllib.request.urlopen(f"{server_url}/health", timeout=5)
        click.echo(json.dumps(json.loads(req.read().decode()), indent=2, ensure_ascii=False))
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
