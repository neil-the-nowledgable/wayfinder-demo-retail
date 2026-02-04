# Wayfinder & ContextCore Demo Assets Inventory

Consolidated inventory of all demo-related assets across the Wayfinder ecosystem.

Last updated: 2026-02-03

---

## Repos Covered

| Repo | Package | Location |
|------|---------|----------|
| ContextCore | Core implementation | `/dev/ContextCore/` |
| wayfinder-demo-retail | Retail demo (this repo) | `/dev/wayfinder-demo-retail/` |
| contextcore-dot-me | Website / docs | `/dev/contextcore-dot-me/` |
| contextcore-rabbit | Waabooz - Alert Routing | `/dev/contextcore-rabbit/` |
| contextcore-fox | Waagosh - Alert Automation | `/dev/contextcore-fox/` |
| contextcore-coyote | Wiisagi-ma'iingan - Agent Pipelines | `/dev/contextcore-coyote/` |
| contextcore-skills | Ajidamoo (Squirrel) - Knowledge Emission | `/dev/contextcore-skills/` |
| startd8-sdk | Multi-LLM Agent SDK | `/dev/startd8-sdk/` |

---

## 1. ContextCore (Core)

### Demo Module (`src/contextcore/demo/`)

| File | Description |
|------|-------------|
| `__init__.py` | Public API: HistoricalTaskTracker, generate_demo_data, load_to_tempo, SERVICE_CONFIGS |
| `generator.py` | HistoricalTaskTracker with time manipulation; generates backdated spans for project-to-operations correlation |
| `exporter.py` | Dual-export to JSON files, OTLP/Tempo (spans), and Loki (logs) |
| `project_data.py` | 11 Google Online Boutique service configs with task hierarchies (epics, stories, tasks) |

### Demo Dashboards (`demo/dashboards/`)

| File | Description |
|------|-------------|
| `project-progress.json` | Task/epic counts, milestone tracking |
| `sprint-metrics.json` | Velocity trends, WIP gauge, cycle time |
| `project-operations.json` | Runtime correlation, service map |

### ProjectContext CRDs (`demo/projectcontexts/`)

11 Kubernetes CRD manifests for Google Online Boutique microservices:

| Service | Criticality | Business Value |
|---------|-------------|----------------|
| `frontend.yaml` | critical | revenue-primary |
| `checkoutservice.yaml` | critical | revenue-primary |
| `paymentservice.yaml` | critical | revenue-primary |
| `cartservice.yaml` | high | revenue-secondary |
| `productcatalogservice.yaml` | high | revenue-primary |
| `shippingservice.yaml` | high | revenue-secondary |
| `currencyservice.yaml` | medium | enabler |
| `emailservice.yaml` | medium | enabler |
| `recommendationservice.yaml` | medium | revenue-secondary |
| `adservice.yaml` | medium | internal enabler |
| `loadgenerator.yaml` | low | internal testing |

### Deployment Scripts (`demo/setup/`)

| File | Description |
|------|-------------|
| `deploy.sh` | Full deployment: kind cluster + observability stack + microservices-demo |
| `deploy.ps1` | Windows PowerShell equivalent |
| `kind-cluster.yaml` | Kind cluster configuration |

### Kubernetes Manifests (`demo/manifests/`)

| Path | Description |
|------|-------------|
| `base/kustomization.yaml` | Base upstream manifests |
| `overlays/contextcore/kustomization.yaml` | ContextCore annotation overlay |

### Python Examples (`examples/`)

| File | Description |
|------|-------------|
| `01_basic_task_tracking.py` | Core "tasks as spans" pattern with OTel lifecycle events |
| `02_agent_insights.py` | Agent decisions, lessons, questions stored as spans |
| `03_artifact_status_derivation.py` | Auto-derive task status from git/CI artifacts |

### Provisioned Grafana Dashboards (`grafana/provisioning/dashboards/json/`)

| File | Description |
|------|-------------|
| `portfolio.json` | Project Portfolio Overview |
| `installation.json` | Installation Verification |
| `value-capabilities.json` | Value Capabilities Explorer |
| `project-progress.json` | Project Progress |
| `sprint-metrics.json` | Sprint Metrics |
| `project-operations.json` | Project Operations |

### CLI Demo Commands

