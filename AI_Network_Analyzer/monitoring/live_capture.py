"""
Live network capture helpers.

Tries Scapy/Npcap packet sniffing when available; otherwise falls back to
OS live connection table via psutil (works on Windows without WinPcap).
"""

from __future__ import annotations

import time
from typing import Any

PROTO_MAP = {6: "TCP", 17: "UDP", 1: "ICMP"}


def list_interfaces() -> list[dict[str, str]]:
    """Return network interfaces with friendly names when possible."""
    results: list[dict[str, str]] = []
    try:
        from scapy.arch.windows import get_windows_if_list

        for iface in get_windows_if_list():
            name = iface.get("name") or iface.get("description") or "unknown"
            desc = iface.get("description") or name
            results.append({"name": name, "description": desc})
    except Exception:
        try:
            from scapy.all import get_if_list

            for name in get_if_list():
                results.append({"name": name, "description": name})
        except Exception:
            pass

    if not results:
        results.append({"name": "System Connections", "description": "OS live connection table"})
    return results


def _packet_to_dict(pkt) -> dict[str, Any] | None:
    from scapy.all import IP, TCP, UDP

    if IP not in pkt:
        return None
    ip_layer = pkt[IP]
    src_port = dst_port = 0
    protocol = int(ip_layer.proto)
    tcp_flags = ""
    if TCP in pkt:
        src_port, dst_port, protocol = pkt[TCP].sport, pkt[TCP].dport, 6
        tcp_flags = str(pkt[TCP].flags)
    elif UDP in pkt:
        src_port, dst_port, protocol = pkt[UDP].sport, pkt[UDP].dport, 17
    pkt_dict = {
        "src_ip": ip_layer.src,
        "dst_ip": ip_layer.dst,
        "src_port": int(src_port),
        "dst_port": int(dst_port),
        "protocol": protocol,
        "length": len(pkt),
        "timestamp": float(pkt.time),
        "tcp_flags": tcp_flags,
    }
    try:
        from monitoring.dpi import enrich_packet_dict
        pkt_dict = enrich_packet_dict(pkt_dict, pkt)
    except Exception:
        pass
    return pkt_dict


def capture_live_packets(
    interface: str | None = None,
    timeout: float = 2.0,
    packet_count: int = 0,
) -> list[dict[str, Any]]:
    """Sniff packets with Scapy. Raises RuntimeError if Npcap/WinPcap missing."""
    from scapy.all import sniff

    kwargs: dict[str, Any] = {"timeout": timeout, "store": True}
    if packet_count and packet_count > 0:
        kwargs["count"] = packet_count
    if interface and interface not in ("System Connections", "auto", ""):
        kwargs["iface"] = interface

    raw_packets = sniff(**kwargs)
    packets: list[dict[str, Any]] = []
    dropped = 0
    for pkt in raw_packets:
        pkt_dict = _packet_to_dict(pkt)
        if pkt_dict is not None:
            packets.append(pkt_dict)
        else:
            dropped += 1
    if dropped:
        try:
            from monitoring.sensors import heartbeat
            heartbeat("local", packets_sec=len(packets) / max(timeout, 0.001), dropped=dropped)
        except Exception:
            pass
    return packets


def capture_live_connections() -> list[dict[str, Any]]:
    """
    Read active TCP/UDP connections from the OS (psutil).

    This is a real live feed of established/listening sockets and does not
    require Npcap. Each connection is returned as a one-packet flow sample.
    """
    import psutil
    import socket

    now = time.time()
    packets: list[dict[str, Any]] = []
    try:
        connections = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, PermissionError):
        connections = []

    for conn in connections:
        if not conn.laddr:
            continue
        raddr = conn.raddr
        if not raddr:
            continue
        if getattr(conn, "status", "") in ("LISTEN",):
            continue

        is_udp = conn.type == socket.SOCK_DGRAM
        protocol = 17 if is_udp else 6
        pkt = {
                "src_ip": str(conn.laddr.ip),
                "dst_ip": str(raddr.ip),
                "src_port": int(conn.laddr.port),
                "dst_port": int(raddr.port),
                "protocol": protocol,
                "length": 64,
                "timestamp": now,
                "tcp_flags": "",
                "status": getattr(conn, "status", "") or "",
                "pid": conn.pid,
            }
        try:
            from monitoring.dpi import enrich_packet_dict
            pkt = enrich_packet_dict(pkt)
        except Exception:
            pass
        packets.append(pkt)
    return packets


def capture_live(
    interface: str = "auto",
    timeout: float = 2.0,
    packet_count: int = 0,
) -> tuple[list[dict[str, Any]], str]:
    """
    Capture live traffic.

    Returns (packets, mode) where mode is 'scapy' or 'system_connections'.
    """
    if interface not in ("System Connections",):
        try:
            packets = capture_live_packets(
                interface=None if interface in ("auto", "") else interface,
                timeout=timeout,
                packet_count=packet_count,
            )
            if packets:
                return packets, "scapy"
        except Exception:
            pass

    return capture_live_connections(), "system_connections"


def protocol_name(proto: int | str) -> str:
    """Map protocol number to name."""
    if isinstance(proto, str) and not proto.isdigit():
        return proto.upper()
    return PROTO_MAP.get(int(proto), str(proto))


# Backwards-compatible alias used elsewhere
def read_pcap(filepath: str) -> list[dict[str, Any]]:
    from scapy.all import rdpcap

    packets: list[dict[str, Any]] = []
    for pkt in rdpcap(filepath):
        pkt_dict = _packet_to_dict(pkt)
        if pkt_dict is not None:
            packets.append(pkt_dict)
    return packets
