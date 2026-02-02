# CLAUDE.md

This file provides guidance to Claude Code for this repository.

## Project Overview

**wayfinder-demo-retail** is a self-tracking demo of the Wayfinder ecosystem (ContextCore reference implementation) using Google's Online Boutique (microservices-demo) as the retail scenario. The demo proves Wayfinder's value by using it to track its own execution.

This repo is a **consumer** of Wayfinder packages — it does not modify them.

## Relationship to Other Repos

| Repo | Role | This demo's relationship |
|------|------|--------------------------|
| `contextcore-spec` | Metadata standard | Implements the spec |
| `wayfinder` / `ContextCore` | Reference implementation | Depends on (imports) |
| `contextcore-rabbit` | Alert automation | Optional dependency |
| `contextcore-fox` | Context enrichment | Optional dependency |
| `contextcore-coyote` | Incident resolution | Optional dependency |
| `contextcore-startd8` | LLM abstraction (Beaver) | Depends on (Lead Contractor) |
| `contextcore-skills` | Skills library (Squirrel) | Optional dependency |
| `contextcore-dot-me` | Website | Separate; links to this demo |
| `startd8-sdk` | Multi-agent SDK | Depends on (workflow engine) |

## Commands

```bash
# Check prerequisites
python demo/run_self_tracking_demo.py --check

# Create demo tasks in ContextCore state
python demo/setup_demo_tasks.py --clean --verbose

# List tasks without creating
python demo/setup_demo_tasks.py --list

# Dry run
python demo/run_self_tracking_demo.py --dry-run

# Execute
python demo/run_self_tracking_demo.py

# Execute specific phases
python demo/run_self_tracking_demo.py --phases 1 2
```

## Environment Variables

```bash
# Required
ANTHROPIC_API_KEY          # For Lead Contractor workflow

# Optional (auto-detected from repo location)
CONTEXTCORE_DEV_ROOT       # Parent directory containing all repos (default: ../  from repo root)
STARTD8_SDK_ROOT           # StartD8 SDK location
CONTEXTCORE_ROOT           # ContextCore location
```

## Project Structure

```
wayfinder-demo-retail/
├── CLAUDE.md                          # This file
├── README.md                          # Project overview and usage
├── .gitignore                         # Standard exclusions
└── demo/
    ├── setup_demo_tasks.py            # Creates ContextCore tasks for demo phases
    └── run_self_tracking_demo.py      # Executes via Lead Contractor workflow
```

## Architecture

The demo is self-tracking: it uses ContextCore tasks executed via the StartD8 Lead Contractor workflow, with LLM costs tracked through Beaver, all visible in Grafana.

```
setup_demo_tasks.py → ~/.contextcore/state/ecosystem-demo/*.json
                                    ↓
run_self_tracking_demo.py → ContextCoreTaskSource → LeadContractorWorkflow
                                    ↓
                            Claude (lead) + GPT-4o-mini (drafter)
                                    ↓
                            Tempo (spans) + Mimir (metrics) + Grafana (dashboards)
```

## Conventions

- Task IDs use `DEMO-P{phase}-{name}` pattern (e.g., `DEMO-P1-SETUP`)
- Paths use `{DEV_ROOT}` placeholder resolved at runtime from env var or auto-detection
- Demo project ID: `ecosystem-demo`
- Demo sprint ID: `demo-sprint-1`

## Offline Task Store

The building plan for this demo is tracked in the Wayfinder offline task store:
`/Users/neilyashinsky/Documents/pers/persOS/context-core/wayfinder/`
