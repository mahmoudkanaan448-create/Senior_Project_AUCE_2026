"""
Email alert system using SMTP for the AI Network Traffic Analyzer.

Sends plain-text alerts to configured SOC recipients when the alert
manager requests email delivery for High/Critical threats.

Credentials are loaded from Settings (database) first, then env/config.
"""
import sys
import logging
import smtplib
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alerts.runtime_config import get_email_settings

logger = logging.getLogger(__name__)


def send_email_alert(subject: str, body: str, to_email: str = None) -> bool:
    """Send an email alert via SMTP. Returns True on success."""
    cfg = get_email_settings()
    recipient = (to_email or cfg["alert_email"] or "").strip()
    username = (cfg["smtp_username"] or "").strip()
    password = cfg["smtp_password"] or ""
    server_host = cfg["smtp_server"] or "smtp.gmail.com"
    server_port = int(cfg["smtp_port"] or 587)

    if not username or not password:
        logger.warning("SMTP credentials not configured – email alert skipped")
        return False

    if not recipient:
        logger.warning("No recipient email configured – email alert skipped")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = username
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(server_host, server_port, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(username, password)
            server.sendmail(username, [recipient], msg.as_string())

        logger.info("Email alert sent to %s – subject: %s", recipient, subject)
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed – check username/app password")
        return False
    except smtplib.SMTPException as exc:
        logger.error("SMTP error while sending alert: %s", exc)
        return False
    except Exception as exc:
        logger.error("Unexpected error sending email alert: %s", exc)
        return False
