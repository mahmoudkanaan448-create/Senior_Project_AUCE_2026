"""
IP blocking – database record plus optional OS-level firewall rule.

Records blocked IPs in the database and best-effort applies Windows
netsh or Linux iptables rules for Critical-severity auto-blocks.
"""
import sys
import platform
import subprocess
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.database import SessionLocal
from database.queries import block_ip, unblock_ip, get_blocked_ips

logger = logging.getLogger(__name__)


def _apply_os_firewall_block(ip: str) -> bool:
    """Attempt to add an OS-level firewall rule (best-effort)."""
    os_name = platform.system()
    try:
        if os_name == "Windows":
            cmd = [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name=AI_NDR_Block_{ip}",
                "dir=in", "action=block",
                f"remoteip={ip}",
                "enable=yes",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logger.info("Windows firewall rule added for %s", ip)
                return True
            logger.warning("netsh returned code %s: %s", result.returncode, result.stderr)
            return False

        if os_name == "Linux":
            cmd = ["iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logger.info("iptables rule added for %s", ip)
                return True
            logger.warning("iptables returned code %s: %s", result.returncode, result.stderr)
            return False

        logger.info("OS firewall integration not available on %s – simulation only", os_name)
        return False

    except FileNotFoundError:
        logger.info("Firewall command not found – running in simulation mode")
        return False
    except subprocess.TimeoutExpired:
        logger.error("Firewall command timed out for IP %s", ip)
        return False
    except Exception as exc:
        logger.error("OS firewall error for %s: %s", ip, exc)
        return False


def block_ip_address(ip: str, reason: str = "") -> bool:
    """Block an IP in the database and optionally at the OS firewall."""
    try:
        db = SessionLocal()
        try:
            block_ip(db, ip_address=ip, attack_type="auto", blocked_by="system", reason=reason)
            logger.info("IP %s added to blocked list – %s", ip, reason)
        finally:
            db.close()

        _apply_os_firewall_block(ip)
        return True

    except Exception as exc:
        logger.error("Failed to block IP %s: %s", ip, exc)
        return False


def unblock_ip_address(ip: str) -> bool:
    """Remove an IP address from the active blocked list."""
    try:
        db = SessionLocal()
        try:
            result = unblock_ip(db, ip_address=ip)
        finally:
            db.close()

        if result:
            logger.info("IP %s removed from blocked list", ip)
        else:
            logger.warning("IP %s was not in the active blocked list", ip)
        return result

    except Exception as exc:
        logger.error("Failed to unblock IP %s: %s", ip, exc)
        return False


def is_blocked(ip: str, db_session) -> bool:
    """Return True if the IP is currently in the active blocked list."""
    try:
        blocked_list = get_blocked_ips(db_session)
        return any(b.ip_address == ip for b in blocked_list)
    except Exception as exc:
        logger.error("Error checking blocked status for %s: %s", ip, exc)
        return False
