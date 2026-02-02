# Demo Scripts

## Files

| File | Purpose |
|------|---------|
| `setup_demo_tasks.py` | Creates ContextCore tasks for each demo phase |
| `run_self_tracking_demo.py` | Executes tasks via Lead Contractor multi-agent workflow |

## Path Resolution

Both scripts auto-detect `DEV_ROOT` from their location:

```
demo/script.py  →  parent: wayfinder-demo-retail/  →  parent: dev/  (DEV_ROOT)
```

Override with `CONTEXTCORE_DEV_ROOT` env var if your repos are elsewhere.

## Usage

See the [project README](../README.md) for full usage instructions.
