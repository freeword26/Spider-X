from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("spider_x.watchdog")


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


class RecoveryAction(str, Enum):
    RESTART_AGENT = "restart_agent"
    REASSIGN_TASK = "reassign_task"
    SCALE_UP = "scale_up"
    ISOLATE_NODE = "isolate_node"
    ALERT_ONLY = "alert_only"


@dataclass
class HealthRecord:
    agent_id: str
    status: HealthStatus
    last_heartbeat: float
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    active_tasks: int = 0
    failed_tasks: int = 0
    total_tasks: int = 0
    consecutive_failures: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryEvent:
    event_id: str
    timestamp: str
    agent_id: str
    action: RecoveryAction
    reason: str
    success: bool
    details: str = ""


@dataclass
class WatchdogConfig:
    heartbeat_timeout: float = 30.0
    check_interval: float = 10.0
    max_consecutive_failures: int = 3
    cpu_threshold: float = 90.0
    memory_threshold: float = 90.0
    task_timeout: float = 300.0
    max_retries: int = 3
    auto_restart: bool = True
    auto_reassign: bool = True


class WatchdogService:
    def __init__(self, config: Optional[WatchdogConfig] = None):
        self.config = config or WatchdogConfig()
        self._health_records: Dict[str, HealthRecord] = {}
        self._recovery_events: List[RecoveryEvent] = []
        self._running = False
        self._check_task: Optional[asyncio.Task] = None
        self._recovery_hooks: Dict[RecoveryAction, List[Callable]] = {}
        self._alert_callbacks: List[Callable] = []

    def register_agent(self, agent_id: str, metadata: Optional[Dict] = None):
        self._health_records[agent_id] = HealthRecord(
            agent_id=agent_id,
            status=HealthStatus.HEALTHY,
            last_heartbeat=time.time(),
            metadata=metadata or {},
        )
        logger.info(f"Watchdog: Agent {agent_id} 已注册监控")

    def deregister_agent(self, agent_id: str):
        self._health_records.pop(agent_id, None)

    def record_heartbeat(self, agent_id: str, cpu: float = 0, memory: float = 0,
                         active_tasks: int = 0, **kwargs):
        record = self._health_records.get(agent_id)
        if not record:
            self.register_agent(agent_id)
            record = self._health_records[agent_id]
        record.last_heartbeat = time.time()
        record.cpu_percent = cpu
        record.memory_percent = memory
        record.active_tasks = active_tasks
        if record.status in (HealthStatus.UNHEALTHY, HealthStatus.DEGRADED):
            if cpu < self.config.cpu_threshold * 0.8 and memory < self.config.memory_threshold * 0.8:
                record.status = HealthStatus.HEALTHY
                record.consecutive_failures = 0
                logger.info(f"Watchdog: Agent {agent_id} 恢复正常")

    def record_task_failure(self, agent_id: str):
        record = self._health_records.get(agent_id)
        if record:
            record.failed_tasks += 1
            record.consecutive_failures += 1
            record.total_tasks += 1

    def record_task_success(self, agent_id: str):
        record = self._health_records.get(agent_id)
        if record:
            record.total_tasks += 1
            record.consecutive_failures = 0

    def on_recovery(self, action: RecoveryAction, callback: Callable):
        self._recovery_hooks.setdefault(action, []).append(callback)

    def on_alert(self, callback: Callable):
        self._alert_callbacks.append(callback)

    async def start(self):
        self._running = True
        self._check_task = asyncio.create_task(self._check_loop())
        logger.info("Watchdog: 监控服务启动")

    async def stop(self):
        self._running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        logger.info("Watchdog: 监控服务停止")

    async def _check_loop(self):
        while self._running:
            try:
                await self._run_health_check()
                await asyncio.sleep(self.config.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Watchdog: 健康检查异常: {e}")
                await asyncio.sleep(1)

    async def _run_health_check(self):
        now = time.time()
        for agent_id, record in list(self._health_records.items()):
            issues = []
            if now - record.last_heartbeat > self.config.heartbeat_timeout:
                issues.append(f"心跳超时 ({now - record.last_heartbeat:.0f}s)")
                record.status = HealthStatus.UNHEALTHY
            if record.cpu_percent > self.config.cpu_threshold:
                issues.append(f"CPU过高 ({record.cpu_percent:.0f}%)")
                record.status = HealthStatus.DEGRADED
            if record.memory_percent > self.config.memory_threshold:
                issues.append(f"内存过高 ({record.memory_percent:.0f}%)")
                record.status = HealthStatus.DEGRADED
            if record.consecutive_failures >= self.config.max_consecutive_failures:
                issues.append(f"连续失败 {record.consecutive_failures} 次")
                record.status = HealthStatus.UNHEALTHY
            if issues and record.status in (HealthStatus.UNHEALTHY, HealthStatus.DEGRADED):
                await self._handle_unhealthy(agent_id, record, issues)

    async def _handle_unhealthy(self, agent_id: str, record: HealthRecord, issues: List[str]):
        reason = "; ".join(issues)
        logger.warning(f"Watchdog: Agent {agent_id} 异常 — {reason}")
        for cb in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(agent_id, record.status.value, reason)
                else:
                    cb(agent_id, record.status.value, reason)
            except Exception:
                pass
        if record.status == HealthStatus.UNHEALTHY and self.config.auto_restart:
            await self._execute_recovery(agent_id, RecoveryAction.RESTART_AGENT, reason)
        if record.active_tasks > 0 and self.config.auto_reassign:
            await self._execute_recovery(agent_id, RecoveryAction.REASSIGN_TASK, reason)

    async def _execute_recovery(self, agent_id: str, action: RecoveryAction, reason: str):
        event = RecoveryEvent(
            event_id=f"recv-{int(time.time())}",
            timestamp=datetime.now().isoformat(),
            agent_id=agent_id,
            action=action,
            reason=reason,
            success=True,
        )
        logger.info(f"Watchdog: 对 {agent_id} 执行恢复 — {action.value}")
        hooks = self._recovery_hooks.get(action, [])
        if hooks:
            for hook in hooks:
                try:
                    if asyncio.iscoroutinefunction(hook):
                        result = await hook(agent_id, reason)
                    else:
                        result = hook(agent_id, reason)
                    event.success = bool(result)
                    event.details = str(result) if result else "OK"
                except Exception as e:
                    event.success = False
                    event.details = str(e)
                    logger.error(f"Watchdog: 恢复钩子异常: {e}")
        else:
            event.success = True
            event.details = f"无钩子，模拟恢复: {action.value}"
        self._recovery_events.append(event)

    def get_health_report(self) -> Dict[str, Any]:
        records = {}
        status_counts = {}
        for aid, rec in self._health_records.items():
            records[aid] = {
                "status": rec.status.value,
                "cpu": rec.cpu_percent,
                "memory": rec.memory_percent,
                "active_tasks": rec.active_tasks,
                "failed_tasks": rec.failed_tasks,
                "last_heartbeat_age": time.time() - rec.last_heartbeat,
            }
            status_counts[rec.status.value] = status_counts.get(rec.status.value, 0) + 1
        return {
            "timestamp": datetime.now().isoformat(),
            "total_monitored": len(self._health_records),
            "status_distribution": status_counts,
            "records": records,
            "recent_recoveries": len([e for e in self._recovery_events[-10:] if e.success]),
            "recent_failures": len([e for e in self._recovery_events[-10:] if not e.success]),
        }
