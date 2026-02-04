# Operator / SRE: 5-Minute Deep-Dive

**One-line pitch:** Business observability means every alert arrives with context.

**Pain addressed:** $247K/yr (enterprise) for incidents without context (15-min MTTA delay at $10K/hr downtime)

---

## Pre-Demo Checklist

- [ ] Grafana running at http://localhost:3000
- [ ] ProjectContext CRDs loaded (11 Online Boutique services)
- [ ] Project-Operations dashboard imported
- [ ] Fox (Waagosh) webhook server available or screenshots ready
- [ ] Historical demo data loaded (run `demo/setup_demo_env.sh`)

---

## Talking Points & Queries

### Minute 1: "ProjectContext — Business Metadata for Services" (1:00)

**Setup:** Show a ProjectContext CRD YAML file for `checkoutservice`.

**Talking point:**
> "Every service has a ProjectContext CRD. It declares the owner, team, criticality, business value, escalation contacts, and runbook links. This isn't documentation that rots in a wiki — it lives with the service and powers alerting."

**File to show:** `ContextCore/demo/projectcontexts/checkoutservice.yaml`

**Key fields to highlight:**
- `criticality: critical`
- `businessValue: revenue-primary`
- `owner` and `escalationContacts`
- `runbookUrl`

### Minute 2: "Enriched Alerts" (2:00)

**Talking point:**
> "When checkoutservice fires an alert, Fox enriches it with ProjectContext data. The page arrives with owner, criticality, recent tasks that touched the service, and a runbook link. No more 'who owns this?' at 2am."

**Query — Enriched alert example:**
```
# LogQL: Alert events with enrichment data
{service="fox"} |= "enriched" | json | alertname = "DemoPhase2Alert" | line_format "{{.alertname}} | criticality={{.criticality}} | owner={{.owner}}"
```

**What to show:** An alert payload before and after Fox enrichment. Before: `{alertname, severity}`. After: `{alertname, severity, owner, team, criticality, recentTasks, runbookUrl}`.

### Minute 3: "Priority Routing" (3:00)

**Talking point:**
> "Critical services page immediately. Low-priority services queue for business hours. The routing is automatic, derived from the ProjectContext criticality field. No manual alert rules to maintain."

**Query — Alert routing by criticality:**
```
# LogQL: Alert routing decisions
{service="rabbit"} |= "route" | json | line_format "{{.service}} ({{.criticality}}) -> {{.route}}"
```

**What to show:** Routing table: `checkoutservice (critical) -> page`, `adservice (medium) -> queue`, `loadgenerator (low) -> log-only`.

### Minute 4: "Project-Operations Correlation" (4:00)

**Setup:** Open the Project-Operations dashboard.

**Talking point:**
> "Services grouped by business value, correlated with runtime health. You can see that the payment service has 3 open tasks AND elevated error rates — that's not a coincidence, it's a signal."

**Dashboard:** Project-Operations (`project-operations.json`)

**Query — Correlate project activity with runtime:**
```
# TraceQL: Recent tasks for a service with runtime issues
{span.task.service = "checkoutservice" && span.task.status != "done"} | select(span.task.id, span.task.title, span.task.status)
```

**What to show:** Dashboard panels showing services organized by criticality with both project task status and runtime metrics side by side.

### Minute 5: "Context at Incident Time" (5:00)

**Talking point:**
> "During an outage, you need context fast. What changed recently? Who owns this? What's the escalation path? All of this is a query away. Context travels with the alert — you don't have to hunt for it."

**Query — Recent changes for a service:**
```
# TraceQL: Tasks completed in last 48h for the affected service
{span.task.service = "checkoutservice" && span.task.status = "done"} | select(span.task.id, span.task.title) | timerange(last 48h)
```

**Visual:** The enriched alert payload + recent task list + ProjectContext metadata — everything an SRE needs at incident time, available in seconds.

---

## Delivered Capabilities

| Capability | Maturity | What It Does |
|-----------|----------|--------------|
| `contextcore.alert.enrichment` | beta | Alerts include owner, criticality, business context |
| `contextcore.alert.priority_routing` | beta | Critical services page immediately; low-priority queues |
| `contextcore.incident.context` | beta | During outage: recent tasks, changes, escalation contacts |

---

## Fallback If Live Queries Fail

If Fox isn't running, show the ProjectContext CRD YAML directly and explain the enrichment flow conceptually. The Project-Operations dashboard should populate from historical data. Have a screenshot of an enriched alert payload ready.
