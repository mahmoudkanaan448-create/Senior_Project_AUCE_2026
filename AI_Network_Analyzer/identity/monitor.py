"""Identity / AD-style authentication monitoring from network flows."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from database.database import SessionLocal
from database.models import NetworkFlow

AUTH_PORTS = {22: "SSH", 23: "TELNET", 88: "KERBEROS", 389: "LDAP",
              636: "LDAPS", 3389: "RDP", 445: "SMB", 5985: "WINRM"}


def auth_anomalies(limit: int = 400) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        flows = db.query(NetworkFlow).order_by(NetworkFlow.flow_id.desc()).limit(limit).all()
    finally:
        db.close()

    by_src: Dict[str, List[NetworkFlow]] = defaultdict(list)
    for f in flows:
        if int(f.destination_port or 0) in AUTH_PORTS:
            by_src[f.source_ip or ""].append(f)

    findings = []
    for src, items in by_src.items():
        ports = {int(f.destination_port or 0) for f in items}
        dsts = {f.destination_ip for f in items}
        pkts = sum(int(f.packets or 0) for f in items)
        if pkts >= 40 or len(items) >= 12:
            findings.append({
                "source_ip": src,
                "service": ",".join(AUTH_PORTS[p] for p in ports if p in AUTH_PORTS),
                "attempts": len(items),
                "destinations": len(dsts),
                "packets": pkts,
                "type": "CredentialAbuse" if len(items) >= 12 else "AuthBurst",
                "severity": "High" if len(items) >= 12 else "Medium",
            })
        if {88, 389, 445} & ports and len(dsts) >= 3:
            findings.append({
                "source_ip": src,
                "service": "AD",
                "attempts": len(items),
                "destinations": len(dsts),
                "packets": pkts,
                "type": "ActiveDirectoryRecon",
                "severity": "High",
            })
    return findings
