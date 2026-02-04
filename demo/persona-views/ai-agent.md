# AI Agent: 5-Minute Deep-Dive

**One-line pitch:** Business observability means agents build on prior knowledge.

**Pain addressed:** $205K/yr (enterprise) for context rediscovery + framework isolation

---

## Pre-Demo Checklist

- [ ] Grafana running at http://localhost:3000
- [ ] Tempo datasource configured and receiving spans
- [ ] Historical demo data with insight spans loaded (run `demo/setup_demo_env.sh`)
- [ ] A2A agent card example available (or screenshot)

---

## Talking Points & Queries

### Minute 1: "Decisions as Telemetry" (1:00)

**Setup:** Show the `02_agent_insights.py` example from ContextCore.

**Talking point:**
> "Every AI decision is an insight span. It has a type (decision, lesson, blocker, question), a confidence score, and evidence links. It's not a log message that disappears — it's a queryable span in Tempo."

**Code reference:** `ContextCore/examples/02_agent_insights.py`

**Query — View emitted insights:**
```
# TraceQL: All insight spans
{span.insight.type != ""} | select(span.insight.type, span.insight.summary, span.insight.confidence)
```

**What to show:** Insight spans in Tempo with structured attributes — type, summary, confidence, evidence URLs.

### Minute 2: "Persistent Memory Across Sessions" (2:00)

**Talking point:**
> "Session 1: Claude decides to use connection pooling for the database service. That decision is stored as a span. Session 2: Before making any decisions, Claude queries Tempo for prior insights. No context re-discovery. Knowledge compounds."

**Query — Retrieve prior decisions:**
```
# TraceQL: High-confidence decisions from previous sessions
{span.insight.type = "decision" && span.insight.confidence >= 0.8} | select(span.insight.summary, span.insight.confidence, span.insight.evidence)
```

**Query — Lessons learned for a service:**
```
# TraceQL: Lessons learned for checkoutservice
{span.insight.type = "lesson" && span.task.service = "checkoutservice"} | select(span.insight.summary, span.insight.confidence)
```

**What to show:** A list of decisions from "last week" — with summaries like "Use connection pooling for DB (confidence: 0.92)" and evidence links.

### Minute 3: "Cross-Agent Collaboration via A2A" (3:00)

**Talking point:**
> "Google's Agent-to-Agent protocol gives agents a standard way to discover and communicate with each other. ContextCore implements A2A — any compatible agent can find and collaborate with ContextCore agents."

**What to show:** The `.well-known/agent.json` agent card:
```json
{
  "name": "contextcore-agent",
  "description": "ContextCore project tracking and insight management",
  "url": "http://localhost:8080",
  "capabilities": {
    "streaming": false,
    "pushNotifications": false
  },
  "skills": [
    {"id": "task-tracking", "name": "Task Tracking"},
    {"id": "insight-management", "name": "Insight Management"},
    {"id": "project-queries", "name": "Project Queries"}
  ]
}
```

**Talking point:**
> "Any A2A-compatible agent — from any framework — can discover this agent, see its skills, and send structured requests via JSON-RPC."

### Minute 4: "Structured Handoffs Between Agents" (4:00)

**Talking point:**
> "When one agent needs to delegate work, it creates a handoff span. The receiving agent picks it up with full context — task history, constraints, prior decisions. No context loss between agents."

**Query — Handoff spans:**
```
# TraceQL: Agent handoff events
{span.handoff.initiated = true} | select(span.handoff.from_agent, span.handoff.to_agent, span.handoff.task_id, span.handoff.context_size)
```

**What to show:** A handoff span showing agent A delegating to agent B with context preservation metrics.

### Minute 5: "Knowledge Compounds" (5:00)

**Talking point:**
> "Decisions persist. Lessons accumulate. Agents discover each other. Context transfers between sessions and between agents. That's not prompt engineering — that's business observability applied to AI operations."

**Query — Knowledge accumulation over time:**
```
# TraceQL: Insight count by type over time
{span.insight.type != ""} | count() by(span.insight.type)
```

**Visual:** A time-series chart showing insight spans accumulating over the demo period — decisions, lessons, questions — growing over time as agents learn.

---

## Delivered Capabilities

| Capability | Maturity | What It Does |
|-----------|----------|--------------|
| `contextcore.insight.emit` | stable | Store decisions/lessons/blockers as OTel spans |
| `contextcore.insight.query` | stable | Retrieve prior insights by project/type/confidence |
| `contextcore.a2a.server` | beta | A2A protocol: agent discovery + JSON-RPC |
| `contextcore.a2a.client` | beta | Communicate with any A2A-compatible agent |
| `contextcore.handoff.initiate` | beta | Structured task delegation between agents |

---

## Fallback If Live Queries Fail

The insight and handoff spans are included in the historical demo dataset. If A2A endpoints aren't running, show the agent card JSON directly and explain the discovery flow. The key demo moment is the TraceQL insight query — ensure that works above all else.
