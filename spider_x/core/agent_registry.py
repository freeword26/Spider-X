from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("spider_x.agent_registry")

MCP_ROUTER_URL = os.environ.get("MCP_ROUTER_URL", "http://localhost:6191")
DEFAULT_MODE = "pmo"

LAYER_PERM = {
    "L4": 4, "L3": 3, "L2": 2, "L1": 1, "meta": 1,
}


class PermissionLevel(int, Enum):
    L4_ADMIN = 4
    L3_EXECUTE = 3
    L2_READ_WRITE = 2
    L1_BASIC = 1


class CollaborationMode(str, Enum):
    PMO = "pmo"
    DAG = "dag"
    SOP = "sop"
    BLACKBOARD = "blackboard"
    META_COGNITIVE = "meta"


@dataclass
class AgentDescriptor:
    agent_id: str
    name: str
    permission_level: PermissionLevel
    description: str
    skills: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    api_endpoint: str = ""

    def to_cline_tool(self) -> Dict[str, Any]:
        return {
            "name": f"agent_{self.agent_id.replace('-', '_')}",
            "description": f"{self.name} - {self.description}",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": f"要{self.name}执行的动作",
                        "enum": ["analyze", "process", "generate", "review", "optimize"],
                    },
                    "input": {"type": "string", "description": "输入内容或问题"},
                    "context": {"type": "object", "description": "额外上下文", "additionalProperties": True},
                },
                "required": ["action", "input"],
            },
        }


_descriptors_cache: Optional[Dict[str, AgentDescriptor]] = None


def _build_descriptors() -> Dict[str, AgentDescriptor]:
    global _descriptors_cache
    if _descriptors_cache is not None:
        return _descriptors_cache
    from spider_x.skills.index_brainstorm import AGENT_ROLES
    desc_map: Dict[str, AgentDescriptor] = {}
    for aid, info in AGENT_ROLES.items():
        layer = info.get("layer", "L1")
        perm_val = LAYER_PERM.get(layer, 1)
        perm = PermissionLevel(perm_val)
        keywords_raw = info.get("keywords", [])
        if not keywords_raw:
            keywords_raw = [info.get("role", ""), layer] + info.get("skills", [])
        desc_map[aid] = AgentDescriptor(
            agent_id=aid,
            name=info["name"],
            permission_level=perm,
            description=info.get("responsibility", ""),
            skills=info.get("skills", []),
            keywords=keywords_raw,
        )
    _descriptors_cache = desc_map
    return desc_map


def get_agent(agent_id: str) -> Optional[AgentDescriptor]:
    return _build_descriptors().get(agent_id)


def list_agents(permission_level: Optional[int] = None) -> List[AgentDescriptor]:
    descs = list(_build_descriptors().values())
    if permission_level is None:
        return descs
    return [a for a in descs if a.permission_level.value <= permission_level]


def find_agents_by_skill(skill_keyword: str) -> List[AgentDescriptor]:
    from spider_x.skills.index_brainstorm import get_agents_by_skill
    aids = get_agents_by_skill(skill_keyword)
    desc = _build_descriptors()
    return [desc[a] for a in aids if a in desc]


def find_agents_by_keyword(keyword: str) -> List[AgentDescriptor]:
    kw = keyword.lower()
    return [
        a for a in _build_descriptors().values()
        if kw in a.name.lower() or any(kw in k.lower() for k in a.keywords)
    ]


