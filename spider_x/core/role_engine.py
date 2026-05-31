"""Spider-X Role Engine — 任务路由 + 本地/云端AI执行.

架构:
  AIRouter      → 按任务关键词匹配角色, 优先级+成本排序
  LocalAIClient → Ollama 本地模型 (codellama/qwen)
  CloudAIProxy  → 云端模型 (Claude/GPT)
  RoleEngine    → 统一入口, 支持并行执行+结果聚合
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import yaml

logger = logging.getLogger("spider_x.role_engine")

DEFAULT_ROLES_PATH = str(Path(__file__).resolve().parent.parent.parent / "roles.yaml")


class AIType(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    BUILTIN = "builtin"


@dataclass
class Role:
    name: str
    type: AIType
    provider: str
    model: str
    agent_id: str
    capabilities: List[str] = field(default_factory=list)
    priority: str = "medium"
    cost_factor: float = 0.0

    @property
    def is_local(self) -> bool:
        return self.type == AIType.LOCAL

    @property
    def is_cloud(self) -> bool:
        return self.type == AIType.CLOUD

    @property
    def priority_rank(self) -> int:
        return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(self.priority, 2)


# ── 本地AI客户端 ──────────────────────────────────────────

class CodeLlamaClient:
    """Ollama CodeLlama 客户端 — 代码生成/审查/调试."""

    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host

    async def generate(self, prompt: str, temperature: float = 0.7,
                       max_tokens: int = 2048) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.host}/api/generate",
                json={
                    "model": "codellama:7b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                },
            )
            resp.raise_for_status()
            return resp.json().get("response", "")


class QwenClient:
    """Ollama Qwen 客户端 — 数据分析/报告生成."""

    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host

    async def generate(self, prompt: str, system: str = "You are a data analyst.",
                       temperature: float = 0.5, max_tokens: int = 4096) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.host}/api/generate",
                json={
                    "model": "qwen:14b",
                    "prompt": f"{system}\n\n{prompt}",
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                },
            )
            resp.raise_for_status()
            return resp.json().get("response", "")


# ── 云端AI代理 ──────────────────────────────────────────

class ClaudeProxy:
    """Anthropic Claude API 代理."""

    def __init__(self):
        self.api_key = os.environ.get("CLAUDE_API_KEY", "")
        self.base_url = "https://api.anthropic.com/v1"

    async def call(self, model: str, prompt: str,
                   max_tokens: int = 4096) -> str:
        if not self.api_key:
            return "[ClaudeProxy] CLAUDE_API_KEY not set"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/messages",
                headers=headers,
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            blocks = data.get("content", [{}])
            return blocks[0].get("text", "") if blocks else ""


class OpenAIProxy:
    """OpenAI GPT API 代理."""

    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.base_url = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")

    async def call(self, model: str, prompt: str, system: str = "You are a helpful assistant.",
                   max_tokens: int = 4096) -> str:
        if not self.api_key:
            return "[OpenAIProxy] OPENAI_API_KEY not set"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [{}])
            return choices[0].get("message", {}).get("content", "")


# ── AIRouter ────────────────────────────────────────────

class AIRouter:
    """AI任务路由器 — 关键词匹配 + 优先级排序."""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.roles: Dict[str, Role] = {}
        self._load_roles()

    def _load_roles(self) -> None:
        p = Path(self.config_path)
        if not p.exists():
            logger.warning("roles.yaml not found: %s", self.config_path)
            return
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        for name, cfg in (data.get("roles", {}) or {}).items():
            self.roles[name] = Role(
                name=name,
                type=AIType(cfg.get("type", "local")),
                provider=cfg.get("provider", "ollama"),
                model=cfg.get("model", ""),
                agent_id=cfg.get("agent_id", name),
                capabilities=cfg.get("capabilities", []),
                priority=cfg.get("priority", "medium"),
                cost_factor=cfg.get("cost_factor", 0.0),
            )
        logger.info("AIRouter loaded %d roles", len(self.roles))

    def match_role(self, task: str) -> List[Role]:
        """根据任务内容匹配角色，按优先级+成本排序.

        匹配逻辑:
          1. 直接匹配 capabilities 中的关键词（英文）
          2. 匹配中文同义词映射
          3. 按优先级+成本排序
        """
        task_lower = task.lower()
        matched = []

        # 中英文能力关键词映射
        CAP_SYNONYMS = {
            "code_generation": ["写代码", "编写", "编码", "实现", "开发", "写一个", "生成代码", "代码生成", "programming", "coding", "write", "generate", "build", "develop", "create", "implement"],
            "debugging": ["调试", "debug", "修复", "fix", "bug", "报错", "错误"],
            "code_review": ["审查", "review", "检查代码", "code review", "评审"],
            "refactoring": ["重构", "refactor", "优化代码", "重写"],
            "data_analysis": ["分析数据", "数据分析", "统计", "data analysis", "analyze", "analysis"],
            "visualization": ["可视化", "图表", "visualization", "chart", "graph", "plot"],
            "report_generation": ["报告", "report", "总结", "生成报告"],
            "web_research": ["研究", "搜索", "查找", "调研", "research", "search"],
            "information_gathering": ["收集", "gather", "查找信息"],
            "fact_checking": ["验证", "事实", "核实", "fact check", "verify"],
            "deep_analysis": ["深度分析", "深入分析", "deep analysis"],
            "content_creation": ["创作", "创建内容", "内容", "content", "写"],
            "copywriting": ["文案", "广告", "营销", "copywriting", "copy"],
            "storytelling": ["故事", "叙述", "story", "narrative"],
            "translation": ["翻译", "translate", "localization"],
            "social_content": ["社交", "微博", "微信", "小红书", "抖音", "social media"],
            "engagement_strategy": ["互动", "用户粘性", "engagement", "互动策略"],
            "trend_analysis": ["趋势", "热点", "流行", "trend"],
            "architecture_design": ["架构", "系统设计", "architecture", "system design"],
            "system_planning": ["规划", "方案", "planning", "roadmap"],
            "tech_evaluation": ["技术评估", "技术选型", "evaluation", "assessment"],
            "security_audit": ["安全审计", "渗透测试", "security audit", "penetration"],
            "vulnerability_scan": ["漏洞扫描", "漏洞", "vulnerability", "cve"],
            "compliance_check": ["合规", "compliance", "法规", "regulation"],
            "threat_modeling": ["威胁建模", "threat", "风险"],
            "performance_analysis": ["性能", "优化", "performance", "optimization"],
            "security_check": ["安全检查", "security", "权限", "鉴权"],
            "task_planning": ["任务规划", "项目计划", "task planning", "project plan"],
            "resource_estimation": ["资源估算", "估时", "estimation"],
            "risk_assessment": ["风险评估", "风险", "risk"],
            "milestone_tracking": ["里程碑", "进度跟踪", "milestone", "progress"],
        }

        for role in self.roles.values():
            if role.type == AIType.BUILTIN:
                continue
            # 直接 capability 匹配
            if any(cap.lower() in task_lower for cap in role.capabilities):
                matched.append(role)
                continue
            # 同义词匹配
            for cap in role.capabilities:
                synonyms = CAP_SYNONYMS.get(cap, [])
                if any(syn.lower() in task_lower for syn in synonyms):
                    matched.append(role)
                    break

        matched.sort(key=lambda r: (r.priority_rank, r.cost_factor))
        return matched

    def reload(self) -> None:
        self.roles.clear()
        self._load_roles()


# ── RoleEngine ──────────────────────────────────────────

class RoleEngine:
    """统一角色引擎 — 路由 + 执行 + 聚合."""

    def __init__(self, roles_path: str = DEFAULT_ROLES_PATH):
        self._roles_path = roles_path
        self._ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        # 路由
        self.router = AIRouter(roles_path)
        # 本地客户端
        self.code_llama = CodeLlamaClient(self._ollama_host)
        self.qwen = QwenClient(self._ollama_host)
        # 云端代理
        self.claude = ClaudeProxy()
        self.openai = OpenAIProxy()

    def load(self) -> int:
        self.router.reload()
        return len(self.router.roles)

    # ── 查询 ───────────────────────────────────────────

    def get_role(self, role_id: str) -> Optional[Role]:
        return self.router.roles.get(role_id)

    def list_roles(self, role_type: str = "") -> List[Role]:
        roles = list(self.router.roles.values())
        if role_type:
            roles = [r for r in roles if r.type == role_type]
        return roles

    def find_by_capability(self, cap: str) -> List[Role]:
        return [r for r in self.router.roles.values() if cap in r.capabilities]

    # ── 执行 ───────────────────────────────────────────

    async def execute(self, role_id: str, prompt: str,
                      context: Optional[Dict] = None) -> Dict[str, Any]:
        """单角色执行."""
        role = self.get_role(role_id)
        if not role:
            return {"error": f"Role '{role_id}' not found", "status": "error"}
        return await self._dispatch(role, prompt, context)

    async def execute_task(self, task: str, context: Optional[Dict] = None,
                            max_parallel: int = 3) -> Dict[str, Any]:
        """自动路由 → 并行执行 → 结果聚合."""
        matched = self.router.match_role(task)
        if not matched:
            return {"error": "No suitable AI role found", "status": "error"}

        selected = matched[:max_parallel]
        logger.info("Task routed to %d roles: %s",
                     len(selected), [r.name for r in selected])

        tasks = [self._dispatch(r, task, context) for r in selected]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self._aggregate(results, selected)

    async def _dispatch(self, role: Role, prompt: str,
                         context: Optional[Dict] = None) -> Dict[str, Any]:
        """按角色类型分发到对应客户端."""
        try:
            if role.is_local:
                return await self._exec_local(role, prompt, context)
            if role.is_cloud:
                return await self._exec_cloud(role, prompt, context)
            return {"role": role.name, "status": "skipped", "message": "builtin role"}
        except Exception as e:
            logger.error("Role execution failed [%s]: %s", role.name, e)
            return {"role": role.name, "status": "error", "error": str(e)}

    async def _exec_local(self, role: Role, prompt: str,
                           ctx: Optional[Dict] = None) -> Dict[str, Any]:
        model = role.model.lower()
        if "codellama" in model:
            text = await self.code_llama.generate(prompt)
        elif "qwen" in model:
            system = (ctx or {}).get("system", "You are a data analyst.")
            text = await self.qwen.generate(prompt, system=system)
        else:
            # 通用 Ollama 调用
            text = await self.code_llama.generate(prompt)
        return {"role": role.name, "type": "local", "provider": role.provider,
                "model": role.model, "response": text, "status": "ok"}

    async def _exec_cloud(self, role: Role, prompt: str,
                           ctx: Optional[Dict] = None) -> Dict[str, Any]:
        model = role.model.lower()
        system = (ctx or {}).get("system", f"You are {role.name}, an AI assistant.")
        if model.startswith("claude"):
            text = await self.claude.call(role.model, prompt)
        elif model.startswith("gpt"):
            text = await self.openai.call(role.model, prompt, system=system)
        else:
            text = await self.openai.call(role.model, prompt, system=system)
        return {"role": role.name, "type": "cloud", "provider": role.provider,
                "model": role.model, "response": text, "status": "ok"}

    def _aggregate(self, results: list, roles: List[Role]) -> Dict[str, Any]:
        """聚合多角色执行结果."""
        primary = None
        alternatives = []
        sources = []
        errors = []
        for r, role in zip(results, roles):
            if isinstance(r, Exception):
                errors.append({"role": role.name, "error": str(r)})
                continue
            sources.append(role.name)
            if primary is None and r.get("status") == "ok":
                primary = r
            else:
                alternatives.append(r)
        return {
            "status": "ok" if primary else "error",
            "primary_result": primary,
            "alternative_results": alternatives,
            "sources": sources,
            "errors": errors,
        }

    # ── 统计 ───────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        local = [r for r in self.router.roles.values() if r.is_local]
        cloud = [r for r in self.router.roles.values() if r.is_cloud]
        builtin = [r for r in self.router.roles.values() if r.type == AIType.BUILTIN]
        return {
            "total_roles": len(self.router.roles),
            "local_count": len(local),
            "cloud_count": len(cloud),
            "builtin_count": len(builtin),
            "ollama_host": self._ollama_host,
            "local_roles": [r.name for r in local],
            "cloud_roles": [r.name for r in cloud],
        }
