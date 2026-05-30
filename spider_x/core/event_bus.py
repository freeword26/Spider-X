"""Spider-X EventBus v2 — in-process pub/sub + RabbitMQ bridge."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger("spider_x.event_bus")


class EventBus:
    def __init__(self, rabbitmq_url: str = "") -> None:
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_log: List[Dict[str, Any]] = []
        self._rabbitmq_url = rabbitmq_url
        self._rmq_ch: Any = None

    async def connect_rabbitmq(self, url: str = "") -> None:
        if url:
            self._rabbitmq_url = url
        if not self._rabbitmq_url:
            return
        try:
            import aio_pika
            conn = await aio_pika.connect_robust(self._rabbitmq_url)
            self._rmq_ch = await conn.channel()
            await self._rmq_ch.declare_exchange("spider_x.events", aio_pika.ExchangeType.TOPIC, durable=True)
            logger.info("EventBus RabbitMQ: %s", self._rabbitmq_url)
        except Exception as e:
            logger.warning("EventBus RabbitMQ failed: %s", e)

    def subscribe(self, event_type: str, handler: Callable) -> str:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        sub_id = f"{event_type}:{id(handler)}"
        self._event_log.append({"action": "subscribe", "event_type": event_type,
            "handler": getattr(handler, "__name__", str(handler)), "sub_id": sub_id,
            "ts": datetime.now().isoformat()})
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        parts = sub_id.split(":", 1)
        if len(parts) != 2:
            return False
        et, hid_s = parts
        try:
            hid = int(hid_s)
        except ValueError:
            return False
        handlers = self._subscribers.get(et, [])
        for h in handlers:
            if id(h) == hid:
                handlers.remove(h)
                self._event_log.append({"action": "unsubscribe", "sub_id": sub_id, "ts": datetime.now().isoformat()})
                return True
        return False

    async def publish(self, event_type: str, **payload: Any) -> List[Dict[str, Any]]:
        results = []
        for handler in self._subscribers.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    r = await handler(**payload)
                else:
                    r = handler(**payload)
                results.append({"handler": getattr(handler, "__name__", str(handler)), "result": r})
            except Exception as e:
                results.append({"handler": getattr(handler, "__name__", str(handler)), "error": str(e)})
        self._event_log.append({"action": "publish", "event_type": event_type,
            "results": len(results), "ts": datetime.now().isoformat()})
        if self._rmq_ch:
            try:
                import aio_pika
                body = json.dumps({"event_type": event_type, "payload": payload,
                    "ts": datetime.now().isoformat()}, default=str).encode()
                await self._rmq_ch.default_exchange.publish(
                    aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                    routing_key=f"event.{event_type}")
            except Exception:
                pass
        return results

    @property
    def subscriptions(self) -> Dict[str, List[str]]:
        return {k: [getattr(h, "__name__", str(h)) for h in v] for k, v in self._subscribers.items()}

    def get_log(self) -> List[Dict[str, Any]]:
        return self._event_log

    def get_status(self) -> Dict[str, Any]:
        return {"subscribers": {k: len(v) for k, v in self._subscribers.items()},
                "total_events": len(self._event_log), "rmq_connected": self._rmq_ch is not None}
