# Business Observability: 5-Minute Concept Demo Runbook

This is the universal intro that any persona watches before their persona-specific deep-dive.

**Total time:** 5 minutes
**Audience:** Any persona (developers, PMs, leaders, SREs, compliance, AI practitioners)

---

## Pre-Demo Setup Checklist

- [ ] Run `demo/setup_demo_env.sh` (generates data, loads to Tempo/Loki, imports dashboards)
- [ ] Verify Grafana at http://localhost:3000 (admin/admin)
- [ ] Verify Tempo at http://localhost:3200/ready
- [ ] Verify Loki at http://localhost:3100/ready
- [ ] Open Portfolio dashboard in a browser tab
- [ ] Open Grafana Explore (Tempo) in a second tab
- [ ] Have `ContextCore/examples/01_basic_task_tracking.py` open in editor
- [ ] Have the ecosystem diagram ready (or whiteboard equivalent)

---

## Minute 1: "The Paradigm" (0:00 - 1:00)

### Talking Points

> "Operational observability transformed how we run systems. Metrics, traces, logs — all queryable, all real-time. You wouldn't run production without Prometheus and Grafana."
>
> "Business observability does the same thing for how we BUILD systems. Tasks, decisions, status — treated as telemetry. Queryable. Real-time. Dashboard-ready."
>
> "ContextCore is the reference implementation. Wayfinder is the ecosystem. Everything emits OpenTelemetry. Everything lands in the same Grafana you already use."

### Visual

Draw or show a diagram with two parallel streams:

```
OPERATIONAL TELEMETRY          BUSINESS TELEMETRY
─────────────────────          ──────────────────
Prometheus (metrics)           Tasks (OTel spans)
Tempo (traces)                 Insights (decisions, lessons)
Loki (logs)                    Handoffs (agent collaboration)
        \                      /
         \                    /
          ──── Grafana ──────
```

### Key Message

"Same infrastructure. Same query language. Same dashboards. New data type: business telemetry."

---

## Minute 2: "Tasks as Spans" (1:00 - 2:00)

### Talking Points

> "A task is an OpenTelemetry span. It has a start time, an end time, attributes, and events. When a task is created, a span starts. When it's completed, the span ends."
>
> "Status isn't manually updated. It's derived from artifacts — commits, PRs, merges. You don't tell the system 'I started working.' The system knows because you pushed a commit."

### Live Demo

1. Show `ContextCore/examples/01_basic_task_tracking.py` briefly in editor
2. Switch to Grafana Explore (Tempo datasource)
3. Run this query:

```
# TraceQL: Find task spans with lifecycle events
{span.task.id != ""} | select(span.task.id, span.task.title, span.task.status) | limit(5)
```

4. Click into a task span to show:
   - Span attributes (task.id, task.title, task.status, task.type)
   - Span events (status transitions: todo -> in_progress -> done)
   - Duration (time from creation to completion)

### Key Message

"A task span is the atomic unit of business observability. Everything else builds on this."

---

## Minute 3: "The Dashboard Layer" (2:00 - 3:00)

### Talking Points

> "Because tasks are spans, we get dashboards for free. Same Grafana. Same TraceQL. Same alerting infrastructure."
>
> "No new tools. No new SaaS subscriptions. Your observability stack just gained a new dimension."

### Live Demo

1. Switch to the Portfolio dashboard tab
2. Show all 11 Online Boutique services at a glance:
   - Health indicators (green/yellow/red)
   - Task counts per service
   - Blocker badges
   - Progress bars
3. Quick drill-down: click `frontend` -> show epic breakdown -> show tasks

### Dashboard URLs

- Portfolio: http://localhost:3000/d/portfolio/project-portfolio-overview
- Sprint Metrics: http://localhost:3000/d/sprint-metrics/sprint-metrics
- Project Progress: http://localhost:3000/d/project-progress/project-progress

### Key Message

