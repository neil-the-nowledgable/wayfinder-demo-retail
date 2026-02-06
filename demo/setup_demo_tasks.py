#!/usr/bin/env python3
"""
ContextCore Ecosystem Demo: Observability Artifact Generation Setup

Creates ContextCore tasks that analyze the Online Boutique microservices
codebase, derive observability requirements from ProjectContext CRDs + source
code, and generate a complete observability artifact set (dashboards, alerts,
SLOs, notification policies, Loki rules, runbooks).

Data Sources:
  - ProjectContext CRDs (SLO targets, criticality, risks, alert channels)
  - Proto definitions (gRPC methods per service)
  - K8s manifests (ports, resources, probes)
  - SERVICE_INFO (language, dependencies, description per service)

Usage:
    python demo/setup_demo_tasks.py
    python demo/setup_demo_tasks.py --dry-run
    python demo/setup_demo_tasks.py --clean
    python demo/setup_demo_tasks.py --list

After running this script, execute the demo with:
    python demo/run_self_tracking_demo.py
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import uuid

try:
    import yaml
except ImportError:
    yaml = None

# =============================================================================
# CONFIGURATION
# =============================================================================

DEMO_PROJECT = "ecosystem-demo"
DEMO_SPRINT = "demo-sprint-1"
STATE_DIR = Path.home() / ".contextcore" / "state" / DEMO_PROJECT

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parent
_DEFAULT_DEV_ROOT = _PROJECT_DIR.parent

DEV_ROOT = Path(os.environ.get("CONTEXTCORE_DEV_ROOT", str(_DEFAULT_DEV_ROOT)))
OUTPUT_DIR = _PROJECT_DIR / "output" / "observability"

# Paths to data sources
CRD_DIR = DEV_ROOT / "ContextCore" / "demo" / "projectcontexts"
PROTO_FILE = (DEV_ROOT / "micro-service-demo" / "microservices-demo"
              / "protos" / "demo.proto")
K8S_DIR = (DEV_ROOT / "micro-service-demo" / "microservices-demo"
            / "kubernetes-manifests")

# =============================================================================
# SERVICE METADATA (standalone -- no contextcore dependency required)
# =============================================================================

SERVICE_INFO = {
    "frontend": {
        "language": "Go",
        "description": "HTTP server delivering the website interface",
        "dependencies": [
            "productcatalogservice", "currencyservice", "cartservice",
            "recommendationservice", "shippingservice", "checkoutservice",
            "adservice",
        ],
    },
    "checkoutservice": {
        "language": "Go",
        "description": "Orchestrates purchase workflow",
        "dependencies": [
            "productcatalogservice", "cartservice", "currencyservice",
            "shippingservice", "paymentservice", "emailservice",
        ],
    },
    "cartservice": {
        "language": "C#",
        "description": "Manages shopping cart with Redis backend",
        "dependencies": [],
    },
    "paymentservice": {
        "language": "Node.js",
        "description": "Processes mock credit card transactions",
        "dependencies": [],
    },
    "productcatalogservice": {
        "language": "Go",
        "description": "Product catalog from JSON with search",
        "dependencies": [],
    },
    "currencyservice": {
        "language": "Node.js",
        "description": "Currency conversion using ECB rates",
        "dependencies": [],
    },
    "shippingservice": {
        "language": "Go",
        "description": "Calculates shipping estimates",
        "dependencies": [],
    },
    "emailservice": {
        "language": "Python",
        "description": "Sends mock order confirmation emails",
        "dependencies": [],
    },
    "recommendationservice": {
        "language": "Python",
        "description": "Product recommendations based on cart",
        "dependencies": ["productcatalogservice"],
    },
    "adservice": {
        "language": "Java",
        "description": "Contextual text advertisements",
        "dependencies": [],
    },
    "loadgenerator": {
        "language": "Python",
        "description": "Simulates user shopping behavior with Locust",
        "dependencies": ["frontend"],
    },
}

# Service tier assignments
TIER_MAP = {
    "critical": ["frontend", "checkoutservice", "cartservice", "paymentservice"],
    "high": ["productcatalogservice", "currencyservice", "shippingservice"],
    "medium": ["emailservice", "recommendationservice", "adservice"],
    "low": ["loadgenerator"],
}

# Reverse lookup: service name -> tier
SERVICE_TO_TIER = {
    svc: tier for tier, services in TIER_MAP.items() for svc in services
}

# Task decomposition setting: True = 1 service per task (reliable), False = batch by tier
# Setting to True fixes truncation issues with GPT-4o-mini when batching 3+ services
DECOMPOSE_TO_SINGLE_SERVICE = True

# Tier task configurations: phase ordering, gating dependencies, artifact types
TIER_CONFIGS = [
    {
        "name": "critical", "prefix": "CRIT", "phase": 1,
        "gate_deps": [],
        "artifacts": [
            "DASHBOARDS", "ALERTS", "SLOS", "NOTIFY", "LOKI-RULES", "RUNBOOKS",
        ],
    },
    {
        "name": "high", "prefix": "HIGH", "phase": 2,
        "gate_deps": ["OB-CRIT-DASHBOARDS"],
        "artifacts": [
            "DASHBOARDS", "ALERTS", "SLOS", "NOTIFY", "LOKI-RULES", "RUNBOOKS",
        ],
    },
    {
        "name": "medium", "prefix": "MED", "phase": 3,
        "gate_deps": ["OB-HIGH-DASHBOARDS"],
        "artifacts": [
            "DASHBOARDS", "ALERTS", "SLOS", "NOTIFY", "LOKI-RULES", "RUNBOOKS",
        ],
    },
    {
        "name": "low", "prefix": "LOW", "phase": 4,
        "gate_deps": ["OB-MED-DASHBOARDS"],
        "artifacts": ["DASHBOARD", "RUNBOOK"],
    },
]

# Human-readable artifact titles
ARTIFACT_TITLES = {
    "DASHBOARDS": "Grafana dashboards",
    "DASHBOARD": "Grafana dashboard",
    "ALERTS": "PrometheusRule alert definitions",
    "SLOS": "SLO definitions",
    "NOTIFY": "notification policies",
    "LOKI-RULES": "Loki recording rules",
    "RUNBOOKS": "operational runbooks",
    "RUNBOOK": "operational runbook",
}

# Delimiter used in drafter output, mapped to output subdirectory and extension
ARTIFACT_OUTPUT_CONFIG = {
    "DASHBOARD": {"dir": "dashboards", "suffix": "dashboard", "ext": "json"},
    "PROMETHEUS_RULE": {"dir": "prometheus-rules", "suffix": "rules", "ext": "yaml"},
    "SLO": {"dir": "slo-definitions", "suffix": "slo", "ext": "yaml"},
    "NOTIFICATION": {"dir": "notification-policies", "suffix": "notifications", "ext": "yaml"},
    "LOKI_RULE": {"dir": "loki-rules", "suffix": "loki-rules", "ext": "yaml"},
    "RUNBOOK": {"dir": "runbooks", "suffix": "runbook", "ext": "md"},
}

# Map task artifact key to the delimiter used in drafter output
ARTIFACT_KEY_TO_DELIMITER = {
    "DASHBOARDS": "DASHBOARD",
    "DASHBOARD": "DASHBOARD",
    "ALERTS": "PROMETHEUS_RULE",
    "SLOS": "SLO",
    "NOTIFY": "NOTIFICATION",
    "LOKI-RULES": "LOKI_RULE",
    "RUNBOOKS": "RUNBOOK",
    "RUNBOOK": "RUNBOOK",
}

# =============================================================================
# DATA LOADING FUNCTIONS
# =============================================================================


def load_project_contexts() -> Dict[str, Dict]:
    """Parse all ProjectContext CRD YAMLs, return dict keyed by service name."""
    if yaml is None or not CRD_DIR.exists():
        return {}

    contexts = {}
    for yaml_file in sorted(CRD_DIR.glob("*.yaml")):
        try:
            doc = yaml.safe_load(yaml_file.read_text())
        except Exception:
            continue

        service_name = yaml_file.stem
        spec = doc.get("spec", {})
        biz = spec.get("business", {})
        reqs = spec.get("requirements", {})
        obs = spec.get("observability", {})

        contexts[service_name] = {
            "criticality": biz.get("criticality", "medium"),
            "value": biz.get("value", "internal"),
            "owner": biz.get("owner", "unknown"),
            "availability": reqs.get("availability", "-"),
            "latency_p99": reqs.get("latencyP99", "-"),
            "error_budget": reqs.get("errorBudget", "-"),
            "throughput": reqs.get("throughput", "-"),
            "risks": spec.get("risks", []),
            "alert_channels": obs.get("alertChannels", []),
        }

    return contexts


def load_proto_definitions() -> Dict[str, List[str]]:
    """Parse demo.proto, extract gRPC method names per service."""
    if not PROTO_FILE.exists():
        return {}

    content = PROTO_FILE.read_text()
    services: Dict[str, List[str]] = {}

    service_re = re.compile(
        r'service\s+(\w+)\s*\{(.*?)^\}',
        re.DOTALL | re.MULTILINE,
    )
    rpc_re = re.compile(r'rpc\s+(\w+)\s*\(')

    for match in service_re.finditer(content):
        proto_name = match.group(1)
        body = match.group(2)
        methods = rpc_re.findall(body)
        # "CartService" -> "cartservice"
        service_key = proto_name.lower()
        services[service_key] = methods

    return services


def load_k8s_manifests() -> Dict[str, Dict]:
    """Parse K8s manifest YAMLs, extract ports, resources, health probes."""
    if yaml is None or not K8S_DIR.exists():
        return {}

    manifests: Dict[str, Dict] = {}
    skip_files = {"kustomization.yaml", "README.md"}

    for yaml_file in sorted(K8S_DIR.glob("*.yaml")):
        if yaml_file.name in skip_files:
            continue

        service_name = yaml_file.stem
        try:
            docs = list(yaml.safe_load_all(yaml_file.read_text()))
        except Exception:
            continue

        info: Dict[str, Any] = {
            "port": None, "resources": {}, "probe_type": None,
        }

        for doc in docs:
            if not isinstance(doc, dict) or doc.get("kind") != "Deployment":
                continue

            containers = (
                doc.get("spec", {})
                .get("template", {})
                .get("spec", {})
                .get("containers", [])
            )
            if not containers:
                continue

            c = containers[0]

            ports = c.get("ports", [])
            if ports:
                info["port"] = ports[0].get("containerPort")

            info["resources"] = c.get("resources", {})

            for probe_key in ("readinessProbe", "livenessProbe"):
                probe = c.get(probe_key, {})
                if "httpGet" in probe:
                    info["probe_type"] = "http"
                    break
                elif "grpc" in probe:
                    info["probe_type"] = "grpc"
                    break
                elif "exec" in probe:
                    info["probe_type"] = "exec"
                    break

        manifests[service_name] = info

    return manifests


# =============================================================================
# CONTEXT BUILDING
# =============================================================================


def build_service_context(
    service_name: str,
    crd: Optional[Dict],
    proto_methods: List[str],
    k8s: Optional[Dict],
) -> Dict:
    """Merge all data sources into a unified service context dict."""
    info = SERVICE_INFO.get(service_name, {})
    crd = crd or {}
    k8s = k8s or {}

    return {
        "name": service_name,
        "language": info.get("language", "unknown"),
        "description": info.get("description", ""),
        "criticality": crd.get("criticality", "medium"),
        "business_value": crd.get("value", "internal"),
        "dependencies": info.get("dependencies", []),
        "grpc_methods": proto_methods,
        "slo": {
            "availability": crd.get("availability", "-"),
            "latency_p99": crd.get("latency_p99", "-"),
            "error_budget": crd.get("error_budget", "-"),
            "throughput": crd.get("throughput", "-"),
        },
        "risks": crd.get("risks", []),
        "alert_channels": crd.get("alert_channels", []),
        "owner": crd.get("owner", "unknown"),
        "k8s": {
            "port": k8s.get("port"),
            "resources": k8s.get("resources", {}),
            "probe_type": k8s.get("probe_type"),
        },
    }


def build_all_contexts() -> Dict[str, Dict]:
    """Load all data sources and build unified service contexts."""
    crds = load_project_contexts()
    proto = load_proto_definitions()
    k8s = load_k8s_manifests()

    contexts = {}
    for service_name in SERVICE_INFO:
        contexts[service_name] = build_service_context(
            service_name,
            crds.get(service_name),
            proto.get(service_name, []),
            k8s.get(service_name),
        )
    return contexts


def group_by_tier(contexts: Dict[str, Dict]) -> Dict[str, List[Dict]]:
    """Group service contexts by criticality tier."""
    tiers: Dict[str, List[Dict]] = {}
    for tier_name, services in TIER_MAP.items():
        tiers[tier_name] = [
            contexts[s] for s in services if s in contexts
        ]
    return tiers


# =============================================================================
# JSONNET PARAMETER SCHEMA TEMPLATE
# =============================================================================

# This schema is included in prompts for artifact types that use jsonnet compilation.
# The drafter generates simple .libsonnet parameter objects conforming to this schema.
PARAMS_SCHEMA_TEMPLATE = '''
## Parameter Schema (.libsonnet)

Generate a Jsonnet object with these fields. Use only simple data types (strings, numbers, arrays, objects).
Do NOT use Grafonnet or any library imports - just plain data.

```jsonnet
{
  name: 'service_name',           // Required: service name (lowercase)
  language: 'Go',                 // Programming language: Go, Node.js, Python, Java, C#
  description: 'Brief description of the service',
  criticality: 'critical',        // critical, high, medium, low
  businessValue: 'revenue-primary', // revenue-primary, revenue-secondary, internal, cost-center
  owner: 'team-name',
  protocol: 'grpc',               // grpc or http
  grpcMethods: ['Method1', 'Method2'],  // gRPC methods (if protocol=grpc)
  httpEndpoints: ['/api/path'],   // HTTP endpoints (if protocol=http)
  slo: {
    availability: 99.95,          // percent (e.g., 99.95 for 99.95%)
    latencyP99: '100ms',          // with unit suffix (ms)
    errorBudget: 0.05,            // percent allowed errors
    throughput: '1000rps',        // requests per second
  },
  dependencies: ['other-service'], // downstream service names
  risks: [
    { priority: 'P1', description: 'Risk description' },
  ],
  alertChannels: ['pagerduty-p1', 'slack-incidents'],
  k8s: {
    port: 8080,
    cpuRequest: '100m',
    memoryRequest: '128Mi',
    cpuLimit: '200m',
    memoryLimit: '256Mi',
    probeType: 'grpc',            // grpc, http, exec
  },
  logFields: {                    // Language-specific log field names
    level: 'level',               // Log level field name
    message: 'msg',               // Message field name
    duration: 'duration_ms',      // Duration field name
    durationUnit: 'ms',           // ms, us, ns, s
  },
}
```

### Language-Specific Log Field Mappings

| Language | level | message | duration | durationUnit |
|----------|-------|---------|----------|--------------|
| Go | level | msg | duration_ms | ms |
| Node.js | level | message | responseTime | ms |
| Python | levelname | message | duration | ms |
| Java | level | message | elapsed_ms | ms |
| C# | Level | Message | ElapsedMilliseconds | ms |
'''

# =============================================================================
# PROMPT HELPERS
# =============================================================================


def _format_service_block(ctx: Dict, index: int) -> str:
    """Format a single service's context for inclusion in a prompt."""
    methods = ", ".join(ctx.get("grpc_methods", [])) or "N/A (HTTP gateway)"
    deps = ", ".join(ctx.get("dependencies", [])) or "none"

    risk_strs = []
    for r in ctx.get("risks", []):
        if isinstance(r, dict):
            risk_strs.append(
                f"{r.get('priority', '?')}: {r.get('description', '')}"
            )
    risks = "; ".join(risk_strs) or "none identified"
    channels = ", ".join(ctx.get("alert_channels", [])) or "none"

    slo = ctx.get("slo", {})
    k8s = ctx.get("k8s", {})
    res = k8s.get("resources", {})
    req = res.get("requests", {})
    lim = res.get("limits", {})

    lines = [
        f"### {index}. {ctx['name']} ({ctx['language']})",
        f"- Description: {ctx['description']}",
        f"- Criticality: {ctx['criticality']} | Value: {ctx['business_value']}",
        f"- gRPC Methods: {methods}",
        (f"- SLO: availability={slo.get('availability', '-')}%, "
         f"latencyP99={slo.get('latency_p99', '-')}, "
         f"errorBudget={slo.get('error_budget', '-')}%, "
         f"throughput={slo.get('throughput', '-')}"),
        f"- Dependencies: {deps}",
        f"- Risks: {risks}",
        f"- Alert Channels: {channels}",
        (f"- K8s: port={k8s.get('port', '-')}, "
         f"requests={req.get('cpu', '-')}/{req.get('memory', '-')}, "
         f"limits={lim.get('cpu', '-')}/{lim.get('memory', '-')}, "
         f"probes={k8s.get('probe_type', '-')}"),
    ]
    return "\n".join(lines)


