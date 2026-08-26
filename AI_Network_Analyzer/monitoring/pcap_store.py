"""Save PCAP evidence for high-severity incidents (forensics)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from config import CAPTURED_DATA_DIR


def save_packet_dicts(packets: List[dict], *, source_ip: str = "", alert_id: Optional[int] = None) -> Optional[str]:
    """Best-effort wrpcap. Returns saved path or None."""
    if not packets:
        return None
    CAPTURED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_ip = (source_ip or "unknown").replace(":", "_")
    path = CAPTURED_DATA_DIR / f"incident_{safe_ip}_{stamp}.pcap"
    try:
        from scapy.all import IP, TCP, UDP, Ether, wrpcap
        scapy_pkts = []
        for p in packets[:500]:
            try:
                pkt = Ether() / IP(src=p.get("src_ip"), dst=p.get("dst_ip"))
                sport = int(p.get("src_port") or 0)
                dport = int(p.get("dst_port") or 0)
                proto = p.get("protocol", 6)
                if int(proto) == 17:
                    pkt = pkt / UDP(sport=sport, dport=dport)
                else:
                    pkt = pkt / TCP(sport=sport, dport=dport)
                scapy_pkts.append(pkt)
            except Exception:
                continue
        if not scapy_pkts:
            return None
        wrpcap(str(path), scapy_pkts)
        _record(str(path), source_ip, alert_id, len(scapy_pkts))
        return str(path)
    except Exception:
        # Fallback: JSONL evidence if Scapy wrpcap unavailable
        jpath = path.with_suffix(".jsonl")
        jpath.write_text("\n".join(str(p) for p in packets[:200]), encoding="utf-8")
        _record(str(jpath), source_ip, alert_id, len(packets))
        return str(jpath)


def _record(path: str, source_ip: str, alert_id: Optional[int], count: int) -> None:
    try:
        from database.database import SessionLocal
        from database.models import PcapEvidence
        db = SessionLocal()
        try:
            db.add(PcapEvidence(path=path, source_ip=source_ip, alert_id=alert_id, packet_count=count))
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


def list_evidence(limit: int = 50) -> List[dict[str, Any]]:
    try:
        from database.database import SessionLocal
        from database.models import PcapEvidence
        db = SessionLocal()
        try:
            rows = db.query(PcapEvidence).order_by(PcapEvidence.evidence_id.desc()).limit(limit).all()
            return [
                {
                    "id": r.evidence_id,
                    "path": r.path,
                    "source_ip": r.source_ip,
                    "alert_id": r.alert_id,
                    "packets": r.packet_count,
                    "time": str(r.created_at),
                }
                for r in rows
            ]
        finally:
            db.close()
    except Exception:
        return []
