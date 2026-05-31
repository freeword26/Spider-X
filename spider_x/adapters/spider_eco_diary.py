"""Spider-X Adapter: SpiderEco Diary — 采集日志存储与经验报告（来自 spider_eco 独特功能）.

将 spider_eco 的 SpiderDiary 完整能力迁移到 Spider-X.
JSON 文件持久化 + 自动分片 + 统计汇总 + 经验报告.

分片策略:
  - 按年分片: tasks_2026.json
  - 单文件超 50MB 自动按月拆分: tasks_2026_06.json
  - 写入时自动轮转，读取时自动合并
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("spider_x.adapters.spider_eco_diary")

SHARD_SIZE_LIMIT = 50 * 1024 * 1024  # 50 MB


def _shard_path(storage_dir: str, dt: Optional[datetime] = None) -> Path:
    """计算当前应写入的分片文件路径。

    规则:
      1. 默认按年分片 → tasks_2026.json
      2. 当年文件超过 50MB → 按月拆分 → tasks_2026_06.json
      3. 当月文件也超 50MB → 继续往下月轮转
    """
    now = dt or datetime.now()
    current_year = now.year
    base = Path(storage_dir) / f"tasks_{current_year}.json"

    if not base.exists():
        return base

    if base.stat().st_size < SHARD_SIZE_LIMIT:
        return base

    # 当年文件超限，按月拆分
    month = now.month
    while month <= 12:
        shard = Path(storage_dir) / f"tasks_{current_year}_{month:02d}.json"
        if not shard.exists() or shard.stat().st_size < SHARD_SIZE_LIMIT:
            return shard
        month += 1

    # 12月也满了，落到次年1月
    return Path(storage_dir) / f"tasks_{current_year + 1}_01.json"


def _append_to_shard(filepath: Path, entry: Dict) -> None:
    """追加一条记录到分片 JSON 文件（JSON Array 格式）。"""
    entries: List[Dict] = []
    if filepath.exists():
        try:
            entries = json.loads(filepath.read_text(encoding="utf-8"))
        except Exception:
            entries = []
    entries.append(entry)
    filepath.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_all_shards(storage_dir: str) -> List[Dict]:
    """读取 data/diary/ 下所有分片文件，按时间顺序合并为单一列表。"""
    all_entries: List[Dict] = []
    storage = Path(storage_dir)
    if not storage.exists():
        return all_entries
    for f in sorted(storage.glob("tasks_*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                all_entries.extend(data)
        except Exception:
            pass
    return all_entries


class SpiderEcoDiaryAdapter:
    """采集日志存储：JSON 文件持久化 + 自动分片 + 统计汇总 + 经验报告.

    spider_eco spider_diary/tool.py 独有功能完整迁移.
    分片写入 (年/月自动拆分)，支持 experience_report(success_rate + lessons).
    """

    def __init__(self, storage_dir: str = "data/diary") -> None:
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        # 启动时加载全部分片到内存索引
        self._entries: List[Dict[str, Any]] = _read_all_shards(str(self._storage_dir))

    def log_task(self, task_id: str, url: str = "", worker: str = "",
                 status: str = "success", result: Optional[Dict] = None,
                 notes: str = "") -> Dict[str, Any]:
        entry = {
            "task_id": task_id, "url": url, "worker": worker,
            "status": status, "result": result or {}, "notes": notes,
            "timestamp": datetime.now().isoformat(),
        }
        # 内存索引
        self._entries.append(entry)

        # 自动分片写入
        shard = _shard_path(str(self._storage_dir))
        _append_to_shard(shard, entry)
        logger.info("Diary logged: %s [%s] worker=%s → %s", task_id, status, worker, shard.name)
        return entry

    def query_by_task(self, task_id: str) -> Dict[str, Any]:
        for e in self._entries:
            if e.get("task_id") == task_id:
                return e
        return {"error": f"task '{task_id}' not found"}

    def query_by_worker(self, worker: str) -> List[Dict[str, Any]]:
        return [e for e in self._entries if e.get("worker") == worker]

    def query_by_status(self, status: str) -> List[Dict[str, Any]]:
        return [e for e in self._entries if e.get("status") == status]

    def query_by_date(self, date_str: str) -> List[Dict[str, Any]]:
        """按日期过滤 (YYYY-MM-DD)。"""
        return [e for e in self._entries if e.get("timestamp", "").startswith(date_str)]

    def summary(self) -> Dict[str, Any]:
        by_status: Dict[str, int] = {}
        by_worker: Dict[str, int] = {}
        for e in self._entries:
            s = e.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
            w = e.get("worker", "unknown")
            by_worker[w] = by_worker.get(w, 0) + 1

        # 分片文件统计
        shards = sorted(self._storage_dir.glob("tasks_*.json"))
        shard_info = [
            {"file": f.name, "size_mb": round(f.stat().st_size / 1024 / 1024, 2)}
            for f in shards
        ]

        return {
            "total_entries": len(self._entries),
            "by_status": by_status,
            "by_worker": by_worker,
            "latest_entry": self._entries[-1] if self._entries else None,
            "storage_dir": str(self._storage_dir),
            "shard_count": len(shard_info),
            "shards": shard_info,
        }

    def experience_report(self) -> Dict[str, Any]:
        total = len(self._entries)
        if total == 0:
            return {"total": 0, "message": "no entries yet"}
        successful = sum(1 for e in self._entries if e.get("status") == "success")
        failed = sum(1 for e in self._entries if e.get("status") in ("failed", "error"))
        lessons = [e.get("notes", "") for e in self._entries
                   if e.get("status") in ("failed", "error") and e.get("notes")]
        success_rate = round(successful / total * 100, 1) if total > 0 else 0.0
        return {
            "total": total, "successful": successful, "failed": failed,
            "success_rate": f"{success_rate}%",
            "lessons": lessons[:20],
            "generated_at": datetime.now().isoformat(),
        }

    def get_status(self) -> Dict[str, Any]:
        shards = list(self._storage_dir.glob("tasks_*.json"))
        total_size = sum(f.stat().st_size for f in shards)
        return {
            "total_entries": len(self._entries),
            "storage_dir": str(self._storage_dir),
            "storage_exists": self._storage_dir.exists(),
            "shard_count": len(shards),
            "total_size_mb": round(total_size / 1024 / 1024, 2),
        }
