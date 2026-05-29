"""Spider-X 蜘蛛群 - Worker智能体集群引擎 v1.0.0"""

__version__ = "1.0.0"

from spider_x.core.app import create_app
from spider_x.core.config import SpiderXConfig, load_config
from spider_x.core.task import Task, TaskStatus, TaskPriority, registry
from spider_x.core.credential_chain import CredentialChainManager
from spider_x.core.sop_engine import SOPEngine
from spider_x.core.observability import init_otel
from spider_x.core.resource_state import ResourceStateService, AgentState, AgentStatus
from spider_x.core.atomic_action import TaskDecomposer
from spider_x.core.chaos_scheduler import ChaosScheduler, TokenBucket
from spider_x.core.subgraph import SubgraphEncapsulator, VirtualSuperAgentManager
from spider_x.core.plugin import PluginManager, PluginState
from spider_x.core.skill_lock import LOCKSSChecker, LockMode
from spider_x.core.skill_gnn import SkillCombinatorGNN
from spider_x.core.skill_kg import SkillKnowledgeGraph
from spider_x.core.worker import WorkerNode, TaskSubmitter

from spider_x.adapters import MiniSpiderAdapter, SpiderMaxAdapter, SpiderRoomAdapter, SpiderDiaryAdapter
from spider_x.skills import SkillManifest, register_builtin_skills, BUILTIN_SKILLS

__all__ = [
    "__version__",
    "create_app", "SpiderXConfig", "load_config",
    "Task", "TaskStatus", "TaskPriority", "registry",
    "CredentialChainManager", "SOPEngine", "init_otel",
    "ResourceStateService", "AgentState", "AgentStatus",
    "TaskDecomposer", "ChaosScheduler", "TokenBucket",
    "SubgraphEncapsulator", "VirtualSuperAgentManager",
    "PluginManager", "PluginState",
    "LOCKSSChecker", "LockMode",
    "SkillCombinatorGNN", "SkillKnowledgeGraph",
    "WorkerNode", "TaskSubmitter",
    "MiniSpiderAdapter", "SpiderMaxAdapter", "SpiderRoomAdapter", "SpiderDiaryAdapter",
    "SkillManifest", "register_builtin_skills", "BUILTIN_SKILLS",
]
