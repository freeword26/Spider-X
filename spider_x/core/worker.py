"""Spider-X Worker."""
from __future__ import annotations
import asyncio, json, logging
from datetime import datetime
import aio_pika
from spider_x.core.task import Task, TaskStatus, TaskPriority, registry
logger = logging.getLogger("spider_x.worker")
__all__ = ["WorkerNode", "TaskSubmitter"]

class TaskSubmitter:
    def __init__(self, url: str): self.url, self._conn, self._ch = url, None, None
    async def connect(self):
        self._conn = await aio_pika.connect_robust(self.url); self._ch = await self._conn.channel(); await self._ch.declare_queue("task_queue", durable=True)
    async def submit(self, task: Task) -> str:
        if not self._ch: await self.connect()
        await self._ch.default_exchange.publish(aio_pika.Message(body=json.dumps(task.to_dict()).encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT), routing_key="task_queue")
        registry.track_task(task); return task.task_id
    async def close(self):
        if self._conn: await self._conn.close()

class WorkerNode:
    def __init__(self, worker_id: str, rabbitmq_url: str, concurrency: int = 5):
        self.worker_id, self.url, self.conc = worker_id, rabbitmq_url, concurrency
        self._conn, self._ch, self._running, self._proc, self._fail = None, None, False, 0, 0
    async def start(self):
        self._running = True; self._conn = await aio_pika.connect_robust(self.url); self._ch = await self._conn.channel()
        await self._ch.set_qos(prefetch_count=self.conc)
        q = await self._ch.declare_queue("task_queue", durable=True); await q.consume(self._on_msg)
        logger.info(f"Worker {self.worker_id} started")
        while self._running: await asyncio.sleep(1)
    async def stop(self): self._running = False;
    async def _on_msg(self, msg: aio_pika.IncomingMessage):
        async with msg.process():
            try:
                b = json.loads(msg.body.decode())
                t = Task(b["task_id"], b["task_type"], b.get("payload",{}), TaskPriority(b.get("priority","P1")))
                t.status = TaskStatus.RUNNING; t.worker_id = self.worker_id; registry.track_task(t)
                h = registry.get_handler(t.task_type)
                if not h: raise ValueError(f"Unknown: {t.task_type}")
                r = await h(t); t.status = TaskStatus.COMPLETED; t.result = r; self._proc += 1
            except Exception as e: self._fail += 1; logger.error(f"Failed: {e}")
