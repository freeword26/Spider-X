"""Spider-X task types, registry, and built-in handlers."""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("spider-x.task")


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


@dataclass
class Task:
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: TaskPriority = TaskPriority.P1
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    worker_id: Optional[str] = None


class TaskRegistry:
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._tasks: Dict[str, Task] = {}

    def register(self, task_type: str):
        def decorator(func: Callable):
            self._handlers[task_type] = func
            return func
        return decorator

    def get_handler(self, task_type: str) -> Optional[Callable]:
        return self._handlers.get(task_type)

    def list_handlers(self) -> List[str]:
        return list(self._handlers.keys())

    def track_task(self, task: Task):
        self._tasks[task.task_id] = task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        return list(self._tasks.values())


registry = TaskRegistry()


@registry.register("echo")
async def handle_echo(task: Task) -> Dict:
    await asyncio.sleep(0.1)
    return {"echo": task.payload.get("message", ""), "processed_at": datetime.now().isoformat()}


@registry.register("shell")
async def handle_shell(task: Task) -> Dict:
    import subprocess
    command = task.payload.get("command", "")
    timeout = task.payload.get("timeout", 30)
    if not command:
        raise ValueError("No command provided")
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


@registry.register("python")
async def handle_python(task: Task) -> Dict:
    code = task.payload.get("code", "")
    if not code:
        raise ValueError("No code provided")
    local_vars = {}
    exec(compile(code, "<task>", "exec"), {}, local_vars)
    return {"locals": {k: str(v) for k, v in local_vars.items()}}


@registry.register("http_request")
async def handle_http_request(task: Task) -> Dict:
    import httpx
    url = task.payload.get("url", "")
    method = task.payload.get("method", "GET").upper()
    headers = task.payload.get("headers", {})
    body = task.payload.get("body")
    timeout = task.payload.get("timeout", 30)
    async with httpx.AsyncClient() as client:
        response = await client.request(method, url, headers=headers, json=body, timeout=timeout)
        return {"status_code": response.status_code, "headers": dict(response.headers), "body": response.text[:10000]}


@registry.register("file_write")
async def handle_file_write(task: Task) -> Dict:
    from pathlib import Path
    path = task.payload.get("path", "")
    content = task.payload.get("content", "")
    encoding = task.payload.get("encoding", "utf-8")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding=encoding)
    return {"path": str(p), "size": len(content)}


@registry.register("file_read")
async def handle_file_read(task: Task) -> Dict:
    from pathlib import Path
    path = task.payload.get("path", "")
    encoding = task.payload.get("encoding", "utf-8")
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    content = p.read_text(encoding=encoding)
    return {"path": str(p), "content": content[:10000], "size": len(content)}


__all__ = [
    "TaskStatus",
    "TaskPriority",
    "Task",
    "TaskRegistry",
    "registry",
    "handle_echo",
    "handle_shell",
    "handle_python",
    "handle_http_request",
    "handle_file_write",
    "handle_file_read",
]