def _services_section(service_contexts: List[Dict]) -> str:
    """Format all service blocks for a prompt."""
    return "\n\n".join(
        _format_service_block(ctx, i + 1)
        for i, ctx in enumerate(service_contexts)
    )


def _output_format_section(
    n: int, delimiter: str, service_contexts: List[Dict],
) -> str:
    """Build the standard output-format section for a prompt (raw JSON/YAML)."""
    names = ", ".join(ctx["name"] for ctx in service_contexts)
    return (
        "## Output Format\n\n"
        f"Output {n} artifact(s), each separated by a delimiter line:\n\n"
        f"--- {delimiter}: {{service_name}} ---\n\n"
        f"Where {{service_name}} is one of: {names}\n\n"
        "Output ONLY the raw content between delimiters. "
        "No markdown code fences inside the delimited sections.\n"
    )


def _params_output_format_section(n: int, service_contexts: List[Dict]) -> str:
    """Build the output-format section for PARAMS (.libsonnet) output."""
    names = ", ".join(ctx["name"] for ctx in service_contexts)
    return (
        "## Output Format\n\n"
        f"Output {n} parameter file(s), each separated by a delimiter line:\n\n"
        "--- PARAMS: {service_name} ---\n\n"
        f"Where {{service_name}} is one of: {names}\n\n"
        "Output ONLY the raw Jsonnet object between delimiters. "
        "No markdown code fences inside the delimited sections.\n"
        "The Jsonnet object should be a simple data structure - no imports or functions.\n"
    )


