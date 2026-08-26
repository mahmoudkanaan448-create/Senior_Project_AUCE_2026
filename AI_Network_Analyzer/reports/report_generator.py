"""
Incident and summary report generation – PDF, CSV, and daily digest.

Builds branded PDF incident reports, CSV prediction exports, and
plain-text daily summaries for analysts and compliance.
"""
import sys
import csv
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional

from fpdf import FPDF

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import REPORTS_DIR
from database.models import Prediction, Alert

logger = logging.getLogger(__name__)


class _IncidentPDF(FPDF):
    """Lightweight FPDF subclass with a branded header / footer."""

    def header(self) -> None:
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "AI Network Traffic Analyzer - Incident Report", ln=True, align="C")
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}} | Generated {datetime.utcnow():%Y-%m-%d %H:%M UTC}", align="C")


def _add_section(pdf: FPDF, title: str, body: str) -> None:
    """Print a titled section with a filled heading bar and wrapped body."""
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(230, 230, 250)
    pdf.cell(0, 8, f"  {title}", ln=True, fill=True)
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, body)
    pdf.ln(3)


def generate_pdf_report(incident_data: dict, output_path: str = None) -> str:
    """Generate a PDF incident report; return the output path or empty on failure."""
    try:
        if output_path is None:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_path = str(REPORTS_DIR / f"incident_{ts}.pdf")

        pdf = _IncidentPDF()
        pdf.alias_nb_pages()
        pdf.add_page()

        _add_section(pdf, "Incident Summary", incident_data.get("summary", "N/A"))

        attack_details = (
            f"Attack Type: {incident_data.get('attack_type', 'N/A')}\n"
            f"Source IP: {incident_data.get('source_ip', 'N/A')}\n"
            f"Destination IP: {incident_data.get('destination_ip', 'N/A')}\n"
            f"Severity: {incident_data.get('severity', 'N/A')}\n"
            f"Protocol: {incident_data.get('protocol', 'N/A')}"
        )
        _add_section(pdf, "Attack Details", attack_details)

        ti = incident_data.get("threat_intel", {})
        if ti:
            ti_text = (
                f"Country: {ti.get('country', 'N/A')}\n"
                f"ISP: {ti.get('isp', 'N/A')}\n"
                f"Reputation: {ti.get('reputation', 'N/A')}\n"
                f"Reports: {ti.get('reports', 0)}\n"
                f"Blacklisted: {ti.get('blacklisted', False)}"
            )
            _add_section(pdf, "Threat Intelligence", ti_text)

        ai_text = (
            f"Model: {incident_data.get('model_name', 'N/A')}\n"
            f"Confidence: {incident_data.get('confidence', 0):.1%}\n"
            f"Anomaly Score: {incident_data.get('anomaly_score', 'N/A')}\n"
            f"Threat Score: {incident_data.get('threat_score', 0):.1f}"
        )
        _add_section(pdf, "AI Prediction", ai_text)

        timeline = incident_data.get("timeline", "N/A")
        _add_section(pdf, "Timeline", str(timeline))

        _add_section(pdf, "Recommendation", incident_data.get("recommendation", "N/A"))

        pdf.output(output_path)
        logger.info("PDF report generated: %s", output_path)
        return output_path

    except Exception as exc:
        logger.error("Failed to generate PDF report: %s", exc)
        return ""


def generate_csv_report(predictions: List[dict], output_path: str = None) -> str:
    """Export prediction dicts to CSV; return the output path or empty on failure."""
    try:
        if not predictions:
            logger.warning("No predictions to export")
            return ""

        if output_path is None:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_path = str(REPORTS_DIR / f"predictions_{ts}.csv")

        fieldnames = list(predictions[0].keys())

        with open(output_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(predictions)

        logger.info("CSV report generated: %s (%d rows)", output_path, len(predictions))
        return output_path

    except Exception as exc:
        logger.error("Failed to generate CSV report: %s", exc)
        return ""


def generate_daily_report(db_session, date: Optional[datetime] = None) -> str:
    """Generate a plain-text daily summary of alerts and predictions."""
    try:
        if date is None:
            date = datetime.utcnow()

        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        predictions = (
            db_session.query(Prediction)
            .filter(Prediction.prediction_time >= day_start, Prediction.prediction_time < day_end)
            .all()
        )

        alerts = (
            db_session.query(Alert)
            .filter(Alert.created_at >= day_start, Alert.created_at < day_end)
            .all()
        )

        severity_counts: dict = {}
        for p in predictions:
            severity_counts[p.severity] = severity_counts.get(p.severity, 0) + 1

        lines = [
            "=" * 60,
            f"  Daily Report – {day_start:%Y-%m-%d}",
            "=" * 60,
            "",
            f"Total Predictions : {len(predictions)}",
            f"Total Alerts      : {len(alerts)}",
            "",
            "Severity Breakdown:",
        ]
        for sev in ("Critical", "High", "Medium", "Low"):
            lines.append(f"  {sev:10s}: {severity_counts.get(sev, 0)}")

        attack_counts: dict = {}
        for p in predictions:
            attack_counts[p.prediction_label] = attack_counts.get(p.prediction_label, 0) + 1

        lines += ["", "Attack Types:"]
        for atk, cnt in sorted(attack_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {atk:20s}: {cnt}")

        lines += ["", "=" * 60]

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = str(REPORTS_DIR / f"daily_{day_start:%Y%m%d}.txt")

        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

        logger.info("Daily report generated: %s", output_path)
        return output_path

    except Exception as exc:
        logger.error("Failed to generate daily report: %s", exc)
        return ""
