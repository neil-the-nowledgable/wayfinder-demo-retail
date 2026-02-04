# Demo Query Cheat Sheet

Pre-written TraceQL and LogQL queries organized by persona and demo moment. Copy-paste into Grafana Explore.

---

## Universal Queries (Concept Demo)

### Basic Task Discovery
```
# TraceQL: Find all task spans
{span.task.id != ""} | select(span.task.id, span.task.title, span.task.status) | limit(10)
```

### Task Lifecycle Events
```
# TraceQL: Task with full lifecycle
{span.task.id = "DEMO-LIVE-001"} | select(span.task.title, span.task.status)
```

### Portfolio Summary
```
# TraceQL: Task counts by service
{span.task.id != "" && resource.project.id = "online-boutique"} | count() by(span.task.service)
```

### Blocker Overview
```
# TraceQL: All current blockers
{span.task.blocker = true && span.task.blocker.resolved = false} | select(span.task.id, span.task.service, span.task.blocker.reason)
```

---

## Developer Queries

### Auto-Derived Status from Artifacts
```
# TraceQL: Status changes triggered by git artifacts
{span.task.id != "" && span.task.status.source = "artifact"} | select(span.task.id, span.task.status, span.artifact.type)
```

### Agent Decisions (Persistent Memory)
```
# TraceQL: High-confidence decisions
{span.insight.type = "decision" && span.insight.confidence >= 0.8} | select(span.insight.summary, span.insight.confidence, span.insight.evidence)
```

### Agent Constraint Evaluations
```
# TraceQL: Constraint checks
{span.agent.constraint.evaluated = true} | select(span.agent.constraint.name, span.agent.constraint.result, span.agent.action)
```

### Decision Audit Trail for a Task
```
# TraceQL: All decisions related to a specific task
{span.task.id = "DEMO-P1-GENERATE" && span.insight.type = "decision"}
```

### Insights by Type
```
# TraceQL: Count insights by type
{span.insight.type != ""} | count() by(span.insight.type)
```

---

## Project Manager Queries

### Project Health by Service
```
# TraceQL: Task status distribution per service
{span.task.id != "" && resource.project.id = "online-boutique"} | count() by(span.task.service, span.task.status)
```

### Sprint Velocity
```
# TraceQL: Completed tasks in current sprint
{span.sprint.id = "demo-sprint-1" && span.task.status = "done"} | count() by(span.task.service)
```

### Stale Tasks (No Activity in 7 Days)
```
# TraceQL: In-progress tasks with no recent events
{span.task.status = "in_progress" && span.task.last_event_age > 7d}
```

### Cycle Time Distribution
```
# TraceQL: Completed tasks with duration
{span.task.status = "done" && span.task.type = "task"} | select(span.task.id, span.task.service, duration)
```

### WIP Count
```
# TraceQL: Currently in-progress tasks
{span.task.status = "in_progress"} | count() by(span.task.service)
```

---

## Engineering Leader Queries

### Cross-Project Portfolio
```
# TraceQL: All projects with health summary
{span.task.type = "epic"} | select(span.task.service, span.task.status, span.task.blocker_count)
```

### Workload Distribution
```
# TraceQL: Active tasks per assignee
{span.task.status = "in_progress"} | count() by(span.task.assignee)
```

### Overload Detection
```
# TraceQL: Assignees with >5 concurrent tasks
{span.task.status = "in_progress"} | count() by(span.task.assignee) | where(count > 5)
```

### Historical State — What Was Happening in Q3?
```
# TraceQL: Tasks active during October
{span.task.status = "in_progress"} | select(span.task.id, span.task.title, span.task.service) | timerange(2025-10-01T00:00:00Z, 2025-10-31T23:59:59Z)
```

### Blockers by Criticality
```
# TraceQL: Blockers ranked by service criticality
{span.task.blocker = true} | count() by(span.task.service) | sort(count, desc)
```

### Gap Prioritization (Services with Most Issues)
```
# TraceQL: Services with most blockers
{span.task.blocker = true} | count() by(span.task.service) | sort(count, desc)
```

---

## Operator / SRE Queries