# =============================================================================
# PROMPT BUILDERS (one per artifact type)
# =============================================================================


def build_dashboard_prompt(tier_name: str, ctxs: List[Dict]) -> str:
    n = len(ctxs)
    header = (
        f"Generate {n} Jsonnet parameter file(s) for Grafana dashboards "
        f"for {tier_name}-tier Online Boutique microservices.\n\n"
        "These parameters will be compiled into dashboards with panels for: "
        "request rate (QPS), latency percentiles (P50/P95/P99), error rate (%), "
        "availability (%), resource saturation (CPU/memory), and dependency health."
    )

    reqs = (
        "## Requirements\n\n"
        "1. Set criticality, protocol (grpc/http), and SLO targets accurately\n"
        "2. For HTTP services (frontend): set protocol to 'http'\n"
        "3. Include all gRPC methods from the service context\n"
        "4. Include dependencies as listed in the service context\n"
        "5. Set owner from the service context\n"
        "6. Include risks with priority and description\n"
        "7. Set k8s.port from the service context\n"
        "8. Use the correct log field names for each service's language\n"
    )

    return (
        f"{header}\n\n## Services\n\n{_services_section(ctxs)}\n\n"
        f"{PARAMS_SCHEMA_TEMPLATE}\n{reqs}\n"
        f"{_params_output_format_section(n, ctxs)}"
    )


