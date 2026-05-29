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
    """Spider-X: Spider Swarm Worker Agent Cluster Engine."""
    pass


@main.command()
@click.option("--host", "-h", default="0.0.0.0", show_default=True, help="Host address to bind the server to.")
@click.option("--port", "-p", default=8006, type=int, show_default=True, help="Port number to listen on.")
@click.option("--config", "-c", "config_path", default=None, type=click.Path(), help="Path to a configuration file (.env or JSON).")
@click.option("--reload", "-r", is_flag=True, default=False, help="Enable auto-reload on code changes.")
def serve(host: str, port: int, config_path: Optional[str], reload: bool):
    """Start the Spider-X API server."""
    config = load_config(config_path)
    logger.info("Starting Spider-X server on %s:%d", host, port)
    logger.info("Environment: %s", config.env.value)
    uvicorn.run(
        "spider_x.cli:_get_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


def _get_app():
    return create_app()


@main.command()
@click.option("--rabbitmq-url", "-q", default=None, help="RabbitMQ connection URL (amqp://user:pass@host:port/vhost).")
@click.option("--concurrency", "-c", default=4, type=int, show_default=True, help="Maximum number of concurrent tasks.")
@click.option("--worker-id", "-w", default=None, help="Unique identifier for this worker node.")
def worker(rabbitmq_url: Optional[str], concurrency: int, worker_id: Optional[str]):
    """Start a Spider-X worker node."""
    config = load_config()
    url = rabbitmq_url or (config.rabbitmq.url if config.rabbitmq else None)
    wid = worker_id or f"worker-{os.getpid()}"
    logger.info("Starting Spider-X worker: %s", wid)
    logger.info("Concurrency: %d", concurrency)
    if url:
        logger.info("Connecting to RabbitMQ: %s", url)
    else:
        logger.warning("No RabbitMQ URL provided; running in standalone mode")
    asyncio.run(_run_worker(wid, concurrency))


async def _run_worker(worker_id: str, concurrency: int):
    logger.info("Worker '%s' started (concurrency=%d)", worker_id, concurrency)
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Worker '%s' stopped by user", worker_id)


@main.command()
def version():
    """Show version information."""
    click.echo(f"Spider-X v{__version__}")
    click.echo(f"Python {sys.version}")
    click.echo(f"Platform: {sys.platform}")


@main.command()
@click.option("--config", "-c", "config_path", default=None, type=click.Path(), help="Path to a configuration file.")
def config(config_path: Optional[str]):
    """Show current configuration."""
    cfg = load_config(config_path)
    data = {
        "env": cfg.env.value,
        "debug": cfg.debug,
        "log_level": cfg.log_level,
        "api": {"host": cfg.api.host, "port": cfg.api.port},
        "rabbitmq": {
            "host": cfg.rabbitmq.host,
            "port": cfg.rabbitmq.port,
            "vhost": cfg.rabbitmq.vhost,
        },
        "max_concurrency": cfg.max_concurrency,
        "plugin_dir": cfg.plugin_dir,
    }
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


@main.command()
@click.argument("project_dir", default=".", type=click.Path())
@click.option("--force", "-f", is_flag=True, default=False, help="Overwrite existing files.")
def init(project_dir: str, force: bool):
    """Initialize a new Spider-X project.

    Creates configuration files and directory structure in PROJECT_DIR.
    """
    base = Path(project_dir).resolve()
    if not base.exists():
        base.mkdir(parents=True)
        logger.info("Created project directory: %s", base)

    env_path = base / ".env"
    if env_path.exists() and not force:
        logger.warning(".env already exists; use --force to overwrite")
    else:
        env_path.write_text(
            "SPIDER_X_ENV=development\n"
            "SPIDER_X_DEBUG=true\n"
            "SPIDER_X_LOG_LEVEL=INFO\n"
            "SPIDER_X_API_HOST=0.0.0.0\n"
            "SPIDER_X_API_PORT=8006\n"
            "SPIDER_X_RABBITMQ_HOST=localhost\n"
            "SPIDER_X_RABBITMQ_PORT=5672\n"
            "SPIDER_X_RABBITMQ_USER=guest\n"
            "SPIDER_X_RABBITMQ_PASSWORD=guest\n"
            "SPIDER_X_RABBITMQ_VHOST=/\n",
            encoding="utf-8",
        )
        logger.info("Created %s", env_path)

    for subdir in ("skills", "plugins", "workflows"):
        sub = base / subdir
        if not sub.exists():
            sub.mkdir()
            logger.info("Created %s/", sub)

    click.echo(f"Spider-X project initialized at {base}")


@main.command()
@click.option("--server-url", "-u", default="http://localhost:8006", show_default=True, help="URL of the running Spider-X server.")
def status(server_url: str):
    """Show system status (requires a running server)."""
    try:
        import urllib.request

        req = urllib.request.urlopen(f"{server_url}/health", timeout=5)
        body = req.read().decode("utf-8")
        data = json.loads(body)
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as exc:
        click.echo(f"Error connecting to server at {server_url}: {exc}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
