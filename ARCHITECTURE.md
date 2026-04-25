# Architecture

## Positioning

This project should compete as a capable AI operator and coding agent, not as an unrestricted remote-control bot.

The right mental model is:
- `Capability layers` over raw OS access
- `Tool-mediated execution` over direct control
- `Visible plans and logs` over silent autonomy
- `Policy scopes and approvals` over blanket permissions

## System Layers

### 1. Core Brain

Responsibilities:
- task decomposition
- step planning
- tool selection
- reflection after each step
- memory retrieval and compression

Current implementation:
- planner, replanning, and reflection loop in [autonomous_agent.py](/C:/Users/Admin/Desktop/ai%20assistant%20for%20pc/autonomous_agent.py)
- model routing and tool calling in [ai_assistant.py](/C:/Users/Admin/Desktop/ai%20assistant%20for%20pc/ai_assistant.py)

### 2. Tool System

The assistant should act through a controlled tool interface.

Primary tool groups:
- `filesystem`: `read_file`, `write_file`, `create_directory`, `search_files`
- `terminal`: `run_shell_command`
- `browser`: `open_browser`, `browser_*`, snapshots
- `code`: `execute_python`, workflow generation, helper synthesis
- `network`: `web_scrape`, `download_file`, site checks
- `os_control`: process, registry, scheduler, screenshots

Design rule:
- prefer small universal tools plus generated scripts/helpers
- generated workflows still execute through policy and audit

### 3. Code Agent

Required loop:
1. inspect repo
2. derive plan
3. edit files
4. run commands or tests
5. observe failure
6. patch and rerun

Near-term gaps:
- stronger repo indexing/summarization
- tighter test/debug loops
- git-native actions with approval boundaries
- structured dependency/install flows

### 4. PC Automation Layer

This layer should stay constrained.

Rules:
- no silent full takeover
- approvals for sensitive actions
- visible execution logs
- snapshots/replay for browser and environment changes

### 5. Memory

Split memory by purpose:
- `working memory`: current run context and events
- `project memory`: run summaries, generated assets, failures
- `user memory`: preferences and profile data
- `system memory`: successful patterns, failure patterns, tool behavior

Current implementation:
- STM/LTM/failure logs in [autonomous_agent.py](/C:/Users/Admin/Desktop/ai%20assistant%20for%20pc/autonomous_agent.py)
- user/project analytics storage in [ai_assistant.py](/C:/Users/Admin/Desktop/ai%20assistant%20for%20pc/ai_assistant.py)

### 6. Execution Engine

The execution engine owns:
- task queue
- retries
- timeout handling
- run persistence
- crash recovery
- audit logging
- replayable world state

Current implementation:
- run state, task execution, replanning, audit, and world-state capture in [autonomous_agent.py](/C:/Users/Admin/Desktop/ai%20assistant%20for%20pc/autonomous_agent.py)

### 7. Multi-Agent Direction

The current codebase is mainly a strong single-agent loop with role separation inside the architecture.

Target role split:
- `planner`
- `executor`
- `coder`
- `debugger`
- `researcher`
- `critic`

Start with logical role separation before turning them into separate agents/processes.

### 8. Interface Layer

Required surfaces:
- CLI for fast execution
- task timeline/status view
- diffs/logs/audit visibility
- approve/reject controls for sensitive actions

Current CLI already exposes:
- `/agent`
- `/agent-runs`
- `/agent-resume`
- `/policy`
- `/policy-set`
- `/audit`

### 9. Safety Layer

Core controls:
- policy scopes by capability
- confirmation prompts for dangerous actions
- audit logs for every run/task
- safe defaults for sensitive scopes
- visible execution state

Current implementation:
- `PolicyEngine`
- `SafetyManager`
- `AuditLogger`

### 10. Dynamic Tooling

The system should feel open-ended because it can generate and run new helpers, not because it has unrestricted access.

Design rule:
- generated scripts are temporary or reusable tools
- generated tools still pass through execution, policy, and audit layers

## Practical Roadmap

### Phase 1
- keep the current autonomous loop
- tighten docs and product framing
- keep dangerous capabilities behind policy scopes
- improve coding-agent workflows and repo understanding

### Phase 2
- add stronger environment isolation per project
- add better test/debug automation
- add structured deployment flows
- improve browser and app automation replay

### Phase 3
- split planner/executor/coder/critic into cooperating agents
- add project memory retrieval and long-horizon task handling
- add richer observability UI

## Non-Goals

Avoid building the system around:
- unrestricted admin access
- silent desktop takeover
- giant fixed tool menus as the only intelligence
- prompt-only autonomy without execution feedback

The winning architecture is a reasoning loop that can safely execute, observe, and rewrite state through controlled tools.