def build_single_service_dashboard_prompt(ctx: Dict) -> str:
    """Build dashboard prompt for a single service."""
    service_name = ctx["name"]
    tier = ctx["criticality"]
    header = (
        f"Generate 1 Jsonnet parameter file for a Grafana dashboard "
        f"for the {service_name} microservice ({tier} criticality).\n\n"
        "These parameters will be compiled into a dashboard with panels for: "
        "request rate (QPS), latency percentiles (P50/P95/P99), error rate (%), "
        "availability (%), resource saturation (CPU/memory), and dependency health."
    )

    reqs = (
        "## Requirements\n\n"
        "1. Set criticality, protocol (grpc/http), and SLO targets accurately\n"
        "2. For HTTP services (frontend): set protocol to 'http'\n"
        "3. Include all gRPC methods from the service context\n"
        "4. Include dependencies as listed in the service context\n"
        "5. Set owner from the service context\n"
        "6. Include risks with priority and description\n"
        "7. Set k8s.port from the service context\n"
        "8. Use the correct log field names for the service's language\n"
    )

    return (
        f"{header}\n\n## Service\n\n{_format_service_block(ctx, 1)}\n\n"
        f"{PARAMS_SCHEMA_TEMPLATE}\n{reqs}\n"
        f"{_params_output_format_section(1, [ctx])}"
    )


def build_alerts_prompt(tier_name: str, ctxs: List[Dict]) -> str:
    n = len(ctxs)
    header = (
        f"Generate {n} Jsonnet parameter file(s) for PrometheusRule alerts "
        f"for {tier_name}-tier Online Boutique microservices.\n\n"
        "These parameters will be compiled into alerting rules derived from "
        "SLO targets: latency P99 alerts and error rate alerts."
    )

    reqs = (
        "## Requirements\n\n"
        "1. Set SLO availability and latencyP99 targets accurately\n"
        "2. Set criticality correctly (determines alert severity and 'for' duration)\n"
        "3. Set protocol to 'http' for frontend, 'grpc' for others\n"
        "4. Include all risks from the service context\n"
        "5. Set alertChannels for alert routing\n"
        "6. Set owner from the service context\n"
    )

    return (
        f"{header}\n\n## Services\n\n{_services_section(ctxs)}\n\n"
        f"{PARAMS_SCHEMA_TEMPLATE}\n{reqs}\n"
        f"{_params_output_format_section(n, ctxs)}"
    )


def build_single_service_alerts_prompt(ctx: Dict) -> str:
    """Build alerts prompt for a single service."""
    service_name = ctx["name"]
    tier = ctx["criticality"]
    header = (
        f"Generate 1 Jsonnet parameter file for PrometheusRule alerts "
        f"for the {service_name} microservice ({tier} criticality).\n\n"
        "These parameters will be compiled into alerting rules derived from "
        "SLO targets: latency P99 alerts and error rate alerts."
    )

    reqs = (
        "## Requirements\n\n"
        "1. Set SLO availability and latencyP99 targets accurately\n"
        "2. Set criticality correctly (determines alert severity and 'for' duration)\n"
        "3. Set protocol to 'http' for frontend, 'grpc' for others\n"
        "4. Include all risks from the service context\n"
        "5. Set alertChannels for alert routing\n"
        "6. Set owner from the service context\n"
    )

    return (
        f"{header}\n\n## Service\n\n{_format_service_block(ctx, 1)}\n\n"
        f"{PARAMS_SCHEMA_TEMPLATE}\n{reqs}\n"
        f"{_params_output_format_section(1, [ctx])}"
    )


def build_slo_prompt(tier_name: str, ctxs: List[Dict]) -> str:
    n = len(ctxs)
    header = (
        f"Generate {n} Jsonnet parameter file(s) for SLO definitions "
        f"for {tier_name}-tier Online Boutique microservices.\n\n"
        "These parameters will be compiled into Sloth PrometheusServiceLevel "
        "definitions with availability targets and multi-window burn-rate alerting."
    )

    reqs = (
        "## Requirements\n\n"
        "1. Set slo.availability from each service's availability target\n"
        "2. Set slo.latencyP99 from each service's latency target (with 'ms' suffix)\n"
        "3. Set slo.errorBudget = 100 - availability (e.g., 99.95 -> 0.05)\n"
        "4. Set owner from the service context\n"
        "5. Set criticality correctly (affects alert severity)\n"
        "6. Set protocol to 'http' for frontend, 'grpc' for others\n"
    )

    return (
        f"{header}\n\n## Services\n\n{_services_section(ctxs)}\n\n"
        f"{PARAMS_SCHEMA_TEMPLATE}\n{reqs}\n"
        f"{_params_output_format_section(n, ctxs)}"
    )


def build_single_service_slo_prompt(ctx: Dict) -> str:
    """Build SLO prompt for a single service."""
    service_name = ctx["name"]
    tier = ctx["criticality"]
    header = (
        f"Generate 1 Jsonnet parameter file for SLO definitions "
        f"for the {service_name} microservice ({tier} criticality).\n\n"
        "These parameters will be compiled into Sloth PrometheusServiceLevel "
        "definitions with availability targets and multi-window burn-rate alerting."
    )

    reqs = (
        "## Requirements\n\n"
        "1. Set slo.availability from the service's availability target\n"
        "2. Set slo.latencyP99 from the service's latency target (with 'ms' suffix)\n"
        "3. Set slo.errorBudget = 100 - availability (e.g., 99.95 -> 0.05)\n"
        "4. Set owner from the service context\n"
        "5. Set criticality correctly (affects alert severity)\n"
        "6. Set protocol to 'http' for frontend, 'grpc' for others\n"
    )

    return (
        f"{header}\n\n## Service\n\n{_format_service_block(ctx, 1)}\n\n"
        f"{PARAMS_SCHEMA_TEMPLATE}\n{reqs}\n"
        f"{_params_output_format_section(1, [ctx])}"
    )


def build_notification_prompt(tier_name: str, ctxs: List[Dict]) -> str:
    n = len(ctxs)
    header = (
        f"Generate {n} Jsonnet parameter file(s) for notification policies "
        f"for {tier_name}-tier Online Boutique microservices.\n\n"
        "These parameters will be compiled into notification routing policies "
        "based on criticality: critical -> PagerDuty, high -> Slack, "
        "medium -> email, low -> log only."
    )

    reqs = (
        "## Requirements\n\n"
        "1. Set alertChannels from each service's context\n"
        "2. Set criticality correctly (determines routing)\n"
        "3. Set owner from the service context\n"
        "4. If alertChannels is empty, use defaults based on criticality:\n"
        "   - critical: ['pagerduty-p1', 'slack-incidents']\n"
        "   - high: ['slack-incidents']\n"
        "   - medium: ['slack-notifications', 'email-oncall']\n"
        "   - low: ['slack-notifications']\n"
    )

    return (
        f"{header}\n\n## Services\n\n{_services_section(ctxs)}\n\n"
        f"{PARAMS_SCHEMA_TEMPLATE}\n{reqs}\n"
        f"{_params_output_format_section(n, ctxs)}"
    )


