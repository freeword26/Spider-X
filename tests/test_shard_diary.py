import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from spider_x.core.shard_writer import (
    ShardWriter, get_shard_path, append_to_shard, read_all_shards,
    DEFAULT_SHARD_LIMIT,
)
from spider_x.adapters.spider_eco_diary import SpiderEcoDiaryAdapter


# ── ShardWriter Tests ──

class TestGetShardPath:
    def test_year_shard(self, tmp_path):
        p = get_shard_path(str(tmp_path))
        assert p.name == f"tasks_{datetime.now().year}.json"

    def test_month_shard_when_year_full(self, tmp_path):
        # 创建一个超过限制的 "年" 分片
        year = datetime.now().year
        base = tmp_path / f"tasks_{year}.json"
        base.write_text("x" * (DEFAULT_SHARD_LIMIT + 1))
        p = get_shard_path(str(tmp_path))
        assert p.name == f"tasks_{year}_{datetime.now().month:02d}.json"

    def test_next_year_when_all_months_full(self, tmp_path):
        year = datetime.now().year
        # 从当前月到12月全部填满
        start_month = datetime.now().month
        for m in range(start_month, 13):
            f = tmp_path / f"tasks_{year}_{m:02d}.json"
            f.write_text("x" * (DEFAULT_SHARD_LIMIT + 1))
        # 年分片本身也填满
        base = tmp_path / f"tasks_{year}.json"
        base.write_text("x" * (DEFAULT_SHARD_LIMIT + 1))
        p = get_shard_path(str(tmp_path))
        assert p.name == f"tasks_{year + 1}_01.json"


class TestAppendToShard:
    def test_create_new_file(self, tmp_path):
        fp = tmp_path / "test.json"
        append_to_shard(fp, {"id": 1})
        data = json.loads(fp.read_text())
        assert len(data) == 1
        assert data[0]["id"] == 1

    def test_append_to_existing(self, tmp_path):
        fp = tmp_path / "test.json"
        append_to_shard(fp, {"id": 1})
        append_to_shard(fp, {"id": 2})
        data = json.loads(fp.read_text())
        assert len(data) == 2

    def test_overwrite_corrupted_file(self, tmp_path):
        fp = tmp_path / "test.json"
        fp.write_text("not valid json{{{")
        append_to_shard(fp, {"id": 1})
        data = json.loads(fp.read_text())
        assert len(data) == 1


class TestReadAllShards:
    def test_read_single_shard(self, tmp_path):
        entries = [{"id": 1}, {"id": 2}]
        (tmp_path / "tasks_2026.json").write_text(json.dumps(entries))
        result = read_all_shards(str(tmp_path))
        assert len(result) == 2

    def test_read_multiple_shards_sorted(self, tmp_path):
        (tmp_path / "tasks_01.json").write_text(json.dumps([{"id": 1}]))
        (tmp_path / "tasks_03.json").write_text(json.dumps([{"id": 3}]))
        (tmp_path / "tasks_02.json").write_text(json.dumps([{"id": 2}]))
        result = read_all_shards(str(tmp_path))
        assert [r["id"] for r in result] == [1, 2, 3]

    def test_no_shards(self, tmp_path):
        result = read_all_shards(str(tmp_path))
        assert result == []


class TestShardWriter:
    def test_append(self, tmp_path):
        w = ShardWriter(str(tmp_path))
        shard = w.append({"task_id": "t1"})
        assert shard.exists()
        assert w.count == 1

    def test_append_many(self, tmp_path):
        w = ShardWriter(str(tmp_path))
        entries = [{"task_id": f"t{i}"} for i in range(5)]
        w.append_many(entries)
        all_data = w.read_all()
        assert len(all_data) == 5

    def test_read_all(self, tmp_path):
        w = ShardWriter(str(tmp_path))
        w.append({"task_id": "t1"})
        w.append({"task_id": "t2"})
        all_data = w.read_all()
        assert len(all_data) == 2

    def test_get_shard_info(self, tmp_path):
        w = ShardWriter(str(tmp_path))
        w.append({"task_id": "t1"})
        info = w.get_shard_info()
        assert len(info) == 1
        assert "size_mb" in info[0]

    def test_custom_prefix(self, tmp_path):
        w = ShardWriter(str(tmp_path), prefix="diary")
        shard = w.append({"id": 1})
        assert "diary_" in shard.name


# ── SpiderEcoDiaryAdapter Tests ──

class TestSpiderEcoDiaryAdapter:
    def test_log_and_query(self, tmp_path):
        adapter = SpiderEcoDiaryAdapter(storage_dir=str(tmp_path))
        adapter.log_task("task-001", url="https://example.com", worker="w1")
        result = adapter.query_by_task("task-001")
        assert result["task_id"] == "task-001"
        assert result["status"] == "success"

    def test_query_by_worker(self, tmp_path):
        adapter = SpiderEcoDiaryAdapter(storage_dir=str(tmp_path))
        adapter.log_task("t1", worker="w1")
        adapter.log_task("t2", worker="w2")
        adapter.log_task("t3", worker="w1")
        results = adapter.query_by_worker("w1")
        assert len(results) == 2

    def test_query_by_status(self, tmp_path):
        adapter = SpiderEcoDiaryAdapter(storage_dir=str(tmp_path))
        adapter.log_task("t1", status="success")
        adapter.log_task("t2", status="failed")
        assert len(adapter.query_by_status("success")) == 1
        assert len(adapter.query_by_status("failed")) == 1

    def test_summary(self, tmp_path):
        adapter = SpiderEcoDiaryAdapter(storage_dir=str(tmp_path))
        adapter.log_task("t1", status="success", worker="w1")
        adapter.log_task("t2", status="failed", worker="w2")
        summary = adapter.summary()
        assert summary["total_entries"] == 2
        assert summary["by_status"]["success"] == 1
        assert summary["shard_count"] >= 1

    def test_experience_report(self, tmp_path):
        adapter = SpiderEcoDiaryAdapter(storage_dir=str(tmp_path))
        adapter.log_task("t1", status="success")
        adapter.log_task("t2", status="success")
        adapter.log_task("t3", status="failed", notes="超时")
        report = adapter.experience_report()
        assert report["total"] == 3
        assert report["successful"] == 2
        assert report["failed"] == 1
        assert "超时" in report["lessons"]

    def test_get_status(self, tmp_path):
        adapter = SpiderEcoDiaryAdapter(storage_dir=str(tmp_path))
        adapter.log_task("t1")
        status = adapter.get_status()
        assert status["total_entries"] == 1
        assert status["shard_count"] >= 1

    def test_persistence_across_instances(self, tmp_path):
        dir_path = str(tmp_path)
        adapter1 = SpiderEcoDiaryAdapter(storage_dir=dir_path)
        adapter1.log_task("t1", worker="w1")
        # 新实例应加载已有分片
        adapter2 = SpiderEcoDiaryAdapter(storage_dir=dir_path)
        result = adapter2.query_by_task("t1")
        assert result["task_id"] == "t1"

    def test_shard_rotation(self, tmp_path):
        """验证当年分片超 50MB 后自动按月拆分。"""
        dir_path = str(tmp_path)
        adapter = SpiderEcoDiaryAdapter(storage_dir=dir_path)
        # 模拟写满年分片
        year_file = tmp_path / f"tasks_{datetime.now().year}.json"
        year_file.write_text("x" * (DEFAULT_SHARD_LIMIT + 1))
        # 再写一条，应落到月分片
        adapter.log_task("big-task")
        month_shard = tmp_path / f"tasks_{datetime.now().year}_{datetime.now().month:02d}.json"
        assert month_shard.exists()
