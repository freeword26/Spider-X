"""Spider-X Adapter: SpiderEco Room — 多Agent协作空间（来自 spider_eco 独特功能）.

将 spider_eco 的 SpidermaxRoomPlugin 完整能力迁移到 Spider-X.
Spider-X 原有 SpiderRoomAdapter 只有 workflow 注册这个是 session 管理 + agent 协作 + URL 分发.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("spider_x.adapters.spider_eco_room")


class SpiderEcoRoomAdapter:
    """多Agent协作空间：agent 注册 / session 管理 / 任务分配 / URL 协调分发.

    spider_eco spidermax_room/skill.py 独有功能完整迁移.
    支持 sessions、assign_task、coordinate_crawl(round_robin/chunk).
    """

    def __init__(self) -> None:
        self._active: bool = False
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def activate(self, meta_url: str = "", **kwargs) -> Dict[str, Any]:
        self._active = True
        logger.info("SpiderEcoRoomAdapter activated")
        return {"status": "activated", "timestamp": datetime.now().isoformat()}

    def deactivate(self) -> Dict[str, Any]:
        self._active = False
        self._agents.clear()
        self._sessions.clear()
        return {"status": "deactivated"}

    def register_agent(self, agent_id: str = "", agent_type: str = "worker",
                       capabilities: Optional[List[str]] = None) -> Dict[str, Any]:
        if not self._active:
            return {"error": "room not active"}
        if not agent_id:
            agent_id = f"agent-{uuid.uuid4().hex[:8]}"
        self._agents[agent_id] = {
            "agent_id": agent_id, "agent_type": agent_type,
            "capabilities": capabilities or [],
            "registered_at": datetime.now().isoformat(),
            "status": "idle",
        }
        return {"status": "registered", "agent_id": agent_id, "agent_type": agent_type}

    def list_agents(self) -> List[Dict[str, Any]]:
        return list(self._agents.values())

    def remove_agent(self, agent_id: str) -> Dict[str, Any]:
        if agent_id in self._agents:
            del self._agents[agent_id]
            return {"status": "removed", "agent_id": agent_id}
        return {"error": f"agent '{agent_id}' not found"}

    def create_session(self, session_name: str = "", task_description: str = "") -> Dict[str, Any]:
        if not self._active:
            return {"error": "room not active"}
        session_id = f"room-{uuid.uuid4().hex[:8]}"
        self._sessions[session_id] = {
            "session_id": session_id,
            "session_name": session_name,
            "task_description": task_description,
            "participants": [],
            "tasks": [],
            "status": "created",
            "created_at": datetime.now().isoformat(),
        }
        return {"status": "created", "session_id": session_id, "session_name": session_name}

    def assign_task(self, session_id: str, agent_id: str, task: str = "") -> Dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return {"error": f"session '{session_id}' not found"}
        agent = self._agents.get(agent_id)
        if not agent:
            return {"error": f"agent '{agent_id}' not found"}
        task_entry = {
            "task": task, "agent_id": agent_id,
            "status": "assigned",
            "assigned_at": datetime.now().isoformat(),
        }
        session["tasks"].append(task_entry)
        if agent_id not in session["participants"]:
            session["participants"].append(agent_id)
        agent["status"] = "busy"
        return {"status": "assigned", "session_id": session_id, "agent_id": agent_id}

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return {"error": f"session '{session_id}' not found"}
        status_counts: Dict[str, int] = {}
        for t in session["tasks"]:
            s = t.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1
        return {
            "session_id": session_id,
            "session_name": session["session_name"],
            "status": session["status"],
            "participants": session["participants"],
            "task_count": len(session["tasks"]),
            "task_status": status_counts,
            "created_at": session["created_at"],
        }

    def list_sessions(self) -> List[Dict[str, Any]]:
        return [
            {"session_id": s["session_id"], "session_name": s["session_name"],
             "status": s["status"], "participants": len(s["participants"]),
             "tasks": len(s["tasks"])}
            for s in self._sessions.values()
        ]

    def coordinate_crawl(self, session_id: str, urls: List[str],
                         strategy: str = "round_robin") -> Dict[str, Any]:
        """协调多个 agent 分发 URL 采集任务."""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": f"session '{session_id}' not found"}
        agents = [aid for aid, a in self._agents.items() if a.get("status") in ("idle", "busy")]
        if not agents:
            return {"error": "no available agents"}

        distribution: Dict[str, List[str]] = {aid: [] for aid in agents}
        if strategy == "round_robin":
            for i, url in enumerate(urls):
                agent_id = agents[i % len(agents)]
                distribution[agent_id].append(url)
        elif strategy == "chunk":
            chunk_size = max(1, len(urls) // len(agents))
            for i, agent_id in enumerate(agents):
                start = i * chunk_size
                end = start + chunk_size if i < len(agents) - 1 else len(urls)
                distribution[agent_id] = urls[start:end]
        else:
            return {"error": f"unknown strategy: {strategy}"}

        # 创建分配记录
        assignments = []
        for agent_id, agent_urls in distribution.items():
            if agent_urls:
                task_entry = {
                    "task": f"crawl_{strategy}", "agent_id": agent_id,
                    "urls": agent_urls, "url_count": len(agent_urls),
                    "status": "assigned", "assigned_at": datetime.now().isoformat(),
                }
                session["tasks"].append(task_entry)
                assignments.append({"agent_id": agent_id, "url_count": len(agent_urls)})
                if agent_id not in session["participants"]:
                    session["participants"].append(agent_id)

        session["status"] = "running"
        return {
            "status": "coordinated", "strategy": strategy,
            "total_urls": len(urls), "agents_used": len([a for a in assignments if a["url_count"] > 0]),
            "assignments": assignments,
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "active": self._active,
            "agents": len(self._agents),
            "sessions": len(self._sessions),
            "agent_ids": list(self._agents.keys()),
            "session_ids": list(self._sessions.keys()),
        }
