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
from typing import List, Dict, Any, Optional
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
    """Build the standard output-format section for a prompt."""
    names = ", ".join(ctx["name"] for ctx in service_contexts)
    return (
        "## Output Format\n\n"
        f"Output {n} artifact(s), each separated by a delimiter line:\n\n"
        f"--- {delimiter}: {{service_name}} ---\n\n"
        f"Where {{service_name}} is one of: {names}\n\n"
        "Output ONLY the raw content between delimiters. "
        "No markdown code fences inside the delimited sections.\n"
    )


# =============================================================================
# PROMPT BUILDERS (one per artifact type)
# =============================================================================


def build_dashboard_prompt(tier_name: str, ctxs: List[Dict]) -> str:
    n = len(ctxs)
    header = (
        f"Generate {n} Grafana dashboard JSON file(s) for "
        f"{tier_name}-tier Online Boutique microservices.\n\n"
        "Each dashboard must include panels for: request rate (QPS), "
        "latency percentiles (P50/P95/P99), error rate (%), "
        "availability (%), resource saturation (CPU/memory), "
        "and dependency health."
    )

    template = (
        "## Reference Template\n\n"
        'Use this skeleton as a starting point for each dashboard:\n\n'
        '```json\n'
        '{\n'
        '  "title": "SERVICE_NAME Service Dashboard",\n'
        '  "uid": "SERVICE_NAME-dashboard",\n'
        '  "tags": ["online-boutique", "SERVICE_NAME"],\n'
        '  "timezone": "browser",\n'
        '  "refresh": "30s",\n'
        '  "time": {"from": "now-1h", "to": "now"},\n'
        '  "templating": {"list": [\n'
        '    {"name": "namespace", "type": "query", "datasource": "prometheus",\n'
        '     "query": "label_values(namespace)"}\n'
        '  ]},\n'
        '  "panels": [\n'
        '    {"title": "Request Rate", "type": "stat",\n'
        '     "gridPos": {"h": 4, "w": 6, "x": 0, "y": 0},\n'
        '     "targets": [{"expr": "sum(rate(grpc_server_handled_total{...}[5m]))"}]}\n'
        '  ]\n'
        '}\n'
        '```\n'
    )

    reqs = (
        "## Requirements\n\n"
        "1. Dashboard UID: {service_name}-dashboard\n"
        "2. Prometheus metrics: grpc_server_handled_total, "
        "grpc_server_handling_seconds_bucket, "
        "container_cpu_usage_seconds_total, "
        "container_memory_working_set_bytes\n"
        "3. For HTTP services (frontend): use http_server_request_duration"
        "_seconds_bucket and http_server_requests_total\n"
        "4. Organize panels into rows: RED metrics, saturation, "
        "dependency health\n"
        "5. Set panel thresholds from each service's SLO targets\n"
        "6. 24-column grid layout; panels at readable sizes\n"
        "7. Include error-budget burn-down panel for services with SLOs\n"
    )

    return (
        f"{header}\n\n## Services\n\n{_services_section(ctxs)}\n\n"
        f"{template}\n{reqs}\n"
        f"{_output_format_section(n, 'DASHBOARD', ctxs)}"
    )


def build_alerts_prompt(tier_name: str, ctxs: List[Dict]) -> str:
    n = len(ctxs)
    header = (
        f"Generate {n} PrometheusRule YAML file(s) for "
        f"{tier_name}-tier Online Boutique microservices.\n\n"
        "Each file defines alerting rules derived from the service's SLO "
        "targets: a latency P99 alert and an error rate alert at minimum."
    )

    template = (
        "## Reference Template\n\n"
        "```yaml\n"
        "apiVersion: monitoring.coreos.com/v1\n"
        "kind: PrometheusRule\n"
        "metadata:\n"
        "  name: SERVICE_NAME-rules\n"
        "  namespace: online-boutique\n"
        "  labels:\n"
        "    app: SERVICE_NAME\n"
        "spec:\n"
        "  groups:\n"
        "    - name: SERVICE_NAME.slo.rules\n"
        "      rules:\n"
        "        - alert: SERVICE_NAMELatencyP99High\n"
        "          expr: |\n"
        "            histogram_quantile(0.99,\n"
        "              sum(rate(grpc_server_handling_seconds_bucket\n"
        '                {grpc_service=~".*SERVICE_NAME.*"}[5m])) by (le)\n'
        "            ) > THRESHOLD\n"
        "          for: 5m\n"
        "          labels:\n"
        "            severity: warning\n"
        "          annotations:\n"
        "            summary: SERVICE_NAME P99 latency above SLO\n"
        "        - alert: SERVICE_NAMEErrorRateHigh\n"
        "          expr: |\n"
        "            sum(rate(grpc_server_handled_total\n"
        '              {grpc_code!="OK",grpc_service=~".*SERVICE_NAME.*"}[5m]))\n'
        "            / sum(rate(grpc_server_handled_total\n"
        '              {grpc_service=~".*SERVICE_NAME.*"}[5m])) > THRESHOLD\n'
        "          for: 5m\n"
        "```\n"
    )

    reqs = (
        "## Requirements\n\n"
        "1. Derive alert thresholds from each service's SLO targets above\n"
        "2. For latency: trigger when P99 exceeds the latencyP99 SLO value\n"
        "3. For errors: trigger when error rate exceeds (1 - availability/100)\n"
        "4. Set severity labels: critical-tier services get 'critical', "
        "others get 'warning'\n"
        "5. Include 'for' duration: 5m for critical, 10m for others\n"
        "6. Add runbook_url annotation pointing to the service runbook\n"
        "7. For HTTP services (frontend), use http_server_* metrics\n"
    )

    return (
        f"{header}\n\n## Services\n\n{_services_section(ctxs)}\n\n"
        f"{template}\n{reqs}\n"
        f"{_output_format_section(n, 'PROMETHEUS_RULE', ctxs)}"
    )


