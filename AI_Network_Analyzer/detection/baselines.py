"""Per-host behavioral baselines + simple concept-drift score."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from database.database import SessionLocal
from database.orm import ensure_models

_m = ensure_models()
HostBaseline = _m.HostBaseline


def update_baseline(ip: str, packet_rate: float, byte_rate: float, port: int) -> Dict[str, Any]:
    if not ip:
        return {}
    db = SessionLocal()
    try:
        row = db.query(HostBaseline).filter(HostBaseline.ip_address == ip).first()
        if row is None:
            row = HostBaseline(
                ip_address=ip,
                avg_packet_rate=packet_rate,
                avg_byte_rate=byte_rate,
                typical_ports=str(port) if port else "",
                samples=1,
                drift_score=0.0,
            )
            db.add(row)
            db.commit()
            return {"ip": ip, "drift_score": 0.0, "samples": 1, "new": True}

        n = max(1, int(row.samples or 1))
        # Exponential moving average (dynamic baseline)
        alpha = 0.15
        row.avg_packet_rate = (1 - alpha) * float(row.avg_packet_rate or 0) + alpha * float(packet_rate or 0)
        row.avg_byte_rate = (1 - alpha) * float(row.avg_byte_rate or 0) + alpha * float(byte_rate or 0)
        ports = [p for p in (row.typical_ports or "").split(",") if p]
        if port and str(port) not in ports:
            ports.append(str(port))
        row.typical_ports = ",".join(ports[-20:])
        # Drift: relative deviation from baseline
        base = max(1.0, float(row.avg_packet_rate or 1))
        drift = abs(float(packet_rate or 0) - base) / base
        row.drift_score = round(float(drift), 3)
        row.samples = n + 1
        row.updated_at = datetime.utcnow()
        db.commit()
        return {
            "ip": ip,
            "drift_score": row.drift_score,
            "samples": row.samples,
            "avg_packet_rate": row.avg_packet_rate,
            "drifted": row.drift_score >= 2.5 and row.samples >= 8,
        }
    finally:
        db.close()


def list_drifted(limit: int = 30) -> list:
    db = SessionLocal()
    try:
        rows = (
            db.query(HostBaseline)
            .filter(HostBaseline.drift_score >= 2.0)
            .order_by(HostBaseline.drift_score.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "ip": r.ip_address,
                "drift": r.drift_score,
                "avg_pkt": round(r.avg_packet_rate or 0, 2),
                "samples": r.samples,
                "updated": str(r.updated_at),
            }
            for r in rows
        ]
    finally:
        db.close()
