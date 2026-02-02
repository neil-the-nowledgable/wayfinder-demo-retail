#!/usr/bin/env python3
"""
ContextCore Ecosystem Demo: Self-Tracking Task Setup

This script creates ContextCore tasks for each demo phase. The demo tracks
itself using the very system it's demonstrating - true dogfooding.

Usage:
    # Create all demo tasks
    python demo/setup_demo_tasks.py

    # Create tasks for specific phases only
    python demo/setup_demo_tasks.py --phases 1 2 3

    # Dry run - show what would be created
    python demo/setup_demo_tasks.py --dry-run

    # Clean up existing demo tasks first
    python demo/setup_demo_tasks.py --clean

After running this script, execute the demo with:
    python demo/run_self_tracking_demo.py
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any
import uuid

# Demo project configuration
DEMO_PROJECT = "ecosystem-demo"
DEMO_SPRINT = "demo-sprint-1"
STATE_DIR = Path.home() / ".contextcore" / "state" / DEMO_PROJECT

# Derive development root directory
# Priority: CONTEXTCORE_DEV_ROOT env var > auto-detect from script location
_SCRIPT_DIR = Path(__file__).resolve().parent  # demo/
_PROJECT_DIR = _SCRIPT_DIR.parent              # wayfinder-demo-retail/
_DEFAULT_DEV_ROOT = _PROJECT_DIR.parent        # dev/

DEV_ROOT = Path(os.environ.get("CONTEXTCORE_DEV_ROOT", str(_DEFAULT_DEV_ROOT)))

# =============================================================================
# DEMO TASK DEFINITIONS
# =============================================================================
# Each task has:
#   - id: Unique identifier
#   - title: Short description
#   - type: epic, story, task
#   - phase: Demo phase number (for ordering)
#   - depends_on: List of task IDs that must complete first
#   - prompt: Detailed instructions for Lead Contractor workflow
#   - package: Which ecosystem package this demonstrates
# =============================================================================

DEMO_TASKS = [
    # ==========================================================================
    # EPIC: Ecosystem Demo
    # ==========================================================================
    {
        "id": "DEMO-EPIC",
        "title": "ContextCore Ecosystem Demonstration",
        "type": "epic",
        "phase": 0,
        "depends_on": [],
        "package": "all",
        "prompt": """This epic tracks the complete ContextCore ecosystem demonstration.

The demo showcases all 6 packages working together:
- Spider (ContextCore) - Core task tracking
- Rabbit - Alert automation
- Fox - Context enrichment
- Coyote - Incident resolution
- Beaver - LLM observability
- Squirrel - Skills library

Success Criteria:
- All phases complete successfully
- Data visible in Grafana dashboards
- LLM costs tracked and reported
- Demo is self-documenting via its own task spans
"""
    },

    # ==========================================================================
    # PHASE 1: Core Framework (Spider)
    # ==========================================================================
    {
        "id": "DEMO-P1-SETUP",
        "title": "Phase 1: Verify Core Installation",
        "type": "task",
        "phase": 1,
        "depends_on": ["DEMO-EPIC"],
        "package": "spider",
        "prompt": """Verify that ContextCore core is properly installed and configured.

EXECUTION STEPS:
1. Check ContextCore CLI is available:
   ```
   contextcore --version
   ```

2. Check observability stack is running:
   ```
   curl -s http://localhost:3000/api/health  # Grafana
   curl -s http://localhost:3200/ready       # Tempo
   curl -s http://localhost:3100/ready       # Loki
   ```

3. Verify OTLP endpoint is accessible:
   ```
   # Check if port 4317 or 14317 is available
   nc -z localhost 4317 || nc -z localhost 14317
   ```

OUTPUT FORMAT (JSON):
{
    "contextcore_version": "<version>",
    "grafana_healthy": true/false,
    "tempo_healthy": true/false,
    "loki_healthy": true/false,
    "otlp_port": 4317 or 14317,
    "status": "ready" or "issues_found",
    "issues": ["list of any issues"]
}

