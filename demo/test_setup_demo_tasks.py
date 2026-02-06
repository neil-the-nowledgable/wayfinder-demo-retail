#!/usr/bin/env python3
"""
Unit tests for setup_demo_tasks.py

Tests cover:
- Decomposed task generation (per-service tasks)
- Batched task generation (per-tier tasks)
- Dependency ordering between tiers
- Service name extraction from task IDs
"""

import os
import sys
import unittest
from pathlib import Path

# Add demo directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from setup_demo_tasks import (
    generate_observability_tasks,
    _generate_decomposed_tasks,
    _generate_batched_tasks,
    build_all_contexts,
    group_by_tier,
    TIER_MAP,
    SERVICE_TO_TIER,
    STANDARD_ARTIFACTS,
    LOADGEN_ARTIFACTS,
    ARTIFACT_DASHBOARDS,
    ARTIFACT_DASHBOARD,
)


class TestDecomposedTaskGeneration(unittest.TestCase):
    """Tests for per-service task decomposition."""

    def setUp(self):
        """Build contexts once for all tests."""
        self.contexts = build_all_contexts()
        self.tasks, self.artifact_ids = _generate_decomposed_tasks(self.contexts)

    def test_task_count(self):
        """Verify correct number of tasks generated."""
        # 10 standard services × 6 artifacts + 1 loadgenerator × 2 artifacts = 62
        num_standard = sum(
            len(services) for tier, services in TIER_MAP.items()
            if tier != "low"
        )
        num_loadgen = len(TIER_MAP.get("low", []))
        expected = (num_standard * len(STANDARD_ARTIFACTS) +
                    num_loadgen * len(LOADGEN_ARTIFACTS))
        self.assertEqual(len(self.tasks), expected)

    def test_task_id_format(self):
        """Verify task IDs follow OB-{SERVICE}-{ARTIFACT} pattern."""
        for task in self.tasks:
            task_id = task["id"]
            parts = task_id.split("-", 2)
            self.assertEqual(parts[0], "OB", f"Task {task_id} should start with OB-")
            self.assertEqual(len(parts), 3, f"Task {task_id} should have 3 parts")

    def test_service_name_in_task(self):
        """Verify service_name field is set in task config."""
        for task in self.tasks:
            self.assertIn("service_name", task,
                          f"Task {task['id']} missing service_name field")

    def test_tier_ordering(self):
        """Verify tasks are generated in tier order (critical first)."""
        tier_first_seen = {}
        for i, task in enumerate(self.tasks):
            service = task.get("service_name")
            tier = SERVICE_TO_TIER.get(service)
            if tier and tier not in tier_first_seen:
                tier_first_seen[tier] = i

        # Critical should appear before high, high before medium, etc.
        tier_order = ["critical", "high", "medium", "low"]
        for i in range(len(tier_order) - 1):
            current = tier_order[i]
            next_tier = tier_order[i + 1]
            if current in tier_first_seen and next_tier in tier_first_seen:
                self.assertLess(
                    tier_first_seen[current],
                    tier_first_seen[next_tier],
                    f"{current} tier should appear before {next_tier} tier"
                )

    def test_alphabetical_within_tier(self):
        """Verify generated tasks are sorted alphabetically within each tier."""
        # Group tasks by tier
        tier_services = {tier: [] for tier in TIER_MAP}
        for task in self.tasks:
            service = task.get("service_name")
            tier = SERVICE_TO_TIER.get(service)
            if tier:
                # Only add service on first occurrence (dashboard task)
                if service not in tier_services[tier]:
                    tier_services[tier].append(service)

        # Verify each tier's services appear in alphabetical order
        for tier, services in tier_services.items():
            self.assertEqual(services, sorted(services),
                             f"Services in {tier} tier should be alphabetically sorted")

    def test_dependencies_reference_dashboard_tasks(self):
        """Verify phase 2+ task dependencies reference dashboard tasks."""
        dashboard_task_ids = {
            task["id"] for task in self.tasks
            if task["id"].endswith(f"-{ARTIFACT_DASHBOARDS}") or
               task["id"].endswith(f"-{ARTIFACT_DASHBOARD}")
        }

        for task in self.tasks:
            deps = task.get("depends_on", [])
            if deps:
                for dep in deps:
                    self.assertIn(dep, dashboard_task_ids,
                                  f"Dependency {dep} should be a dashboard task")

    def test_critical_tier_no_dependencies(self):
        """Verify critical tier tasks have no dependencies."""
        critical_services = set(TIER_MAP.get("critical", []))
        for task in self.tasks:
            if task.get("service_name") in critical_services:
                self.assertEqual(task.get("depends_on", []), [],
                                 f"Critical tier task {task['id']} should have no dependencies")


