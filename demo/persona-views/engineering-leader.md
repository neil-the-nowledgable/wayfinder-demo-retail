# Engineering Leader: 5-Minute Deep-Dive

**One-line pitch:** Business observability means portfolio decisions backed by real-time data.

**Pain addressed:** $258K/yr (enterprise) for 5-tool portfolio assembly + audit team disruption

---

## Pre-Demo Checklist

- [ ] Grafana running at http://localhost:3000
- [ ] Portfolio dashboard imported and populated
- [ ] Historical demo data loaded with 3 months of history (run `demo/setup_demo_env.sh`)
- [ ] Multiple projects visible in portfolio view

---

## Talking Points & Queries

### Minute 1: "One Dashboard, Not Five Tools" (1:00)

**Setup:** Open the Portfolio dashboard in Grafana.

**Talking point:**
> "Right now, you assemble portfolio status from Jira, GitHub, Slack, CI dashboards, and spreadsheets. This is all of them — one view. Same Grafana your SREs already use for ops."

**Dashboard:** Project Portfolio Overview (`portfolio.json`)

**What to show:** Cross-project portfolio view with health indicators, progress bars, and blocker counts for all 11 services.

### Minute 2: "Workload Distribution" (2:00)

**Talking point:**
> "Who's overloaded? Who has capacity? Not guesswork from sprint planning — derived from actual task assignments and completion rates."

**Query — Team workload:**
```
# TraceQL: Active tasks per assignee
{span.task.status = "in_progress"} | count() by(span.task.assignee)
```

**Query — Overload detection:**
```
# TraceQL: Assignees with >5 concurrent in-progress tasks
{span.task.status = "in_progress"} | count() by(span.task.assignee) | where(count > 5)
```

**What to show:** A workload heatmap or table showing task distribution across team members, with overloaded individuals highlighted.

### Minute 3: "Historical Queries — Instant Answers" (3:00)

**Talking point:**
> "VP asks 'What was the team working on in Q3?' You don't schedule a meeting. You don't dig through old standups. You query Tempo with a time range."

**Query — Point-in-time state:**
```
# TraceQL: What was in progress during October
{span.task.status = "in_progress"} | select(span.task.id, span.task.title, span.task.service) | timerange(2025-10-01T00:00:00Z, 2025-10-31T23:59:59Z)
```

**Query — What was blocked:**
```
# TraceQL: Blockers during Q3
{span.task.blocker = true} | select(span.task.id, span.task.title, span.task.blocker.reason) | timerange(2025-07-01T00:00:00Z, 2025-09-30T23:59:59Z)
```

**What to show:** Tempo returning historical task state instantly — no archaeology required.

### Minute 4: "ROI-Driven Prioritization" (4:00)

**Talking point:**
> "Roadmap gaps ranked by ROI signal. Not by who argued loudest in the planning meeting. The data shows which services have the most blockers, the longest cycle times, the highest business value."

**Query — Gap prioritization:**
```
# TraceQL: Services with most blockers, sorted by business criticality
{span.task.blocker = true} | count() by(span.task.service) | sort(count, desc)
```

**What to show:** A ranked list of services by blocker count, cross-referenced with criticality from ProjectContext CRDs (critical > high > medium > low).

### Minute 5: "The Executive Summary" (5:00)

**Talking point:**
> "One dashboard replaces five tools. Historical state is a query, not a research project. Workload is visible, not guessed. Priorities are data-driven, not opinion-driven. That's business observability for engineering leaders."

**Visual:** The portfolio dashboard, a historical query result, and the workload view — three capabilities that replace an entire tool chain.

---

## Delivered Capabilities

| Capability | Maturity | What It Does |
|-----------|----------|--------------|
| `contextcore.dashboard.portfolio` | stable | Cross-project portfolio health |
| `contextcore.dashboard.workload` | beta | Team workload distribution, overload detection |
| `contextcore.audit.time_queries` | stable | Query project state at any historical point |
| `contextcore.value.gap_prioritization` | stable | Roadmap gaps ranked by ROI signal |

---

## Fallback If Live Queries Fail

Historical queries depend on the 3-month demo dataset. If time-range queries return empty, verify the demo data time range with:
```
{resource.project.id = "online-boutique"} | select(span.task.id) | limit(5)
```
Adjust time ranges to match the generated data window.