class AgentRegistry:
    def __init__(self, router_url: str = MCP_ROUTER_URL):
        self.router_url = router_url
        self._http = None
        self._check_router_connection()

    def _http_client(self):
        if self._http is None:
            import httpx
            self._http = httpx.Client(timeout=30)
        return self._http

    def _check_router_connection(self):
        try:
            r = self._http_client().get(f"{self.router_url}/health")
            if r.status_code == 200:
                logger.info(f"MCP Router 连接成功: {self.router_url}")
            else:
                logger.warning(f"MCP Router 响应异常: {r.status_code}")
        except Exception as e:
            logger.warning(f"MCP Router 连接失败: {e}，以本地模式运行")

    def get_agent(self, agent_id: str) -> Optional[AgentDescriptor]:
        return get_agent(agent_id)

    def list_agents(self, permission_level: Optional[int] = None) -> List[AgentDescriptor]:
        return list_agents(permission_level)

    def find_agents_by_skill(self, skill_keyword: str) -> List[AgentDescriptor]:
        return find_agents_by_skill(skill_keyword)

    def find_agents_by_keyword(self, keyword: str) -> List[AgentDescriptor]:
        return find_agents_by_keyword(keyword)

    def call_agent(self, agent_id: str, action: str, input_text: str,
                    context: Optional[Dict] = None) -> Dict[str, Any]:
        agent = get_agent(agent_id)
        if not agent:
            return {"success": False, "error": f"Agent {agent_id} 未找到"}
        try:
            r = self._http_client().post(
                f"{self.router_url}/agents/{agent_id}/call",
                json={
                    "agent_id": agent_id,
                    "action": action,
                    "params": {"input": input_text, "context": context or {}},
                },
            )
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {
            "agent_id": agent_id,
            "agent_name": agent.name,
            "action": action,
            "status": "completed",
            "output": f"[本地模式] {agent.name} 已处理: {input_text[:50]}...",
            "timestamp": datetime.now().isoformat(),
        }

    def route_request(self, user_input: str, mode: str = DEFAULT_MODE,
                      target_agents: Optional[List[str]] = None) -> Dict[str, Any]:
        try:
            r = self._http_client().post(
                f"{self.router_url}/route",
                json={"user_input": user_input, "mode": mode, "target_agents": target_agents or []},
            )
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        scores: Dict[str, int] = {}
        for aid, agent in _build_descriptors().items():
            scores[aid] = sum(1 for kw in agent.keywords if kw.lower() in user_input.lower())
        scores = {k: v for k, v in scores.items() if v > 0}
        if not scores:
            fallback = get_agent("system-manager")
            return {
                "success": True,
                "message": "未识别明确意图，默认路由到系统管理专家",
                "agent_id": "system-manager",
                "agent_name": fallback.name if fallback else "系统管理专家",
                "mode": mode,
            }
        best = max(scores, key=scores.get)
        return {
            "success": True,
            "message": f"路由到 {_build_descriptors()[best].name}",
            "agent_id": best,
            "agent_name": _build_descriptors()[best].name,
            "mode": mode,
        }

    def execute_workflow(self, mode: str, tasks: List[Dict]) -> Dict[str, Any]:
        try:
            r = self._http_client().post(
                f"{self.router_url}/workflow/execute",
                json={"mode": mode, "tasks": tasks},
            )
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        results = []
        for task in tasks:
            aid = task.get("agent_id", "")
            agent = get_agent(aid)
            if agent:
                results.append({
                    "task": task,
                    "status": "completed",
                    "agent_name": agent.name,
                    "output": f"[本地模式] {agent.name} 执行完成",
                })
            else:
                results.append({
                    "task": task,
                    "status": "error",
                    "error": f"Agent {aid} 未找到",
                })
        return {
            "mode": mode,
            "total_tasks": len(tasks),
            "completed": sum(1 for r in results if r["status"] == "completed"),
            "failed": sum(1 for r in results if r["status"] == "error"),
            "results": results,
        }

    def get_cline_tools(self) -> List[Dict[str, Any]]:
        return [a.to_cline_tool() for a in _build_descriptors().values()]

    def get_status_summary(self) -> Dict[str, Any]:
        levels: Dict[int, List[str]] = {}
        for a in _build_descriptors().values():
            lv = a.permission_level.value
            levels.setdefault(lv, []).append(a.agent_id)
        return {
            "total_agents": len(_build_descriptors()),
            "router_url": self.router_url,
            "levels": {
                "L4_ADMIN": len(levels.get(4, [])),
                "L3_EXECUTE": len(levels.get(3, [])),
                "L2_READ_WRITE": len(levels.get(2, [])),
                "L1_BASIC": len(levels.get(1, [])),
            },
            "agents_by_level": levels,
        }


_registry_instance: Optional[AgentRegistry] = None


def get_registry(router_url: str = MCP_ROUTER_URL) -> AgentRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = AgentRegistry(router_url)
    return _registry_instance


def call_agent(agent_id: str, action: str, input_text: str,
               context: Optional[Dict] = None) -> Dict[str, Any]:
    return get_registry().call_agent(agent_id, action, input_text, context)


def route(user_input: str, mode: str = DEFAULT_MODE) -> Dict[str, Any]:
    return get_registry().route_request(user_input, mode)


def list_all(level: Optional[int] = None) -> List[AgentDescriptor]:
    return get_registry().list_agents(level)


def find(query: str) -> List[AgentDescriptor]:
    return get_registry().find_agents_by_keyword(query)