class TestBatchedTaskGeneration(unittest.TestCase):
    """Tests for per-tier task batching (legacy mode)."""

    def setUp(self):
        """Build contexts once for all tests."""
        self.contexts = build_all_contexts()
        self.tiers = group_by_tier(self.contexts)
        self.tasks, self.artifact_ids = _generate_batched_tasks(
            self.contexts, self.tiers
        )

    def test_task_count(self):
        """Verify correct number of batched tasks."""
        # 3 standard tiers × 6 artifacts + 1 low tier × 2 artifacts = 20
        num_standard_tiers = len([t for t in TIER_MAP if t != "low"])
        num_low_tiers = 1 if "low" in TIER_MAP else 0
        expected = (num_standard_tiers * len(STANDARD_ARTIFACTS) +
                    num_low_tiers * len(LOADGEN_ARTIFACTS))
        self.assertEqual(len(self.tasks), expected)

    def test_task_id_format(self):
        """Verify task IDs follow OB-{TIER}-{ARTIFACT} pattern."""
        valid_prefixes = {"CRIT", "HIGH", "MED", "LOW"}
        for task in self.tasks:
            task_id = task["id"]
            parts = task_id.split("-", 2)
            self.assertEqual(parts[0], "OB", f"Task {task_id} should start with OB-")
            self.assertIn(parts[1], valid_prefixes,
                          f"Task {task_id} should have valid tier prefix")


class TestFullTaskGeneration(unittest.TestCase):
    """Tests for the complete generate_observability_tasks() function."""

    def test_includes_epic(self):
        """Verify epic task is included."""
        tasks = generate_observability_tasks()
        epic_tasks = [t for t in tasks if t["id"] == "OB-EPIC"]
        self.assertEqual(len(epic_tasks), 1)
        self.assertEqual(epic_tasks[0]["type"], "epic")

    def test_includes_utility_tasks(self):
        """Verify load, verify, and summary tasks are included."""
        tasks = generate_observability_tasks()
        task_ids = {t["id"] for t in tasks}
        self.assertIn("OB-LOAD", task_ids)
        self.assertIn("OB-VERIFY", task_ids)
        self.assertIn("OB-SUMMARY", task_ids)

    def test_load_depends_on_all_artifacts(self):
        """Verify OB-LOAD depends on all artifact tasks."""
        tasks = generate_observability_tasks()
        load_task = next(t for t in tasks if t["id"] == "OB-LOAD")
        artifact_tasks = [
            t for t in tasks
            if t["id"] not in ("OB-EPIC", "OB-LOAD", "OB-VERIFY", "OB-SUMMARY")
        ]
        self.assertEqual(
            set(load_task["depends_on"]),
            {t["id"] for t in artifact_tasks}
        )


class TestServiceNameExtraction(unittest.TestCase):
    """Tests for extracting service names from task IDs."""

    def test_decomposed_task_id_extraction(self):
        """Test extracting service name from decomposed task ID."""
        test_cases = [
            ("OB-FRONTEND-DASHBOARDS", "frontend"),
            ("OB-CHECKOUTSERVICE-ALERTS", "checkoutservice"),
            ("OB-LOADGENERATOR-RUNBOOK", "loadgenerator"),
        ]
        for task_id, expected_service in test_cases:
            parts = task_id.split("-", 2)
            service = parts[1].lower()
            self.assertEqual(service, expected_service)


if __name__ == "__main__":
    unittest.main()