### Enriched Alert Events
```
# LogQL: Alert events with Fox enrichment
{service="fox"} |= "enriched" | json | line_format "{{.alertname}} | criticality={{.criticality}} | owner={{.owner}}"
```

### Alert Routing Decisions
```
# LogQL: Rabbit routing decisions
{service="rabbit"} |= "route" | json | line_format "{{.service}} ({{.criticality}}) -> {{.route}}"
```

### Recent Changes for an Affected Service
```
# TraceQL: Tasks completed in last 48h for a service
{span.task.service = "checkoutservice" && span.task.status = "done"} | select(span.task.id, span.task.title) | timerange(last 48h)
```

### Active Tasks for a Service (During Incident)
```
# TraceQL: In-progress tasks for a specific service
{span.task.service = "checkoutservice" && span.task.status != "done"} | select(span.task.id, span.task.title, span.task.status)
```

### Service Criticality Lookup
```
# TraceQL: Find services by criticality level
{span.task.service != "" && resource.service.criticality = "critical"} | select(span.task.service) | distinct()
```

---

## Compliance Officer Queries

### Full Task Lifecycle (Structured Logs)
```
# LogQL: Complete lifecycle for payment service tasks
{project="online-boutique"} |= "paymentservice" | json | task_type = "task" | line_format "{{.timestamp}} | {{.task_id}} | {{.status}} | {{.actor}}"
```

### Point-in-Time Audit
```
# TraceQL: All payment service activity in October
{span.task.service = "paymentservice"} | select(span.task.id, span.task.title, span.task.status, span.task.assignee) | timerange(2025-10-01T00:00:00Z, 2025-10-31T23:59:59Z)
```

### Blockers During Audit Period
```
# TraceQL: Blockers during Q3
{span.task.service = "paymentservice" && span.task.blocker = true} | select(span.task.id, span.task.blocker.reason, span.task.blocker.resolved) | timerange(2025-07-01T00:00:00Z, 2025-09-30T23:59:59Z)
```

### Evidence Chain (Decision to Deployment)
```
# TraceQL: Trace a specific task's evidence chain
{span.task.id = "DEMO-P1-GENERATE"} | select(span.task.title, span.insight.type, span.artifact.type, span.artifact.url)
```

### Structured Audit Export (CSV-like)
```
# LogQL: Export all status changes as structured data
{project="online-boutique"} | json | line_format "{{.timestamp}},{{.task_id}},{{.status}},{{.actor}},{{.evidence_url}}"
```

---

## AI Agent Queries

### All Insight Spans
```
# TraceQL: View all emitted insights
{span.insight.type != ""} | select(span.insight.type, span.insight.summary, span.insight.confidence)
```

### High-Confidence Decisions
```
# TraceQL: Decisions with confidence >= 0.8
{span.insight.type = "decision" && span.insight.confidence >= 0.8} | select(span.insight.summary, span.insight.confidence, span.insight.evidence)
```

### Lessons Learned for a Service
```
# TraceQL: Lessons for checkoutservice
{span.insight.type = "lesson" && span.task.service = "checkoutservice"} | select(span.insight.summary, span.insight.confidence)
```

### Agent Handoff Events
```
# TraceQL: Handoff spans between agents
{span.handoff.initiated = true} | select(span.handoff.from_agent, span.handoff.to_agent, span.handoff.task_id, span.handoff.context_size)
```

### Knowledge Accumulation Over Time
```
# TraceQL: Insight count by type
{span.insight.type != ""} | count() by(span.insight.type)
```

### Questions Pending Resolution
```
# TraceQL: Unresolved agent questions
{span.insight.type = "question" && span.insight.resolved = false} | select(span.insight.summary, span.task.service)
```

---

## Query Tips

- **Time ranges:** Use the Grafana time picker (top right) or add `| timerange(...)` to TraceQL queries
- **Service filter:** Replace `checkoutservice` with any of the 11 Online Boutique services
- **Limit results:** Add `| limit(N)` to any query to cap output
- **Datasource:** TraceQL queries use the Tempo datasource; LogQL queries use the Loki datasource
- **Explore view:** Grafana > Explore (compass icon) > select datasource > paste query
