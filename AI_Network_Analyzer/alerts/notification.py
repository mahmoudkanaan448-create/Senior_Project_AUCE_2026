"""
Unified notification dispatcher – Telegram + dashboard only.
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alerts.telegram_alert import send_telegram_alert

logger = logging.getLogger(__name__)


def notify(channel: str, message: str, recipient: str = None) -> bool:
    """Send a notification via telegram or dashboard channel."""
    channel = (channel or "").lower().strip()

    try:
        if channel in ("email", "whatsapp", "wa"):
            logger.warning("Channel '%s' disabled – use Telegram", channel)
            return False

        if channel == "telegram":
            return send_telegram_alert(message)

        if channel == "dashboard":
            logger.info("Dashboard notification queued: %s", message[:120])
            return True

        logger.warning("Unknown notification channel: %s", channel)
        return False

    except Exception as exc:
        logger.error("Failed to dispatch notification via %s: %s", channel, exc)
        return False
