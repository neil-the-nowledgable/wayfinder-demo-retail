# Compliance Officer: 5-Minute Deep-Dive

**One-line pitch:** Business observability means audit-ready by design.

**Pain addressed:** $206K/yr (enterprise) for officer labor + team disruption during audits

---

## Pre-Demo Checklist

- [ ] Grafana running at http://localhost:3000
- [ ] Loki datasource configured and receiving logs
- [ ] Tempo datasource configured with historical demo data
- [ ] Historical demo data loaded with 3 months of history (run `demo/setup_demo_env.sh`)

---

## Talking Points & Queries

### Minute 1: "Every Status Change Is a Structured Log" (1:00)

**Setup:** Open Grafana Explore view with Loki datasource selected.

**Talking point:**
> "Every task status change is logged as structured JSON in Loki. Created, started, blocked, completed — each transition is an immutable log entry with timestamps, actors, and evidence."

**Query — Full task lifecycle:**
```
# LogQL: Complete lifecycle for a specific task
{project="online-boutique"} |= "paymentservice" | json | task_type = "task" | line_format "{{.timestamp}} | {{.task_id}} | {{.status}} | {{.actor}}"
```

**What to show:** A sequence of structured log entries showing a task moving through `todo -> in_progress -> review -> done`, each with timestamps and the actor who triggered the transition.

### Minute 2: "Time-Range Queries — Instant Audit Answers" (2:00)

**Talking point:**
> "Auditor asks: 'Show me everything that happened with the payment service in October.' You don't schedule a meeting. You don't pull people off their work. You run a query."

**Query — Point-in-time audit:**
```
# TraceQL: All payment service activity in October
{span.task.service = "paymentservice"} | select(span.task.id, span.task.title, span.task.status, span.task.assignee) | timerange(2025-10-01T00:00:00Z, 2025-10-31T23:59:59Z)
```

**Query — What was blocked and why:**
```
# TraceQL: Blockers during audit period
{span.task.service = "paymentservice" && span.task.blocker = true} | select(span.task.id, span.task.blocker.reason, span.task.blocker.resolved)
```

**What to show:** Instant results — task IDs, titles, statuses, assignees, blockers — all from a single query against historical data.

### Minute 3: "Evidence Chain — Decision to Deployment" (3:00)

**Talking point:**
> "For any change, you can trace the complete evidence chain: the architectural decision, the implementation commits, the test results, and the deployment. All linked by trace IDs."

**Query — Evidence chain:**
```
# TraceQL: Trace a decision through to deployment
{span.task.id = "DEMO-P1-GENERATE"} | select(span.task.title, span.insight.type, span.artifact.type, span.artifact.url)
```

**What to show:** A trace view in Tempo showing:
1. ADR (architectural decision record) span
2. Implementation commit spans linked to the ADR
3. Test result spans
4. Deployment span

All connected by parent-child span relationships.

### Minute 4: "Structured Data, Not Narratives" (4:00)

**Talking point:**
> "Traditional audit evidence is screenshots, emails, and narratives. This is structured JSON. It's machine-queryable, tamper-evident (immutable log storage), and complete by default — not compiled after the fact."

**Query — Structured audit export:**
```
# LogQL: Export all status changes as structured JSON for audit package
{project="online-boutique"} | json | line_format "{{.timestamp}},{{.task_id}},{{.status}},{{.actor}},{{.evidence_url}}"
```

**What to show:** Structured data output that could be piped directly into an audit report or compliance tool. Contrast with: "In the old world, this would be 3 weeks of pulling people into meetings."

### Minute 5: "Audit-Ready by Design" (5:00)

**Talking point:**
> "You didn't prepare for this audit. The data was already there. Every status change, every decision, every blocker — logged as structured telemetry from day one. Audit response in minutes, not weeks."

**Visual:** The Loki query results + Tempo trace view + evidence chain — everything an auditor needs, produced by normal development activity with zero additional overhead.

---

## Delivered Capabilities

| Capability | Maturity | What It Does |
|-----------|----------|--------------|
| `contextcore.audit.full_trail` | stable | Every status change logged as structured JSON in Loki |
| `contextcore.audit.time_queries` | stable | Query project state at any point in time |
| `contextcore.audit.evidence_linking` | beta | Trace from decision -> code -> test -> deployment |

---

## Fallback If Live Queries Fail

Loki queries depend on log data being loaded. If Loki is not available, demonstrate using Tempo TraceQL queries only (the time-range and evidence-chain queries work against span data). Have a screenshot of the structured log output ready as backup.