def build_single_service_notification_prompt(ctx: Dict) -> str:
    """Build notification prompt for a single service."""
    service_name = ctx["name"]
    tier = ctx["criticality"]
    header = (
        f"Generate 1 Jsonnet parameter file for notification policies "
        f"for the {service_name} microservice ({tier} criticality).\n\n"
        "These parameters will be compiled into notification routing policies "
        "based on criticality: critical -> PagerDuty, high -> Slack, "
        "medium -> email, low -> log only."
    )

    reqs = (
        "## Requirements\n\n"
        "1. Set alertChannels from the service's context\n"
        "2. Set criticality correctly (determines routing)\n"
        "3. Set owner from the service context\n"
        "4. If alertChannels is empty, use defaults based on criticality:\n"
        "   - critical: ['pagerduty-p1', 'slack-incidents']\n"
        "   - high: ['slack-incidents']\n"
        "   - medium: ['slack-notifications', 'email-oncall']\n"
        "   - low: ['slack-notifications']\n"
    )

    return (
        f"{header}\n\n## Service\n\n{_format_service_block(ctx, 1)}\n\n"
        f"{PARAMS_SCHEMA_TEMPLATE}\n{reqs}\n"
        f"{_params_output_format_section(1, [ctx])}"
    )


def build_loki_rules_prompt(tier_name: str, ctxs: List[Dict]) -> str:
    n = len(ctxs)
    header = (
        f"Generate {n} Jsonnet parameter file(s) for Loki recording rules "
        f"for {tier_name}-tier Online Boutique microservices.\n\n"
        "These parameters will be compiled into Loki RecordingRules that "
        "derive Prometheus metrics from structured JSON logs: "
        "error counts, latency, and request counts."
    )

    reqs = (
        "## Requirements\n\n"
        "1. Set language correctly for each service\n"
        "2. Set logFields with the correct field names for each language:\n"
        "   - Go: level='level', message='msg', duration='duration_ms', durationUnit='ms'\n"
        "   - Node.js: level='level', message='message', duration='responseTime', durationUnit='ms'\n"
        "   - Python: level='levelname', message='message', duration='duration', durationUnit='ms'\n"
        "   - Java: level='level', message='message', duration='elapsed_ms', durationUnit='ms'\n"
        "   - C#: level='Level', message='Message', duration='ElapsedMilliseconds', durationUnit='ms'\n"
        "3. Set criticality from the service context\n"
    )

    return (
        f"{header}\n\n## Services\n\n{_services_section(ctxs)}\n\n"
        f"{PARAMS_SCHEMA_TEMPLATE}\n{reqs}\n"
        f"{_params_output_format_section(n, ctxs)}"
    )


def build_single_service_loki_rules_prompt(ctx: Dict) -> str:
    """Build Loki rules prompt for a single service."""
    service_name = ctx["name"]
    language = ctx["language"]
    header = (
        f"Generate 1 Jsonnet parameter file for Loki recording rules "
        f"for the {service_name} microservice ({language}).\n\n"
        "These parameters will be compiled into Loki RecordingRules that "
        "derive Prometheus metrics from structured JSON logs: "
        "error counts, latency, and request counts."
    )

    reqs = (
        "## Requirements\n\n"
        "1. Set language correctly for this service\n"
        "2. Set logFields with the correct field names for the language:\n"
        "   - Go: level='level', message='msg', duration='duration_ms', durationUnit='ms'\n"
        "   - Node.js: level='level', message='message', duration='responseTime', durationUnit='ms'\n"
        "   - Python: level='levelname', message='message', duration='duration', durationUnit='ms'\n"
        "   - Java: level='level', message='message', duration='elapsed_ms', durationUnit='ms'\n"
        "   - C#: level='Level', message='Message', duration='ElapsedMilliseconds', durationUnit='ms'\n"
        "3. Set criticality from the service context\n"
    )

    return (
        f"{header}\n\n## Service\n\n{_format_service_block(ctx, 1)}\n\n"
        f"{PARAMS_SCHEMA_TEMPLATE}\n{reqs}\n"
        f"{_params_output_format_section(1, [ctx])}"
    )


def build_runbook_prompt(tier_name: str, ctxs: List[Dict]) -> str:
    n = len(ctxs)
    header = (
        f"Generate {n} operational runbook(s) in Markdown for "
        f"{tier_name}-tier Online Boutique microservices.\n\n"
        "Each runbook covers: service overview, SLOs, alert response, "
        "K8s commands, dependencies, risks, and escalation."
    )

    template = (
        "## Reference Template\n\n"
        "```markdown\n"
        "# SERVICE_NAME Operational Runbook\n\n"
        "## Service Overview\n"
        "| Field | Value |\n"
        "|-------|-------|\n"
        "| Language | LANG |\n"
        "| Criticality | TIER |\n"
        "| Owner | OWNER |\n"
        "| Port | PORT |\n\n"
        "## SLOs\n"
        "| Metric | Target |\n"
        "|--------|--------|\n"
        "| Availability | X% |\n"
        "| Latency P99 | Yms |\n\n"
        "## Alert Response\n"
        "### SERVICE_NAMELatencyP99High\n"
        "**Severity**: warning | **Threshold**: ... \n"
        "**Steps**: 1. Check... 2. Scale... 3. Escalate...\n\n"
        "## Kubernetes Commands\n"
        "```bash\n"
        "kubectl get pods -l app=SERVICE_NAME -n online-boutique\n"
        "kubectl logs -l app=SERVICE_NAME -n online-boutique --tail=100\n"
        "kubectl rollout restart deployment/SERVICE_NAME -n online-boutique\n"
        "```\n\n"
        "## Dependencies\n"
        "...\n\n"
        "## Escalation\n"
        "1. On-call: CHANNEL\n"
        "2. Team lead: OWNER\n"
        "```\n"
    )

    reqs = (
        "## Requirements\n\n"
        "1. Include all SLO targets from the service context\n"
        "2. List every risk with its priority and mitigation\n"
        "3. Include kubectl commands for: pod status, logs, restart, "
        "describe, top\n"
        "4. Alert response section for each alert type "
        "(latency, error rate)\n"
        "5. Dependency health checks: how to verify each upstream is OK\n"
        "6. Escalation path using the service's alertChannels\n"
    )

    return (
        f"{header}\n\n## Services\n\n{_services_section(ctxs)}\n\n"
        f"{template}\n{reqs}\n"
        f"{_output_format_section(n, 'RUNBOOK', ctxs)}"
    )


