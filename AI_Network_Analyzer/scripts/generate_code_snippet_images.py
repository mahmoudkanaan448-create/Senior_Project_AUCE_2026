"""Generate research-paper code snippet images + Arabic captions index."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "research_paper_assets" / "code_snippets"
OUT.mkdir(parents=True, exist_ok=True)

# Navy + gold theme
BG = (12, 26, 46)
PANEL = (18, 35, 61)
GOLD = (212, 175, 55)
WHITE = (248, 250, 252)
MUTED = (148, 163, 184)
GREEN = (134, 239, 172)
CODE_KW = (125, 211, 252)
CODE_STR = (253, 224, 71)
CODE_CMT = (148, 163, 184)

SNIPPETS = [
    {
        "file": "01_hybrid_ai_decision_fusion.png",
        "title_en": "Decision Fusion (Hybrid AI)",
        "title_ar": "اندماج قرارات النماذج الخمسة",
        "why_ar": "يُستخدم في الورقة لإظهار كيف يُدمَج خرج النماذج في قرار نهائي واحد مع درجة تهديد.",
        "path": ROOT / "detection" / "decision_engine.py",
        "max_lines": 55,
    },
    {
        "file": "02_attack_detector.png",
        "title_en": "Multi-Model Attack Detector",
        "title_ar": "محرك الكشف متعدد النماذج",
        "why_ar": "يوضح تحميل النماذج وتشغيل التنبؤ على تدفق واحد (قلب نظام NDR).",
        "path": ROOT / "detection" / "attack_detector.py",
        "max_lines": 60,
    },
    {
        "file": "03_feature_extraction.png",
        "title_en": "Feature Extraction",
        "title_ar": "استخراج خصائص حركة الشبكة",
        "why_ar": "مهم علمياً: تحويل الحزم/التدفقات إلى متجه رقمي للنماذج.",
        "path": ROOT / "monitoring" / "feature_extraction.py",
        "max_lines": 55,
    },
    {
        "file": "04_live_capture.png",
        "title_en": "Live Traffic Capture",
        "title_ar": "التقاط الحركة الحية",
        "why_ar": "يبين آلية المراقبة الحية (Scapy أو اتصالات النظام).",
        "path": ROOT / "monitoring" / "live_capture.py",
        "max_lines": 55,
    },
    {
        "file": "05_neural_models.png",
        "title_en": "Autoencoder / Sequence Models",
        "title_ar": "نماذج التعلم العميق / الشبكات العصبية",
        "why_ar": "يوضح دعم Python 3.14 عبر PyTorch أو بديل scikit-learn.",
        "path": ROOT / "training" / "neural_models.py",
        "max_lines": 55,
    },
    {
        "file": "06_xai.png",
        "title_en": "Explainable AI (XAI)",
        "title_ar": "الذكاء الاصطناعي القابل للتفسير",
        "why_ar": "يعزز الشفافية: لماذا اتخذ النموذج القرار (مهم للجنة).",
        "path": ROOT / "explainable_ai" / "xai.py",
        "max_lines": 50,
    },
    {
        "file": "07_auth_jwt.png",
        "title_en": "JWT Authentication",
        "title_ar": "المصادقة الآمنة JWT",
        "why_ar": "يظهر الجانب الأمني للنظام (bcrypt + JWT).",
        "path": ROOT / "api" / "authentication.py",
        "max_lines": 50,
    },
    {
        "file": "08_fastapi_routes.png",
        "title_en": "REST API Routes",
        "title_ar": "واجهات REST API",
        "why_ar": "يثبت المعمارية الخدمية وطريقة استدعاء التنبؤ.",
        "path": ROOT / "api" / "routes.py",
        "max_lines": 55,
    },
]


def font(size: int, bold: bool = False):
    candidates = [
        r"C:\Windows\Fonts\consola.ttf",
        r"C:\Windows\Fonts\cour.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    if bold:
        candidates = [
            r"C:\Windows\Fonts\consolab.ttf",
            r"C:\Windows\Fonts\courbd.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
        ] + candidates
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def arabic_font(size: int):
    for p in [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
        r"C:\Windows\Fonts\seguiemj.ttf",
    ]:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def pick_lines(path: Path, max_lines: int) -> list[str]:
    if not path.exists():
        return [f"# Missing file: {path}"]
    raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
    # Prefer starting near a def/class after module docstring
    start = 0
    for i, line in enumerate(raw):
        if line.startswith("def ") or line.startswith("class "):
            start = i
            break
    chunk = raw[start : start + max_lines]
    # number lines
    return [f"{start + i + 1:>4}| {line}" for i, line in enumerate(chunk)]


def colorize(line: str) -> tuple[str, tuple]:
    stripped = line[6:] if len(line) > 6 and line[5] == "|" else line
    s = stripped.lstrip()
    if s.startswith("#") or s.startswith('"""') or s.startswith("'''"):
        return line, CODE_CMT
    if s.startswith("def ") or s.startswith("class ") or s.startswith("return ") or s.startswith("import ") or s.startswith("from "):
        return line, CODE_KW
    if '"' in s or "'" in s:
        return line, WHITE
    return line, WHITE


def render_snippet(spec: dict) -> Path:
    lines = pick_lines(spec["path"], spec["max_lines"])
    f_code = font(15)
    f_title = font(22, bold=True)
    f_ar = arabic_font(18)
    f_small = arabic_font(14)

    line_h = 22
    width = 1100
    header_h = 110
    height = header_h + 30 + len(lines) * line_h + 40

    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, width, header_h], fill=PANEL)
    draw.rectangle([0, header_h - 4, width, header_h], fill=GOLD)

    draw.text((24, 18), spec["title_en"], fill=GOLD, font=f_title)
    # Arabic may need reshape for correct display - try plain first
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        ar_title = get_display(arabic_reshaper.reshape(spec["title_ar"]))
        ar_why = get_display(arabic_reshaper.reshape(spec["why_ar"]))
    except Exception:
        ar_title = spec["title_ar"]
        ar_why = spec["why_ar"]

    draw.text((24, 50), ar_title, fill=WHITE, font=f_ar)
    draw.text((24, 78), ar_why, fill=MUTED, font=f_small)

    y = header_h + 16
    rel = spec["path"].relative_to(ROOT).as_posix()
    draw.text((24, y), f"# File: {rel}", fill=GREEN, font=f_code)
    y += line_h + 6

    for line in lines:
        text, col = colorize(line)
        # truncate long lines
        if len(text) > 120:
            text = text[:117] + "..."
        draw.text((24, y), text, fill=col, font=f_code)
        y += line_h

    out = OUT / spec["file"]
    img.save(out, "PNG")
    return out


def main():
    index_lines = [
        "# Code Snippets for Research Paper",
        "",
        "Use these images in the Implementation / Methodology section.",
        "",
    ]
    for spec in SNIPPETS:
        out = render_snippet(spec)
        print("Wrote", out)
        index_lines += [
            f"## {spec['title_en']}",
            f"- Arabic: {spec['title_ar']}",
            f"- Why: {spec['why_ar']}",
            f"- Image: `code_snippets/{spec['file']}`",
            f"- Source: `{spec['path'].relative_to(ROOT).as_posix()}`",
            "",
        ]
    (OUT.parent / "CODE_SNIPPETS_INDEX.md").write_text("\n".join(index_lines), encoding="utf-8")
    print("Index written")


if __name__ == "__main__":
    main()
