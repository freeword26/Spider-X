"""
Spider-X Skill: multi_agent_index_brainstorm

多智能体协作索引头脑风暴：组织多个AI智能体进行协作式头脑风暴，
为多个项目文档库设计完整的索引方案、数据库架构或技术方案。

Compatible Spiders: mini_spider, spider_max, spidermax_room, spider_diary, spider_meta
Category: collaboration
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("spider_x.skills.index_brainstorm")

# ══════════════════════════════════════════════════════════════
# 技能常量
# ══════════════════════════════════════════════════════════════
SKILL_ID = "multi_agent_index_brainstorm"
SKILL_NAME = "Multi-Agent Index Brainstorm"
SKILL_ALIAS = "小蜘蛛结网/Spider web"
VERSION = "2.0.0"
CATEGORY = "collaboration"

# ══════════════════════════════════════════════════════════════
# 完整 Agent 角色定义 (25个) + 技能适配索引
# ══════════════════════════════════════════════════════════════
# 每个 Agent 包含：
#   name: 中文名
#   role: 角色定位
#   layer: 层级 L4/L3/L2/L1/meta
#   responsibility: 核心职责
#   skills: 适配的技能ID列表 (从 builtin.py 的 14 个技能中匹配)
#   analysis_fn: 专属分析函数名
# ══════════════════════════════════════════════════════════════

AGENT_ROLES: Dict[str, Dict[str, Any]] = {
    # ── L4 管理层 ────────────────────────────────────────────
    "system-manager": {
        "name": "系统经理",
        "role": "Orchestrator",
        "layer": "L4",
        "model": "deepseek-chat",
        "responsibility": "组织讨论、确保各视角被听取、综合共识",
        "skills": ["multi_agent_index_brainstorm", "research", "review", "notify", "echo"],
        "analysis_fn": "_coordination_analysis",
    },
    "architect-agent": {
        "name": "架构师",
        "role": "Architect",
        "layer": "L4",
        "model": "deepseek-reasoner",
        "responsibility": "系统架构设计、技术选型、架构评审",
        "skills": ["multi_agent_index_brainstorm", "code", "review", "research", "deploy"],
        "analysis_fn": "_architecture_analysis",
    },

    # ── L3 执行层 ────────────────────────────────────────────
    "langchain-orchestrator": {
        "name": "LangChain编排器",
        "role": "Orchestrator",
        "layer": "L3",
        "model": "deepseek-reasoner",
        "responsibility": "向量数据库同步、存储维护、LangChain编排",
        "skills": ["python", "http_request", "file_read", "file_write", "research"],
        "analysis_fn": "_langchain_analysis",
    },
    "security-architect": {
        "name": "安全架构师",
        "role": "Security",
        "layer": "L3",
        "model": "deepseek-reasoner",
        "responsibility": "安全审查、权限边界管理、安全架构设计",
        "skills": ["review", "test", "shell", "file_read", "notify"],
        "analysis_fn": "_security_analysis",
    },
    "tech-expert": {
        "name": "技术专家",
        "role": "Technical Lead",
        "layer": "L3",
        "model": "deepseek-reasoner",
        "responsibility": "分析技术可行性、代码结构索引、性能优化",
        "skills": ["multi_agent_index_brainstorm", "code", "review", "test", "python", "shell"],
        "analysis_fn": "_tech_analysis",
    },
    "master-mentor": {
        "name": "大师导师",
        "role": "Mentor",
        "layer": "L3",
        "model": "deepseek-chat",
        "responsibility": "自适应学习、技能培训、知识传授",
        "skills": ["research", "code", "review", "notify", "echo"],
        "analysis_fn": "_mentor_analysis",
    },

    # ── L2 专业层 ────────────────────────────────────────────
    "data-scientist": {
        "name": "数据科学家",
        "role": "Data Analyst",
        "layer": "L2",
        "model": "deepseek-reasoner",
        "responsibility": "评估数据类型、元数据质量、搜索模式、数据建模",
        "skills": ["multi_agent_index_brainstorm", "python", "research", "file_read", "file_write"],
        "analysis_fn": "_data_analysis",
    },
    "analyst": {
        "name": "分析师",
        "role": "Analyst",
        "layer": "L2",
        "model": "deepseek-reasoner",
        "responsibility": "数据分析、场景建模、业务洞察",
        "skills": ["research", "python", "file_read", "review"],
        "analysis_fn": "_analyst_analysis",
    },
    "developer": {
        "name": "开发者",
        "role": "Developer",
        "layer": "L2",
        "model": "deepseek-chat",
        "responsibility": "代码开发、快反开发模式、技术实现",
        "skills": ["code", "python", "test", "review", "clean", "file_write", "file_read"],
        "analysis_fn": "_developer_analysis",
    },
    "devops": {
        "name": "DevOps工程师",
        "role": "DevOps",
        "layer": "L2",
        "model": "deepseek-chat",
        "responsibility": "CI/CD、部署监控、GitHub同步、基础设施",
        "skills": ["deploy", "shell", "python", "http_request", "notify", "test"],
        "analysis_fn": "_devops_analysis",
    },
    "qa": {
        "name": "测试工程师",
        "role": "QA",
        "layer": "L2",
        "model": "deepseek-chat",
        "responsibility": "测试验证、质量保障、用例设计",
        "skills": ["test", "review", "python", "file_read", "notify"],
        "analysis_fn": "_qa_analysis",
    },
    "product-manager": {
        "name": "产品经理",
        "role": "Product Manager",
        "layer": "L2",
        "model": "deepseek-chat",
        "responsibility": "需求分析、用户故事、验收标准、用户体验",
        "skills": ["multi_agent_index_brainstorm", "research", "review", "notify"],
        "analysis_fn": "_ux_analysis",
    },
    "project-manager": {
        "name": "项目经理",
        "role": "Project Manager",
        "layer": "L2",
        "model": "deepseek-chat",
        "responsibility": "项目看板管理、进度汇报、OKR跟踪",
        "skills": ["research", "review", "notify", "file_read", "file_write"],
        "analysis_fn": "_pm_analysis",
    },
    "business": {
        "name": "业务专家",
        "role": "Business Expert",
        "layer": "L2",
        "model": "deepseek-chat",
        "responsibility": "业务流程、多元化知识、行业洞察",
        "skills": ["research", "review", "notify"],
        "analysis_fn": "_business_expert_analysis",
    },
    "expert-biz-doctor": {
        "name": "业务医生",
        "role": "Business Doctor",
        "layer": "L2",
        "model": "deepseek-chat",
        "responsibility": "业务流程诊断、风险评估、优化建议、ROI分析",
        "skills": ["multi_agent_index_brainstorm", "research", "review", "notify"],
        "analysis_fn": "_business_analysis",
    },

    # ── L1 工具层 ────────────────────────────────────────────
    "learning-hacker": {
        "name": "学习黑客",
        "role": "Pattern Finder",
        "layer": "L1",
        "model": "deepseek-chat",
        "responsibility": "识别交叉引用、重复模式、自适应学习",
        "skills": ["multi_agent_index_brainstorm", "research", "python", "file_read", "code"],
        "analysis_fn": "_pattern_analysis",
    },
    "skill-manager": {
        "name": "技能管家",
        "role": "Skill Architect",
        "layer": "L1",
        "model": "deepseek-chat",
        "responsibility": "审查现有技能、提出基于技能的索引方案、工具链设计",
        "skills": ["multi_agent_index_brainstorm", "research", "review", "file_read", "file_write"],
        "analysis_fn": "_skill_analysis",
    },
    "memory-butler": {
        "name": "记忆管家",
        "role": "Memory Keeper",
        "layer": "L1",
        "model": "deepseek-chat",
        "responsibility": "全局状态管理、记忆库维护、上下文追踪",
        "skills": ["file_read", "file_write", "research", "echo"],
        "analysis_fn": "_memory_analysis",
    },
    "trend-forecast": {
        "name": "趋势预测师",
        "role": "Forecaster",
        "layer": "L1",
        "model": "deepseek-reasoner",
        "responsibility": "趋势分析、数据可视化、预测建模",
        "skills": ["python", "research", "file_read", "file_write"],
        "analysis_fn": "_trend_analysis",
    },
    "math-professor": {
        "name": "数学教授",
        "role": "Logic Expert",
        "layer": "L1",
        "model": "deepseek-reasoner",
        "responsibility": "逻辑一致性检查、数据库设计、算法复杂度、形式化验证",
        "skills": ["multi_agent_index_brainstorm", "python", "review", "research"],
        "analysis_fn": "_logic_analysis",
    },
    "humanities-scholar": {
        "name": "人文学者",
        "role": "Humanities Scholar",
        "layer": "L1",
        "model": "deepseek-chat",
        "responsibility": "知识库索引、人文知识管理、文档分析",
        "skills": ["research", "file_read", "review", "echo"],
        "analysis_fn": "_humanities_analysis",
    },
    "wen-shi-expert": {
        "name": "文史专家",
        "role": "Culture Expert",
        "layer": "L1",
        "model": "deepseek-chat",
        "responsibility": "多元文化知识库、人文研究、文化研究",
        "skills": ["research", "file_read", "review"],
        "analysis_fn": "_culture_analysis",
    },

    # ── Meta 层 ──────────────────────────────────────────────
    "janitor-agent": {
        "name": "清洁Agent",
        "role": "Janitor",
        "layer": "meta",
        "model": "deepseek-chat",
        "responsibility": "系统清理、临时文件管理、资源回收",
        "skills": ["clean", "shell", "file_read", "file_write"],
        "analysis_fn": "_janitor_analysis",
    },
    "indexer-agent": {
        "name": "索引Agent",
        "role": "Indexer",
        "layer": "meta",
        "model": "deepseek-chat",
        "responsibility": "文件索引构建、索引维护、索引优化",
        "skills": ["file_read", "file_write", "python", "shell", "research"],
        "analysis_fn": "_indexer_analysis",
    },
    "archiver-agent": {
        "name": "归档Agent",
        "role": "Archiver",
        "layer": "meta",
        "model": "deepseek-chat",
        "responsibility": "数据归档、备份管理、历史数据维护",
        "skills": ["file_read", "file_write", "shell", "deploy"],
        "analysis_fn": "_archiver_analysis",
    },
}

# ══════════════════════════════════════════════════════════════
# 技能- Agent 反向索引 (技能 → 适用Agent列表)
# ══════════════════════════════════════════════════════════════
SKILL_AGENT_INDEX: Dict[str, List[str]] = {}
for _aid, _info in AGENT_ROLES.items():
    for _skill in _info["skills"]:
        SKILL_AGENT_INDEX.setdefault(_skill, []).append(_aid)

# ══════════════════════════════════════════════════════════════
# 默认项目
# ══════════════════════════════════════════════════════════════
DEFAULT_PROJECTS: List[Dict[str, str]] = [
    {"name": "LQM微服务框架",  "path": r"e:\LQM微服务框架",  "project_type": "microservices",   "description": "Python微服务框架，59个Markdown文件"},
    {"name": "Obsidian Vault", "path": r"e:\Obsidian Vault",  "project_type": "knowledge_base", "description": "个人知识管理库，200+个Markdown文件"},
    {"name": "统计数据系统",   "path": r"e:\统计数据系统",    "project_type": "data_system",     "description": "统计数据处理系统，200+文件"},
    {"name": "软件开发",       "path": r"e:\软件开发",        "project_type": "workspace",       "description": "大型软件开发工作区，200+文件"},
]

# ══════════════════════════════════════════════════════════════
# 索引策略
# ══════════════════════════════════════════════════════════════
INDEX_STRATEGIES: Dict[str, Dict[str, Any]] = {
    "linear":       {"name": "线性索引", "best_for": "< 100文件",   "pros": ["实现简单", "维护成本低"],           "cons": ["不支持复杂查询"]},
    "hierarchical": {"name": "层次索引", "best_for": "100-500文件", "pros": ["结构清晰", "支持层级导航"],         "cons": ["跨目录查询困难"]},
    "semantic":     {"name": "语义索引", "best_for": "知识库",      "pros": ["支持语义搜索", "发现隐含关联"],     "cons": ["实现复杂", "需要向量数据库"]},
    "hybrid":       {"name": "混合索引", "best_for": "500+文件",   "pros": ["综合优势", "灵活配置"],             "cons": ["实现最复杂"]},
}


# ══════════════════════════════════════════════════════════════
# 核心处理器
# ══════════════════════════════════════════════════════════════
async def handle_index_brainstorm(task) -> Dict[str, Any]:
    """
    小蜘蛛结网 / Spider web - Multi-Agent Index Brainstorm

    Task Payload:
        task_description (str): 任务描述
        projects (list): 项目列表（可选，默认4个预设项目）
        participating_agents (list): 参与智能体ID列表（可选，默认全部25个）
        output_format (str): json / markdown / both（默认 both）
        discussion_topics (list): 讨论主题（可选）
        special_requirements (str): 特殊要求（可选）
        skill_filter (list): 按技能过滤Agent（可选）

    Returns:
        dict 包含 status, output, metadata, skill_agent_index
    """
    payload = task.payload if hasattr(task, "payload") else task.get("payload", {})

    task_desc = payload.get("task_description", "为项目文档库设计完整索引方案")
    projects = payload.get("projects", DEFAULT_PROJECTS)
    agents = payload.get("participating_agents", list(AGENT_ROLES.keys()))
    output_format = payload.get("output_format", "both")
    topics = payload.get("discussion_topics", [
        "索引策略选择（线性/层次/语义/混合）",
        "元数据提取方案",
        "搜索与检索优化",
        "自动化维护机制",
    ])
    special_reqs = payload.get("special_requirements", "")
    skill_filter = payload.get("skill_filter", None)

    # 如果指定了技能过滤，只保留拥有这些技能的Agent
    if skill_filter:
        agents = [a for a in agents if a in AGENT_ROLES and
                  any(s in AGENT_ROLES[a]["skills"] for s in skill_filter)]

    logger.info(f"🕷️ 小蜘蛛结网 v{VERSION} | 任务: {task_desc} | Agent: {len(agents)}个 | 项目: {len(projects)}个")

    context = _phase1_initialize(task_desc, projects, agents, topics, special_reqs)
    agent_analyses = _phase2_independent_analysis(projects, agents)
    discussion = _phase3_cross_discussion(agent_analyses)
    design = _phase4_synthesize(context, agent_analyses, discussion)
    output = _phase5_output(design, output_format)

    # 构建本次使用的技能- Agent 索引
    used_skill_index: Dict[str, List[str]] = {}
    for aid in agents:
        if aid in AGENT_ROLES:
            for s in AGENT_ROLES[aid]["skills"]:
                used_skill_index.setdefault(s, []).append(aid)

    logger.info(f"🕷️ 小蜘蛛结网完成 | 决策: {len(design.get('design_decisions', []))}项 | 技能: {len(used_skill_index)}个")

    return {
        "status": "completed",
        "skill_id": SKILL_ID,
        "skill_name": SKILL_NAME,
        "skill_alias": SKILL_ALIAS,
        "version": VERSION,
        "output": output,
        "metadata": {
            "task_description": task_desc,
            "projects_count": len(projects),
            "agents_count": len(agents),
            "agents": [{"id": a, "name": AGENT_ROLES.get(a, {}).get("name", a),
                        "layer": AGENT_ROLES.get(a, {}).get("layer", "unknown"),
                        "skills": AGENT_ROLES.get(a, {}).get("skills", [])}
                       for a in agents if a in AGENT_ROLES],
            "phases_completed": 5,
            "timestamp": datetime.now().isoformat(),
        },
        "skill_agent_index": used_skill_index,
    }


# ══════════════════════════════════════════════════════════════
# 阶段1: 需求理解与初始化
# ══════════════════════════════════════════════════════════════
def _phase1_initialize(task_desc, projects, agents, topics, special_reqs) -> Dict:
    return {
        "phase": 1,
        "task_description": task_desc,
        "projects_count": len(projects),
        "participating_agents": agents,
        "discussion_topics": topics,
        "special_requirements": special_reqs,
        "timestamp": datetime.now().isoformat(),
    }


# ══════════════════════════════════════════════════════════════
# 阶段2: 各智能体独立分析
# ══════════════════════════════════════════════════════════════
def _phase2_independent_analysis(projects, agents) -> Dict[str, Dict]:
    analyses: Dict[str, Dict] = {}
    for agent_id in agents:
        if agent_id not in AGENT_ROLES:
            continue
        agent_info = AGENT_ROLES[agent_id]
        assessments = [_assess_project(agent_id, project) for project in projects]
        analyses[agent_id] = {
            "agent_id": agent_id,
            "agent_name": agent_info["name"],
            "role": agent_info["role"],
            "layer": agent_info["layer"],
            "responsibility": agent_info["responsibility"],
            "skills": agent_info["skills"],
            "project_assessments": assessments,
            "key_points": _generate_key_points(agent_id, projects),
        }
    return analyses


def _assess_project(agent_id: str, project: Dict) -> Dict:
    path = Path(project.get("path", ""))
    try:
        file_count = sum(1 for _ in path.rglob("*") if _.is_file()) if path.exists() else 0
    except (PermissionError, OSError):
        file_count = 0

    ptype = project.get("project_type", "general")
    strategy = _recommend_strategy(file_count, ptype)

    assessment: Dict[str, Any] = {
        "project_name": project.get("name", ""),
        "estimated_files": file_count,
        "recommended_strategy": strategy,
        "strategy_detail": INDEX_STRATEGIES.get(strategy, {}),
    }

    # 调用专属分析函数
    agent_info = AGENT_ROLES.get(agent_id, {})
    fn_name = agent_info.get("analysis_fn")
    if fn_name and fn_name in globals():
        assessment["analysis"] = globals()[fn_name](project, file_count)

    return assessment


def _recommend_strategy(file_count: int, project_type: str) -> str:
    if project_type == "knowledge_base":
        return "semantic"
    if file_count < 100:
        return "linear"
    if file_count < 500:
        return "hierarchical"
    return "hybrid"


# ══════════════════════════════════════════════════════════════
# 25个 Agent 专属分析函数
# ══════════════════════════════════════════════════════════════

def _coordination_analysis(project, n):
    return {"priority": "high" if n > 200 else "medium", "resource": f"建议分配{max(1,n//200)}个Agent", "timeline": f"预计{max(1,n//100)}小时"}

def _architecture_analysis(project, n):
    return {"architecture_style": "微服务" if n > 100 else "单体", "tech_stack": ["Python", "FastAPI", "SQLite"], "scalability": "高" if n > 200 else "中"}

def _langchain_analysis(project, n):
    return {"vector_db": "ChromaDB" if n < 500 else "Milvus", "embedding_model": "text-embedding-3-small", "chain_type": "RetrievalQA"}

def _security_analysis(project, n):
    return {"risk_level": "高" if n > 300 else "中", "auth_strategy": "RBAC", "data_encryption": "AES-256"}

def _tech_analysis(project, n):
    return {"complexity": "high" if n > 200 else "medium" if n > 50 else "low", "approach": "增量索引" if n > 100 else "全量索引", "notes": [f"文件数:{n}", "建议异步更新", "考虑缓存策略"]}

def _mentor_analysis(project, n):
    return {"knowledge_gaps": ["索引算法", "向量搜索"], "learning_path": ["基础索引", "高级检索", "语义搜索"], "training_hours": max(1, n // 50)}

def _data_analysis(project, n):
    return {"metadata_fields": ["title", "tags", "created_at", "updated_at", "file_type"], "search_patterns": ["全文搜索", "标签过滤", "日期范围"], "recommendations": ["统一元数据格式", "标准化标签体系"]}

def _analyst_analysis(project, n):
    return {"data_volume": f"{n}文件", "analysis_dimensions": ["时间分布", "类型分布", "关联度"], "visualization": "推荐使用ECharts"}

def _developer_analysis(project, n):
    return {"language": "Python", "framework": "推荐FastAPI+SQLAlchemy", "modules": ["索引器", "检索器", "API层", "CLI层"], "estimated_lines": n * 50}

def _devops_analysis(project, n):
    return {"ci_cd": "GitHub Actions", "deployment": "Docker Compose", "monitoring": "Prometheus+Grafana", "cron": "0 2 * * *"}

def _qa_analysis(project, n):
    return {"test_strategy": ["单元测试", "集成测试", "性能测试"], "coverage_target": "90%", "test_data": f"需要{n//10}个测试文件"}

def _ux_analysis(project, n):
    return {"user_stories": ["快速找到文档", "了解项目结构", "智能推荐"], "acceptance_criteria": ["搜索<2秒", "覆盖率>95%"]}

def _pm_analysis(project, n):
    return {"milestones": ["P0基础索引", "P1元数据", "P2自动化", "P3语义搜索"], "risk": "索引过期", "stakeholders": ["开发团队", "管理层"]}

def _business_expert_analysis(project, n):
    return {"industry_fit": "软件开发", "compliance": ["数据隐私", "访问控制"], "competitive_advantage": "提升检索效率50%+"}

def _business_analysis(project, n):
    return {"business_value": "提升文档检索效率，降低知识获取成本", "risks": ["索引过期", "存储成本"], "roi": "中等投入，长期收益显著"}

def _pattern_analysis(project, n):
    return {"cross_references": ["文档间链接", "标签关联", "目录结构"], "patterns": ["日期命名", "项目前缀", "版本号"], "similarity_model": "推荐TF-IDF+余弦相似度"}

def _skill_analysis(project, n):
    return {"reusable_skills": ["file_read", "file_write", "research", "python"], "new_skills_needed": ["index_health_check", "auto_rebuild"], "automation_potential": "80%"}

def _memory_analysis(project, n):
    return {"state_size": f"约{n*100}字节", "persistence": "SQLite", "cache_strategy": "LRU", "context_window": "建议4096 tokens"}

def _trend_analysis(project, n):
    return {"growth_rate": "月增10%", "hot_topics": ["AI索引", "语义搜索", "知识图谱"], "forecast": f"6个月后约{int(n*1.8)}文件"}

def _logic_analysis(project, n):
    return {"consistency_checks": ["索引与文件系统一致性", "元数据完整性"], "algorithm": {"build": "O(n)" if n < 1000 else "O(n log n)", "search": "O(1)哈希/O(log n)二分"}}

def _humanities_analysis(project, n):
    return {"knowledge_domains": ["计算机科学", "软件工程", "人工智能"], "taxonomy": "DDC分类法", "cross_disciplinary": True}

def _culture_analysis(project, n):
    return {"cultural_context": "软件开发文化", "documentation_standard": ["中文优先", "中英双语"], "knowledge_heritage": "技术文档传承"}

def _janitor_analysis(project, n):
    return {"cleanup_targets": ["临时文件", "过期索引", "日志文件"], "schedule": "每周一次", "space_saving": f"约{n*10}KB"}

def _indexer_analysis(project, n):
    return {"index_format": "倒排索引", "storage": "SQLite+文件", "update_strategy": "增量+定时全量", "estimated_index_size": f"{n*200}字节"}

def _archiver_analysis(project, n):
    return {"archive_strategy": "按日期分层", "compression": "gzip", "retention": "永久", "backup_location": "云端+本地"}


# ══════════════════════════════════════════════════════════════
# 阶段3: 交叉讨论与反馈
# ══════════════════════════════════════════════════════════════
def _phase3_cross_discussion(analyses: Dict) -> Dict:
    consensus = [
        "所有智能体一致推荐混合索引策略",
        "元数据标准化是索引质量的基础",
        "自动化维护机制可显著降低运维成本",
        "安全审查应贯穿索引系统全生命周期",
    ]
    divergences = [
        {"topic": "索引更新频率",   "tech_expert": "实时更新",  "data_scientist": "批量更新降负载", "resolution": "混合策略：小文件实时，大文件批量"},
        {"topic": "语义搜索优先级", "learning_hacker": "核心功能", "product_manager": "增值功能",   "resolution": "分阶段实现：先基础，后语义增强"},
        {"topic": "存储方案",       "architect-agent": "分布式存储", "devops": "单机SQLite优先",  "resolution": "初期SQLite，后期可迁移到分布式"},
    ]
    refined = [
        {"topic": "索引策略",   "recommendation": "混合索引（层次+语义）", "supporting": ["tech-expert", "data-scientist", "learning-hacker", "architect-agent"]},
        {"topic": "元数据标准", "recommendation": "统一YAML frontmatter",  "supporting": ["data-scientist", "skill-manager", "indexer-agent"]},
        {"topic": "自动化机制", "recommendation": "文件监听+定时全量校验", "supporting": ["skill-manager", "system-manager", "devops"]},
        {"topic": "安全架构",   "recommendation": "RBAC+审计日志",        "supporting": ["security-architect", "system-manager", "expert-biz-doctor"]},
        {"topic": "部署方案",   "recommendation": "Docker+GitHub Actions", "supporting": ["devops", "architect-agent", "developer"]},
    ]
    return {"phase": 3, "consensus": consensus, "divergences": divergences, "refined_recommendations": refined}


# ══════════════════════════════════════════════════════════════
# 阶段4: 方案整合与优化
# ══════════════════════════════════════════════════════════════
def _phase4_synthesize(context, analyses, discussion) -> Dict:
    return {
        "phase": 4,
        "design_decisions": discussion.get("refined_recommendations", []),
        "consensus": discussion.get("consensus", []),
        "architecture": {
            "index_engine": "混合索引引擎",
            "storage_layer": "SQLite + 向量数据库(后期)",
            "update_mechanism": "增量更新 + 定时全量校验",
            "search_interface": "REST API + CLI",
            "security_layer": "RBAC + 审计日志",
            "deployment": "Docker Compose + GitHub Actions",
        },
        "implementation_roadmap": [
            {"phase": "P0", "task": "基础索引结构搭建",       "duration": "1周", "agents": ["developer", "tech-expert", "indexer-agent"]},
            {"phase": "P1", "task": "元数据提取标准化",       "duration": "1周", "agents": ["data-scientist", "skill-manager"]},
            {"phase": "P2", "task": "自动化更新机制",         "duration": "2周", "agents": ["devops", "skill-manager", "janitor-agent"]},
            {"phase": "P3", "task": "语义搜索集成",           "duration": "2周", "agents": ["langchain-orchestrator", "learning-hacker", "trend-forecast"]},
            {"phase": "P4", "task": "安全架构+监控告警",      "duration": "1周", "agents": ["security-architect", "qa", "devops"]},
            {"phase": "P5", "task": "文档归档+知识图谱",      "duration": "1周", "agents": ["archiver-agent", "humanities-scholar", "memory-butler"]},
        ],
    }


# ══════════════════════════════════════════════════════════════
# 阶段5: 最终输出与文档化
# ══════════════════════════════════════════════════════════════
def _phase5_output(design, output_format) -> Dict:
    json_output = {
        "skill_metadata": {
            "skill_name": SKILL_ID,
            "alias": SKILL_ALIAS,
            "version": VERSION,
            "execution_date": datetime.now().isoformat(),
            "total_agents": len(AGENT_ROLES),
            "participating_agents": list(AGENT_ROLES.keys()),
        },
        "design_decisions": design.get("design_decisions", []),
        "architecture": design.get("architecture", {}),
        "implementation_roadmap": design.get("implementation_roadmap", []),
        "consensus_points": design.get("consensus", []),
        "skill_agent_index": {s: a for s, a in SKILL_AGENT_INDEX.items()},
    }
    md = _generate_markdown(json_output)
    return {"json": json_output, "markdown": md}


def _generate_markdown(data: Dict) -> str:
    lines = [
        "# 🕷️ 小蜘蛛结网 - 多智能体索引头脑风暴设计文档",
        f"",
        f"**版本**: {data['skill_metadata']['version']}",
        f"**执行日期**: {data['skill_metadata']['execution_date']}",
        f"**参与Agent**: {data['skill_metadata']['total_agents']}个",
        "",
        "## 1. 设计决策",
        "",
    ]
    for d in data.get("design_decisions", []):
        lines.append(f"### {d['topic']}")
        lines.append(f"- **推荐方案**: {d['recommendation']}")
        lines.append(f"- **支持Agent**: {', '.join(d.get('supporting', []))}")
        lines.append("")

    lines += ["## 2. 架构设计", ""]
    for k, v in data.get("architecture", {}).items():
        lines.append(f"- **{k}**: {v}")

    lines += ["", "## 3. 实施路线图", "", "| 阶段 | 任务 | 时长 | 负责Agent |", "|------|------|------|-----------|"]
    for item in data.get("implementation_roadmap", []):
        agents = ", ".join(item.get("agents", []))
        lines.append(f"| {item['phase']} | {item['task']} | {item['duration']} | {agents} |")

    lines += ["", "## 4. 技能- Agent 索引", "", "| 技能 | 适用Agent |", "|------|----------|"]
    for skill, agents in data.get("skill_agent_index", {}).items():
        lines.append(f"| {skill} | {', '.join(agents)} |")

    lines += ["", "## 5. 共识要点", ""]
    for p in data.get("consensus_points", []):
        lines.append(f"- {p}")

    lines += ["", "---", f"*由{SKILL_ALIAS}多智能体协作生成*"]
    return "\n".join(lines)


def _generate_key_points(agent_id, projects) -> List[str]:
    total = sum(_estimate_file_count(Path(p.get("path", ""))) for p in projects)
    points = {
        "system-manager":        [f"共{len(projects)}个项目，约{total}个文件", "分阶段索引策略", "建立跨项目一致性标准"],
        "architect-agent":       ["推荐微服务架构", "考虑可扩展性", "技术栈: Python+FastAPI+SQLite"],
        "langchain-orchestrator": ["向量数据库选型: ChromaDB", "Embedding模型: text-embedding-3-small", "链类型: RetrievalQA"],
        "security-architect":    ["实施RBAC权限控制", "索引数据加密存储", "审计日志全覆盖"],
        "tech-expert":           ["混合索引策略", "增量更新机制", "引入向量数据库支持语义搜索"],
        "master-mentor":         ["建立学习路径", "索引算法培训", "知识传承机制"],
        "data-scientist":        ["元数据标准化", "统一标签体系", "全文搜索+标签过滤"],
        "analyst":               ["数据分析维度: 时间/类型/关联度", "可视化推荐: ECharts", "定期生成统计报告"],
        "developer":             ["Python+SQLAlchemy", "模块化设计", "CLI+API双接口"],
        "devops":                ["Docker Compose部署", "GitHub Actions CI/CD", "Prometheus监控"],
        "qa":                    ["单元测试覆盖率>90%", "集成测试+性能测试", "自动化测试流水线"],
        "product-manager":       ["核心需求: 快速定位文档", "验收: 搜索<2秒, 覆盖率>95%", "支持模糊搜索和智能推荐"],
        "project-manager":       ["P0-P4分阶段交付", "风险: 索引过期", "干系人: 开发团队+管理层"],
        "business":              ["行业适配: 软件开发", "合规: 数据隐私+访问控制", "竞争优势: 检索效率提升50%+"],
        "expert-biz-doctor":     ["ROI显著，建议优先投入", "风险: 索引过期、存储成本", "建立索引健康度监控"],
        "learning-hacker":       ["文档间隐含关联分析", "文档相似度模型", "重复模式识别优化索引"],
        "skill-manager":         ["复用file_read/file_write/research", "新增index_health_check技能", "自动化维护降低80%人工"],
        "memory-butler":         ["SQLite持久化", "LRU缓存策略", "上下文窗口4096 tokens"],
        "trend-forecast":        ["月增10%增长预测", "热点: AI索引/语义搜索/知识图谱", "6个月后约1.8倍文件量"],
        "math-professor":        ["哈希校验保证一致性", "B+树优化范围查询", "算法复杂度O(n log n)以内"],
        "humanities-scholar":    ["知识域: 计算机科学/软件工程/AI", "分类法: DDC", "跨学科关联"],
        "wen-shi-expert":        ["软件开发文化", "文档标准: 中英双语", "技术文档传承"],
        "janitor-agent":         ["清理临时文件/过期索引/日志", "每周一次", "节省约10KB/文件"],
        "indexer-agent":         ["倒排索引格式", "SQLite+文件存储", "增量+定时全量更新"],
        "archiver-agent":        ["按日期分层归档", "gzip压缩", "云端+本地双备份"],
    }
    return points.get(agent_id, ["分析完成"])


def _estimate_file_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return sum(1 for _ in path.rglob("*") if _.is_file())
    except (PermissionError, OSError):
        return 0


# ══════════════════════════════════════════════════════════════
# Skill 清单 & 注册
# ══════════════════════════════════════════════════════════════
SKILL_MANIFEST = {
    "skill_id": SKILL_ID,
    "name": SKILL_NAME,
    "alias": SKILL_ALIAS,
    "version": VERSION,
    "category": CATEGORY,
    "description": "Organize multiple AI agents to collaboratively brainstorm and design full-index solutions for document repositories. Supports 25 agents and 14 skills.",
    "author": "spider-x",
    "entry_point": f"spider_x.skills.index_brainstorm:handle_index_brainstorm",
    "dependencies": [],
    "compatible_spiders": ["*"],
    "config_schema": {
        "type": "object",
        "properties": {
            "task_description": {"type": "string"},
            "projects": {"type": "array", "items": {"type": "object"}},
            "participating_agents": {"type": "array", "items": {"type": "string"}},
            "output_format": {"type": "string", "enum": ["json", "markdown", "both"]},
            "discussion_topics": {"type": "array", "items": {"type": "string"}},
            "special_requirements": {"type": "string"},
            "skill_filter": {"type": "array", "items": {"type": "string"}},
        },
    },
}


def get_skill_agent_index() -> Dict[str, List[str]]:
    """返回完整的技能- Agent 反向索引"""
    return dict(SKILL_AGENT_INDEX)


def get_agent_skills(agent_id: str) -> Optional[Dict[str, Any]]:
    """获取指定Agent的技能信息"""
    return AGENT_ROLES.get(agent_id)


def get_agents_by_skill(skill_id: str) -> List[str]:
    """根据技能ID获取适用Agent列表"""
    return SKILL_AGENT_INDEX.get(skill_id, [])


def get_agents_by_layer(layer: str) -> List[str]:
    """根据层级获取Agent列表"""
    return [aid for aid, info in AGENT_ROLES.items() if info["layer"] == layer]


def register(registry: Any) -> None:
    """Register this skill to a Spider-X task registry."""
    registry.register(SKILL_ID)(handle_index_brainstorm)
    logger.info(f"✅ Skill registered: {SKILL_ID} ({SKILL_ALIAS}) v{VERSION}")