def build_single_service_runbook_prompt(ctx: Dict) -> str:
    """Build runbook prompt for a single service."""
    service_name = ctx["name"]
    tier = ctx["criticality"]
    header = (
        f"Generate 1 operational runbook in Markdown for "
        f"the {service_name} microservice ({tier} criticality).\n\n"
        "The runbook covers: service overview, SLOs, alert response, "
        "K8s commands, dependencies, risks, and escalation."
    )

    template = (
        "## Reference Template\n\n"
        "```markdown\n"
        "# SERVICE_NAME Operational Runbook\n\n"
        "## Service Overview\n"
        "| Field | Value |\n"
        "|-------|-------|\n"
        "| Language | LANG |\n"
        "| Criticality | TIER |\n"
        "| Owner | OWNER |\n"
        "| Port | PORT |\n\n"
        "## SLOs\n"
        "| Metric | Target |\n"
        "|--------|--------|\n"
        "| Availability | X% |\n"
        "| Latency P99 | Yms |\n\n"
        "## Alert Response\n"
        "### SERVICE_NAMELatencyP99High\n"
        "**Severity**: warning | **Threshold**: ... \n"
        "**Steps**: 1. Check... 2. Scale... 3. Escalate...\n\n"
        "## Kubernetes Commands\n"
        "```bash\n"
        "kubectl get pods -l app=SERVICE_NAME -n online-boutique\n"
        "kubectl logs -l app=SERVICE_NAME -n online-boutique --tail=100\n"
        "kubectl rollout restart deployment/SERVICE_NAME -n online-boutique\n"
        "```\n\n"
        "## Dependencies\n"
        "...\n\n"
        "## Escalation\n"
        "1. On-call: CHANNEL\n"
        "2. Team lead: OWNER\n"
        "```\n"
    )

    reqs = (
        "## Requirements\n\n"
        "1. Include all SLO targets from the service context\n"
        "2. List every risk with its priority and mitigation\n"
        "3. Include kubectl commands for: pod status, logs, restart, "
        "describe, top\n"
        "4. Alert response section for each alert type "
        "(latency, error rate)\n"
        "5. Dependency health checks: how to verify each upstream is OK\n"
        "6. Escalation path using the service's alertChannels\n"
    )

    return (
        f"{header}\n\n## Service\n\n{_format_service_block(ctx, 1)}\n\n"
        f"{template}\n{reqs}\n"
        f"{_output_format_section(1, 'RUNBOOK', [ctx])}"
    )


# =============================================================================
# UTILITY PROMPT BUILDERS (load, verify, summary)
# =============================================================================


def build_load_prompt() -> str:
    """Prompt for importing generated artifacts to the Grafana stack."""
    output = str(OUTPUT_DIR)
    return (
        "Import all generated observability artifacts to the local "
        "Grafana/observability stack.\n\n"
        f"## Artifact Directory\n\n{output}\n\n"
        "## Steps\n\n"
        "### 1. Import Grafana Dashboards\n"
        f"For each JSON file in {output}/dashboards/:\n"
        "```bash\n"
        "for f in " + output + "/dashboards/*.json; do\n"
        '  echo "Importing $(basename $f)..."\n'
        "  DASH=$(cat \"$f\")\n"
        "  curl -s -X POST -H 'Content-Type: application/json' "
        "-u admin:admin \\\n"
        '    -d "{\\\"dashboard\\\": $DASH, \\\"overwrite\\\": true}" \\\n'
        "    http://localhost:3000/api/dashboards/db\n"
        "done\n"
        "```\n\n"
        "### 2. Validate PrometheusRules\n"
        f"For each YAML in {output}/prometheus-rules/:\n"
        "Parse with Python yaml.safe_load to confirm validity.\n\n"
        "### 3. Validate SLO Definitions\n"
        f"For each YAML in {output}/slo-definitions/:\n"
        "Parse with Python yaml.safe_load to confirm validity.\n\n"
        "### 4. Validate Notification Policies\n"
        f"For each YAML in {output}/notification-policies/:\n"
        "Parse with Python yaml.safe_load to confirm validity.\n\n"
        "### 5. Validate Loki Rules\n"
        f"For each YAML in {output}/loki-rules/:\n"
        "Parse with Python yaml.safe_load to confirm validity.\n\n"
        "## Output Format (JSON)\n"
        "```json\n"
        "{\n"
        '  "dashboards_imported": N,\n'
        '  "prometheus_rules_valid": N,\n'
        '  "slos_valid": N,\n'
        '  "notifications_valid": N,\n'
        '  "loki_rules_valid": N,\n'
        '  "errors": []\n'
        "}\n"
        "```\n"
    )


def build_verify_prompt() -> str:
    """Prompt for verifying artifact completeness and correctness."""
    output = str(OUTPUT_DIR)
    services_no_lg = [s for s in SERVICE_INFO if s != "loadgenerator"]
    all_services = list(SERVICE_INFO.keys())

    return (
        "Verify all observability artifacts were generated and loaded.\n\n"
        f"## Artifact Directory\n\n{output}\n\n"
        "## Checks\n\n"
        "### 1. File Existence\n"
        f"Dashboard JSON files for all 11 services: {', '.join(all_services)}\n"
        f"PrometheusRule YAMLs for 10 services (no loadgenerator): "
        f"{', '.join(services_no_lg)}\n"
        "SLO YAMLs for 10 services\n"
        "Notification policy YAMLs for 10 services\n"
        "Loki rule YAMLs for 10 services\n"
        f"Runbook MDs for all 11 services\n\n"
        "### 2. JSON Validity\n"
        "Parse every .json file with json.loads(). Report any parse errors.\n\n"
        "### 3. YAML Validity\n"
        "Parse every .yaml file with yaml.safe_load(). Report any errors.\n\n"
        "### 4. SLO Consistency\n"
        "For each service, compare:\n"
        "- PrometheusRule alert threshold vs SLO definition objective\n"
        "- Alert severity vs service criticality tier\n"
        "Report any mismatches.\n\n"
        "### 5. Grafana API Check\n"
        "Query Grafana for imported dashboards:\n"
        "```bash\n"
        "curl -s -u admin:admin "
        "'http://localhost:3000/api/search?type=dash-db' | "
        "python3 -c \"import sys,json; "
        "ds=json.load(sys.stdin); "
        'print(f"Dashboards found: {len(ds)}"); '
        "[print(f'  - {d[\"title\"]}') for d in ds "
        "if 'online-boutique' in str(d.get('tags',''))]\"\n"
        "```\n\n"
        "### 6. Coverage Matrix\n"
        "Print a table: service (rows) x artifact type (columns)\n"
        "Mark each cell with a checkmark or X.\n\n"
        "## Output Format (JSON)\n"
        "```json\n"
        "{\n"
        '  "total_expected": 62,\n'
        '  "total_found": N,\n'
        '  "json_valid": N,\n'
        '  "yaml_valid": N,\n'
        '  "slo_consistent": true/false,\n'
        '  "grafana_dashboards": N,\n'
        '  "coverage_percent": N,\n'
        '  "missing": []\n'
        "}\n"
        "```\n"
    )