"Your status report is a dashboard. Your sprint review is a dashboard. Your portfolio review is a dashboard. All real-time. All derived."

---

## Minute 4: "The Intelligence Layer" (3:00 - 4:00)

### Talking Points

> "Agents emit decisions as insight spans — with confidence scores and evidence links. Not hidden in chat logs. Queryable. Auditable."
>
> "Alerts arrive with business context. When checkoutservice pages at 2am, the alert includes the owner, criticality, recent tasks, and a runbook link."

### Live Demo — Insight Query

In Grafana Explore (Tempo):

```
# TraceQL: Find agent decisions with high confidence
{span.insight.type = "decision" && span.insight.confidence >= 0.8} | select(span.insight.summary, span.insight.confidence) | limit(3)
```

Show one insight span's details — summary, confidence, evidence.

### Live Demo — Enriched Alert (Brief)

Show a ProjectContext CRD snippet:

```yaml
# checkoutservice — business metadata that powers alert enrichment
spec:
  criticality: critical
  businessValue: revenue-primary
  owner: checkout-team
  escalationContacts:
    - oncall@company.com
```

> "This metadata rides with the alert. No 'who owns this?' investigation."

### Key Message

"Intelligence is queryable telemetry, not tribal knowledge."

---

## Minute 5: "The Ecosystem" (4:00 - 5:00)

### Talking Points

> "ContextCore is the core. The ecosystem extends it with purpose-built capabilities."

Name each expansion pack by purpose:

| Purpose | Package | Ojibwe Name | What It Does |
|---------|---------|-------------|-------------|
| Alert Routing | Rabbit | Waabooz | Business-aware alert triage |
| Alert Automation | Fox | Waagosh | Context enrichment for incidents |
| Agent Pipelines | Coyote | Wiisagi-ma'iingan | Multi-agent incident resolution |
| Multi-LLM Agent SDK | Beaver | StartD8 | Workflow orchestration + cost tracking |
| Knowledge Management | Squirrel | Ajidamoo | Skills and lessons persistence |

> "Everything emits OTel. Everything lands in Grafana. No silos. No tool-switching. One unified view of your entire software operation."

### Visual

Ecosystem data flow:

```
ContextCore (Spider) ──── Tasks as spans
     │
     ├── Rabbit ──── Alert routing by business criticality
     ├── Fox ──── Alert enrichment with project context
     ├── Coyote ──── Multi-agent incident resolution
     ├── Beaver ──── LLM cost tracking + workflow orchestration
     └── Squirrel ──── Skills persistence + knowledge emission
     │
     └──── All emit OTel ──── Grafana
```

### Closing

> "That's business observability. Treat project and business data with the same discipline you already use for operational telemetry. Tasks are spans. Status is derived. Everything is queryable."

---

## Transition to Persona Deep-Dives

After the 5-minute concept demo, transition to a persona-specific deep-dive:

| Persona | File | Duration |
|---------|------|----------|
| Developer | `demo/persona-views/developer.md` | 5 min |
| Project Manager | `demo/persona-views/project-manager.md` | 5 min |
| Engineering Leader | `demo/persona-views/engineering-leader.md` | 5 min |
| Operator / SRE | `demo/persona-views/operator-sre.md` | 5 min |
| Compliance Officer | `demo/persona-views/compliance.md` | 5 min |
| AI Agent | `demo/persona-views/ai-agent.md` | 5 min |

**Combined time:** 5 min (concept) + 5 min (persona) = ~10 min total

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Portfolio dashboard empty | Verify Tempo datasource in Grafana Settings > Data Sources |
| TraceQL query returns no results | Re-run `demo/setup_demo_env.sh` to regenerate and reload data |
| Grafana not reachable | Check Docker: `docker ps \| grep grafana` |
| Loki queries fail | Verify Loki datasource; some queries work Tempo-only as fallback |
| Dashboards not found | Re-import: `demo/setup_demo_env.sh` handles this automatically |
