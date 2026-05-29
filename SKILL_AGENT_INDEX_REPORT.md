# ======================================================================
#  Spider-X Agent-Skill Integration Report
#  Generated: 2026-05-28
# ======================================================================

## System Topology

```
E:\软件开发\Spider-X\
    run.py                          # Entry point
    spider_x\
        __init__.py
        cli.py                      # CLI interface
        core\                       # Core engine
            plugin.py
            resource_state.py
            skill_kg.py             # Skill Knowledge Graph
            skill_lock.py           # Skill locking
            sop_engine.py           # SOP execution
            subgraph.py             # Agent collaboration graph
            observability.py
            chaos_scheduler.py
            atomic_action.py
        skills\                     # <<< SKILL REGISTRY >>>
            __init__.py             # Package entry, exports all indexes
            manifest.py             # SkillManifest data class + discovery
            builtin.py              # 13 built-in skills + handlers
            index_brainstorm.py     # multi_agent_index_brainstorm (NEW)
            skill_agent_index.json  # Complete Agent-Skill index (NEW)
        adapters\
            mini_spider.py          # Bridge to mini_spider agents
            spider_max.py
            spider_room.py
            spider_diary.py
```

## Agent Roster (25 agents, 5 layers)

### L4 Management (2 agents)
| Agent ID              | Name         | Primary Skills                          |
|-----------------------|--------------|-----------------------------------------|
| system-manager        | 系统经理      | multi_agent_index_brainstorm, research, review, notify, echo |
| architect-agent       | 架构师        | multi_agent_index_brainstorm, code, review, research, deploy |

### L3 Execution (4 agents)
| Agent ID              | Name         | Primary Skills                          |
|-----------------------|--------------|-----------------------------------------|
| langchain-orchestrator| LangChain编排器| python, http_request, file_read, file_write, research |
| security-architect    | 安全架构师    | review, test, shell, file_read, notify  |
| tech-expert           | 技术专家      | multi_agent_index_brainstorm, code, review, test, python, shell |
| master-mentor         | 大师导师      | research, code, review, notify, echo    |

### L2 Professional (9 agents)
| Agent ID              | Name         | Primary Skills                          |
|-----------------------|--------------|-----------------------------------------|
| data-scientist        | 数据科学家    | multi_agent_index_brainstorm, python, research, file_read, file_write |
| analyst               | 分析师        | research, python, file_read, review     |
| developer             | 开发者        | code, python, test, review, clean, file_write, file_read |
| devops                | DevOps工程师  | deploy, shell, python, http_request, notify, test |
| qa                    | 测试工程师    | test, review, python, file_read, notify |
| product-manager       | 产品经理      | multi_agent_index_brainstorm, research, review, notify |
| project-manager       | 项目经理      | research, review, notify, file_read, file_write |
| business              | 业务专家      | research, review, notify               |
| expert-biz-doctor     | 业务医生      | multi_agent_index_brainstorm, research, review, notify |

### L1 Utility (7 agents)
| Agent ID              | Name         | Primary Skills                          |
|-----------------------|--------------|-----------------------------------------|
| learning-hacker       | 学习黑客      | multi_agent_index_brainstorm, research, python, file_read, code |
| skill-manager         | 技能管家      | multi_agent_index_brainstorm, research, review, file_read, file_write |
| memory-butler         | 记忆管家      | file_read, file_write, research, echo   |
| trend-forecast        | 趋势预测师    | python, research, file_read, file_write |
| math-professor        | 数学教授      | multi_agent_index_brainstorm, python, review, research |
| humanities-scholar    | 人文学者      | research, file_read, review, echo       |
| wen-shi-expert        | 文史专家      | research, file_read, review            |

### Meta (3 agents)
| Agent ID              | Name         | Primary Skills                          |
|-----------------------|--------------|-----------------------------------------|
| janitor-agent         | 清洁Agent     | clean, shell, file_read, file_write     |
| indexer-agent         | 索引Agent     | file_read, file_write, python, shell, research |
| archiver-agent        | 归档Agent     | file_read, file_write, shell, deploy    |

## Skill Registry (14 skills)

### Built-in Skills (from builtin.py)
| Skill ID         | Category   | Handler                              | Agent Count |
|------------------|------------|--------------------------------------|-------------|
| echo             | utility    | _echo                                | 4           |
| shell            | system     | _shell                               | 6           |
| python           | system     | _python                              | 11          |
| http_request     | network    | _http                                | 2           |
| file_write       | file       | _fw                                  | 10          |
| file_read        | file       | _fr                                  | 16          |
| research         | workflow   | _stub                                | 18          |
| code             | workflow   | _stub                                | 5           |
| review           | workflow   | _stub                                | 16          |
| test             | workflow   | _stub                                | 5           |
| clean            | workflow   | _stub                                | 2           |
| deploy           | workflow   | _stub                                | 3           |
| notify           | workflow   | _stub                                | 9           |