SUCCESS CRITERIA:
- ContextCore CLI responds to --version
- At least Grafana and Tempo are healthy
- OTLP endpoint is reachable
"""
    },
    {
        "id": "DEMO-P1-GENERATE",
        "title": "Phase 1: Generate Historical Project Data",
        "type": "task",
        "phase": 1,
        "depends_on": ["DEMO-P1-SETUP"],
        "package": "spider",
        "prompt": """Generate 3 months of historical project data for the Online Boutique demo.

EXECUTION STEPS:
1. Navigate to ContextCore directory:
   ```
   cd {DEV_ROOT}/ContextCore
   ```

2. Generate demo data with fixed seed for reproducibility:
   ```
   contextcore demo generate --project online-boutique --seed 42 --months 3
   ```

3. Verify output files exist:
   ```
   ls -la demo_output/
   ```

4. Count generated spans:
   ```
   python3 -c "import json; d=json.load(open('demo_output/demo_spans.json')); print(f'Spans: {len(d)}')"
   ```

OUTPUT FORMAT (JSON):
{
    "spans_generated": <count>,
    "epics": <count>,
    "stories": <count>,
    "tasks": <count>,
    "blockers": <count>,
    "sprints": <count>,
    "output_file": "demo_output/demo_spans.json",
    "file_size_kb": <size>
}

SUCCESS CRITERIA:
- At least 200 spans generated
- demo_spans.json file exists
- File is valid JSON
"""
    },
    {
        "id": "DEMO-P1-LOAD",
        "title": "Phase 1: Load Spans to Tempo",
        "type": "task",
        "phase": 1,
        "depends_on": ["DEMO-P1-GENERATE"],
        "package": "spider",
        "prompt": """Load the generated demo spans into Tempo for visualization.

EXECUTION STEPS:
1. Determine OTLP endpoint (from previous task or detect):
   ```
   OTLP_PORT=$(nc -z localhost 4317 && echo 4317 || echo 14317)
   ```

2. Load spans to Tempo:
   ```
   cd {DEV_ROOT}/ContextCore
   contextcore demo load --file ./demo_output/demo_spans.json --endpoint localhost:$OTLP_PORT --insecure
   ```

3. Verify data in Tempo via Grafana API:
   ```
   curl -s -u admin:admin "http://localhost:3000/api/datasources/proxy/uid/tempo/api/search?tags=project.id%3Donline-boutique&limit=5"
   ```

OUTPUT FORMAT (JSON):
{
    "spans_loaded": <count>,
    "otlp_endpoint": "localhost:<port>",
    "tempo_query_success": true/false,
    "traces_found": <count>,
    "sample_trace_ids": ["<id1>", "<id2>"]
}

SUCCESS CRITERIA:
- Spans loaded without error
- Tempo query returns results
- At least 1 trace found with project.id=online-boutique
"""
    },
    {
        "id": "DEMO-P1-DASHBOARDS",
        "title": "Phase 1: Import Grafana Dashboards",
        "type": "task",
        "phase": 1,
        "depends_on": ["DEMO-P1-LOAD"],
        "package": "spider",
        "prompt": """Import all ContextCore Grafana dashboards for visualization.

EXECUTION STEPS:
1. Import dashboards from demo directory:
   ```
   cd {DEV_ROOT}/ContextCore
   for d in ./demo/dashboards/*.json; do
       echo "Importing $(basename $d)..."
       curl -s -X POST -H "Content-Type: application/json" -u admin:admin \\
           -d "{\\"dashboard\\": $(cat \\"$d\\"), \\"overwrite\\": true}" \\
           http://localhost:3000/api/dashboards/db
   done
   ```

2. Import dashboards from provisioning directory:
   ```
   for d in ./grafana/provisioning/dashboards/json/*.json; do
       echo "Importing $(basename $d)..."
       curl -s -X POST -H "Content-Type: application/json" -u admin:admin \\
           -d "{\\"dashboard\\": $(cat \\"$d\\"), \\"overwrite\\": true}" \\
           http://localhost:3000/api/dashboards/db
   done
   ```

3. List imported dashboards:
   ```
   curl -s -u admin:admin "http://localhost:3000/api/search?type=dash-db" | jq '.[].title'
   ```

