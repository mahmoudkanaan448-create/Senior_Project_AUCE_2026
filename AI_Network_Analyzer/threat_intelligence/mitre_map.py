"""
MITRE ATT&CK mapping for AI-NDR attack labels.

Maps each detection label to primary tactic(s) and technique ID(s).
Additive enrichment only – never changes detection logic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Enterprise ATT&CK technique references (stable IDs)
_MITRE: Dict[str, Dict[str, Any]] = {
    "Normal": {
        "tactics": ["None"],
        "techniques": [],
        "summary": "Benign traffic – no ATT&CK mapping.",
    },
    "DoS": {
        "tactics": ["Impact"],
        "techniques": [
            {"id": "T1498", "name": "Network Denial of Service"},
            {"id": "T1499", "name": "Endpoint Denial of Service"},
        ],
        "summary": "Denial-of-service style traffic flooding a service or host.",
    },
    "DDoS": {
        "tactics": ["Impact"],
        "techniques": [
            {"id": "T1498", "name": "Network Denial of Service"},
            {"id": "T1498.001", "name": "Direct Network Flood"},
        ],
        "summary": "Distributed denial-of-service across many sources.",
    },
    "PortScan": {
        "tactics": ["Discovery", "Reconnaissance"],
        "techniques": [
            {"id": "T1046", "name": "Network Service Discovery"},
            {"id": "T1595.001", "name": "Scanning IP Blocks"},
        ],
        "summary": "Active scanning to discover open services.",
    },
    "BruteForce": {
        "tactics": ["Credential Access"],
        "techniques": [
            {"id": "T1110", "name": "Brute Force"},
            {"id": "T1110.001", "name": "Password Guessing"},
        ],
        "summary": "Repeated authentication attempts against an account/service.",
    },
    "SQLInjection": {
        "tactics": ["Initial Access", "Execution"],
        "techniques": [
            {"id": "T1190", "name": "Exploit Public-Facing Application"},
            {"id": "T1059", "name": "Command and Scripting Interpreter"},
        ],
        "summary": "Injection against a database-backed application.",
    },
    "WebAttack": {
        "tactics": ["Initial Access"],
        "techniques": [
            {"id": "T1190", "name": "Exploit Public-Facing Application"},
            {"id": "T1505", "name": "Server Software Component"},
        ],
        "summary": "Web application exploit or malicious HTTP payload.",
    },
    "Botnet": {
        "tactics": ["Command and Control", "Impact"],
        "techniques": [
            {"id": "T1071", "name": "Application Layer Protocol"},
            {"id": "T1584", "name": "Compromise Infrastructure"},
        ],
        "summary": "Bot-like C2 or coordinated malicious traffic.",
    },
    "Infiltration": {
        "tactics": ["Lateral Movement", "Collection"],
        "techniques": [
            {"id": "T1021", "name": "Remote Services"},
            {"id": "T1005", "name": "Data from Local System"},
        ],
        "summary": "Internal movement / data access after foothold.",
    },
    "Malware": {
        "tactics": ["Execution", "Persistence"],
        "techniques": [
            {"id": "T1204", "name": "User Execution"},
            {"id": "T1059", "name": "Command and Scripting Interpreter"},
        ],
        "summary": "Malware-related traffic patterns.",
    },
    "Ransomware": {
        "tactics": ["Impact"],
        "techniques": [
            {"id": "T1486", "name": "Data Encrypted for Impact"},
            {"id": "T1490", "name": "Inhibit System Recovery"},
        ],
        "summary": "Ransomware encryption / recovery disruption indicators.",
    },
    "Exfiltration": {
        "tactics": ["Exfiltration"],
        "techniques": [
            {"id": "T1041", "name": "Exfiltration Over C2 Channel"},
            {"id": "T1048", "name": "Exfiltration Over Alternative Protocol"},
        ],
        "summary": "Unusual outbound data volume or destination.",
    },
    "LateralMovement": {
        "tactics": ["Lateral Movement"],
        "techniques": [
            {"id": "T1021", "name": "Remote Services"},
            {"id": "T1570", "name": "Lateral Tool Transfer"},
        ],
        "summary": "Internal host-to-host movement using admin services.",
    },
    "C2": {
        "tactics": ["Command and Control"],
        "techniques": [
            {"id": "T1071", "name": "Application Layer Protocol"},
            {"id": "T1573", "name": "Encrypted Channel"},
        ],
        "summary": "Command-and-control beaconing or suspicious DNS/TLS.",
    },
    "PrivilegeEscalation": {
        "tactics": ["Privilege Escalation"],
        "techniques": [
            {"id": "T1068", "name": "Exploitation for Privilege Escalation"},
        ],
        "summary": "Burst of privileged internal protocol access.",
    },
    "Insider": {
        "tactics": ["Collection", "Exfiltration"],
        "techniques": [
            {"id": "T1074", "name": "Data Staged"},
            {"id": "T1530", "name": "Data from Cloud Storage"},
        ],
        "summary": "Insider-threat style deviation from a trusted host baseline.",
    },
    "ConceptDrift": {
        "tactics": ["Discovery"],
        "techniques": [
            {"id": "T1046", "name": "Network Service Discovery"},
        ],
        "summary": "Host traffic drifted from its learned behavioral baseline.",
    },
    "Unknown": {
        "tactics": ["Unknown"],
        "techniques": [
            {"id": "T1105", "name": "Ingress Tool Transfer"},
        ],
        "summary": "Unclassified anomalous traffic – review manually.",
    },
}

_BASE_URL = "https://attack.mitre.org/techniques/"


def _normalize_label(label: Optional[str]) -> str:
    if not label:
        return "Unknown"
    key = str(label).strip()
    if key in _MITRE:
        return key
    # Soft aliases
    aliases = {
        "dos": "DoS",
        "ddos": "DDoS",
        "port scan": "PortScan",
        "port_scan": "PortScan",
        "brute force": "BruteForce",
        "brute_force": "BruteForce",
        "sql injection": "SQLInjection",
        "web attack": "WebAttack",
        "attack": "Unknown",
    }
    return aliases.get(key.lower(), "Unknown" if key.lower() != "normal" else "Normal")


def map_attack_to_mitre(label: Optional[str]) -> Dict[str, Any]:
    """Return MITRE ATT&CK enrichment for an attack label."""
    key = _normalize_label(label)
    entry = _MITRE.get(key, _MITRE["Unknown"])
    techniques = list(entry.get("techniques") or [])
    enriched = []
    for t in techniques:
        tid = t["id"]
        # Sub-techniques use slash in URL: T1498/001
        url_id = tid.replace(".", "/")
        enriched.append({
            "id": tid,
            "name": t["name"],
            "url": f"{_BASE_URL}{url_id}/",
        })
    primary = enriched[0] if enriched else None
    return {
        "attack_label": key,
        "tactics": list(entry.get("tactics") or []),
        "techniques": enriched,
        "technique_ids": [t["id"] for t in enriched],
        "primary_technique": primary["id"] if primary else "",
        "primary_technique_name": primary["name"] if primary else "",
        "summary": entry.get("summary", ""),
        "mitre_url": primary["url"] if primary else "https://attack.mitre.org/",
    }


def format_mitre_short(label: Optional[str]) -> str:
    """One-line string for Telegram / banners."""
    m = map_attack_to_mitre(label)
    ids = ", ".join(m["technique_ids"][:3]) or "n/a"
    tactics = ", ".join(m["tactics"][:2])
    return f"MITRE: {tactics} | {ids}"


def list_all_mappings() -> List[Dict[str, Any]]:
    """All label → MITRE rows for dashboard tables."""
    rows = []
    for label in _MITRE:
        m = map_attack_to_mitre(label)
        rows.append({
            "Attack Label": m["attack_label"],
            "Tactics": ", ".join(m["tactics"]),
            "Techniques": ", ".join(m["technique_ids"]),
            "Primary": m["primary_technique_name"],
            "Summary": m["summary"],
        })
    return rows
