"""
General-purpose utility functions for the AI Network Traffic Analyzer.

Shared helpers for timestamps, IP validation, severity colours/ranks,
and human-readable byte formatting used across API and dashboard.
"""
import ipaddress
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_timestamp() -> str:
    """Return the current UTC time as a formatted string."""
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def is_private_ip(ip: str) -> bool:
    """Check whether *ip* belongs to a private / reserved range."""
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        logger.warning("Invalid IP address passed to is_private_ip: %s", ip)
        return False


def validate_ip(ip: str) -> bool:
    """Return True if *ip* is a syntactically valid IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def severity_to_color(severity: str) -> str:
    """Map a severity label to a hex colour for UI rendering."""
    colors = {
        "Low":      "#28a745",
        "Medium":   "#ffc107",
        "High":     "#fd7e14",
        "Critical": "#dc3545",
    }
    return colors.get(severity, "#6c757d")


def format_bytes(num_bytes: int) -> str:
    """Convert a raw byte count to a human-readable string (e.g. '1.5 MB')."""
    try:
        value = float(num_bytes)
    except (TypeError, ValueError):
        return "0 B"

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024.0:
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} PB"


def severity_order(severity: str) -> int:
    """Return a numeric rank for sorting: Low=1 … Critical=4."""
    order = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
    return order.get(severity, 0)