OUTPUT FORMAT (JSON):
{
    "dashboards_imported": <count>,
    "dashboard_names": ["Project Portfolio Overview", "Sprint Metrics", ...],
    "import_errors": []
}

SUCCESS CRITERIA:
- At least 3 dashboards imported
- No import errors
- "Project Portfolio Overview" dashboard exists
"""
    },
    {
        "id": "DEMO-P1-LIVE",
        "title": "Phase 1: Create Live Task",
        "type": "task",
        "phase": 1,
        "depends_on": ["DEMO-P1-DASHBOARDS"],
        "package": "spider",
        "prompt": """Create a live task to demonstrate real-time task tracking.

EXECUTION STEPS:
1. Start a new task:
   ```
   contextcore task start --id DEMO-LIVE-001 --title "Live demo task created by Lead Contractor" \\
       --type task --project online-boutique --status todo
   ```

2. Wait 2 seconds, then update to in_progress:
   ```
   sleep 2
   contextcore task update --id DEMO-LIVE-001 --status in_progress
   ```

3. Wait 2 seconds, then complete:
   ```
   sleep 2
   contextcore task complete --id DEMO-LIVE-001
   ```

4. Verify task span in Tempo:
   ```
   curl -s -u admin:admin "http://localhost:3000/api/datasources/proxy/uid/tempo/api/search?tags=task.id%3DDEMO-LIVE-001&limit=1"
   ```

OUTPUT FORMAT (JSON):
{
    "task_id": "DEMO-LIVE-001",
    "lifecycle_events": ["created", "in_progress", "completed"],
    "duration_seconds": <duration>,
    "span_found_in_tempo": true/false,
    "trace_id": "<trace_id>"
}

SUCCESS CRITERIA:
- Task progresses through all states
- Span visible in Tempo
- Total duration > 4 seconds (proves real transitions)
"""
    },

    # ==========================================================================
    # PHASE 2: Alert Pipeline (Rabbit + Fox)
    # ==========================================================================
    {
        "id": "DEMO-P2-INSTALL",
        "title": "Phase 2: Install Alert Packages",
        "type": "task",
        "phase": 2,
        "depends_on": ["DEMO-P1-LIVE"],
        "package": "rabbit",
        "prompt": """Verify Rabbit and Fox packages are installed.

EXECUTION STEPS:
1. Check Rabbit installation:
   ```
   python3 -c "import contextcore_rabbit; print(f'Rabbit version: {contextcore_rabbit.__version__}')"
   ```

   If not installed:
   ```
   pip3 install -e {DEV_ROOT}/contextcore-rabbit[otel,dev]
   ```

2. Check Fox installation:
   ```
   python3 -c "import contextcore_fox; print('Fox installed')"
   ```

   If not installed:
   ```
   pip3 install -e {DEV_ROOT}/contextcore-fox[dev]
   ```

3. Verify CLI commands:
   ```
   contextcore-rabbit --help > /dev/null && echo "Rabbit CLI OK"
   contextcore-fox --help > /dev/null && echo "Fox CLI OK"
   ```

OUTPUT FORMAT (JSON):
{
    "rabbit_installed": true/false,
    "rabbit_version": "<version>",
    "fox_installed": true/false,
    "rabbit_cli": true/false,
    "fox_cli": true/false
}

SUCCESS CRITERIA:
- Both packages importable
- Both CLI commands work
"""
    },
    {
        "id": "DEMO-P2-WEBHOOK",
        "title": "Phase 2: Test Alert Webhook",
        "type": "task",
        "phase": 2,
        "depends_on": ["DEMO-P2-INSTALL"],
        "package": "fox",
        "prompt": """Test the Fox webhook server with a simulated alert.

EXECUTION STEPS:
1. Start Fox webhook server in background:
   ```
   cd {DEV_ROOT}/contextcore-fox
   CONTEXTCORE_FOX_CONTEXTCORE_ENABLED=true timeout 30 contextcore-fox serve --port 8085 &
   FOX_PID=$!
   sleep 3
   ```