def build_summary_prompt() -> str:
    """Prompt for generating the final execution report."""
    return (
        "Generate a summary report of the observability artifact "
        "generation demo.\n\n"
        "## Report Sections\n\n"
        "### 1. Execution Overview\n"
        "- Total tasks executed, success/failure counts\n"
        "- Total LLM cost across all tasks\n"
        "- Artifacts generated per tier\n\n"
        "### 2. Coverage Matrix\n"
        "Table showing service x artifact type with status:\n"
        "| Service | Dashboard | Alerts | SLO | Notify | Loki | Runbook |\n"
        "| ... | ... |\n\n"
        "### 3. Artifact Statistics\n"
        "- Total file count and size per artifact type\n"
        "- Average file size per type\n\n"
        "### 4. Key Findings\n"
        "- Any services with incomplete coverage\n"
        "- Any SLO consistency issues\n"
        "- Recommendations for production deployment\n\n"
        "## Output Format (JSON)\n"
        "```json\n"
        "{\n"
        '  "demo_complete": true,\n'
        '  "tasks_executed": N,\n'
        '  "artifacts_generated": N,\n'
        '  "coverage_percent": N,\n'
        '  "total_cost": "$X.XX",\n'
        '  "summary": "One-paragraph summary"\n'
        "}\n"
        "```\n"
    )


# =============================================================================
# TASK GENERATION
# =============================================================================

# Map artifact key to prompt builder function (batched, multi-service)
_PROMPT_BUILDERS = {
    "DASHBOARDS": build_dashboard_prompt,
    "DASHBOARD": build_dashboard_prompt,
    "ALERTS": build_alerts_prompt,
    "SLOS": build_slo_prompt,
    "NOTIFY": build_notification_prompt,
    "LOKI-RULES": build_loki_rules_prompt,
    "RUNBOOKS": build_runbook_prompt,
    "RUNBOOK": build_runbook_prompt,
}

# Map artifact key to single-service prompt builder function
_SINGLE_SERVICE_PROMPT_BUILDERS = {
    "DASHBOARDS": build_single_service_dashboard_prompt,
    "DASHBOARD": build_single_service_dashboard_prompt,
    "ALERTS": build_single_service_alerts_prompt,
    "SLOS": build_single_service_slo_prompt,
    "NOTIFY": build_single_service_notification_prompt,
    "LOKI-RULES": build_single_service_loki_rules_prompt,
    "RUNBOOKS": build_single_service_runbook_prompt,
    "RUNBOOK": build_single_service_runbook_prompt,
}

# Phase assignment by tier for per-service task decomposition
_TIER_TO_PHASE = {
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 4,
}


