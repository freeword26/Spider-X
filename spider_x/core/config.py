"""Spider-X Configuration v2."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

__all__ = ["SpiderXConfig", "load_config", "AgentStatus"]


class AgentStatus:
    IDLE = "idle"
    BUSY = "busy"
    DRAINING = "draining"
    OFFLINE = "offline"


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
    rabbitmq_user: str = "admin"
    rabbitmq_password: str = "admin123"
    rabbitmq_vhost: str = "/"
    _rabbitmq_url: Optional[str] = field(default=None, repr=False)
    diary_storage_dir: str = "data/diary"
    max_concurrency: int = 10
    enable_bidding: bool = False

    @property
    def rabbitmq_url(self) -> str:
        if self._rabbitmq_url:
            return self._rabbitmq_url
        return f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@{self.rabbitmq_host}:{self.rabbitmq_port}/{self.rabbitmq_vhost}"

    @rabbitmq_url.setter
    def rabbitmq_url(self, value: str):
        self._rabbitmq_url = value


def load_config(env_file: str | None = None) -> SpiderXConfig:
    ev: dict[str, str] = {}
    ef = env_file or os.getenv("SPIDER_ECO_ENV_FILE", ".env")
    p = Path(ef)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    ev[k.strip()] = v.strip()

    def get(key: str, default: str = "") -> str:
        return os.environ.get(key, ev.get(key, default))

    cfg = SpiderXConfig(
        env=get("SPIDER_ECO_ENV", "development"),
        debug=get("SPIDER_ECO_DEBUG", "false").lower() == "true",
        log_level=get("SPIDER_ECO_LOG_LEVEL", "INFO"),
        api_host=get("SPIDER_ECO_API_HOST", "0.0.0.0"),
        api_port=int(get("SPIDER_ECO_API_PORT", "8006")),
        api_key=get("SPIDER_ECO_API_KEY") or None,
        rabbitmq_host=get("SPIDER_ECO_RABBITMQ_HOST", "localhost"),
        rabbitmq_port=int(get("SPIDER_ECO_RABBITMQ_PORT", "5672")),
        rabbitmq_user=get("SPIDER_ECO_RABBITMQ_USER", "admin"),
        rabbitmq_password=get("SPIDER_ECO_RABBITMQ_PASSWORD", "admin123"),
        rabbitmq_vhost=get("SPIDER_ECO_RABBITMQ_VHOST", "/"),
        diary_storage_dir=get("SPIDER_ECO_DIARY_DIR", "data/diary"),
        max_concurrency=int(get("SPIDER_ECO_MAX_CONCURRENCY", "10")),
        enable_bidding=get("SPIDER_ECO_ENABLE_BIDDING", "false").lower() == "true",
    )
    explicit_url = get("SPIDER_ECO_RABBITMQ_URL", "")
    if explicit_url:
        cfg.rabbitmq_url = explicit_url
    return cfg
