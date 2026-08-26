"""Smoke-test NDR 2.0 modules without starting the dashboard."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from database.database import init_db

failures = []


def check(name, fn):
    try:
        fn()
        print(f"OK  {name}")
    except Exception as exc:
        failures.append(f"{name}: {exc}")
        print(f"FAIL {name}: {exc}")


def main():
    check("init_db", init_db)
    check("dpi", lambda: __import__("monitoring.dpi", fromlist=["protocol_from_ports"]).protocol_from_ports(443, 80))
    check("specialists", lambda: __import__("detection.specialists", fromlist=["detect_specialists"]).detect_specialists(
        {"source_ip": "10.0.0.8", "destination_ip": "10.0.0.5", "destination_port": 445, "packet_rate": 5}
    ))
    check("baselines", lambda: __import__("detection.baselines", fromlist=["update_baseline"]).update_baseline("10.0.0.8", 3.0, 100.0, 443))
    check("assets", lambda: __import__("assets.inventory", fromlist=["upsert_from_flow"]).upsert_from_flow("10.0.0.8", "10.0.0.5", 445))
    check("ioc", lambda: __import__("threat_intelligence.ioc_manager", fromlist=["list_iocs"]).list_iocs())
    check("policy", lambda: __import__("response.policy", fromlist=["response_mode"]).response_mode())
    check("copilot", lambda: __import__("soc.copilot", fromlist=["nl_query"]).nl_query("critical alerts"))
    check("hunt", lambda: __import__("soc.hunting", fromlist=["hunt"]).hunt(limit=5))
    check("sensors", lambda: __import__("monitoring.sensors", fromlist=["list_sensors"]).list_sensors())
    check("mitre", lambda: __import__("threat_intelligence.mitre_map", fromlist=["map_attack_to_mitre"]).map_attack_to_mitre("Exfiltration"))
    check("playbooks", lambda: __import__("soar.playbooks", fromlist=["list_playbooks"]).list_playbooks())
    check("pipeline", lambda: __import__("ndr_core.pipeline", fromlist=["enrich_and_respond"]).enrich_and_respond(
        flow={"source_ip": "10.0.0.8", "destination_ip": "8.8.8.8", "destination_port": 53, "dns_query": "a" * 70},
        prediction={"prediction_label": "Unknown", "severity": "Medium"},
    ))
    check("domain", lambda: __import__("threat_intelligence.domain_intel", fromlist=["score_domain"]).score_domain("abc123xyz789longlabel.xyz"))
    check("identity", lambda: __import__("identity.monitor", fromlist=["auth_anomalies"]).auth_anomalies())
    check("siem", lambda: __import__("ops.siem", fromlist=["emit_event"]).emit_event("smoke", {"ok": True}))
    check("stdlib_platform", lambda: __import__("platform").system())
    if failures:
        print("\nFAILED:", len(failures))
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print("\nAll NDR smoke checks passed.")


if __name__ == "__main__":
    main()
