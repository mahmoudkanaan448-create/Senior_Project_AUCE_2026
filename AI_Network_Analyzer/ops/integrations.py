"""Outbound company integrations: Splunk HEC, Elasticsearch, Jira. No email."""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from typing import Any, Dict


def fanout(event_type: str, payload: Dict[str, Any]) -> Dict[str, bool]:
    out = {
        "splunk": _splunk(event_type, payload),
        "elastic": _elastic(event_type, payload),
        "jira": False,
    }
    if event_type in ("alert", "incident") and str(payload.get("severity") or payload.get("priority") or "") in (
        "High", "Critical",
    ):
        out["jira"] = _jira(event_type, payload)
    return out


def _post(url: str, body: bytes, headers: Dict[str, str], timeout: float = 6.0) -> bool:
    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False


def _splunk(event_type: str, payload: Dict[str, Any]) -> bool:
    url = os.getenv("SPLUNK_HEC_URL") or ""
    token = os.getenv("SPLUNK_HEC_TOKEN") or ""
    if not url or not token:
        return False
    body = json.dumps({
        "event": {"product": "AI-NDR", "type": event_type, **payload},
        "sourcetype": "aindr:json",
        "source": "ai-network-analyzer",
    }).encode("utf-8")
    return _post(url, body, {
        "Authorization": f"Splunk {token}",
        "Content-Type": "application/json",
    })


def _elastic(event_type: str, payload: Dict[str, Any]) -> bool:
    base = (os.getenv("ELASTIC_URL") or "").rstrip("/")
    if not base:
        return False
    index = os.getenv("ELASTIC_INDEX") or "aindr-alerts"
    url = f"{base}/{index}/_doc"
    headers = {"Content-Type": "application/json"}
    user = os.getenv("ELASTIC_USER") or ""
    password = os.getenv("ELASTIC_PASSWORD") or ""
    api_key = os.getenv("ELASTIC_API_KEY") or ""
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"
    elif user:
        token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    body = json.dumps({"product": "AI-NDR", "type": event_type, **payload}, default=str).encode("utf-8")
    return _post(url, body, headers)


def _jira(event_type: str, payload: Dict[str, Any]) -> bool:
    base = (os.getenv("JIRA_URL") or "").rstrip("/")
    token = os.getenv("JIRA_TOKEN") or ""
    user = os.getenv("JIRA_USER") or ""
    project = os.getenv("JIRA_PROJECT") or "SOC"
    if not base or not token or not user:
        return False
    summary = f"[AI-NDR] {payload.get('label') or payload.get('alert_type') or event_type} {payload.get('source_ip') or ''}"
    desc = json.dumps(payload, default=str)[:1800]
    body = json.dumps({
        "fields": {
            "project": {"key": project},
            "summary": summary[:120],
            "description": desc,
            "issuetype": {"name": os.getenv("JIRA_ISSUE_TYPE") or "Task"},
        }
    }).encode("utf-8")
    auth = base64.b64encode(f"{user}:{token}".encode("utf-8")).decode("ascii")
    return _post(f"{base}/rest/api/2/issue", body, {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
    })
