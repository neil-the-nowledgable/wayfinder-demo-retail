#!/usr/bin/env python3
"""
ContextCore Ecosystem Demo: Self-Tracking Execution

This script runs the ecosystem demo using the Lead Contractor workflow.
The demo tracks itself using ContextCore tasks - true dogfooding.

Architecture:
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SELF-TRACKING DEMO EXECUTION                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. setup_demo_tasks.py creates tasks in ~/.contextcore/state/ecosystem-demo│
│                                                                              │
│  2. This script (run_self_tracking_demo.py) executes them via:              │
│     - ContextCoreTaskSource: Loads pending tasks                            │
│     - ContextCoreTaskRunner: Orchestrates execution                         │
│     - LeadContractorWorkflow: Multi-agent execution                         │
│       • Claude (lead): Creates execution spec                               │
│       • GPT-4o-mini (drafter): Executes commands                            │
│       • Claude (reviewer): Validates output                                  │
│                                                                              │
│  3. Beaver integration tracks LLM costs automatically                        │
│                                                                              │
│  4. Results visible in Grafana dashboards                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

Usage:
    # First, set up the demo tasks
    python demo/setup_demo_tasks.py --clean

    # Then run the demo
    python demo/run_self_tracking_demo.py

    # Or run specific phases only
    python demo/run_self_tracking_demo.py --phases 1 2

    # Dry run to see what would be executed
    python demo/run_self_tracking_demo.py --dry-run

Prerequisites:
    - ContextCore installed: pip install -e /path/to/ContextCore
    - StartD8 SDK installed: pip install -e /path/to/startd8-sdk[all]
    - ANTHROPIC_API_KEY set
    - Observability stack running (Grafana, Tempo, etc.)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add paths for development (prefer environment variables if set)
STARTD8_ROOT = os.environ.get("STARTD8_SDK_ROOT", "")
CONTEXTCORE_ROOT = os.environ.get("CONTEXTCORE_ROOT", "")

STARTD8_PATH = Path(STARTD8_ROOT) / "src" if STARTD8_ROOT else None
CONTEXTCORE_PATH = Path(CONTEXTCORE_ROOT) / "src" if CONTEXTCORE_ROOT else None

if STARTD8_PATH and STARTD8_PATH.exists():
    sys.path.insert(0, str(STARTD8_PATH))
if CONTEXTCORE_PATH and CONTEXTCORE_PATH.exists():
    sys.path.insert(0, str(CONTEXTCORE_PATH))

# Demo configuration
DEMO_PROJECT = "ecosystem-demo"
DEMO_SPRINT = "demo-sprint-1"


def check_prerequisites() -> Dict[str, Any]:
    """Check that all prerequisites are met."""
    results = {
        "contextcore": False,
        "startd8": False,
        "anthropic_key": False,
        "tasks_exist": False,
        "ready": False,
        "issues": []
    }

    # Check ContextCore
    try:
        import contextcore
        results["contextcore"] = True
    except ImportError:
        results["issues"].append("ContextCore not installed: pip install -e /path/to/ContextCore")

    # Check StartD8 SDK
    try:
        from startd8.integrations.contextcore import ContextCoreTaskSource, ContextCoreTaskRunner
        from startd8.workflows.builtin import LeadContractorWorkflow
        results["startd8"] = True
    except ImportError as e:
        results["issues"].append(f"StartD8 SDK not installed: {e}")

    # Check API key
    if os.environ.get("ANTHROPIC_API_KEY"):
        results["anthropic_key"] = True
    else:
        results["issues"].append("ANTHROPIC_API_KEY not set")

    # Check tasks exist
    state_dir = Path.home() / ".contextcore" / "state" / DEMO_PROJECT
    if state_dir.exists():
        task_files = list(state_dir.glob("*.json"))
        results["tasks_exist"] = len(task_files) > 0
        results["task_count"] = len(task_files)
        if not results["tasks_exist"]:
            results["issues"].append("No demo tasks found. Run: python demo/setup_demo_tasks.py")
    else:
        results["issues"].append(f"Demo project not found: {state_dir}")
        results["issues"].append("Run: python demo/setup_demo_tasks.py")

    results["ready"] = all([
        results["contextcore"],
        results["startd8"],
        results["anthropic_key"],
        results["tasks_exist"]
    ])

    return results


def run_demo(
    phases: Optional[List[int]] = None,
    dry_run: bool = False,
    verbose: bool = False,
    yes: bool = False,
    output_file: Optional[str] = None,
    lead_agent: str = "anthropic:claude-sonnet-4-20250514",
    drafter_agent: str = "openai:gpt-4o-mini",
    max_iterations: int = 3,
) -> Dict[str, Any]:
    """Run the self-tracking ecosystem demo."""

    # Import here to allow prerequisite check to work without full deps
    from startd8.integrations.contextcore import (
        ContextCoreTaskSource,
        ContextCoreTaskRunner,
    )
    from startd8.workflows.builtin import LeadContractorWorkflow

    print("=" * 70)
    print("CONTEXTCORE ECOSYSTEM DEMO: Self-Tracking Execution")
    print("=" * 70)
    print()
    print("This demo demonstrates the ContextCore ecosystem by USING it.")
    print("Each phase is a ContextCore task, executed via Lead Contractor workflow.")
    print()

    # Load tasks from ContextCore
    status_filter = ["todo", "backlog"]
    source = ContextCoreTaskSource(
        project_id=DEMO_PROJECT,
        status_filter=status_filter,
    )

    tasks = source.get_pending_tasks()

    if not tasks:
        print(f"No pending tasks found in project: {DEMO_PROJECT}")
        print("Run: python demo/setup_demo_tasks.py")
        return {"error": "No tasks found"}

    # Filter by phase if specified
    if phases:
        original_count = len(tasks)
        tasks = [t for t in tasks if t.context.get("task.phase") in phases or t.context.get("task.phase") == 0]
        print(f"Filtered to phases {phases}: {len(tasks)}/{original_count} tasks")

    # Display tasks
    print(f"Found {len(tasks)} pending tasks:")
    print("-" * 70)
    for task in tasks:
        phase = task.context.get("task.phase", "?")
        package = task.context.get("task.package", "?")
        deps = f" (deps: {', '.join(task.depends_on)})" if task.depends_on else ""
        print(f"  Phase {phase} [{package}] {task.task_id}: {task.title}{deps}")
    print("-" * 70)
    print()

    # Dry run mode
    if dry_run:
        print("[DRY RUN] Would execute the above tasks using Lead Contractor workflow")
        print()
        print("Workflow configuration:")
        print(f"  Lead agent: {lead_agent}")
        print(f"  Drafter agent: {drafter_agent}")
        print(f"  Max iterations: {max_iterations}")
        print()
        print("To execute, remove --dry-run flag")
        return {
            "dry_run": True,
            "tasks": [t.task_id for t in tasks],
        }

    # Confirm if not forced
    if not yes:
        response = input(f"Execute {len(tasks)} tasks via Lead Contractor workflow? [y/N] ")
        if response.lower() not in ("y", "yes"):
            print("Aborted")
            return {"aborted": True}

    # Set up workflow
    workflow = LeadContractorWorkflow()

    # Inject agent configuration into tasks
    for task in tasks:
        config = task.to_workflow_config()
        config["lead_agent"] = lead_agent
        config["drafter_agent"] = drafter_agent
        config["max_iterations"] = max_iterations
        task.config = config

    # Create runner
    runner = ContextCoreTaskRunner(
        project_id=DEMO_PROJECT,
        sprint_id=DEMO_SPRINT,
        emit_insights=True,
    )

    # Progress callback
    def on_task_complete(task_id: str, result):
        if result.success:
            status = "✅"
            cost = f"${result.result.metrics.total_cost:.4f}" if result.result else ""
            msg = cost or "Success"
        elif result.skipped:
            status = "⏭️ "
            msg = result.skip_reason or "Skipped"
        else:
            status = "❌"
            msg = result.error or "Failed"
        print(f"  {status} {task_id}: {msg}")

    print()
    print("=" * 70)
    print("EXECUTING DEMO")
    print("=" * 70)
    print(f"Project: {DEMO_PROJECT}")
    print(f"Sprint: {DEMO_SPRINT}")
    print(f"Lead Agent: {lead_agent}")
    print(f"Drafter Agent: {drafter_agent}")
    print("-" * 70)
    print()

    start_time = datetime.now()

    # Run all tasks
    results = runner.run_all(
        tasks=tasks,
        workflow=workflow,
        on_task_complete=on_task_complete,
        stop_on_failure=False,  # Continue even if a task fails
    )

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Get summary
    summary = runner.get_summary()

    # Print results
    print()
    print("=" * 70)
    print("DEMO EXECUTION SUMMARY")
    print("=" * 70)
    print(f"Project: {summary['project_id']}")
    print(f"Sprint: {summary['sprint_id']}")
    print(f"Duration: {duration:.1f} seconds")
    print()
    print(f"Tasks Executed: {summary['total_tasks']}")
    print(f"  ✅ Succeeded: {summary['succeeded']}")
    print(f"  ❌ Failed: {summary['failed']}")
    print(f"  ⏭️  Skipped: {summary['skipped']}")
    print()
    print(f"Success Rate: {summary['success_rate']:.1f}%")
    print(f"Total LLM Cost: ${summary['total_cost']:.4f}")
    print(f"Total Tokens: {summary.get('total_tokens', 'N/A')}")
    print("=" * 70)
    print()
    print("🎉 Demo complete! View results in Grafana:")
    print("   http://localhost:3000")
    print()
    print("TraceQL queries to explore:")
    print(f"   {{project.id=\"{DEMO_PROJECT}\"}}")
    print("   {task.type=\"task\" && task.status=\"done\"}")
    print()

    # Save results if requested
    if output_file:
        output_data = {
            "demo": "contextcore-ecosystem",
            "project_id": DEMO_PROJECT,
            "sprint_id": DEMO_SPRINT,
            "execution_time": str(datetime.now()),
            "duration_seconds": duration,
            "summary": summary,
            "agents": {
                "lead": lead_agent,
                "drafter": drafter_agent,
            },
            "results": {
                task_id: {
                    "success": r.success,
                    "skipped": r.skipped,
                    "error": r.error,
                    "skip_reason": r.skip_reason,
                    "metrics": r.result.to_dict()["metrics"] if r.result else None,
                }
                for task_id, r in results.items()
            }
        }
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        print(f"Results saved to: {output_file}")

    return {
        "success": summary['success_rate'] == 100,
        "summary": summary,
        "duration_seconds": duration,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run the self-tracking ContextCore ecosystem demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--phases",
        type=int,
        nargs="+",
        help="Only run specific phases (1-6)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without running"
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--output", "-o",
        help="Save results to JSON file"
    )
    parser.add_argument(
        "--lead-agent",
        default="anthropic:claude-sonnet-4-20250514",
        help="Lead agent spec (default: claude-sonnet-4-20250514)"
    )
    parser.add_argument(
        "--drafter-agent",
        default="openai:gpt-4o-mini",
        help="Drafter agent spec (default: gpt-4o-mini)"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum review iterations (default: 3)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check prerequisites only"
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run setup_demo_tasks.py first"
    )

    args = parser.parse_args()

    # Check prerequisites
    prereqs = check_prerequisites()

    if args.check or not prereqs["ready"]:
        print("=" * 70)
        print("PREREQUISITE CHECK")
        print("=" * 70)
        print(f"ContextCore installed: {'✅' if prereqs['contextcore'] else '❌'}")
        print(f"StartD8 SDK installed: {'✅' if prereqs['startd8'] else '❌'}")
        print(f"ANTHROPIC_API_KEY set: {'✅' if prereqs['anthropic_key'] else '❌'}")
        print(f"Demo tasks exist: {'✅' if prereqs['tasks_exist'] else '❌'}", end="")
        if prereqs.get('task_count'):
            print(f" ({prereqs['task_count']} tasks)")
        else:
            print()
        print()

        if prereqs["issues"]:
            print("Issues to resolve:")
            for issue in prereqs["issues"]:
                print(f"  ❌ {issue}")
            print()

        if args.check:
            return

        if not prereqs["ready"]:
            print("Cannot proceed until prerequisites are met.")
            sys.exit(1)

    # Run setup if requested
    if args.setup:
        print("Running setup_demo_tasks.py...")
        setup_script = Path(__file__).parent / "setup_demo_tasks.py"
        os.system(f"python3 {setup_script} --clean --verbose")
        print()

    # Run the demo
    try:
        result = run_demo(
            phases=args.phases,
            dry_run=args.dry_run,
            verbose=args.verbose,
            yes=args.yes,
            output_file=args.output,
            lead_agent=args.lead_agent,
            drafter_agent=args.drafter_agent,
            max_iterations=args.max_iterations,
        )

        if result.get("error") or result.get("aborted"):
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
