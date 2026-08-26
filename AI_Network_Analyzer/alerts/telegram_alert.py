"""
Telegram bot notification system for the AI Network Traffic Analyzer.

Credentials are loaded from Settings (database) first, then env/config.
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple, Union

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alerts.runtime_config import get_telegram_settings

logger = logging.getLogger(__name__)


def _normalize_chat_id(raw: str) -> Union[int, str]:
    """Telegram accepts int for private chats; keep strings for @channel names."""
    value = (raw or "").strip().replace(" ", "")
    if value.startswith("@"):
        return value
    if value.lstrip("-").isdigit():
        try:
            return int(value)
        except ValueError:
            return value
    return value


def send_telegram_alert(message: str) -> bool:
    """Send an alert via Telegram. Returns True on success."""
    ok, _ = send_telegram_alert_detailed(message)
    return ok


def send_telegram_alert_detailed(message: str, *, verify_bot: bool = False) -> Tuple[bool, str]:
    """
    Send Telegram alert and return (success, detail_message).

    verify_bot: when True, call getMe first (Settings test). For live alerts we
    skip getMe to avoid rate limits during campaign bursts.
    """
    cfg = get_telegram_settings()
    token = (cfg.get("bot_token") or "").strip()
    chat_raw = (cfg.get("chat_id") or "").strip()

    if not token:
        return False, "Bot Token is empty. Paste the token from @BotFather."
    if not chat_raw:
        return False, "Chat ID is empty. Get it from @userinfobot after starting your bot."
    if ":" not in token or len(token) < 30:
        return False, "Bot Token looks invalid. It should look like 123456789:AAH..."

    chat_id = _normalize_chat_id(chat_raw)
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    if verify_bot:
        try:
            me = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15)
            me_json = me.json() if me.content else {}
            if me.status_code != 200 or not me_json.get("ok"):
                desc = me_json.get("description") or me.text[:200]
                return False, f"Invalid bot token (getMe failed): {desc}"
        except requests.Timeout:
            return False, "Telegram API timed out while checking the bot token."
        except requests.ConnectionError:
            return False, "Cannot reach api.telegram.org. Check internet / firewall."
        except Exception as exc:
            return False, f"Token check failed: {exc}"

    # Plain text only – avoid HTML parse failures on real alerts
    text = (message or "").strip() or "AI Network Analyzer alert"
    # Strip characters that sometimes break Telegram clients
    text = text.replace("\x00", "")
    if len(text) > 4000:
        text = text[:3990] + "..."

    payloads = [
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
    ]
    if isinstance(chat_id, int):
        payloads.append({"chat_id": str(chat_id), "text": text, "disable_web_page_preview": True})

    last_error = "Unknown Telegram error"
    try:
        for attempt in range(3):
            for payload in payloads:
                response = requests.post(url, json=payload, timeout=20)
                try:
                    data = response.json()
                except Exception:
                    data = {}

                if response.status_code == 200 and data.get("ok"):
                    logger.info("Telegram alert sent successfully")
                    return True, "Message sent successfully."

                desc = data.get("description") or response.text[:300]
                last_error = f"HTTP {response.status_code}: {desc}"
                low = str(desc).lower()

                # Flood control – wait and retry
                if response.status_code == 429 or "too many requests" in low:
                    retry_after = 1
                    try:
                        retry_after = int((data.get("parameters") or {}).get("retry_after") or 1)
                    except Exception:
                        pass
                    time.sleep(min(max(retry_after, 1), 5))
                    continue

                if "chat not found" in low:
                    return False, (
                        "Chat not found. Open your bot in Telegram and press Start, "
                        "then confirm Chat ID with @userinfobot."
                    )
                if "unauthorized" in low:
                    return False, "Unauthorized. Bot Token is wrong or revoked."
                if "blocked" in low:
                    return False, "Bot was blocked by the user. Unblock and press Start again."

            time.sleep(0.35)

        logger.error("Telegram send failed: %s", last_error)
        return False, last_error

    except requests.Timeout:
        return False, "Telegram API request timed out."
    except requests.ConnectionError:
        return False, "Cannot connect to Telegram API."
    except Exception as exc:
        logger.error("Unexpected Telegram error: %s", exc)
        return False, f"Unexpected error: {exc}"


def fetch_recent_chat_ids() -> Dict[str, Any]:
    """List recent chat ids from getUpdates (after user messages the bot)."""
    cfg = get_telegram_settings()
    token = (cfg.get("bot_token") or "").strip()
    if not token:
        return {"ok": False, "error": "No token", "chats": []}
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15)
        data = r.json()
        chats = []
        for upd in data.get("result") or []:
            msg = upd.get("message") or upd.get("edited_message") or {}
            chat = msg.get("chat") or {}
            if chat.get("id") is not None:
                chats.append({
                    "id": chat.get("id"),
                    "type": chat.get("type"),
                    "username": chat.get("username"),
                    "first_name": chat.get("first_name"),
                    "title": chat.get("title"),
                })
        uniq = {}
        for c in chats:
            uniq[c["id"]] = c
        return {"ok": bool(data.get("ok")), "chats": list(uniq.values()), "raw_error": data.get("description")}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "chats": []}
