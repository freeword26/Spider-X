"""Spider-X 数据分片写入工具.

使用示例:
    from spider_x.core.shard_writer import ShardWriter

    writer = ShardWriter("data/tasks")
    writer.append({"task_id": "t1", "status": "done"})

    # 自动按年分片，超 50MB 按月拆分
    # → data/tasks/tasks_2026.json
    # → data/tasks/tasks_2026_07.json  (当 2026.json 超 50MB)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("spider_x.shard_writer")

DEFAULT_SHARD_LIMIT = 50 * 1024 * 1024  # 50 MB


def get_shard_path(storage_dir: str, dt: Optional[datetime] = None,
                   size_limit: int = DEFAULT_SHARD_LIMIT) -> Path:
    """计算当前应写入的分片文件路径。

    规则:
      1. 按年分片 → tasks_2026.json
      2. 当年文件超过 size_limit → 按月拆分 → tasks_2026_06.json
      3. 当月也满 → 继续往下月轮转
    """
    now = dt or datetime.now()
    year = now.year
    base = Path(storage_dir) / f"tasks_{year}.json"

    if not base.exists() or base.stat().st_size < size_limit:
        return base

    month = now.month
    while month <= 12:
        shard = Path(storage_dir) / f"tasks_{year}_{month:02d}.json"
        if not shard.exists() or shard.stat().st_size < size_limit:
            return shard
        month += 1

    # 12月也满，次年1月
    return Path(storage_dir) / f"tasks_{year + 1}_01.json"


def append_to_shard(filepath: Path, entry: Dict) -> None:
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


def read_all_shards(storage_dir: str, pattern: str = "tasks_*.json") -> List[Dict]:
    """读取 storage_dir 下所有分片文件，按文件名排序后合并。"""
    all_entries: List[Dict] = []
    storage = Path(storage_dir)
    if not storage.exists():
        return all_entries
    for f in sorted(storage.glob(pattern)):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                all_entries.extend(data)
        except Exception:
            pass
    return all_entries


class ShardWriter:
    """自动分片 JSON 写入器.

    每个分片文件是一个 JSON Array，追加写入。
    自动按年/月分片，单文件不超 size_limit。
    """

    def __init__(self, storage_dir: str, prefix: str = "tasks",
                 size_limit: int = DEFAULT_SHARD_LIMIT):
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._prefix = prefix
        self._size_limit = size_limit
        self._count = 0

    def append(self, entry: Dict, dt: Optional[datetime] = None) -> Path:
        """追加一条记录，返回写入的分片文件路径。"""
        shard = self._resolve_shard(dt)
        append_to_shard(shard, entry)
        self._count += 1
        return shard

    def append_many(self, entries: List[Dict], dt: Optional[datetime] = None) -> Path:
        """批量追加多条记录到同一分片。"""
        shard = self._resolve_shard(dt)
        existing: List[Dict] = []
        if shard.exists():
            try:
                existing = json.loads(shard.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        existing.extend(entries)
        shard.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._count += len(entries)
        return shard

    def read_all(self) -> List[Dict]:
        """读取全部分片，合并返回。"""
        return read_all_shards(str(self._dir), f"{self._prefix}_*.json")

    def get_shard_info(self) -> List[Dict]:
        """返回分片文件列表及大小。"""
        shards = sorted(self._dir.glob(f"{self._prefix}_*.json"))
        return [
            {"file": f.name, "size_mb": round(f.stat().st_size / 1024 / 1024, 2)}
            for f in shards
        ]

    def _resolve_shard(self, dt: Optional[datetime] = None) -> Path:
        now = dt or datetime.now()
        year = now.year
        base = self._dir / f"{self._prefix}_{year}.json"
        if not base.exists() or base.stat().st_size < self._size_limit:
            return base
        month = now.month
        while month <= 12:
            shard = self._dir / f"{self._prefix}_{year}_{month:02d}.json"
            if not shard.exists() or shard.stat().st_size < self._size_limit:
                return shard
            month += 1
        return self._dir / f"{self._prefix}_{year + 1}_01.json"

    @property
    def count(self) -> int:
        return self._count
