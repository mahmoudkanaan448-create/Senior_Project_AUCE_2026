"""Generate expanded architecture diagrams with Pillow (no matplotlib)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "new_figures"
OUT.mkdir(parents=True, exist_ok=True)

BG = (7, 17, 31)
PANEL = (18, 35, 61)
PANEL2 = (26, 47, 74)
GREEN = (20, 83, 45)
RED = (127, 29, 29)
GOLD = (212, 175, 55)
WHITE = (248, 250, 252)
MUTED = (203, 213, 225)


def font(size=14):
    for name in ("segoeui.ttf", "arial.ttf", "calibri.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def box(draw, xy, text, fill=PANEL, outline=GOLD):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=12, fill=fill, outline=outline, width=2)
    # center text
    f = font(13)
    lines = text.split("\n")
    th = sum(f.getbbox(l)[3] - f.getbbox(l)[1] + 4 for l in lines)
    cy = y1 + (y2 - y1 - th) / 2
    for line in lines:
        bb = f.getbbox(line)
        tw = bb[2] - bb[0]
        draw.text((x1 + (x2 - x1 - tw) / 2, cy), line, fill=WHITE, font=f)
        cy += bb[3] - bb[1] + 4


def arrow(draw, x1, y1, x2, y2):
    draw.line((x1, y1, x2, y2), fill=GOLD, width=3)
    # simple arrow head
    if abs(x2 - x1) >= abs(y2 - y1):
        s = 1 if x2 > x1 else -1
        draw.polygon([(x2, y2), (x2 - 10 * s, y2 - 6), (x2 - 10 * s, y2 + 6)], fill=GOLD)
    else:
        s = 1 if y2 > y1 else -1
        draw.polygon([(x2, y2), (x2 - 6, y2 - 10 * s), (x2 + 6, y2 - 10 * s)], fill=GOLD)


def title(draw, w, text):
    f = font(20)
    bb = f.getbbox(text)
    tw = bb[2] - bb[0]
    draw.text(((w - tw) / 2, 18), text, fill=GOLD, font=f)


def save_architecture():
    w, h = 1400, 900
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    title(d, w, "Expanded System Architecture (Implemented AI-NDR)")
    row1 = [
        (40, 90, 300, 190, "Traffic Sources\nLive NIC / CSV / Simulation"),
        (360, 90, 650, 190, "Monitoring\nCapture + Features"),
        (710, 90, 1020, 190, "Hybrid AI Engine\nRF / XGB / IF / AE / LSTM"),
        (1080, 90, 1360, 190, "Decision Fusion\n+ Confidence"),
    ]
    row2 = [
        (40, 280, 300, 380, "MITRE ATT&CK\nMapping"),
        (360, 280, 650, 380, "Threat Intel\nGeo / AbuseIPDB"),
        (710, 280, 1020, 380, "XAI Explanations\nPer-prediction JSON"),
        (1080, 280, 1360, 380, "Online Learning\nSGD partial_fit"),
    ]
    row3 = [
        (40, 470, 300, 570, "SOAR Playbooks\nAlert / Block"),
        (360, 470, 650, 570, "Telegram + Local\nNotify / Sound"),
        (710, 470, 1020, 570, "SQLite / Postgres\nFlows / Alerts / XAI"),
        (1080, 470, 1360, 570, "Firewall Block\nDB / OS"),
    ]
    row4 = [
        (180, 680, 650, 800, "FastAPI Backend (:8000)\nAuth / REST / Health / SOC APIs", GREEN),
        (720, 680, 1220, 800, "Streamlit SOC Dashboard (:8501)\n16 pages + Company trial", GREEN),
    ]
    for x1, y1, x2, y2, t in row1:
        box(d, (x1, y1, x2, y2), t, fill=PANEL2)
    for x1, y1, x2, y2, t in row2:
        box(d, (x1, y1, x2, y2), t)
    for x1, y1, x2, y2, t in row3:
        box(d, (x1, y1, x2, y2), t)
    for x1, y1, x2, y2, t, fc in row4:
        box(d, (x1, y1, x2, y2), t, fill=fc)
    for x in [300, 650, 1020]:
        arrow(d, x, 140, x + 55, 140)
    arrow(d, 505, 190, 505, 275)
    arrow(d, 865, 190, 865, 275)
    arrow(d, 170, 380, 170, 465)
    arrow(d, 505, 380, 505, 465)
    arrow(d, 865, 570, 865, 675)
    arrow(d, 505, 570, 415, 675)
    img.save(OUT / "fig_expanded_architecture.png")


def save_pipeline():
    w, h = 1400, 520
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    title(d, w, "End-to-End Detection & Response Pipeline")
    steps = [
        "1. Flow\nInput", "2. Feature\nVector", "3. 5 Models\nPredict",
        "4. Fuse\nSeverity", "5. MITRE\nMap", "6. SOAR\nPlaybook", "7. Notify\n+ Block",
    ]
    xs = []
    for i, t in enumerate(steps):
        x1 = 30 + i * 195
        x2 = x1 + 170
        box(d, (x1, 140, x2, 280), t)
        xs.append((x1, x2))
    for i in range(len(xs) - 1):
        arrow(d, xs[i][1], 210, xs[i + 1][0], 210)
    box(d, (250, 360, 1150, 470),
        "Side path: queue sample → Online Learning buffer → optional SGD vote",
        fill=PANEL2)
    img.save(OUT / "fig_detection_pipeline.png")


def save_deployment():
    w, h = 1200, 620
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    title(d, w, "Server Deployment with Auto-Recovery Supervisor")
    box(d, (320, 80, 880, 180), "ops.supervisor / run_server.bat\nHealth check every 15s", fill=RED)
    box(d, (60, 260, 560, 400), "API Process\nuvicorn main:app :8000\n/api/v1/health", fill=GREEN)
    box(d, (640, 260, 1140, 400), "Dashboard Process\nstreamlit home.py :8501\nHeadless server mode", fill=GREEN)
    box(d, (250, 470, 950, 570), "Optional 24/7 capture daemon + auto-heal: dirs, DB, restart", fill=PANEL2)
    arrow(d, 500, 180, 310, 255)
    arrow(d, 700, 180, 890, 255)
    arrow(d, 600, 400, 600, 465)
    img.save(OUT / "fig_server_supervisor.png")


def save_mitre_soar():
    w, h = 1200, 640
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    title(d, w, "MITRE Mapping + SOAR Playbook Example (Ransomware)")
    box(d, (40, 90, 360, 200), "Detected Label\nRansomware", fill=PANEL2)
    box(d, (420, 90, 760, 200), "MITRE ATT&CK\nImpact / T1486")
    box(d, (820, 90, 1160, 200), "Playbook\nRansomware IR")
    arrow(d, 360, 145, 415, 145)
    arrow(d, 760, 145, 815, 145)
    steps = ["create_alert", "enrich_mitre\n+ TI", "Telegram\n+ Local sound", "block_ip\nHigh+"]
    for i, t in enumerate(steps):
        x1 = 40 + i * 290
        box(d, (x1, 280, x1 + 250, 400), t)
        if i < 3:
            arrow(d, x1 + 250, 340, x1 + 285, 340)
    box(d, (220, 470, 980, 570), "Then: queue_online_sample for incremental learning", fill=GREEN)
    img.save(OUT / "fig_mitre_soar.png")


if __name__ == "__main__":
    save_architecture()
    save_pipeline()
    save_deployment()
    save_mitre_soar()
    print("Saved to", OUT)
    for p in sorted(OUT.glob("*.png")):
        print(" -", p.name, p.stat().st_size)
