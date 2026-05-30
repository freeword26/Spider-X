"""Spider-X Adapter: SpiderEco Diary — 采集日志存储与经验报告（来自 spider_eco 独特功能）.

将 spider_eco 的 SpiderDiary 完整能力迁移到 Spider-X.
Spider-X 原有 SpiderDiaryAdapter 只有报告这个是 JSON 文件存储 + experience_report.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("spider_x.adapters.spider_eco_diary")


class SpiderEcoDiaryAdapter:
    """采集日志存储：JSON 文件持久化 + 统计汇总 + 经验报告.

    spider_eco spider_diary/tool.py 独有功能完整迁移.
    每个 task 单独 .json 文件，支持 experience_report(success_rate + lessons).
    """

    def __init__(self, storage_dir: str = "data/diary") -> None:
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._entries: List[Dict[str, Any]] = []
        self._load_existing()

    def _load_existing(self) -> None:
        for f in sorted(self._storage_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                self._entries.append(data)
            except Exception:
                pass

    def log_task(self, task_id: str, url: str = "", worker: str = "",
                 status: str = "success", result: Optional[Dict] = None,
                 notes: str = "") -> Dict[str, Any]:
        entry = {
            "task_id": task_id, "url": url, "worker": worker,
            "status": status, "result": result or {}, "notes": notes,
            "timestamp": datetime.now().isoformat(),
        }
        self._entries.append(entry)
        (self._storage_dir / f"{task_id}.json").write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        logger.info("Diary logged: %s [%s] worker=%s", task_id, status, worker)
        return entry

    def query_by_task(self, task_id: str) -> Dict[str, Any]:
        f = self._storage_dir / f"{task_id}.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        return {"error": f"task '{task_id}' not found"}

    def query_by_worker(self, worker: str) -> List[Dict[str, Any]]:
        return [e for e in self._entries if e.get("worker") == worker]

    def query_by_status(self, status: str) -> List[Dict[str, Any]]:
        return [e for e in self._entries if e.get("status") == status]

    def summary(self) -> Dict[str, Any]:
        by_status: Dict[str, int] = {}
        by_worker: Dict[str, int] = {}
        for e in self._entries:
            s = e.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
            w = e.get("worker", "unknown")
            by_worker[w] = by_worker.get(w, 0) + 1
        return {
            "total_entries": len(self._entries),
            "by_status": by_status, "by_worker": by_worker,
            "latest_entry": self._entries[-1] if self._entries else None,
            "storage_dir": str(self._storage_dir),
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
        return {
            "total_entries": len(self._entries),
            "storage_dir": str(self._storage_dir),
            "storage_exists": self._storage_dir.exists(),
        }
