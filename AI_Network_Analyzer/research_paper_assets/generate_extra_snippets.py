"""Extra code snippet images for newly implemented modules."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "research_paper_assets" / "code_snippets"
OUT.mkdir(parents=True, exist_ok=True)

BG = (12, 26, 46)
PANEL = (18, 35, 61)
GOLD = (212, 175, 55)
WHITE = (248, 250, 252)
MUTED = (148, 163, 184)
GREEN = (134, 239, 172)

SNIPPETS = [
    ("09_mitre_map.png", "MITRE ATT&CK Mapping", ROOT / "threat_intelligence" / "mitre_map.py", 45),
    ("10_soar_playbooks.png", "SOAR Playbooks", ROOT / "soar" / "playbooks.py", 45),
    ("11_soar_engine.png", "SOAR Engine", ROOT / "soar" / "engine.py", 50),
    ("12_online_learning.png", "Online Incremental Learning", ROOT / "training" / "online_learning.py", 50),
    ("13_alert_manager.png", "Alert Manager + Playbook Hook", ROOT / "alerts" / "alert_manager.py", 50),
    ("14_threat_simulation.png", "Threat Simulation Engine", ROOT / "detection" / "attack_simulator.py", 45),
    ("15_supervisor.png", "Server Auto-Recovery Supervisor", ROOT / "ops" / "supervisor.py", 45),
    ("16_telegram_alert.png", "Telegram Alert Delivery", ROOT / "alerts" / "telegram_alert.py", 40),
    ("17_ai_assistant.png", "AI Security Assistant", ROOT / "soc" / "assistant.py", 45),
]


def _font(size=14):
    for name in ("consola.ttf", "CascadiaMono.ttf", "cour.ttf", "DejaVuSansMono.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def render(path_out, title, src, max_lines):
    text = src.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()[:max_lines]
    body = "\n".join(lines)
    font = _font(13)
    title_font = _font(18)
    # measure
    tmp = Image.new("RGB", (10, 10))
    d0 = ImageDraw.Draw(tmp)
    bbox = d0.multiline_textbbox((0, 0), body, font=font)
    w = max(980, bbox[2] + 60)
    h = bbox[3] + 110
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((16, 16, w - 16, h - 16), radius=14, fill=PANEL, outline=GOLD, width=2)
    draw.text((36, 28), title, fill=GOLD, font=title_font)
    draw.text((36, 56), str(src.relative_to(ROOT)).replace("\\", "/"), fill=MUTED, font=font)
    draw.multiline_text((36, 84), body, fill=WHITE, font=font, spacing=4)
    img.save(OUT / path_out)
    print("Wrote", OUT / path_out)


if __name__ == "__main__":
    for fname, title, src, n in SNIPPETS:
        if src.exists():
            render(fname, title, src, n)
        else:
            print("MISSING", src)
