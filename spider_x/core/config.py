"""Spider-X Configuration - Environment-based settings."""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

__all__ = ["SpiderXConfig", "load_config", "AgentStatus"]

class AgentStatus:
    IDLE = "idle"; BUSY = "busy"; DRAINING = "draining"; OFFLINE = "offline"

@dataclass
class SpiderXConfig:
    env: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8006
    api_key: Optional[str] = None
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_vhost: str = "/"
    rabbitmq_url: Optional[str] = None
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    otel_service_name: str = "spider-x"
    otel_endpoint: str = "http://otel-collector:4318"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    credential_secret: Optional[str] = None
    webui_path: Optional[str] = None
    plugin_dir: str = "/var/lib/spider-x/plugins"
    max_concurrency: int = 10
    enable_bidding: bool = False

    def __post_init__(self):
        if self.rabbitmq_url is None:
            self.rabbitmq_url = f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@{self.rabbitmq_host}:{self.rabbitmq_port}/{self.rabbitmq_vhost}"
        if self.credential_secret is None:
            self.credential_secret = os.getenv("SPIDER_X_CREDENTIAL_SECRET", "spider-x-secret-v1")
        if self.webui_path is None:
            ep = os.getenv("SPIDER_X_WEBUI_PATH")
            self.webui_path = ep if ep else str(Path(__file__).resolve().parent.parent.parent / "webui")

def load_config(env_file: str | None = None) -> SpiderXConfig:
    ev = {}
    ef = env_file or ".env"
    p = Path(ef)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    ev[k.strip()] = v.strip()
    def get(key, default=""): return os.environ.get(key, ev.get(key, default))
    return SpiderXConfig(
        env=get("SPIDER_X_ENV", "development"), debug=get("SPIDER_X_DEBUG", "false").lower() == "true",
        log_level=get("SPIDER_X_LOG_LEVEL", "INFO"), api_host=get("SPIDER_X_API_HOST", "0.0.0.0"),
        api_port=int(get("SPIDER_X_API_PORT", "8006")), api_key=get("SPIDER_X_API_KEY") or None,
        rabbitmq_host=get("SPIDER_X_RABBITMQ_HOST", "localhost"), rabbitmq_port=int(get("SPIDER_X_RABBITMQ_PORT", "5672")),
        rabbitmq_user=get("SPIDER_X_RABBITMQ_USER", "guest"), rabbitmq_password=get("SPIDER_X_RABBITMQ_PASSWORD", "guest"),
        rabbitmq_vhost=get("SPIDER_X_RABBITMQ_VHOST", "/"), credential_secret=get("SPIDER_X_CREDENTIAL_SECRET") or None,
        webui_path=get("SPIDER_X_WEBUI_PATH") or None, plugin_dir=get("SPIDER_X_PLUGIN_DIR", "/var/lib/spider-x/plugins"),
        max_concurrency=int(get("SPIDER_X_MAX_CONCURRENCY", "10")), enable_bidding=get("SPIDER_X_ENABLE_BIDDING", "false").lower() == "true",
    )
