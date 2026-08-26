"""
Specialist detectors – campaign/behavior rules on top of Hybrid AI labels.

Used for PortScan, DDoS, BruteForce, Botnet/C2, Exfil, Lateral Movement,
credential abuse. Complements the 5-model ensemble (does not replace it).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

AUTH_PORTS = {22, 23, 3389, 5900, 21, 445}
LATERAL_PORTS = {135, 139, 445, 3389, 22, 5985, 5986}
PRIVATE_PREFIXES = ("10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.",
                    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
                    "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.")


def _private(ip: str) -> bool:
    ip = ip or ""
    return ip.startswith(PRIVATE_PREFIXES) or ip.startswith("127.")


def detect_specialists(flow: Dict[str, Any], recent_flows: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
    """Return extra detections [{type, severity, reason, score}]."""
    findings: List[Dict[str, Any]] = []
    src = str(flow.get("source_ip") or flow.get("src_ip") or "")
    dst = str(flow.get("destination_ip") or flow.get("dst_ip") or "")
    dport = int(flow.get("destination_port") or flow.get("dst_port") or 0)
    pkt_rate = float(flow.get("packet_rate") or 0)
    bytes_total = float(flow.get("byte_count") or flow.get("bytes_total") or 0)
    packets = int(flow.get("packet_count") or flow.get("packets") or 0)
    syn = float((flow.get("features") or {}).get("syn_count") or 0)
    dns_q = str(flow.get("dns_query") or "")
    app = str(flow.get("app_protocol") or "")

    recent = recent_flows or []

    # Port scan: many distinct dest ports from same source
    if recent:
        ports = {int(f.get("destination_port") or f.get("dst_port") or 0) for f in recent if str(f.get("source_ip") or f.get("src_ip") or "") == src}
        dsts = {str(f.get("destination_ip") or f.get("dst_ip") or "") for f in recent if str(f.get("source_ip") or f.get("src_ip") or "") == src}
        if len(ports) >= 12:
            findings.append({"type": "PortScan", "severity": "High", "score": 8.2,
                             "reason": f"Source {src} hit {len(ports)} distinct ports / {len(dsts)} hosts"})

    # DDoS / flood
    if pkt_rate >= 200 or packets >= 400:
        findings.append({"type": "DDoS", "severity": "Critical", "score": 9.0,
                         "reason": f"Flood-like rate {pkt_rate:.1f} pkt/s ({packets} packets)"})
    elif pkt_rate >= 80:
        findings.append({"type": "DoS", "severity": "High", "score": 7.5,
                         "reason": f"High packet rate {pkt_rate:.1f} pkt/s"})

    # Brute force / credential abuse
    if dport in AUTH_PORTS and (packets >= 30 or syn >= 20):
        findings.append({"type": "BruteForce", "severity": "High", "score": 8.0,
                         "reason": f"Repeated auth attempts toward port {dport}"})

    # C2 / botnet beaconing: small regular flows
    if recent:
        src_flows = [f for f in recent if str(f.get("source_ip") or "") == src]
        if 8 <= len(src_flows) <= 40:
            sizes = [float(f.get("byte_count") or f.get("bytes_total") or 0) for f in src_flows]
            if sizes and max(sizes) < 1500 and (max(sizes) - min(sizes) < 400):
                findings.append({"type": "Botnet", "severity": "High", "score": 7.8,
                                 "reason": "Periodic similar-size flows (possible C2 beaconing)"})

    # Exfiltration: large outbound
    if bytes_total >= 5_000_000 and not _private(dst):
        findings.append({"type": "Exfiltration", "severity": "Critical", "score": 8.8,
                         "reason": f"Large outbound transfer {int(bytes_total)} bytes to {dst}"})

    # Lateral movement: private-to-private admin ports
    if _private(src) and _private(dst) and dport in LATERAL_PORTS and src != dst:
        findings.append({"type": "LateralMovement", "severity": "High", "score": 8.1,
                         "reason": f"Internal {src} → {dst}:{dport} (admin/lateral port)"})

    # DNS tunneling / DGA
    if dns_q and (len(dns_q) > 60 or app == "DNS"):
        from monitoring.dpi import _suspicious_dns
        if _suspicious_dns(dns_q):
            findings.append({"type": "C2", "severity": "High", "score": 7.6,
                             "reason": f"Suspicious DNS query {dns_q[:80]}"})

    # Privilege-escalation proxy: many unique dest admin ports from one internal host
    if recent and _private(src):
        admin_hits = [
            f for f in recent
            if str(f.get("source_ip") or "") == src
            and int(f.get("destination_port") or 0) in LATERAL_PORTS
        ]
        if len(admin_hits) >= 8:
            findings.append({"type": "PrivilegeEscalation", "severity": "High", "score": 7.4,
                             "reason": "Burst of internal admin-protocol access"})

    return findings


def kill_chain_stage(attack_type: str) -> str:
    mapping = {
        "PortScan": "Discovery",
        "BruteForce": "Credential Access",
        "SQLInjection": "Initial Access",
        "WebAttack": "Initial Access",
        "LateralMovement": "Lateral Movement",
        "PrivilegeEscalation": "Privilege Escalation",
        "Botnet": "Command and Control",
        "C2": "Command and Control",
        "Exfiltration": "Exfiltration",
        "Ransomware": "Impact",
        "DoS": "Impact",
        "DDoS": "Impact",
        "Malware": "Execution",
        "Infiltration": "Lateral Movement",
        "Insider": "Collection",
    }
    return mapping.get(attack_type, "Unknown")