def _generate_batched_tasks(
    contexts: Dict[str, Dict],
    tiers: Dict[str, List[Dict]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Generate tasks batched by tier (original behavior).

    Returns (tasks, all_artifact_ids).
    """
    tasks: List[Dict[str, Any]] = []
    all_artifact_ids: List[str] = []

    for tc in TIER_CONFIGS:
        tier_name = tc["name"]
        tier_ctxs = tiers.get(tier_name, [])
        n = len(tier_ctxs)

        for artifact_key in tc["artifacts"]:
            task_id = f"OB-{tc['prefix']}-{artifact_key}"
            artifact_title = ARTIFACT_TITLES.get(artifact_key, artifact_key)

            builder = _PROMPT_BUILDERS.get(artifact_key)
            if builder:
                prompt = builder(tier_name, tier_ctxs)
            else:
                prompt = f"Generate {artifact_title} for {tier_name} tier."

            tasks.append({
                "id": task_id,
                "title": (
                    f"Generate {n} {artifact_title} ({tier_name} tier)"
                ),
                "type": "task",
                "phase": tc["phase"],
                "depends_on": list(tc["gate_deps"]),
                "package": "all",
                "prompt": prompt,
            })

            all_artifact_ids.append(task_id)

    return tasks, all_artifact_ids


def _generate_decomposed_tasks(
    contexts: Dict[str, Dict],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Generate 1 task per service (decomposed mode).

    This mode avoids truncation issues with GPT-4o-mini by generating
    smaller tasks that produce ~36 lines of output each instead of
    batching 3-4 services which can exceed the drafter's output limit.

    Returns (tasks, all_artifact_ids).
    """
    tasks: List[Dict[str, Any]] = []
    all_artifact_ids: List[str] = []

    # Standard artifacts (all services except loadgenerator)
    standard_artifacts = [
        "DASHBOARDS", "ALERTS", "SLOS", "NOTIFY", "LOKI-RULES", "RUNBOOKS"
    ]
    # Loadgenerator only gets dashboard and runbook
    loadgen_artifacts = ["DASHBOARD", "RUNBOOK"]

    # Track dashboard task IDs per tier for phase gating.
    # All critical services must complete their dashboards before high starts, etc.
    tier_dashboard_ids: Dict[str, List[str]] = {
        "critical": [], "high": [], "medium": [], "low": []
    }

    # Process services in tier order to ensure dependencies are populated
    # correctly. Within each tier, sort alphabetically for deterministic output.
    tier_order = ["critical", "high", "medium", "low"]

    for tier in tier_order:
        services_in_tier = sorted(TIER_MAP.get(tier, []))
        phase = _TIER_TO_PHASE.get(tier, 3)

        for service_name in services_in_tier:
            ctx = contexts.get(service_name)
            if not ctx:
                continue

            # Choose artifact list based on service
            if service_name == "loadgenerator":
                artifacts = loadgen_artifacts
            else:
                artifacts = standard_artifacts

            for artifact_key in artifacts:
                # Task ID: OB-{SERVICE}-{ARTIFACT}
                # e.g., OB-FRONTEND-DASHBOARDS, OB-CHECKOUTSERVICE-ALERTS
                task_id = f"OB-{service_name.upper()}-{artifact_key}"
                artifact_title = ARTIFACT_TITLES.get(artifact_key, artifact_key)

                # Get single-service prompt builder
                builder = _SINGLE_SERVICE_PROMPT_BUILDERS.get(artifact_key)
                if builder:
                    prompt = builder(ctx)
                else:
                    prompt = f"Generate {artifact_title} for {service_name}."

                # Dependencies: tier-level gating on dashboard artifacts
                # - Critical tier (phase 1): no dependencies
                # - High tier (phase 2): depends on all critical dashboards
                # - Medium tier (phase 3): depends on all high dashboards
                # - Low tier (phase 4): depends on all medium dashboards
                depends_on: List[str] = []
                if tier == "high":
                    depends_on = list(tier_dashboard_ids["critical"])
                elif tier == "medium":
                    depends_on = list(tier_dashboard_ids["high"])
                elif tier == "low":
                    depends_on = list(tier_dashboard_ids["medium"])

                tasks.append({
                    "id": task_id,
                    "title": f"Generate {artifact_title} for {service_name}",
                    "type": "task",
                    "phase": phase,
                    "depends_on": depends_on,
                    "package": "all",
                    "prompt": prompt,
                    "service_name": service_name,  # For runner to extract
                })

                all_artifact_ids.append(task_id)

                # Track dashboard task IDs for tier gating
                if artifact_key in ("DASHBOARDS", "DASHBOARD"):
                    tier_dashboard_ids[tier].append(task_id)

    return tasks, all_artifact_ids


def generate_observability_tasks() -> List[Dict[str, Any]]:
    """Build the full observability task list with dependency graph.

    When DECOMPOSE_TO_SINGLE_SERVICE=True (default), generates 1 task per
    service per artifact type (~66 tasks for 11 services × 6 artifact types).
    This avoids truncation issues with GPT-4o-mini.

    When DECOMPOSE_TO_SINGLE_SERVICE=False, batches services by tier
    (original behavior, ~24 tasks total).

    Tier phases run sequentially (cost control); tasks within a tier
    run in parallel.
    """
    contexts = build_all_contexts()
    tiers = group_by_tier(contexts)

    tasks: List[Dict[str, Any]] = []
    all_artifact_ids: List[str] = []

    # Phase 0: Epic (auto-completed, not dispatched to workflow)
    tasks.append({
        "id": "OB-EPIC",
        "title": "Online Boutique Observability Artifact Generation",
        "type": "epic",
        "phase": 0,
        "depends_on": [],
        "package": "all",
        "prompt": (
            "Epic container for observability artifact generation across "
            "all 11 Online Boutique microservices. Generates dashboards, "
            "alerts, SLOs, notification policies, Loki rules, and runbooks "
            "derived from ProjectContext CRDs and source code analysis."
        ),
    })

    # Phases 1-4: Artifact generation (batched or decomposed)
    if DECOMPOSE_TO_SINGLE_SERVICE:
        artifact_tasks, all_artifact_ids = _generate_decomposed_tasks(contexts)
    else:
        artifact_tasks, all_artifact_ids = _generate_batched_tasks(
            contexts, tiers
        )
    tasks.extend(artifact_tasks)

    # Phase 5: Load artifacts
    tasks.append({
        "id": "OB-LOAD",
        "title": "Import observability artifacts to Grafana stack",
        "type": "task",
        "phase": 5,
        "depends_on": list(all_artifact_ids),
        "package": "spider",
        "prompt": build_load_prompt(),
    })

    # Phase 5: Verify artifacts
    tasks.append({
        "id": "OB-VERIFY",
        "title": "Verify artifact generation and loading",
        "type": "task",
        "phase": 5,
        "depends_on": ["OB-LOAD"],
        "package": "spider",
        "prompt": build_verify_prompt(),
    })

    # Phase 6: Summary report
    tasks.append({
        "id": "OB-SUMMARY",
        "title": "Generate execution summary and coverage report",
        "type": "task",
        "phase": 6,
        "depends_on": ["OB-VERIFY"],
        "package": "all",
        "prompt": build_summary_prompt(),
    })

    return tasks


# =============================================================================
# TASK STATE INFRASTRUCTURE (preserved from original)
# =============================================================================


def generate_trace_id() -> str:
    """Generate a valid 32-character trace ID."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generate a valid 16-character span ID."""
    return uuid.uuid4().hex[:16]


def create_task_json(
    task: Dict[str, Any], parent_span_id: str = None,
) -> Dict[str, Any]:
    """Create a ContextCore task state JSON structure."""
    now = datetime.now(timezone.utc).isoformat()
    trace_id = generate_trace_id()
    span_id = generate_span_id()

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
            "task.priority": (
                "high" if task["phase"] <= 2 else "medium"
            ),
            "task.prompt": task["prompt"],
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
    verbose: bool = False,
) -> Dict[str, Any]:
    """Create demo tasks in ContextCore state directory."""

    results = {
        "tasks_created": [],
        "tasks_skipped": [],
        "errors": [],
        "state_dir": str(STATE_DIR),
    }

    # Generate the observability task list
    source_tasks = generate_observability_tasks()

    # Filter tasks by phase if specified
    if phases:
        source_tasks = [
            t for t in source_tasks
            if t["phase"] in phases or t["phase"] == 0
        ]

    if verbose:
        print(f"Demo project: {DEMO_PROJECT}")
        print(f"State directory: {STATE_DIR}")
        print(f"Tasks to create: {len(source_tasks)}")
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
    for task in source_tasks:
        task_file = STATE_DIR / f"{task['id']}.json"

        if task_file.exists() and not clean:
            results["tasks_skipped"].append(task["id"])
            if verbose:
                print(f"  Skipped (exists): {task['id']}")
            continue

        parent_span = epic_span_id if task["type"] != "epic" else None
        task_json = create_task_json(task, parent_span)

        if task["type"] == "epic":
            epic_span_id = task_json["span_id"]

        if dry_run:
            deps = (
                f" (depends: {', '.join(task['depends_on'])})"
                if task['depends_on'] else ""
            )
            print(f"[DRY RUN] Phase {task['phase']}: {task['id']}")
            print(f"          {task['title']}{deps}")
            print()
        else:
            with open(task_file, 'w') as f:
                json.dump(task_json, f, indent=2)
            results["tasks_created"].append(task["id"])
            if verbose:
                print(f"  Created: {task['id']} - {task['title']}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Set up observability artifact generation tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--phases", type=int, nargs="+",
        help="Only create tasks for specific phases (0-6)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be created without creating",
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Remove existing demo tasks before creating",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List all demo tasks without creating",
    )

    args = parser.parse_args()

    if args.list:
        tasks = generate_observability_tasks()
        print("=" * 70)
        print("OBSERVABILITY ARTIFACT GENERATION TASKS")
        print("=" * 70)
        print()
        for task in tasks:
            deps = (
                f" (depends: {', '.join(task['depends_on'])})"
                if task['depends_on'] else ""
            )
            print(
                f"Phase {task['phase']}: [{task['package'].upper()}] "
                f"{task['id']}"
            )
            print(f"         {task['title']}{deps}")
            print()
        print(f"Total: {len(tasks)} tasks")
        return

    print("=" * 70)
    print("OBSERVABILITY ARTIFACT GENERATION: Task Setup")
    print("=" * 70)
    print()

    results = setup_demo_tasks(
        phases=args.phases,
        dry_run=args.dry_run,
        clean=args.clean,
        verbose=args.verbose or args.dry_run,
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
        print("  python demo/run_self_tracking_demo.py")
        print()
        print("Or execute via StartD8 SDK directly:")
        print(
            f"  python $STARTD8_SDK_ROOT/scripts/"
            f"run_contextcore_workflow.py \\"
        )
        print(
            f"      --from-contextcore --project-id {DEMO_PROJECT} --yes"
        )


if __name__ == "__main__":
    main()
