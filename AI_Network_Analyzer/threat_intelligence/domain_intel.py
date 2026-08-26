"""Domain reputation + hash lookup (heuristic + optional VirusTotal)."""

from __future__ import annotations

import hashlib
import os
from typing import Any, Dict

SUSPICIOUS_TLDS = {".xyz", ".top", ".gq", ".tk", ".ml", ".cf", ".ru", ".cn", ".click", ".zip"}
DGA_HINTS = ("xn--",)


def score_domain(domain: str) -> Dict[str, Any]:
    d = (domain or "").strip().lower().rstrip(".")
    if not d:
        return {"domain": "", "score": 0, "reputation": "unknown", "flags": []}
    flags = []
    score = 20
    if any(d.endswith(t) for t in SUSPICIOUS_TLDS):
        flags.append("suspicious_tld")
        score += 25
    labels = d.split(".")
    if labels and len(labels[0]) >= 18:
        flags.append("long_label")
        score += 15
    if labels and sum(c.isdigit() for c in labels[0]) > 6:
        flags.append("dga_like")
        score += 30
    if any(h in d for h in DGA_HINTS):
        flags.append("punycode")
        score += 10
    if len(d) > 60:
        flags.append("possible_tunnel")
        score += 20
    score = min(100, score)
    rep = "malicious" if score >= 70 else "suspicious" if score >= 45 else "benign"
    return {"domain": d, "score": score, "reputation": rep, "flags": flags}


def lookup_hash(file_hash: str) -> Dict[str, Any]:
    """Local + optional VirusTotal hash reputation."""
    h = (file_hash or "").strip().lower()
    out: Dict[str, Any] = {"hash": h, "algo": _algo(h), "reputation": "unknown", "source": "local"}
    if not h:
        return out
    key = os.getenv("VIRUSTOTAL_API_KEY", "")
    if not key:
        return out
    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://www.virustotal.com/api/v3/files/{h}",
            headers={"x-apikey": key, "User-Agent": "AI-NDR/2.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            import json
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        stats = ((data.get("data") or {}).get("attributes") or {}).get("last_analysis_stats") or {}
        mal = int(stats.get("malicious") or 0)
        out["vt_malicious"] = mal
        out["source"] = "virustotal"
        out["reputation"] = "malicious" if mal >= 3 else "suspicious" if mal >= 1 else "benign"
    except Exception as exc:
        out["error"] = str(exc)
    return out


def _algo(h: str) -> str:
    n = len(h)
    if n == 32:
        return "md5"
    if n == 40:
        return "sha1"
    if n == 64:
        return "sha256"
    return "unknown"


def sha256_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()
