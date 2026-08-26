"""
SOAR playbook definitions – attack-type response recipes.

Each playbook lists ordered steps. The engine executes them safely;
unknown steps are skipped. Existing severity rules still apply as baseline.
"""

from __future__ import annotations

from typing import Any, Dict, List

# Severity floor for each playbook (Low/Medium/High/Critical)
PLAYBOOKS: Dict[str, Dict[str, Any]] = {
    "default": {
        "name": "Default Containment",
        "description": "Create alert, notify Telegram, local sound for Medium+.",
        "min_severity": "Medium",
        "steps": [
            {"action": "create_alert"},
            {"action": "local_notify"},
            {"action": "send_telegram"},
            {"action": "enrich_mitre"},
            {"action": "webhook"},
            {"action": "queue_online_sample"},
        ],
    },
    "PortScan": {
        "name": "Recon / PortScan Response",
        "description": "Alert + notify; temporary DB block on High+.",
        "min_severity": "Medium",
        "steps": [
            {"action": "create_alert"},
            {"action": "enrich_mitre"},
            {"action": "enrich_ti"},
            {"action": "local_notify"},
            {"action": "send_telegram"},
            {"action": "block_ip", "when_severity_at_least": "High"},
            {"action": "queue_online_sample"},
        ],
    },
    "DoS": {
        "name": "DoS Mitigation",
        "description": "Fast notify + block Critical sources.",
        "min_severity": "Medium",
        "steps": [
            {"action": "create_alert"},
            {"action": "enrich_mitre"},
            {"action": "local_notify"},
            {"action": "send_telegram"},
            {"action": "block_ip", "when_severity_at_least": "Critical"},
            {"action": "queue_online_sample"},
        ],
    },
    "DDoS": {
        "name": "DDoS Mitigation",
        "description": "Aggressive notify; block Critical; recommend scrubbing.",
        "min_severity": "High",
        "steps": [
            {"action": "create_alert"},
            {"action": "enrich_mitre"},
            {"action": "local_notify"},
            {"action": "send_telegram"},
            {"action": "block_ip", "when_severity_at_least": "Critical"},
            {"action": "queue_online_sample"},
        ],
    },
    "BruteForce": {
        "name": "Credential Attack Response",
        "description": "Alert + notify; block High+ sources.",
        "min_severity": "Medium",
        "steps": [
            {"action": "create_alert"},
            {"action": "enrich_mitre"},
            {"action": "local_notify"},
            {"action": "send_telegram"},
            {"action": "block_ip", "when_severity_at_least": "High"},
            {"action": "queue_online_sample"},
        ],
    },
    "SQLInjection": {
        "name": "Web SQLi Response",
        "description": "Alert SOC; enrich; block High+.",
        "min_severity": "Medium",
        "steps": [
            {"action": "create_alert"},
            {"action": "enrich_mitre"},
            {"action": "enrich_ti"},
            {"action": "local_notify"},
            {"action": "send_telegram"},
            {"action": "block_ip", "when_severity_at_least": "High"},
            {"action": "queue_online_sample"},
        ],
    },
    "WebAttack": {
        "name": "Web Attack Response",
        "description": "WAF-oriented notify and optional block.",
        "min_severity": "Medium",
        "steps": [
            {"action": "create_alert"},
            {"action": "enrich_mitre"},
            {"action": "local_notify"},
            {"action": "send_telegram"},
            {"action": "block_ip", "when_severity_at_least": "High"},
            {"action": "queue_online_sample"},
        ],
    },
    "Botnet": {
        "name": "Botnet / C2 Response",
        "description": "Quarantine path: notify + block High+.",
        "min_severity": "Medium",
        "steps": [
            {"action": "create_alert"},
            {"action": "enrich_mitre"},
            {"action": "enrich_ti"},
            {"action": "local_notify"},
            {"action": "send_telegram"},
            {"action": "block_ip", "when_severity_at_least": "High"},
            {"action": "queue_online_sample"},
        ],
    },
    "Infiltration": {
        "name": "Infiltration Response",
        "description": "High priority isolate path.",
        "min_severity": "High",
        "steps": [
            {"action": "create_alert"},
            {"action": "enrich_mitre"},
            {"action": "enrich_ti"},
            {"action": "local_notify"},
            {"action": "send_telegram"},
            {"action": "block_ip", "when_severity_at_least": "High"},
            {"action": "queue_online_sample"},
        ],
    },
    "Malware": {
        "name": "Malware Response",
        "description": "Contain host traffic; notify SOC.",
        "min_severity": "Medium",
        "steps": [
            {"action": "create_alert"},
            {"action": "enrich_mitre"},
            {"action": "local_notify"},
            {"action": "send_telegram"},
            {"action": "block_ip", "when_severity_at_least": "High"},
            {"action": "queue_online_sample"},
        ],
    },
    "Ransomware": {
        "name": "Ransomware IR",
        "description": "Immediate Critical path – notify + block.",
        "min_severity": "High",
        "steps": [
            {"action": "create_alert"},
            {"action": "enrich_mitre"},
            {"action": "local_notify"},
            {"action": "send_telegram"},
            {"action": "block_ip", "when_severity_at_least": "High"},
            {"action": "queue_online_sample"},
        ],
    },
    "Exfiltration": {
        "name": "Data Exfiltration Response",
        "description": "Critical outbound-data path: notify + timed block.",
        "min_severity": "High",
        "steps": [
            {"action": "create_alert"},
            {"action": "enrich_mitre"},
            {"action": "enrich_ti"},
            {"action": "local_notify"},
            {"action": "send_telegram"},
            {"action": "webhook"},
            {"action": "block_ip", "when_severity_at_least": "High", "duration": "24h"},
            {"action": "queue_online_sample"},
        ],
    },
    "LateralMovement": {
        "name": "Lateral Movement Response",
        "description": "Internal east-west containment.",
        "min_severity": "High",
        "steps": [
            {"action": "create_alert"},
            {"action": "enrich_mitre"},
            {"action": "local_notify"},
            {"action": "send_telegram"},
            {"action": "webhook"},
            {"action": "block_ip", "when_severity_at_least": "High", "duration": "1h"},
            {"action": "queue_online_sample"},
        ],
    },
    "C2": {
        "name": "C2 Containment",
        "description": "Beacon / DNS / TLS C2 path.",
        "min_severity": "High",
        "steps": [
            {"action": "create_alert"},
            {"action": "enrich_mitre"},
            {"action": "enrich_ti"},
            {"action": "local_notify"},
            {"action": "send_telegram"},
            {"action": "webhook"},
            {"action": "block_ip", "when_severity_at_least": "High", "duration": "24h"},
            {"action": "queue_online_sample"},
        ],
    },
    "PrivilegeEscalation": {
        "name": "Privilege Escalation Response",
        "description": "Investigate privileged internal access bursts.",
        "min_severity": "High",
        "steps": [
            {"action": "create_alert"},
            {"action": "enrich_mitre"},
            {"action": "local_notify"},
            {"action": "send_telegram"},
            {"action": "webhook"},
            {"action": "queue_online_sample"},
        ],
    },
    "Insider": {
        "name": "Insider Threat Response",
        "description": "UEBA deviation – notify, do not auto-block trusted assets.",
        "min_severity": "Medium",
        "steps": [
            {"action": "create_alert"},
            {"action": "enrich_mitre"},
            {"action": "local_notify"},
            {"action": "send_telegram"},
            {"action": "webhook"},
            {"action": "queue_online_sample"},
        ],
    },
}


def get_playbook(attack_label: str) -> Dict[str, Any]:
    """Resolve playbook for an attack label (fallback: default)."""
    key = (attack_label or "").strip()
    pb = PLAYBOOKS.get(key) or PLAYBOOKS["default"]
    return dict(pb)


def list_playbooks() -> List[Dict[str, Any]]:
    """Flat list for dashboard display."""
    rows = []
    for key, pb in PLAYBOOKS.items():
        rows.append({
            "Key": key,
            "Name": pb["name"],
            "Min Severity": pb.get("min_severity", "Medium"),
            "Steps": " → ".join(s["action"] for s in pb.get("steps", [])),
            "Description": pb.get("description", ""),
        })
    return rows
