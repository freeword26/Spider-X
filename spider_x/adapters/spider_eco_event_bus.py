"""Spider-X Adapter: SpiderEco EventBus — 事件总线适配器（来自 spider_eco 独特功能）.

将 spider_eco 的进程内 EventBus 集成到 Spider-X，
同时支持 RabbitMQ 跨系统事件分发（TAPD/AstrBot 协同）。
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("spider_x.adapters.event_bus")


class EventBusAdapter:
    """进程内 Pub/Sub EventBus + RabbitMQ 桥接适配.

    spider_eco 独有功能：subscribe/publish/unsubscribe/event log.
    升级：async handler 支持 + RabbitMQ 跨系统分发.
    """

    def __init__(self, rabbitmq_url: str = "", exchange: str = "spider_x.events") -> None:
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_log: List[Dict[str, Any]] = []
        self._rabbitmq_url = rabbitmq_url
        self._exchange = exchange
        self._rmq_conn: Any = None
        self._rmq_ch: Any = None

    async def connect_rabbitmq(self, url: str = "") -> None:
        """连接 RabbitMQ，启用跨系统事件分发."""
        if url:
            self._rabbitmq_url = url
        if not self._rabbitmq_url:
            return
        try:
            import aio_pika
            self._rmq_conn = await aio_pika.connect_robust(self._rabbitmq_url)
            self._rmq_ch = await self._rmq_conn.channel()
            await self._rmq_ch.declare_exchange(self._exchange, aio_pika.ExchangeType.TOPIC, durable=True)
            logger.info("EventBus RabbitMQ connected: %s", self._rabbitmq_url)
        except Exception as e:
            logger.warning("EventBus RabbitMQ connect failed: %s, running in local-only mode", e)
            self._rmq_ch = None

    def subscribe(self, event_type: str, handler: Callable) -> str:
        sub_id = f"{event_type}:{id(handler)}"
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        self._event_log.append({
            "action": "subscribe", "event_type": event_type,
            "handler": getattr(handler, "__name__", str(handler)),
            "sub_id": sub_id, "ts": datetime.now().isoformat(),
        })
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        parts = sub_id.split(":", 1)
        if len(parts) != 2:
            return False
        event_type_str, handler_id_s = parts
        try:
            handler_id = int(handler_id_s)
        except ValueError:
            return False
        handlers = self._subscribers.get(event_type_str, [])
        for h in handlers:
            if id(h) == handler_id:
                handlers.remove(h)
                self._event_log.append({
                    "action": "unsubscribe", "event_type": event_type_str,
                    "sub_id": sub_id, "ts": datetime.now().isoformat(),
                })
                return True
        return False

    async def publish(self, event_type: str, **payload: Any) -> List[Dict[str, Any]]:
        """发布事件：本地 handler + RabbitMQ 跨系统分发."""
        results: List[Dict[str, Any]] = []
        # 本地分发
        for handler in self._subscribers.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**payload)
                else:
                    result = handler(**payload)
                results.append({"handler": getattr(handler, "__name__", str(handler)), "result": result})
            except Exception as e:
                results.append({"handler": getattr(handler, "__name__", str(handler)), "error": str(e)})
        self._event_log.append({
            "action": "publish", "event_type": event_type,
            "payload": {k: str(v)[:200] for k, v in payload.items()},
            "results": results, "ts": datetime.now().isoformat(),
        })
        # RabbitMQ 跨系统分发
        if self._rmq_ch:
            try:
                import aio_pika
                msg_body = json.dumps({
                    "event_type": event_type, "payload": payload,
                    "source": "spider_x", "ts": datetime.now().isoformat(),
                }, default=str).encode()
                await self._rmq_ch.default_exchange.publish(
                    aio_pika.Message(body=msg_body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                    routing_key=f"event.{event_type}",
                )
            except Exception as e:
                logger.debug("EventBus RabbitMQ publish failed: %s", e)
        return results

    async def start_rabbitmq_consumer(self, binding_keys: Optional[List[str]] = None) -> None:
        """启动 RabbitMQ 消费者，接收来自 TAPD/AstrBot 的事件."""
        if not self._rmq_ch:
            return
        import aio_pika
        queue = await self._rmq_declare_queue("spider_x_events", binding_keys or ["event.#"])
        await queue.consume(self._on_rmq_message)
        logger.info("EventBus RabbitMQ consumer started, binding: %s", binding_keys or ["event.#"])

    async def _rmq_declare_queue(self, name: str, keys: List[str]):
        import aio_pika
        q = await self._rmq_ch.declare_queue(name, durable=True)
        for k in keys:
            await q.bind(self._exchange, routing_key=k)
        return q

    async def _on_rmq_message(self, msg: Any) -> None:
        import aio_pika
        async with msg.process():
            try:
                data = json.loads(msg.body.decode())
                event_type = data.get("event_type", "unknown")
                await self.publish(event_type, **data.get("payload", {}))
            except Exception as e:
                logger.warning("EventBus RMQ message error: %s", e)

    @property
    def subscriptions(self) -> Dict[str, List[str]]:
        return {k: [getattr(h, "__name__", str(h)) for h in v] for k, v in self._subscribers.items()}

    def get_log(self) -> List[Dict[str, Any]]:
        return self._event_log

    def get_status(self) -> Dict[str, Any]:
        return {
            "subscribers": {k: len(v) for k, v in self._subscribers.items()},
            "total_events_logged": len(self._event_log),
            "rabbitmq_connected": self._rmq_ch is not None,
            "rabbitmq_url": self._rabbitmq_url,
            "exchange": self._exchange,
        }

    async def close(self) -> None:
        if self._rmq_conn:
            await self._rmq_conn.close()