2. Send test alert:
   ```
   curl -s -X POST http://localhost:8085/webhook/grafana \\
       -H "Content-Type: application/json" \\
       -d '{
           "receiver": "ecosystem-demo",
           "status": "firing",
           "alerts": [{
               "status": "firing",
               "labels": {
                   "alertname": "DemoPhase2Alert",
                   "service": "checkoutservice",
                   "project_id": "online-boutique",
                   "severity": "warning"
               },
               "annotations": {
                   "summary": "Demo alert from Lead Contractor workflow"
               }
           }]
       }'
   ```

3. Check Fox logs for processing confirmation

4. Stop Fox server:
   ```
   kill $FOX_PID 2>/dev/null || true
   ```

OUTPUT FORMAT (JSON):
{
    "fox_started": true/false,
    "webhook_response_code": 200,
    "alert_processed": true/false,
    "enrichment_applied": true/false,
    "fox_stopped": true/false
}

SUCCESS CRITERIA:
- Fox server starts successfully
- Webhook returns 200
- Alert is processed (visible in logs)
"""
    },

    # ==========================================================================
    # PHASE 3: Incident Resolution (Coyote)
    # ==========================================================================
    {
        "id": "DEMO-P3-INSTALL",
        "title": "Phase 3: Verify Coyote Installation",
        "type": "task",
        "phase": 3,
        "depends_on": ["DEMO-P2-WEBHOOK"],
        "package": "coyote",
        "prompt": """Verify Coyote incident resolution package is installed.

EXECUTION STEPS:
1. Check Coyote installation:
   ```
   python3 -c "import contextcore_coyote; print('Coyote installed')"
   ```

   If not installed:
   ```
   pip3 install -e {DEV_ROOT}/contextcore-coyote[all]
   ```

2. Verify CLI:
   ```
   coyote --help > /dev/null && echo "Coyote CLI OK"
   ```

3. Check API key availability:
   ```
   [ -n "$ANTHROPIC_API_KEY" ] && echo "API key available" || echo "API key missing"
   ```

OUTPUT FORMAT (JSON):
{
    "coyote_installed": true/false,
    "coyote_cli": true/false,
    "api_key_available": true/false
}

SUCCESS CRITERIA:
- Coyote package importable
- CLI command works
- API key is set (or note if missing)
"""
    },
    {
        "id": "DEMO-P3-INVESTIGATE",
        "title": "Phase 3: Run Sample Investigation",
        "type": "task",
        "phase": 3,
        "depends_on": ["DEMO-P3-INSTALL"],
        "package": "coyote",
        "prompt": """Run a sample error investigation using Coyote (if API key available).

EXECUTION STEPS:
1. Create sample error log:
   ```
   cat > /tmp/demo_error.log << 'EOF'
2026-01-23T14:32:15Z ERROR [checkoutservice] NullPointerException in CartHandler
    at CartHandler.processCheckout(CartHandler.java:142)
Caused by: Cart items list is null for user_id=usr_12345
EOF
   ```

2. If ANTHROPIC_API_KEY is set, run investigation:
   ```
   if [ -n "$ANTHROPIC_API_KEY" ]; then
       coyote investigate --log-file /tmp/demo_error.log --project online-boutique 2>&1 | head -50
   else
       echo "Skipping investigation - no API key"
   fi
   ```

3. Check for investigation output:
   ```
   [ -f investigation_report.md ] && echo "Report generated" || echo "No report"
   ```

OUTPUT FORMAT (JSON):
{
    "error_log_created": true,
    "investigation_run": true/false,
    "api_key_available": true/false,
    "report_generated": true/false,
    "skip_reason": "no API key" (if skipped)
}

SUCCESS CRITERIA:
- Error log file created
- If API key available: investigation runs
- If no API key: gracefully skipped with note
"""
    },

    # ==========================================================================
    # PHASE 4: LLM Observability (Beaver)
    # ==========================================================================
    {
        "id": "DEMO-P4-INSTALL",
        "title": "Phase 4: Verify Beaver Installation",
        "type": "task",
        "phase": 4,
        "depends_on": ["DEMO-P3-INVESTIGATE"],
        "package": "beaver",
        "prompt": """Verify Beaver (contextcore-startd8) LLM observability package.