def build_slo_prompt(tier_name: str, ctxs: List[Dict]) -> str:
    n = len(ctxs)
    header = (
        f"Generate {n} SLO definition YAML file(s) for "
        f"{tier_name}-tier Online Boutique microservices.\n\n"
        "Each defines availability target, error budget, "
        "and multi-window burn-rate alerting windows."
    )

    template = (
        "## Reference Template\n\n"
        "```yaml\n"
        "apiVersion: sloth.slok.dev/v1\n"
        "kind: PrometheusServiceLevel\n"
        "metadata:\n"
        "  name: SERVICE_NAME-slo\n"
        "  namespace: online-boutique\n"
        "spec:\n"
        "  service: SERVICE_NAME\n"
        "  labels:\n"
        "    team: OWNER\n"
        "    tier: TIER\n"
        "  slos:\n"
        "    - name: availability\n"
        "      objective: 99.95\n"
        "      sli:\n"
        "        events:\n"
        "          errorQuery: |\n"
        '            sum(rate(grpc_server_handled_total{grpc_code!="OK",\n'
        '              grpc_service=~".*SERVICE_NAME.*"}[{{.window}}]))\n'
        "          totalQuery: |\n"
        "            sum(rate(grpc_server_handled_total{\n"
        '              grpc_service=~".*SERVICE_NAME.*"}[{{.window}}]))\n'
        "      alerting:\n"
        "        pageAlert: {}\n"
        "        ticketAlert: {}\n"
        "    - name: latency\n"
        "      objective: 99.0\n"
        "      sli:\n"
        "        events:\n"
        "          errorQuery: |\n"
        "            sum(rate(grpc_server_handling_seconds_bucket{\n"
        '              le="LATENCY_THRESHOLD",\n'
        '              grpc_service=~".*SERVICE_NAME.*"}[{{.window}}]))\n'
        "          totalQuery: |\n"
        "            sum(rate(grpc_server_handling_seconds_count{\n"
        '              grpc_service=~".*SERVICE_NAME.*"}[{{.window}}]))\n'
        "```\n"
    )

    reqs = (
        "## Requirements\n\n"
        "1. Set availability objective from each service's SLO availability\n"
        "2. Set latency threshold from each service's latencyP99 target\n"
        "3. Error budget = 100 - availability (e.g., 99.95 -> 0.05%)\n"
        "4. Include burn-rate windows: 1h (page), 6h (page), 1d (ticket), "
        "3d (ticket)\n"
        "5. Use the service's team/owner in labels\n"
        "6. For HTTP services, use http_server_* metrics in SLI queries\n"
    )

    return (
        f"{header}\n\n## Services\n\n{_services_section(ctxs)}\n\n"
        f"{template}\n{reqs}\n"
        f"{_output_format_section(n, 'SLO', ctxs)}"
    )