```bash
contextcore demo generate [--seed 42]     # Generate 3-month project history as OTel spans
contextcore demo load --file <path>        # Load spans to Tempo
contextcore demo services                  # List all 11 microservices with metadata
contextcore demo setup                     # Full environment setup (kind + observability + demo)
```

---

## 2. wayfinder-demo-retail (This Repo)

### Demo Scripts (`demo/`)

| File | Description |
|------|-------------|
| `setup_demo_tasks.py` | Creates ContextCore tasks; supports `--concept-mode` (7 concept tasks) and full mode (13 tasks + 1 epic across 6 phases) |
| `run_self_tracking_demo.py` | Orchestrates self-tracking demo via Lead Contractor workflow; `--check` for prerequisite validation |
| `setup_demo_env.sh` | One-command pre-demo setup: generates data, loads to Tempo/Loki, imports dashboards, creates concept tasks |

### Concept Demo (`demo/`)

| File | Description |
|------|-------------|
| `CONCEPT_DEMO_RUNBOOK.md` | 5-minute universal "Intro to Business Observability" with per-minute talking points, dashboard URLs, and queries |
| `DEMO_QUERIES.md` | Pre-written TraceQL and LogQL queries organized by persona and demo moment |

### Persona View Cards (`demo/persona-views/`)

| File | Persona | Pain Addressed |
|------|---------|---------------|
| `developer.md` | Developer | $475K/yr — auto-status from commits + AI persistent memory |
| `project-manager.md` | Project Manager | $117K/yr — portfolio dashboard + sprint metrics |
| `engineering-leader.md` | Engineering Leader | $258K/yr — portfolio visibility + historical queries |
| `operator-sre.md` | Operator / SRE | $247K/yr — enriched alerts with business context |
| `compliance.md` | Compliance Officer | $206K/yr — instant audit evidence + time queries |
| `ai-agent.md` | AI Agent | $205K/yr — persistent insights + A2A collaboration |

### BPA Product Catalog (`demo/`)

| File | Description |
|------|-------------|
| `BPA-Products-v0.1.json` | 15 products for Blue Planet Adventures: 6 coats, 4 shirts, 2 boots, 2 shoes, 1 tent spike |
| `bpa-products-coats.json` | 6-product subset with mixed categories (coats, shirts, boots, shoes) |
| `bpa-products-example.json` | 3-product example showing SKU-level format (color + size embedded in ID) |
| `import-json.py` | Script to import product JSON into the demo catalog service |
| `microservices-boutique-products.md` | Reference list of 9 original Online Boutique product IDs |
| `demo_dev_log_2026_02_01.md` | Dev log documenting BPA product set design decisions |

---

## 3. contextcore-dot-me (Website)

### Demo Scripts (`demo/`)

| File | Description |
|------|-------------|
| `setup_demo_tasks.py` | Original copy (canonical version now in wayfinder-demo-retail) |
| `run_self_tracking_demo.py` | Original copy (canonical version now in wayfinder-demo-retail) |
| `README.md` | Points to wayfinder-demo-retail as canonical location |

### Ecosystem Documentation

| File | Description |
|------|-------------|
| `run_roi_calculator.py` | Interactive ROI calculator for ContextCore adoption |

---

## 4. contextcore-rabbit (Waabooz - Alert Routing)

| File | Description |
|------|-------------|
| `examples/basic_usage.py` | Webhook server setup with PrintAlertAction and HighSeverityAction handlers |
| `examples/grafana_dashboard.json` | Grafana dashboard for Rabbit alert processing monitoring |

---

## 5. contextcore-fox (Waagosh - Alert Automation)

| File | Description |
|------|-------------|
| `examples/basic_alert_handling.py` | Webhook server with project context enrichment and SLO display |
| `dashboards/fox-alert-automation.json` | Grafana dashboard for alert context enrichment and criticality routing |
| `k8s/deployment.yaml` | Kubernetes deployment manifest for Fox in observability namespace |

---

## 6. contextcore-coyote (Wiisagi-ma'iingan - Agent Pipelines)

No standalone demo files. Demo content documented inline in README with Python code examples for Investigator, Designer, and Implementer agents.

---

## 7. contextcore-skills (Ajidamoo - Knowledge Emission)

### Examples

