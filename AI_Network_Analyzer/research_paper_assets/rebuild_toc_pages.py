"""Rebuild static TOC page numbers using Word COM heading page lookup."""
from __future__ import annotations

import re
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent / "_working_thesis.docx"
DESKTOP = Path(
    r"C:\Users\mohamad\OneDrive\Desktop\AI_Powered_Network_Traffic_Analyser_Anomaly_Detector_AUCE_FINAL_UPDATED.docx"
)


def norm_key(t: str) -> str:
    t = re.sub(r"\t\d+$", "", t.strip())
    t = re.sub(r"\s+", " ", t)
    return t.lower()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    src = WORK if WORK.exists() else DESKTOP
    if not src.exists():
        raise SystemExit(f"Missing {src}")

    import win32com.client

    wdActiveEndPageNumber = 7
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = word.Documents.Open(str(src.resolve()), ReadOnly=False)
    if doc is None:
        raise RuntimeError("Word failed to open document")

    # Build map: heading text -> page number (first match)
    pages: dict[str, int] = {}
    for i in range(1, doc.Paragraphs.Count + 1):
        para = doc.Paragraphs(i)
        try:
            st = para.Style.NameLocal if para.Style else ""
        except Exception:
            st = ""
        if not st.startswith("Heading"):
            continue
        t = (para.Range.Text or "").strip().replace("\r", "").replace("\x07", "")
        if not t:
            continue
        try:
            pg = para.Range.Information(wdActiveEndPageNumber)
        except Exception:
            pg = 0
        key = norm_key(t)
        if key not in pages:
            pages[key] = int(pg)

    # Also map numbered prefixes like "4.3.1 Per-Model..."
    for i in range(1, doc.Paragraphs.Count + 1):
        para = doc.Paragraphs(i)
        try:
            st = para.Style.NameLocal if para.Style else ""
        except Exception:
            st = ""
        if not st.lower().startswith("toc"):
            continue
        raw = (para.Range.Text or "").strip().replace("\r", "").replace("\x07", "")
        if not raw:
            continue
        title = raw.split("\t")[0].strip()
        key = norm_key(title)
        pg = pages.get(key)
        if pg is None:
            # try partial: match by section number prefix
            m = re.match(r"^(\d+(?:\.\d+)*)", title)
            if m:
                num = m.group(1)
                for k, v in pages.items():
                    if k.startswith(num + " ") or k.startswith("chapter " + num):
                        pg = v
                        break
        if pg:
            para.Range.Text = f"{title}\t{pg}"
        # chapter headings
        m2 = re.match(r"^(Chapter \d+ - .+)$", title, re.I)
        if m2 and pages.get(norm_key(m2.group(1))):
            para.Range.Text = f"{title}\t{pages[norm_key(m2.group(1))]}"

    doc.Fields.Update()
    for i in range(1, doc.TablesOfContents.Count + 1):
        doc.TablesOfContents(i).Update()
    doc.Save()

    # Save copy to desktop if possible
    try:
        doc.SaveAs2(str(DESKTOP.resolve()))
        print("Saved Desktop:", DESKTOP)
    except Exception as exc:
        print("Desktop save:", exc)
        doc.Save()

    doc.Close()
    word.Quit()

    stale = 0
    from docx import Document

    check = Document(str(src))
    for p in check.paragraphs:
        st = (p.style.name if p.style else "").lower()
        if st.startswith("toc") and (p.text or "").strip().endswith("\t3"):
            stale += 1
    print(f"Remaining TOC entries with page 3: {stale}")


if __name__ == "__main__":
    main()