EXECUTION STEPS:
1. Check Beaver installation:
   ```
   python3 -c "from contextcore_startd8 import TrackedClaudeAgent, ContextCoreCostTracker; print('Beaver installed')"
   ```

   If not installed:
   ```
   pip3 install -e {DEV_ROOT}/contextcore-startd8[dev]
   ```

2. Verify components:
   ```
   python3 -c "
from contextcore_startd8 import TrackedClaudeAgent, ContextCoreCostTracker, AgentInsightBridge
print('TrackedClaudeAgent: OK')
print('ContextCoreCostTracker: OK')
print('AgentInsightBridge: OK')
"
   ```

OUTPUT FORMAT (JSON):
{
    "beaver_installed": true/false,
    "tracked_agent": true/false,
    "cost_tracker": true/false,
    "insight_bridge": true/false
}

SUCCESS CRITERIA:
- All Beaver components importable
"""
    },
    {
        "id": "DEMO-P4-TRACK",
        "title": "Phase 4: Demonstrate LLM Cost Tracking",
        "type": "task",
        "phase": 4,
        "depends_on": ["DEMO-P4-INSTALL"],
        "package": "beaver",
        "prompt": """Demonstrate LLM cost tracking with Beaver (this task itself is tracked!).

NOTE: This task is being executed by the Lead Contractor workflow, which means
the LLM calls for THIS task are already being tracked via Beaver integration.

EXECUTION STEPS:
1. Report that this execution demonstrates Beaver:
   ```
   echo "This task execution is tracked via Beaver integration"
   echo "The Lead Contractor workflow uses TrackedClaudeAgent"
   echo "Cost metrics are being emitted to Mimir"
   ```

2. Check if cost metrics endpoint is configured:
   ```
   curl -s "http://localhost:9009/api/v1/query?query=startd8_cost_total" 2>/dev/null | head -5 || echo "Mimir query not available"
   ```

OUTPUT FORMAT (JSON):
{
    "self_tracking_active": true,
    "note": "This task execution demonstrates Beaver - the Lead Contractor workflow is using TrackedClaudeAgent",
    "mimir_available": true/false,
    "workflow_cost_tracked": true
}

SUCCESS CRITERIA:
- Acknowledge that this execution is self-demonstrating
- Note that Lead Contractor uses Beaver for tracking
"""
    },

    # ==========================================================================
    # PHASE 5: Skills Library (Squirrel)
    # ==========================================================================
    {
        "id": "DEMO-P5-SKILLS",
        "title": "Phase 5: Demonstrate Skills Library",
        "type": "task",
        "phase": 5,
        "depends_on": ["DEMO-P4-TRACK"],
        "package": "squirrel",
        "prompt": """Demonstrate the Squirrel skills library with progressive disclosure.

EXECUTION STEPS:
1. Check skills directory exists:
   ```
   ls {DEV_ROOT}/contextcore-skills/skills/
   ```

2. Measure token efficiency:
   ```
   MANIFEST="{DEV_ROOT}/contextcore-skills/skills/dev-tour-guide/MANIFEST.yaml"
   FULL="{DEV_ROOT}/contextcore-skills/skills/dev-tour-guide/SKILL.md"

   MANIFEST_SIZE=$(wc -c < "$MANIFEST" 2>/dev/null || echo 0)
   FULL_SIZE=$(wc -c < "$FULL" 2>/dev/null || echo 0)

   MANIFEST_TOKENS=$((MANIFEST_SIZE / 4))
   FULL_TOKENS=$((FULL_SIZE / 4))

   if [ $FULL_TOKENS -gt 0 ]; then
       SAVINGS=$(( (FULL_TOKENS - MANIFEST_TOKENS) * 100 / FULL_TOKENS ))
   else
       SAVINGS=0
   fi

   echo "MANIFEST tokens: $MANIFEST_TOKENS"
   echo "Full SKILL tokens: $FULL_TOKENS"
   echo "Savings: $SAVINGS%"
   ```

