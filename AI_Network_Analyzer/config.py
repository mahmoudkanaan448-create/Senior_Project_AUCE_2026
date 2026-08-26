"""
Central configuration for AI Network Traffic Analyzer & Anomaly Detector.

Single source of truth for database URL, JWT settings, AI thresholds,
paths, threat-intel keys, and notification credentials. Override secrets
via environment variables; defaults suit local development.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ── Application version ───────────────────────────────────────────────────────
APP_VERSION = "1.0.0"

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except Exception:
    pass

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'database' / 'analyzer.db'}")

# ── JWT Authentication ────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-ai-ndr-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

# ── Paths ─────────────────────────────────────────────────────────────────────
MODELS_DIR = BASE_DIR / "models"
DATASETS_DIR = BASE_DIR / "datasets"
CAPTURED_DATA_DIR = BASE_DIR / "captured_data"
LOGS_DIR = BASE_DIR / "logs"
REPORTS_DIR = BASE_DIR / "reports"

# ── AI thresholds ─────────────────────────────────────────────────────────────
AI_CONFIDENCE_THRESHOLD = 0.5
ANOMALY_THRESHOLD = -0.3          # Isolation Forest: more negative = more anomalous
AUTOENCODER_ERROR_THRESHOLD = 0.1
THREAT_SCORE_BLOCK_THRESHOLD = 7.0

# ── Threat Intelligence ───────────────────────────────────────────────────────
ABUSEIPDB_API_KEY = os.getenv("ABUSEIPDB_API_KEY", "")
VIRUSTOTAL_API_KEY = os.getenv("VIRUSTOTAL_API_KEY", "")

# ── Email Notifications ──────────────────────────────────────────────────────
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")

# ── Telegram Notifications ───────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Dashboard ─────────────────────────────────────────────────────────────────
DASHBOARD_REFRESH_SECONDS = 5

# ── Company / production-pilot ────────────────────────────────────────────────
COMPANY_MODE = os.getenv("AINDR_COMPANY_MODE", "0")
BACKUPS_DIR = BASE_DIR / "backups"
SPLUNK_HEC_URL = os.getenv("SPLUNK_HEC_URL", "")
SPLUNK_HEC_TOKEN = os.getenv("SPLUNK_HEC_TOKEN", "")
ELASTIC_URL = os.getenv("ELASTIC_URL", "")
JIRA_URL = os.getenv("JIRA_URL", "")
JIRA_USER = os.getenv("JIRA_USER", "")
JIRA_TOKEN = os.getenv("JIRA_TOKEN", "")
JIRA_PROJECT = os.getenv("JIRA_PROJECT", "SOC")

# Feature order must match model training input.
FEATURE_COLUMNS = [
    "duration", "protocol_type", "src_bytes", "dst_bytes",
    "count", "srv_count", "serror_rate", "rerror_rate",
    "same_srv_rate", "diff_srv_rate", "dst_host_count",
    "dst_host_srv_count", "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate", "dst_host_serror_rate",
    "dst_host_rerror_rate", "packet_count", "byte_count",
    "packet_rate", "flow_rate", "avg_packet_size",
    "syn_count", "ack_count", "fin_count", "rst_count",
    "psh_count", "urg_count", "flow_duration",
    "fwd_packets", "bwd_packets", "fwd_bytes", "bwd_bytes",
    "min_packet_length", "max_packet_length", "mean_packet_length",
    "std_packet_length", "inter_arrival_time",
    "active_time", "idle_time",
]

ATTACK_LABELS = [
    "Normal", "DoS", "DDoS", "PortScan", "BruteForce",
    "SQLInjection", "WebAttack", "Botnet", "Infiltration",
    "Malware", "Ransomware", "Unknown", "C2", "Exfiltration",
    "LateralMovement", "PrivilegeEscalation", "Insider",
]
