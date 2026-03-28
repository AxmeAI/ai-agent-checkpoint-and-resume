# AI Agent Checkpoint and Resume

AI agents crash. State gets lost. AXME makes every agent operation durable by default - no checkpoint code, no framework lock-in.

Your agent crashes at step 47 of 50. LangGraph: write checkpoint code, configure PostgresSaver, manage state manually. CrewAI: start over from step 1. AXME: restart the agent. It picks up at step 47 automatically.

> **Alpha** - Built with [AXME](https://github.com/AxmeAI/axme) (AXP Intent Protocol).
> [cloud.axme.ai](https://cloud.axme.ai) - [hello@axme.ai](mailto:hello@axme.ai)

---

## The Problem

AI agents do multi-step work. They crash. The state is gone.

```
Agent starts ETL pipeline:
  [1/4] Extract    - done
  [2/4] Validate   - done
  [3/4] Transform  - done
  [4/4] Load       - CRASH (OOM, network, restart)

What now?
  - LangGraph: did you configure PostgresSaver? No? Start over.
  - CrewAI: "limited state management, failures typically require restart"
  - Swarm: "no persistence, state exists only in memory"
  - Raw Python: hope you wrote checkpoint logic yourself
```

What breaks:
- **State lives in memory** - process dies, state dies
- **Checkpoint is DIY** - every framework has its own persistence mechanism (or none)
- **No standard** - LangGraph has `SqliteSaver`, CrewAI has nothing, Swarm has nothing
- **Restart = start over** - no way to resume from the last good step
- **Cross-machine is impossible** - checkpoints are local files, not network-accessible

---

## The Solution: Durable Intent Lifecycle

```
Agent starts ETL pipeline via AXME intent:
  [1/4] Extract    - done (state in AXME)
  [2/4] Validate   - done (state in AXME)
  [3/4] Transform  - done (state in AXME)
  [4/4] Load       - CRASH

Restart agent:
  AXME redelivers the intent (state: IN_PROGRESS)
  Agent resumes. No data lost. No code changes.
```

State is in PostgreSQL, not in memory. The agent is stateless. The platform is stateful.

---

## Quick Start

```bash
pip install axme
export AXME_API_KEY="your-key"   # Get one: axme login
```

```python
from axme import AxmeClient, AxmeClientConfig
import os

client = AxmeClient(AxmeClientConfig(api_key=os.environ["AXME_API_KEY"]))

# Submit a multi-step pipeline
intent_id = client.send_intent({
    "intent_type": "intent.pipeline.process.v1",
    "to_agent": "agent://myorg/production/pipeline-agent",
    "payload": {
        "pipeline": "etl-customers",
        "steps": ["extract", "validate", "transform", "load"],
        "total_rows": 500000,
    },
})

print(f"Pipeline submitted: {intent_id}")

# Wait for completion. If agent crashes, intent stays in current state.
# Restart agent - AXME redelivers. No checkpoint code needed.
result = client.wait_for(intent_id)
print(f"Done: {result['status']}")
```

---

## Before / After

### Before: DIY Checkpointing (100+ lines per framework)

```python
# LangGraph: framework-specific checkpoint setup
from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = "postgresql://user:pass@localhost/checkpoints"
checkpointer = PostgresSaver.from_conn_string(DB_URI)

# Build graph with checkpointer attached
graph = builder.compile(checkpointer=checkpointer)

# Resume from checkpoint (if exists)
config = {"configurable": {"thread_id": job_id}}
state = graph.get_state(config)
if state and state.values:
    result = graph.invoke(None, config)  # resume
else:
    result = graph.invoke(initial_state, config)  # start fresh

# Plus: manage DB connection, handle schema migrations,
# clean up old checkpoints, handle serialization errors...

# CrewAI: no built-in persistence
# "limited state management, failures typically require restart"

# Swarm: no persistence at all
# "state exists only in memory"
```

### After: AXME Durable Execution (zero checkpoint code)

```python
intent_id = client.send_intent({
    "intent_type": "intent.pipeline.process.v1",
    "to_agent": "agent://myorg/production/pipeline-agent",
    "payload": {"pipeline": "etl-customers", "steps": ["extract", "validate", "transform", "load"]},
})
result = client.wait_for(intent_id)
```

No `PostgresSaver`. No `SqliteSaver`. No checkpoint DB. No schema migrations. No serialization.

The intent lifecycle is durable by default. Agent crashes, intent stays. Agent restarts, intent redelivers.

---

## How Crash Recovery Works

```
Normal flow:
  CREATED -> SUBMITTED -> DELIVERED -> IN_PROGRESS -> COMPLETED

Agent crashes at IN_PROGRESS:
  CREATED -> SUBMITTED -> DELIVERED -> IN_PROGRESS -> (agent dies)

  Intent stays at IN_PROGRESS in AXME's PostgreSQL.
  No timer. No cron. Just durable state.

Agent restarts:
  Agent calls client.listen("pipeline-agent-demo")
  AXME redelivers the intent (max_delivery_attempts: 3)
  Agent picks up where it left off.
  IN_PROGRESS -> COMPLETED
```

---

## Comparison With Framework Checkpointing

| | LangGraph | CrewAI | Swarm | AXME |
|---|---|---|---|---|
| Persistence | PostgresSaver (opt-in) | None | None | Default (built-in) |
| Checkpoint code | 20+ lines | N/A | N/A | 0 lines |
| DB setup | You manage | N/A | N/A | Managed (AXME Cloud) |
| Resume after crash | From last checkpoint | Start over | Start over | Automatic redelivery |
| Cross-machine | No (local state) | No | No | Yes (network state) |
| Framework lock-in | LangGraph only | CrewAI only | Swarm only | Any framework |

---

## How It Works

```
+-----------+  send_intent()   +----------------+  deliver     +-----------+
|           | ---------------> |                | -----------> |           |
| Initiator |                  |   AXME Cloud   |              |   Agent   |
|           | <- wait_for() -- |   (platform)   | <- resume()  |           |
|           |  resumes when    |                |  with result |           |
|           |  agent completes | intent state   |              | processes |
|           |                  | in PostgreSQL  |  crash?      | steps     |
|           |                  | (durable)      |  redeliver!  |           |
+-----------+                  +----------------+              +-----------+
```

1. Initiator submits a **pipeline intent** with steps and data
2. AXME **delivers** to the agent via SSE stream
3. Agent **processes** steps and **resumes** with result
4. If agent **crashes** - intent stays at current state in PostgreSQL
5. Agent **restarts** - AXME **redelivers** the intent (up to 3 attempts)
6. Agent picks up and **completes** the pipeline

---

## Works With Any Agent Framework

AXME durability works underneath any framework. No framework changes needed.

| Framework | How AXME Adds Durability |
|-----------|--------------------------|
| **LangGraph** | Replace PostgresSaver with AXME intent lifecycle |
| **CrewAI** | Add durability where CrewAI has none |
| **AutoGen** | Durable multi-agent conversations across restarts |
| **OpenAI Agents SDK** | Survive crashes without losing agent state |
| **Any Python code** | `send_intent()` + `wait_for()` = durable by default |

---

## Run the Full Example

### Prerequisites

```bash
# Install CLI (one-time)
curl -fsSL https://raw.githubusercontent.com/AxmeAI/axme-cli/main/install.sh | sh
# Open a new terminal, or run the "source" command shown by the installer

# Log in
axme login

# Install Python SDK
pip install axme
```

### Terminal 1 - submit the intent

```bash
axme scenarios apply scenario.json
# Note the intent_id in the output
```

### Terminal 2 - start the agent

Get the agent key after scenario apply:

```bash
# macOS
cat ~/Library/Application\ Support/axme/scenario-agents.json | grep -A2 pipeline-agent-demo

# Linux
cat ~/.config/axme/scenario-agents.json | grep -A2 pipeline-agent-demo
```

Run the agent:

```bash
AXME_API_KEY=<agent-key> python agent.py
```

### Try crash recovery

1. While the agent is processing, press Ctrl+C to kill it
2. Check intent status: `axme intents get <intent_id>` (still IN_PROGRESS)
3. Restart the agent: `AXME_API_KEY=<agent-key> python agent.py`
4. Agent picks up the intent and completes it

### Verify

```bash
axme intents get <intent_id>
# lifecycle_status: COMPLETED
```

---

## Related

- [AXME](https://github.com/AxmeAI/axme) - project overview
- [AXP Spec](https://github.com/AxmeAI/axp-spec) - open Intent Protocol specification
- [AXME Examples](https://github.com/AxmeAI/axme-examples) - 20+ runnable examples across 5 languages
- [AXME CLI](https://github.com/AxmeAI/axme-cli) - manage intents, agents, scenarios from the terminal
- [Async Human Approval for AI Agents](https://github.com/AxmeAI/async-human-approval-for-ai-agents) - async approval with reminders
- [Durable Execution with Human Approval](https://github.com/AxmeAI/durable-execution-with-human-approval) - what Temporal can't do

---

Built with [AXME](https://github.com/AxmeAI/axme) (AXP Intent Protocol).