3. List available skills:
   ```
   for skill in {DEV_ROOT}/contextcore-skills/skills/*/; do
       echo "- $(basename $skill)"
   done
   ```

OUTPUT FORMAT (JSON):
{
    "skills_found": ["dev-tour-guide", "capability-value-promoter"],
    "manifest_tokens": <count>,
    "full_skill_tokens": <count>,
    "token_savings_percent": <percent>,
    "progressive_disclosure_works": true
}

SUCCESS CRITERIA:
- At least 1 skill found
- Token savings > 80%
- Progressive disclosure pattern demonstrated
"""
    },

    # ==========================================================================
    # PHASE 6: Integration Summary
    # ==========================================================================
    {
        "id": "DEMO-P6-SUMMARY",
        "title": "Phase 6: Generate Demo Summary",
        "type": "task",
        "phase": 6,
        "depends_on": ["DEMO-P5-SKILLS"],
        "package": "all",
        "prompt": """Generate a summary of the ecosystem demo execution.

EXECUTION STEPS:
1. Count tasks in this demo project:
   ```
   ls ~/.contextcore/state/ecosystem-demo/*.json 2>/dev/null | wc -l
   ```

2. Check Grafana for demo data:
   ```
   curl -s -u admin:admin "http://localhost:3000/api/search?query=ContextCore" | jq '.[].title' 2>/dev/null || echo "Query failed"
   ```

3. Summarize what was demonstrated:
   - Phase 1 (Spider): Task tracking, historical data, dashboards
   - Phase 2 (Rabbit+Fox): Alert pipeline
   - Phase 3 (Coyote): Incident investigation
   - Phase 4 (Beaver): LLM cost tracking (self-demonstrating)
   - Phase 5 (Squirrel): Skills library

4. Note the self-tracking nature:
   ```
   echo "This demo tracked itself using ContextCore tasks"
   echo "Executed via Lead Contractor multi-agent workflow"
   echo "LLM costs tracked via Beaver integration"
   ```

OUTPUT FORMAT (JSON):
{
    "demo_complete": true,
    "phases_executed": 6,
    "packages_demonstrated": ["spider", "rabbit", "fox", "coyote", "beaver", "squirrel"],
    "self_tracking": true,
    "lead_contractor_workflow": true,
    "dashboards_available": ["list of dashboard names"],
    "grafana_url": "http://localhost:3000",
    "summary": "ContextCore ecosystem demo completed successfully. All 6 packages demonstrated. Demo was self-tracking via ContextCore tasks executed by Lead Contractor workflow."
}

SUCCESS CRITERIA:
- All phases completed
- Summary generated
- Self-tracking nature acknowledged
"""
    }
]


def generate_trace_id() -> str:
    """Generate a valid 32-character trace ID."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generate a valid 16-character span ID."""
    return uuid.uuid4().hex[:16]


def create_task_json(task: Dict[str, Any], parent_span_id: str = None) -> Dict[str, Any]:
    """Create a ContextCore task state JSON structure."""
    now = datetime.now(timezone.utc).isoformat()
    trace_id = generate_trace_id()
    span_id = generate_span_id()

    # Resolve {DEV_ROOT} placeholder in prompt
    resolved_prompt = task["prompt"].replace("{DEV_ROOT}", str(DEV_ROOT))

    return {
        "task_id": task["id"],
        "span_name": f"task:{task['id']}",
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "start_time": now,
        "end_time": None,
        "attributes": {
            "task.id": task["id"],
            "task.title": task["title"],
            "task.type": task["type"],
            "task.status": "todo",
            "task.priority": "high" if task["phase"] <= 2 else "medium",
            "task.prompt": resolved_prompt,
            "task.depends_on": task["depends_on"],
            "task.phase": task["phase"],
            "task.package": task["package"],
            "project.id": DEMO_PROJECT,
            "sprint.id": DEMO_SPRINT,
        },
        "events": [],
        "status": "UNSET",
        "status_description": None,
        "schema_version": 2,
        "project_id": DEMO_PROJECT,
    }