def build_notification_prompt(tier_name: str, ctxs: List[Dict]) -> str:
    n = len(ctxs)
    header = (
        f"Generate {n} notification policy YAML file(s) for "
        f"{tier_name}-tier Online Boutique microservices.\n\n"
        "Route alerts by criticality: critical -> PagerDuty, "
        "high -> Slack #incidents, medium -> email, low -> log only."
    )

    template = (
        "## Reference Template\n\n"
        "```yaml\n"
        "apiVersion: alerting.grafana.com/v1\n"
        "kind: NotificationPolicy\n"
        "metadata:\n"
        "  name: SERVICE_NAME-notifications\n"
        "  namespace: online-boutique\n"
        "spec:\n"
        "  service: SERVICE_NAME\n"
        "  criticality: TIER\n"
        "  routes:\n"
        "    - matchers:\n"
        '        - name: service\n'
        '          value: SERVICE_NAME\n'
        '        - name: severity\n'
        '          value: critical\n'
        "      receiver: pagerduty-p1\n"
        "      repeatInterval: 5m\n"
        "    - matchers:\n"
        '        - name: service\n'
        '          value: SERVICE_NAME\n'
        '        - name: severity\n'
        '          value: warning\n'
        "      receiver: slack-incidents\n"
        "      repeatInterval: 30m\n"
        "  contactPoints:\n"
        "    - name: pagerduty-p1\n"
        "      type: pagerduty\n"
        "    - name: slack-incidents\n"
        "      type: slack\n"
        "      settings:\n"
        "        channel: online-boutique-alerts\n"
        "```\n"
    )

    reqs = (
        "## Requirements\n\n"
        "1. Use each service's alertChannels from the context above\n"
        "2. Critical-tier: PagerDuty for critical severity, Slack for warning\n"
        "3. High-tier: Slack for all severities\n"
        "4. Medium-tier: email for critical, Slack for warning\n"
        "5. Include escalation: if not ack'd in 15min, escalate one level\n"
        "6. Set mute timings for maintenance windows (weekdays 2-4am UTC)\n"
        "7. Include the service owner in notification metadata\n"
    )

    return (
        f"{header}\n\n## Services\n\n{_services_section(ctxs)}\n\n"
        f"{template}\n{reqs}\n"
        f"{_output_format_section(n, 'NOTIFICATION', ctxs)}"
    )


def build_loki_rules_prompt(tier_name: str, ctxs: List[Dict]) -> str:
    n = len(ctxs)
    header = (
        f"Generate {n} Loki recording rule YAML file(s) for "
        f"{tier_name}-tier Online Boutique microservices.\n\n"
        "Derive Prometheus metrics from structured JSON logs: "
        "error counts, latency from log timestamps, request counts."
    )

    template = (
        "## Reference Template\n\n"
        "```yaml\n"
        "apiVersion: loki.grafana.com/v1\n"
        "kind: RecordingRule\n"
        "metadata:\n"
        "  name: SERVICE_NAME-loki-rules\n"
        "  namespace: online-boutique\n"
        "spec:\n"
        "  groups:\n"
        "    - name: SERVICE_NAME.log_metrics\n"
        "      interval: 1m\n"
        "      rules:\n"
        "        - record: SERVICE_NAME:log_errors:rate1m\n"
        "          expr: |\n"
        '            sum(rate({app="SERVICE_NAME"}\n'
        '              |= "error" | json | level="error" [1m]))\n'
        "        - record: SERVICE_NAME:log_requests:rate1m\n"
        "          expr: |\n"
        '            sum(rate({app="SERVICE_NAME"}\n'
        "              | json [1m]))\n"
        "        - record: SERVICE_NAME:log_latency_seconds:avg1m\n"
        "          expr: |\n"
        '            avg(rate({app="SERVICE_NAME"}\n'
        '              | json | unwrap duration_ms [1m])) / 1000\n'
        "```\n"
    )

    lang_note = (
        "## Language-Specific Log Patterns\n\n"
        "- Go services: structured JSON with 'level', 'msg', 'duration_ms'\n"
        "- Node.js services: structured JSON with 'level', 'message', "
        "'responseTime'\n"
        "- Python services: structured JSON with 'levelname', 'message', "
        "'duration'\n"
        "- Java services: structured JSON with 'level', 'message', "
        "'elapsed_ms'\n"
        "- C# services: structured JSON with 'Level', 'Message', "
        "'ElapsedMilliseconds'\n\n"
    )

    reqs = (
        "## Requirements\n\n"
        "1. Use the correct log field names for each service's language\n"
        "2. Include error rate, request rate, and latency metrics\n"
        "3. Add a rule for log volume (bytes/sec) per service\n"
        "4. Include severity breakdown: count by log level\n"
        "5. Use 1m recording interval for all rules\n"
    )

    return (
        f"{header}\n\n## Services\n\n{_services_section(ctxs)}\n\n"
        f"{template}\n{lang_note}{reqs}\n"
        f"{_output_format_section(n, 'LOKI_RULE', ctxs)}"
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

# Map artifact key to prompt builder function
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


def generate_observability_tasks() -> List[Dict[str, Any]]:
    """Build the full observability task list with dependency graph.

    Returns 23 executable tasks + 1 auto-completed epic = 24 task dicts.
    Tier phases run sequentially (cost control); artifacts within a tier
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

    # Phases 1-4: Tier artifact generation
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
