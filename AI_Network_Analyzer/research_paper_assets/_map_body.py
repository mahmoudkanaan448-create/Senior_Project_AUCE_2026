"""Map body element order: paragraphs and tables."""
from docx import Document
from docx.text.paragraph import Paragraph
from pathlib import Path

doc = Document(str(Path(r"C:\Users\mohamad\OneDrive\Desktop\AI_Powered_Network_Traffic_Analyser_Anomaly_Detector_AUCE_FINAL_UPDATED.docx")))
body = doc.element.body
tbl_i = 0
for idx, child in enumerate(body):
    tag = child.tag.split("}")[-1]
    if tag == "p":
        t = (Paragraph(child, body).text or "").strip()
        if any(k in t for k in ("List of", "Chapter 1", "Declaration", "Abstract")) or idx < 30:
            print(f"P{idx}: {t[:70]}")
    elif tag == "tbl":
        trs = child.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr")
        rows = len(trs)
        cols = len(trs[0].findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc")) if trs else 0
        cells = [n.text for n in child.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")][:4]
        prev = ""
        for j in range(idx - 1, max(-1, idx - 5), -1):
            c2 = body[j]
            if c2.tag.split("}")[-1] == "p":
                prev = (Paragraph(c2, body).text or "")[:55]
                break
        print(f"T#{tbl_i} @{idx} {rows}x{cols} after [{prev}] cells={cells}")
        tbl_i += 1
        if tbl_i >= 15:
            break
