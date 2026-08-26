"""Academic-style diagrams (white background, consistent fonts) for the thesis."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "new_figures"
OUT.mkdir(parents=True, exist_ok=True)

BG = (255, 255, 255)
PANEL = (241, 245, 249)
BORDER = (30, 41, 59)
ACCENT = (29, 78, 216)
GOLD = (180, 140, 30)
TEXT = (15, 23, 42)
MUTED = (71, 85, 105)


def font(size: int, bold: bool = False):
    names = ("arialbd.ttf", "calibrib.ttf") if bold else ("arial.ttf", "calibri.ttf", "segoeui.ttf")
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except Exception:
            pass
    return ImageFont.load_default()


def t(draw, xy, text, size=14, bold=False, fill=TEXT):
    draw.text(xy, text, fill=fill, font=font(size, bold))


def box(draw, xy, label, fill=PANEL, w=2):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=8, fill=fill, outline=BORDER, width=w)
    f = font(13)
    lines = label.split("\n")
    th = sum(f.getbbox(l)[3] - f.getbbox(l)[1] + 3 for l in lines)
    cy = y1 + (y2 - y1 - th) / 2
    for line in lines:
        bb = f.getbbox(line)
        tw = bb[2] - bb[0]
        draw.text((x1 + (x2 - x1 - tw) / 2, cy), line, fill=TEXT, font=f)
        cy += bb[3] - bb[1] + 3


def arrow(draw, x1, y1, x2, y2):
    draw.line((x1, y1, x2, y2), fill=ACCENT, width=2)
    if abs(x2 - x1) >= abs(y2 - y1):
        s = 1 if x2 > x1 else -1
        draw.polygon([(x2, y2), (x2 - 9 * s, y2 - 5), (x2 - 9 * s, y2 + 5)], fill=ACCENT)
    else:
        s = 1 if y2 > y1 else -1
        draw.polygon([(x2, y2), (x2 - 5, y2 - 9 * s), (x2 + 5, y2 - 9 * s)], fill=ACCENT)


def header(draw, w, title, subtitle=""):
    """Plain academic title (no dark banner — supervisor §14–15)."""
    t(draw, (24, 18), title, 18, True)
    if subtitle:
        t(draw, (24, 44), subtitle, 12, False, MUTED)


def fig1_architecture():
    w, h = 1300, 780
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    header(d, w, "Figure 1 — Proposed System Architecture (Implemented Prototype)")
    boxes = [
        (40, 80, 280, 160, "Traffic Input\nNIC / CSV / Simulation"),
        (320, 80, 560, 160, "Feature Extraction\n39 flow features"),
        (600, 80, 860, 160, "Hybrid AI Engine\nRF · XGB · IF · AE · LSTM"),
        (900, 80, 1240, 160, "Decision Fusion\nLabel · Score · Severity"),
        (40, 220, 280, 300, "XAI JSON\nPer prediction"),
        (320, 220, 560, 300, "Threat Intel\nMITRE · Geo"),
        (600, 220, 860, 300, "Alerts + SOAR\nPlaybooks"),
        (900, 220, 1240, 300, "Response\nBlock · Telegram"),
        (200, 380, 520, 480, "FastAPI Backend\nPort 8000"),
        (560, 380, 1080, 480, "Streamlit SOC Dashboard\n16 pages"),
        (320, 540, 980, 640, "SQLite / PostgreSQL\nFlows · Predictions · Alerts · XAI"),
    ]
    for b in boxes:
        box(d, b[:4], b[4])
    for x in (280, 560, 860):
        arrow(d, x, 120, x + 35, 120)
    arrow(d, 640, 160, 640, 215)
    arrow(d, 640, 300, 640, 375)
    arrow(d, 640, 480, 640, 535)
    img.save(OUT / "fig01_proposed_architecture.png")


def fig2_pipeline():
    w, h = 1300, 420
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    header(d, w, "Figure 2 — AI Detection Pipeline")
    steps = ["Capture", "Features", "Scale", "5 Models", "Fuse", "Alert", "Store"]
    xs = []
    for i, s in enumerate(steps):
        x1 = 40 + i * 175
        box(d, (x1, 120, x1 + 150, 220), s)
        xs.append((x1, x1 + 150))
    for i in range(len(xs) - 1):
        arrow(d, xs[i][1], 170, xs[i + 1][0], 170)
    t(d, (40, 280), "Unsupervised path: Isolation Forest + Autoencoder anomaly scores feed fusion.", 13, False, MUTED)
    img.save(OUT / "fig02_ai_pipeline.png")


def fig4_data_pipeline():
    w, h = 1300, 500
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    header(d, w, "Figure 4 — System Data Pipeline", "(Not a formal DFD; shows data movement in the implemented system)")
    box(d, (40, 90, 260, 170), "External Entity\nAdmin / Network")
    box(d, (320, 90, 560, 170), "Process\nCapture + Extract")
    box(d, (620, 90, 860, 170), "Process\nTrain / Infer")
    box(d, (920, 90, 1240, 170), "Data Store\nSQLite DB")
    box(d, (320, 260, 860, 340), "Process\nDashboard + API")
    arrow(d, 260, 130, 315, 130)
    arrow(d, 560, 130, 615, 130)
    arrow(d, 860, 130, 915, 130)
    arrow(d, 590, 170, 590, 255)
    arrow(d, 180, 170, 180, 300)
    arrow(d, 180, 300, 315, 300)
    img.save(OUT / "fig04_data_pipeline.png")


def fig5_use_case():
    w, h = 1100, 620
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    header(d, w, "Figure 5 — Use Case Diagram")
    box(d, (40, 280, 200, 380), "Administrator\n(SOC Analyst)", fill=(219, 234, 254))
    for i, (lab, y) in enumerate([
        ("Monitor live traffic", 100), ("Run AI detection", 180), ("Review alerts + XAI", 260),
        ("Threat Simulation", 340), ("Block IP / Export report", 420), ("Configure Telegram", 500),
    ]):
        box(d, (400, y, 760, y + 60), lab)
        arrow(d, 200, 330, 395, y + 30)
    box(d, (820, 250, 1060, 410), "AI-NDR System\n(FastAPI + Streamlit + Models)")
    arrow(d, 760, 330, 815, 330)
    img.save(OUT / "fig05_use_case.png")


def fig6_sequence():
    w, h = 1300, 560
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    header(d, w, "Figure 6 — Sequence Diagram: Real-Time Detection")
    actors = [("Admin", 80), ("Dashboard", 280), ("API", 520), ("AI Engine", 760), ("Database", 1000)]
    for name, x in actors:
        t(d, (x, 70), name, 13, True)
        draw = d
        draw.line((x + 40, 95, x + 40, 500), fill=MUTED, width=1)
    msgs = [(0, 1, 110, "Submit flow / CSV"), (1, 2, 150, "POST /detect"), (2, 3, 190, "predict()"),
            (3, 4, 230, "store prediction + XAI"), (4, 2, 270, "OK"), (2, 1, 310, "JSON result"),
            (1, 0, 350, "Show label + explanation"), (3, 2, 390, "create alert if Medium+"),
            (2, 4, 430, "insert alert"), (2, 0, 470, "Telegram notify (optional)")]
    for a, b, y, m in msgs:
        x1 = actors[a][1] + 40
        x2 = actors[b][1] + 40
        arrow(d, x1, y, x2, y)
        t(d, ((x1 + x2) / 2 - 60, y - 14), m, 11)
    img.save(OUT / "fig06_sequence.png")


def fig7_activity():
    w, h = 1100, 700
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    header(d, w, "Figure 7 — Activity Diagram: Detection Workflow")
    nodes = [
        ("box", (450, 80, 550, 120), "Start"),
        ("box", (400, 150, 600, 210), "Capture / ingest flow"),
        ("box", (400, 250, 600, 310), "Extract 39 features"),
        ("box", (400, 350, 600, 410), "Run models + fusion"),
        ("box", (400, 450, 600, 510), "Severity >= Medium?"),
        ("box", (120, 570, 320, 630), "Create alert + playbook"),
        ("box", (580, 570, 780, 630), "Log only"),
        ("box", (450, 660, 550, 700), "End"),
    ]
    for kind, xy, label in nodes:
        fill = (219, 234, 254) if label in ("Start", "End") else PANEL
        box(d, xy, label, fill=fill)
    arrow(d, 500, 120, 500, 145)
    arrow(d, 500, 210, 500, 245)
    arrow(d, 500, 310, 500, 345)
    arrow(d, 500, 410, 500, 445)
    arrow(d, 450, 510, 220, 565)
    arrow(d, 550, 510, 680, 565)
    arrow(d, 220, 630, 480, 665)
    arrow(d, 680, 630, 520, 665)
    t(d, (530, 480), "Yes", 12, True, ACCENT)
    t(d, (350, 480), "No", 12, True, ACCENT)
    img.save(OUT / "fig07_activity.png")


def fig8_stride():
    w, h = 1200, 520
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    header(d, w, "Figure 8 — STRIDE Threat Model (Simplified)")
    threats = [
        ("Spoofing", "JWT auth on API/dashboard"),
        ("Tampering", "DB access control + backups"),
        ("Repudiation", "Audit logs / alert history"),
        ("Information disclosure", "Minimise stored payloads"),
        ("Denial of service", "Supervisor auto-restart"),
        ("Elevation of privilege", "Role-based Company mode"),
    ]
    for i, (th, mit) in enumerate(threats):
        y = 85 + i * 68
        box(d, (40, y, 320, y + 52), th, fill=(254, 226, 226))
        box(d, (380, y, 1160, y + 52), f"Mitigation: {mit}", fill=(220, 252, 231))
        arrow(d, 320, y + 26, 375, y + 26)
    img.save(OUT / "fig08_stride.png")


def fig_hybrid_fusion():
    w, h = 1200, 380
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    header(d, w, "Hybrid Decision Fusion (decision_engine.fuse_decisions)")
    models = ["RF vote", "XGB vote", "IF vote", "AE score", "LSTM vote"]
    for i, m in enumerate(models):
        box(d, (40 + i * 220, 100, 220 + i * 220, 180), m)
    box(d, (350, 240, 850, 320), "Majority / confidence weighting → final_label, threat_score, severity")
    for i in range(5):
        arrow(d, 130 + i * 220, 180, 600, 235)
    img.save(OUT / "fig_hybrid_fusion.png")


def fig_cm_roc_examples():
    w, h = 700, 520
    for name, title, fn in [
        ("fig_cm_example.png", "Confusion Matrix (how to read)", "cm"),
        ("fig_roc_example.png", "ROC Curve (illustrative)", "roc"),
    ]:
        img = Image.new("RGB", (w, h), BG)
        d = ImageDraw.Draw(img)
        header(d, w, title)
        if fn == "cm":
            labels = ["Pred N", "Pred A"]
            for i, lb in enumerate(["Actual N", "Actual A"]):
                t(d, (120, 90 + i * 100), lb, 12, True)
                for j in range(2):
                    val = "TN" if i == 0 and j == 0 else "FP" if i == 0 and j == 1 else "FN" if i == 1 and j == 0 else "TP"
                    box(d, (200 + j * 120, 80 + i * 100, 300 + j * 120, 160 + i * 100), val)
            t(d, (40, 420), "Measured RF matrix is Figure 17.", 13, False, MUTED)
        else:
            d.line((80, 420, 620, 80), fill=ACCENT, width=3)
            d.line((80, 420, 620, 420), fill=BORDER)
            d.line((80, 420, 80, 80), fill=BORDER)
            t(d, (300, 440), "FPR", 12, True)
            t(d, (30, 240), "TPR", 12, True)
        img.save(Path(__file__).resolve().parent / "evaluation" / name)


def main():
    fig1_architecture()
    fig2_pipeline()
    # fig3 uses fig_expanded_architecture from generate_new_figures.py
    fig4_data_pipeline()
    fig5_use_case()
    fig6_sequence()
    fig7_activity()
    fig8_stride()
    fig_hybrid_fusion()
    fig_cm_roc_examples()
    print("Academic diagrams saved to", OUT)


if __name__ == "__main__":
    main()
