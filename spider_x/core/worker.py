"""Spider-X Worker v2 — RabbitMQ consumer with real task dispatch."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

import aio_pika
from spider_x.core.task import Task, TaskStatus, TaskPriority, registry

logger = logging.getLogger("spider_x.worker")


class TaskSubmitter:
    def __init__(self, url: str):
        self.url = url
        self._conn = None
        self._ch = None

    async def connect(self):
        self._conn = await aio_pika.connect_robust(self.url)
        self._ch = await self._conn.channel()
        await self._ch.declare_queue("spider_x_tasks", durable=True)

    async def submit(self, task: str) -> str:
        if not self._ch:
            await self.connect()
        import uuid
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        await self._ch.default_exchange.publish(
            aio_pika.Message(body=json.dumps({"task_id": task_id, "payload": task}).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key="spider_x_tasks")
        return task_id

    async def close(self):
        if self._conn:
            await self._conn.close()


class WorkerNode:
    def __init__(self, worker_id: str, rabbitmq_url: str, concurrency: int = 5):
        self.worker_id = worker_id
        self.rabbitmq_url = rabbitmq_url
        self.concurrency = concurrency
        self._conn = None
        self._ch = None
        self._running = False
        self._processed = 0
        self._failed = 0

    async def start(self):
        self._running = True
        self._conn = await aio_pika.connect_robust(self.rabbitmq_url)
        self._ch = await self._conn.channel()
        await self._ch.set_qos(prefetch_count=self.concurrency)
        q = await self._ch.declare_queue("spider_x_tasks", durable=True)
        await q.consume(self._on_message)
        logger.info("Worker '%s' started (concurrency=%d)", self.worker_id, self.concurrency)
        while self._running:
            await asyncio.sleep(1)

    async def stop(self):
        self._running = False
        if self._conn:
            await self._conn.close()

    async def _on_message(self, msg: aio_pika.IncomingMessage):
        async with msg.process():
            try:
                body = json.loads(msg.body.decode())
                task = Task(
                    body.get("task_id", f"task-{datetime.now().timestamp()}"),
                    body.get("task_type", body.get("type", "echo")),
                    body.get("payload", body),
                    TaskPriority(body.get("priority", "P1")),
                )
                task.status = TaskStatus.RUNNING
                task.worker_id = self.worker_id
                task.started_at = datetime.now().isoformat()
                registry.track_task(task)
                handler = registry.get_handler(task.task_type)
                if not handler:
                    raise ValueError(f"No handler for: {task.task_type}")
                result = await handler(task)
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.now().isoformat()
                self._processed += 1
                logger.info("Task %s [%s] done", task.task_id, task.task_type)
            except Exception as e:
                self._failed += 1
                logger.error("Task failed: %s", e, exc_info=True)


__all__ = ["WorkerNode", "TaskSubmitter"]