def setup_demo_tasks(
    phases: List[int] = None,
    dry_run: bool = False,
    clean: bool = False,
    verbose: bool = False
) -> Dict[str, Any]:
    """Create demo tasks in ContextCore state directory."""

    results = {
        "tasks_created": [],
        "tasks_skipped": [],
        "errors": [],
        "state_dir": str(STATE_DIR),
    }

    # Filter tasks by phase if specified
    tasks_to_create = DEMO_TASKS
    if phases:
        tasks_to_create = [t for t in DEMO_TASKS if t["phase"] in phases or t["phase"] == 0]

    if verbose:
        print(f"Demo project: {DEMO_PROJECT}")
        print(f"State directory: {STATE_DIR}")
        print(f"Tasks to create: {len(tasks_to_create)}")
        print()

    # Clean existing tasks if requested
    if clean and STATE_DIR.exists():
        if dry_run:
            print(f"[DRY RUN] Would remove: {STATE_DIR}")
        else:
            shutil.rmtree(STATE_DIR)
            print(f"Cleaned: {STATE_DIR}")

    # Create state directory
    if not dry_run:
        STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Track epic span ID for parent linking
    epic_span_id = None

    # Create each task
    for task in tasks_to_create:
        task_file = STATE_DIR / f"{task['id']}.json"

        if task_file.exists() and not clean:
            results["tasks_skipped"].append(task["id"])
            if verbose:
                print(f"⏭️  Skipped (exists): {task['id']}")
            continue

        # Use epic span as parent for non-epic tasks
        parent_span = epic_span_id if task["type"] != "epic" else None

        task_json = create_task_json(task, parent_span)

        # Track epic span ID
        if task["type"] == "epic":
            epic_span_id = task_json["span_id"]

        if dry_run:
            print(f"[DRY RUN] Would create: {task_file.name}")
            print(f"          Title: {task['title']}")
            print(f"          Phase: {task['phase']}, Package: {task['package']}")
            if task["depends_on"]:
                print(f"          Depends on: {', '.join(task['depends_on'])}")
            print()
        else:
            with open(task_file, 'w') as f:
                json.dump(task_json, f, indent=2)
            results["tasks_created"].append(task["id"])
            if verbose:
                print(f"✅ Created: {task['id']} - {task['title']}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Set up ContextCore tasks for ecosystem demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--phases",
        type=int,
        nargs="+",
        help="Only create tasks for specific phases (1-6)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without creating"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove existing demo tasks before creating"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all demo tasks without creating"
    )

    args = parser.parse_args()

    if args.list:
        print("=" * 70)
        print("CONTEXTCORE ECOSYSTEM DEMO TASKS")
        print("=" * 70)
        print()
        for task in DEMO_TASKS:
            deps = f" (depends: {', '.join(task['depends_on'])})" if task['depends_on'] else ""
            print(f"Phase {task['phase']}: [{task['package'].upper()}] {task['id']}")
            print(f"         {task['title']}{deps}")
            print()
        return

    print("=" * 70)
    print("CONTEXTCORE ECOSYSTEM DEMO: Task Setup")
    print("=" * 70)
    print()

    results = setup_demo_tasks(
        phases=args.phases,
        dry_run=args.dry_run,
        clean=args.clean,
        verbose=args.verbose or args.dry_run
    )

    print()
    print("-" * 70)
    print(f"Tasks created: {len(results['tasks_created'])}")
    print(f"Tasks skipped: {len(results['tasks_skipped'])}")
    if results['errors']:
        print(f"Errors: {len(results['errors'])}")
    print(f"State directory: {results['state_dir']}")
    print()

    if not args.dry_run and results['tasks_created']:
        print("Next step: Run the demo with:")
        print(f"  python demo/run_self_tracking_demo.py")
        print()
        print("Or execute via StartD8 SDK directly:")
        print(f"  python $STARTD8_SDK_ROOT/scripts/run_contextcore_workflow.py \\")
        print(f"      --from-contextcore --project-id {DEMO_PROJECT} --yes")


if __name__ == "__main__":
    main()
