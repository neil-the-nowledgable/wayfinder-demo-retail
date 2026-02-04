# Project Manager: 5-Minute Deep-Dive

**One-line pitch:** Business observability means your status report writes itself.

**Pain addressed:** $117K/yr (enterprise) for weekly status compilation + chasing developers for updates

---

## Pre-Demo Checklist

- [ ] Grafana running at http://localhost:3000
- [ ] Portfolio dashboard imported and populated
- [ ] Sprint Metrics dashboard imported
- [ ] Historical demo data loaded (run `demo/setup_demo_env.sh`)

---

## Talking Points & Queries

### Minute 1: "Portfolio at a Glance" (1:00)

**Setup:** Open the Portfolio dashboard in Grafana.

**Talking point:**
> "This is every project in your portfolio. Health, blockers, progress — all derived from actual work artifacts. Nobody compiled this. It compiled itself."

**Dashboard:** Project Portfolio Overview (`portfolio.json`)

**What to show:** All 11 Online Boutique services with health indicators, task counts, and blocker badges.

### Minute 2: "Drill Down Without Asking Anyone" (2:00)

**Talking point:**
> "Click any project to drill into the hierarchy. Portfolio to epic to story to task. Each level shows real status derived from commits and CI, not from someone remembering to update a ticket."

**Query — Project hierarchy drill-down:**
```
# TraceQL: All tasks for frontend service, hierarchical
{resource.project.id = "online-boutique" && span.task.service = "frontend"} | select(span.task.type, span.task.id, span.task.status)
```

**What to show:** Click `frontend` (critical) -> see epics -> click an epic -> see stories -> see individual tasks with lifecycle events.

### Minute 3: "Sprint Metrics — Live" (3:00)

**Talking point:**
> "Velocity, burndown, cycle time — updating in real-time. Not calculated on Friday afternoon from manually-updated tickets. Calculated from actual task span durations."

**Dashboard:** Sprint Metrics (`sprint-metrics.json`)

**Query — Sprint velocity:**
```
# TraceQL: Completed tasks in current sprint
{span.sprint.id = "demo-sprint-1" && span.task.status = "done"} | count() by(span.task.service)
```

**What to show:** Velocity trend chart, burndown curve, WIP gauge, cycle time distribution.

### Minute 4: "Stale Task Detection" (4:00)

**Talking point:**
> "Instead of chasing developers, the system flags tasks that haven't had activity in N days. No awkward 'hey, what's the status?' messages. The data tells you."

**Query — Find stale tasks:**
```
# TraceQL: Tasks with no events in last 7 days
{span.task.status = "in_progress" && span.task.last_event_age > 7d}
```

**What to show:** A list of tasks flagged as stale with last-activity timestamps. Contrast with: "In the old world, you'd send 5 Slack messages to find this out."

### Minute 5: "Monday Morning — Done" (5:00)

**Talking point:**
> "Your Monday morning status meeting? Open this dashboard. Everything is there. Progress, blockers, velocity, stale tasks. Real-time data, no manual compilation, no chasing developers."

**Visual:** The Portfolio dashboard as the single source of truth. Everything a PM needs in one view.

---

## Delivered Capabilities

| Capability | Maturity | What It Does |
|-----------|----------|--------------|
| `contextcore.dashboard.portfolio` | stable | All projects in one Grafana view with health/blockers |
| `contextcore.dashboard.project_drilldown` | stable | Portfolio -> Epic -> Story -> Task hierarchy |
| `contextcore.dashboard.sprint` | beta | Velocity, burndown, cycle time — real-time |
| `contextcore.status.stale_detection` | beta | Alert when tasks go stale (no activity in N days) |

---

## Fallback If Live Queries Fail

The Portfolio and Sprint dashboards are pre-loaded with historical data. All panels should populate from the demo dataset. If a panel is empty, verify Tempo datasource connectivity in Grafana Settings > Data Sources.
