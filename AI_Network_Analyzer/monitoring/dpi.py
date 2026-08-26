"""
Lightweight DPI / protocol metadata extraction.

Does not decrypt TLS. Extracts DNS queries, HTTP Host, TLS SNI/certs when
Scapy layers are present. Safe no-op if layers unavailable.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


WELL_KNOWN = {
    20: "FTP-DATA", 21: "FTP", 22: "SSH", 23: "TELNET", 25: "SMTP",
    53: "DNS", 67: "DHCP", 80: "HTTP", 110: "POP3", 123: "NTP",
    143: "IMAP", 161: "SNMP", 389: "LDAP", 443: "HTTPS", 445: "SMB",
    587: "SMTP", 993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 1521: "ORACLE",
    3306: "MYSQL", 3389: "RDP", 5432: "POSTGRES", 5900: "VNC",
    6379: "REDIS", 8080: "HTTP-ALT", 8443: "HTTPS-ALT",
}


def protocol_from_ports(src_port: int, dst_port: int, ip_proto: int | str = 6) -> str:
    for p in (int(dst_port or 0), int(src_port or 0)):
        if p in WELL_KNOWN:
            return WELL_KNOWN[p]
    if str(ip_proto) in ("1", "ICMP"):
        return "ICMP"
    if str(ip_proto) in ("17", "UDP"):
        return "UDP"
    return "TCP"


def enrich_packet_dict(pkt_dict: Dict[str, Any], scapy_pkt=None) -> Dict[str, Any]:
    """Add app-protocol metadata onto a packet dict."""
    src_p = int(pkt_dict.get("src_port") or 0)
    dst_p = int(pkt_dict.get("dst_port") or 0)
    proto = pkt_dict.get("protocol", 6)
    pkt_dict["app_protocol"] = protocol_from_ports(src_p, dst_p, proto)
    pkt_dict.setdefault("dns_query", "")
    pkt_dict.setdefault("http_host", "")
    pkt_dict.setdefault("tls_sni", "")
    pkt_dict.setdefault("tls_issuer", "")
    if scapy_pkt is None:
        return pkt_dict
    try:
        from scapy.layers.dns import DNS, DNSQR
        if scapy_pkt.haslayer(DNS) and scapy_pkt[DNS].qd:
            q = scapy_pkt[DNS].qd
            if isinstance(q, DNSQR):
                pkt_dict["dns_query"] = q.qname.decode(errors="ignore").rstrip(".")
                pkt_dict["app_protocol"] = "DNS"
    except Exception:
        pass
    try:
        raw = bytes(scapy_pkt)
        if b"Host: " in raw:
            host = raw.split(b"Host: ", 1)[1].split(b"\r\n", 1)[0]
            pkt_dict["http_host"] = host.decode(errors="ignore")[:180]
            pkt_dict["app_protocol"] = "HTTP"
    except Exception:
        pass
    try:
        from scapy.layers.tls.handshake import TLSClientHello
        if scapy_pkt.haslayer(TLSClientHello):
            hello = scapy_pkt[TLSClientHello]
            sni = getattr(hello, "ext", None)
            pkt_dict["app_protocol"] = "TLS"
            if sni:
                pkt_dict["tls_sni"] = str(sni)[:180]
    except Exception:
        pass
    return pkt_dict


def summarize_flow_dpi(packets: list) -> Dict[str, Any]:
    """Aggregate DPI fields from packet dicts in a flow."""
    dns, hosts, sni = [], [], []
    apps = []
    for p in packets or []:
        if not isinstance(p, dict):
            continue
        if p.get("dns_query"):
            dns.append(p["dns_query"])
        if p.get("http_host"):
            hosts.append(p["http_host"])
        if p.get("tls_sni"):
            sni.append(p["tls_sni"])
        if p.get("app_protocol"):
            apps.append(p["app_protocol"])
    app = apps[0] if apps else ""
    return {
        "app_protocol": app,
        "dns_query": dns[0] if dns else "",
        "http_host": hosts[0] if hosts else "",
        "tls_sni": sni[0] if sni else "",
        "suspicious_dns": _suspicious_dns(dns[0] if dns else ""),
    }


def _suspicious_dns(q: str) -> bool:
    if not q:
        return False
    q = q.lower()
    if len(q) > 60:
        return True  # possible tunneling / DGA-like
    labels = q.split(".")
    if labels and len(labels[0]) >= 20 and sum(c.isdigit() for c in labels[0]) > 6:
        return True
    return False


def tls_cert_flags(issuer: str = "", sni: str = "", age_days: Optional[float] = None) -> Dict[str, Any]:
    flags = []
    if issuer and any(x in issuer.lower() for x in ("localhost", "self-signed", "unknown")):
        flags.append("suspicious_issuer")
    if sni and sni.count(".") == 0:
        flags.append("odd_sni")
    if age_days is not None and age_days < 2:
        flags.append("very_new_cert")
    return {"flags": flags, "suspicious": bool(flags)}
