# Wayfinder Demo: Retail (Online Boutique)

A self-tracking demo of the [Wayfinder](https://github.com/neilyashinsky/wayfinder) ecosystem using Google's [Online Boutique](https://github.com/GoogleCloudPlatform/microservices-demo) (microservices-demo) as the retail scenario.

## What This Demonstrates

The demo proves Wayfinder's value by **using it to track its own execution**:

- **Spider** (ContextCore) — Tasks tracked as OTel spans, visible in Grafana
- **Rabbit** — Alert automation via Grafana webhooks
- **Fox** — Context enrichment on incoming alerts
- **Coyote** — AI-powered incident investigation
- **Beaver** — LLM cost tracking across the Lead Contractor workflow
- **Squirrel** — Skill discovery with progressive disclosure

## Architecture

```
setup_demo_tasks.py
    │
    ▼
~/.contextcore/state/ecosystem-demo/*.json    (ContextCore task state)
    │
    ▼
run_self_tracking_demo.py
    │
    ├── ContextCoreTaskSource          (load pending tasks)
    ├── ContextCoreTaskRunner          (orchestrate execution)
    └── LeadContractorWorkflow         (multi-agent execution)
         ├── Claude (lead)             (creates execution spec)
         ├── GPT-4o-mini (drafter)     (executes commands)
         └── Claude (reviewer)         (validates output)
    │
    ▼
Tempo (traces) + Mimir (metrics) + Grafana (dashboards)
```

## Quick Start

```bash
# 1. Set environment
export ANTHROPIC_API_KEY=your-key
export CONTEXTCORE_DEV_ROOT=/path/to/dev  # parent dir of all repos

# 2. Check prerequisites
python demo/run_self_tracking_demo.py --check

# 3. Create demo tasks
python demo/setup_demo_tasks.py --clean --verbose

# 4. Dry run
python demo/run_self_tracking_demo.py --dry-run

# 5. Execute
python demo/run_self_tracking_demo.py
```

## Prerequisites

### Required

- Python 3.9+
- [ContextCore](https://github.com/neilyashinsky/ContextCore) installed
- [StartD8 SDK](https://github.com/neilyashinsky/startd8-sdk) installed with `[all]` extras
- `ANTHROPIC_API_KEY` set

### Optional (for full demo)

- contextcore-rabbit, contextcore-fox, contextcore-coyote, contextcore-startd8, contextcore-skills
- Observability stack: Grafana, Tempo, Mimir, Loki

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Claude API key |
| `CONTEXTCORE_DEV_ROOT` | No | Auto-detected | Parent directory containing all repos |
| `STARTD8_SDK_ROOT` | No | — | StartD8 SDK location (for sys.path) |
| `CONTEXTCORE_ROOT` | No | — | ContextCore location (for sys.path) |

## Demo Phases

| Phase | Package | Tasks | Description |
|-------|---------|-------|-------------|
| 1 | Spider | 5 | Core install, data generation, Tempo load, dashboards, live task |
| 2 | Rabbit + Fox | 2 | Package install, webhook test with simulated alert |
| 3 | Coyote | 2 | Package install, sample error investigation |
| 4 | Beaver | 2 | Package install, LLM cost tracking (self-demonstrating) |
| 5 | Squirrel | 1 | Skill discovery, progressive disclosure token savings |
| 6 | All | 1 | Integration summary |

## CLI Options

### setup_demo_tasks.py

```
--phases N [N ...]   Only create tasks for specific phases (1-6)
--dry-run            Show what would be created
--clean              Remove existing demo tasks first
--verbose, -v        Verbose output
--list               List all tasks without creating
```

### run_self_tracking_demo.py

```
--check              Check prerequisites only
--phases N [N ...]   Only run specific phases (1-6)
--dry-run            Show what would be executed
--yes, -y            Skip confirmation prompt
--verbose, -v        Verbose output
--output, -o FILE    Save results to JSON file
--lead-agent SPEC    Lead agent (default: claude-sonnet-4-20250514)
--drafter-agent SPEC Drafter agent (default: gpt-4o-mini)
--max-iterations N   Max review iterations (default: 3)
--setup              Run setup_demo_tasks.py first
```

## Viewing Results

### Grafana

Open http://localhost:3000 (admin/admin) and look for:
- **Project Progress** — Task hierarchy and status
- **Sprint Metrics** — Velocity and cycle time
- **Project Operations** — Runtime correlation

### TraceQL

```
{project.id="ecosystem-demo"}
{task.type="task" && task.status="done"}
{task.phase="2"}
```

## License

Equitable Use License v1.0