### Collaboration Skill (NEW - index_brainstorm.py)
| Skill ID                      | Category      | Handler                    | Agent Count |
|-------------------------------|---------------|----------------------------|-------------|
| multi_agent_index_brainstorm  | collaboration | handle_index_brainstorm    | 9           |

## Skill-Agent Reverse Index

```
multi_agent_index_brainstorm(9)  <- system-manager, architect-agent, tech-expert,
                                     data-scientist, product-manager, expert-biz-doctor,
                                     learning-hacker, skill-manager, math-professor

research(18)                     <- system-manager, architect-agent, langchain-orchestrator,
                                     master-mentor, data-scientist, analyst, product-manager,
                                     project-manager, business, expert-biz-doctor, learning-hacker,
                                     skill-manager, memory-butler, trend-forecast, math-professor,
                                     humanities-scholar, wen-shi-expert, indexer-agent

file_read(16)                    <- langchain-orchestrator, security-architect, data-scientist,
                                     analyst, developer, qa, project-manager, learning-hacker,
                                     skill-manager, memory-butler, trend-forecast, humanities-scholar,
                                     wen-shi-expert, janitor-agent, indexer-agent, archiver-agent

review(16)                      <- system-manager, architect-agent, security-architect,
                                     tech-expert, master-mentor, analyst, developer, qa,
                                     product-manager, project-manager, business, expert-biz-doctor,
                                     skill-manager, math-professor, humanities-scholar, wen-shi-expert

python(11)                      <- langchain-orchestrator, tech-expert, data-scientist,
                                     analyst, developer, devops, qa, learning-hacker,
                                     trend-forecast, math-professor, indexer-agent

file_write(10)                  <- langchain-orchestrator, data-scientist, developer,
                                     project-manager, skill-manager, memory-butler, trend-forecast,
                                     janitor-agent, indexer-agent, archiver-agent

notify(9)                       <- system-manager, security-architect, master-mentor, devops,
                                     qa, product-manager, project-manager, business, expert-biz-doctor

code(5)                         <- architect-agent, tech-expert, master-mentor, developer,
                                     learning-hacker

test(5)                         <- security-architect, tech-expert, developer, devops, qa

shell(6)                        <- security-architect, tech-expert, devops, janitor-agent,
                                     indexer-agent, archiver-agent

deploy(3)                       <- architect-agent, devops, archiver-agent

echo(4)                         <- system-manager, master-mentor, memory-butler, humanities-scholar

clean(2)                        <- developer, janitor-agent

http_request(2)                 <- langchain-orchestrator, devops
```

## Files Modified/Created

| File | Action | Description |
|------|--------|-------------|
| `spider_x/skills/index_brainstorm.py` | CREATED | Skill handler with 25 agents, 14 skills, 5-phase workflow |
| `spider_x/skills/skill_agent_index.json` | CREATED | Complete Agent-Skill index (JSON) |
| `spider_x/skills/__init__.py` | MODIFIED | Added exports for index functions |
| `spider_x/skills/builtin.py` | MODIFIED | Added multi_agent_index_brainstorm to BUILTIN_SKILLS |

## API Exports (from spider_x.skills)

```python
from spider_x.skills import (
    # Manifest system
    SkillManifest, load_skill_manifest, discover_skills,
    # Built-in registry
    register_builtin_skills, BUILTIN_SKILLS,
    # Index brainstorm skill
    INDEX_BRAINSTORM_MANIFEST, AGENT_ROLES, SKILL_AGENT_INDEX,
    # Query APIs
    get_skill_agent_index,    # -> Dict[skill_id, List[agent_id]]
    get_agent_skills,         # -> Dict with agent info + skills
    get_agents_by_skill,      # -> List[agent_id] for a skill
    get_agents_by_layer,      # -> List[agent_id] for a layer (L4/L3/L2/L1/meta)
)
```

## Task Payload Schema

```json
{
    "task_description": "str - 任务描述",
    "projects": ["list - 项目列表 (可选, 默认4个预设)"],
    "participating_agents": ["list - Agent ID列表 (可选, 默认全部25个)"],
    "output_format": "json|markdown|both (默认both)",
    "discussion_topics": ["list - 讨论主题 (可选)"],
    "special_requirements": "str - 特殊要求 (可选)",
    "skill_filter": ["list - 按技能过滤Agent (可选)"]
}
```

## Return Schema

```json
{
    "status": "completed",
    "skill_id": "multi_agent_index_brainstorm",
    "skill_name": "Multi-Agent Index Brainstorm",
    "skill_alias": "小蜘蛛结网/Spider web",
    "version": "2.0.0",
    "output": {
        "json": {"skill_metadata": {}, "design_decisions": [], ...},
        "markdown": "# 小蜘蛛结网 - ..."
    },
    "metadata": {
        "task_description": "...",
        "projects_count": 4,
        "agents_count": 25,
        "agents": [{"id": "...", "name": "...", "layer": "...", "skills": []}],
        "phases_completed": 5,
        "timestamp": "..."
    },
    "skill_agent_index": {
        "research": ["system-manager", "architect-agent", ...],
        "file_read": ["langchain-orchestrator", ...],
        ...
    }
}
```