| File | Description |
|------|-------------|
| `examples/sample-skill-emission.py` | Programmatic API for loading skills into Tempo backend |
| `examples/sample-value-proposition.yaml` | Capability-to-value mapping structure for auto-error-investigation |

### Emission Scripts (`scripts/`)

| File | Description |
|------|-------------|
| `squirrel_emit_all.py` | Unified emitter for lessons learned + knowledge items to Tempo |
| `lessons_learned_emitter.py` | Domain-specific lessons learned emitter |
| `lessons_learned_parser.py` | Multi-domain lessons learned file parser |
| `squirrel_knowledge_emitter.py` | Skill knowledge and capabilities emitter |
| `squirrel_knowledge_parser.py` | Capability index and skill metadata parser |

---

## 8. startd8-sdk (Multi-LLM Agent SDK)

### Python Examples (`examples/`)

| File | Description |
|------|-------------|
| `basic_usage.py` | Quick start: compare three models with provider registry |
| `advanced_benchmark.py` | Custom comparison metrics and cost analysis |
| `orchestration_example.py` | Multi-agent sequential workflow execution |
| `provider_examples.py` | Provider-specific configuration patterns |
| `git_integration.py` | Git tracking for feature implementations |
| `iterative_dev_workflow_example.py` | Dev-review-fix loop with agent feedback cycles |
| `async_features_demo.py` | Async/await patterns for non-blocking agent calls |
| `document_enhancement_example.py` | Multi-agent document processing and enhancement |
| `ASYNC_FEATURES.md` | Guide to async features |

### Job Queue Examples (`examples/job_queue/`)

| File | Description |
|------|-------------|
| `README.md` | Job queue system documentation |
| `simple_task_startd8_job.json` | Simple task job definition |
| `design_doc_startd8_job.json` | Design document generation job |
| `code_review_startd8_job.json` | Code review task job |

### Integration Scripts (`scripts/`)

| File | Description |
|------|-------------|
| `init_project_tracking.py` | Initialize project tracking with OTel spans |
| `sync_project_reality.py` | Sync project metadata with observability backend |
| `start_metrics_exporter.py` | Start OTel metrics exporter |
| `run_baseline_evaluation.py` | Baseline evaluation benchmarks across models |
| `generate_feature_jobs.py` | Generate job definitions for feature tasks |
| `run_contextcore_workflow.py` | Execute ContextCore workflow with project tracking |
| `integrate_contextcore_metadata.py` | Integrate ContextCore metadata and semantic conventions |
| `view_contextcore_tasks.sh` | View ContextCore tasks via CLI |
| `start-loki-stack.sh` | Start Loki observability stack |

---

## Summary

| Repo | Examples | Dashboards | Scripts | Docs/Runbooks | CRDs/K8s | Total |
|------|----------|------------|---------|---------------|----------|-------|
| ContextCore | 3 | 9 | 3 | 0 | 13 | 28 |
| wayfinder-demo-retail | 0 | 0 | 3 | 9 | 0 | 18* |
| contextcore-dot-me | 0 | 0 | 1 | 0 | 0 | 1 |
| contextcore-rabbit | 2 | 0 | 0 | 0 | 0 | 2 |
| contextcore-fox | 1 | 1 | 0 | 0 | 1 | 3 |
| contextcore-coyote | 0 | 0 | 0 | 0 | 0 | 0 |
| contextcore-skills | 2 | 0 | 5 | 0 | 0 | 7 |
| startd8-sdk | 9 | 0 | 9 | 0 | 0 | 18 |
| **Total** | **17** | **10** | **21** | **9** | **14** | **77** |

*wayfinder-demo-retail includes 6 BPA product data files + 3 demo scripts + 6 persona views + 2 runbooks/query docs

### Asset Types Across Ecosystem

- **Grafana Dashboards:** 10 (3 demo + 6 provisioned + 1 Fox)
- **ProjectContext CRDs:** 11 (Online Boutique microservices)
- **Python Examples:** 17 runnable scripts
- **Emission/Integration Scripts:** 21
- **Demo Runbooks:** 2 (concept demo + query cheat sheet)
- **Persona View Cards:** 6 (developer, PM, leader, SRE, compliance, AI agent)
- **Product Catalogs:** 3 JSON files (BPA retail data)
- **Deployment Manifests:** 3 (deploy.sh, deploy.ps1, kind-cluster.yaml)
