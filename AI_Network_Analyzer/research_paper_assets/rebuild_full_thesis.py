"""
Full thesis rebuild from WORKING_LOF template + all 19 doctor points.
Output: Desktop FINAL_UPDATED.docx  |  PDF on Desktop is NOT deleted.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent
DESKTOP = Path(r"C:\Users\mohamad\OneDrive\Desktop")
FINAL = DESKTOP / "AI_Powered_Network_Traffic_Analyser_Anomaly_Detector_AUCE_FINAL_UPDATED.docx"

BASE = ASSETS / "WORKING_LOF.docx"
for alt in (ASSETS / "_master_work.docx", ASSETS / "ORIGINAL_FINAL.docx"):
    if not BASE.exists() and alt.exists():
        BASE = alt

STAGING = ASSETS / "_REBUILD_STAGING.docx"


def step(label: str, cmd: list[str], cwd: str | None = None) -> None:
    print(f"\n{'='*60}\n{label}\n{'='*60}")
    subprocess.run(cmd, check=True, cwd=cwd or str(ASSETS))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if not BASE.exists():
        raise SystemExit(f"Base template missing: {BASE}")

    step("1. Regenerate metrics & figures", [
        sys.executable, "-m", "training.evaluate_models",
    ], cwd=str(ROOT))
    step("2. Academic diagrams", [sys.executable, "generate_academic_diagrams.py"])
    step("3. Evaluation figures", [sys.executable, "render_eval_figures.py"])

    print(f"\n{'='*60}\n4. Copy base template\n{'='*60}")
    shutil.copy2(BASE, STAGING)
    print(BASE.name, "->", STAGING.name)

    import doctor_email_revision as dr

    dr.PAPER = STAGING
    dr.BACKUP = ASSETS / "_dr_revision_backup.docx"
    print("\n5. Doctor email revision (points 1-11)...")
    dr.main()

    import doctor_complete_revision as dcr

    dcr.PAPER = STAGING
    print("\n6. Doctor complete revision (all 19 points)...")
    dcr.main()

    # Polish expects _FINAL_STAGING or desktop file
    shutil.copy2(STAGING, ASSETS / "_FINAL_STAGING.docx")
    # Polish inline (skip subprocess verify exit — master_reorder fixes TOC)
    import polish_final_thesis as pl

    print("\n7. Polish (Ch7/8, spacing, figures)...")
    shutil.copy2(STAGING, pl.STAGING)
    doc = __import__("docx").Document(str(pl.STAGING))
    pl.remove_chapter7(doc)
    pl.renumber_chapter8_to_7(doc)
    pl.fix_toc(doc)
    pl.fix_global_chapter_refs(doc)
    pl.space_body_text(doc)
    pl.space_captions(doc)
    pl.space_tables(doc)
    pl.refresh_key_figures(doc)
    pl.enlarge_figures(doc)
    pl.page_break_before_chapters(doc)
    doc.save(str(pl.STAGING))
    polished = pl.STAGING
    shutil.copy2(polished, ASSETS / "_master_work.docx")

    step("8. Master reorder (TOC, headings, tables)", [sys.executable, "master_reorder.py"])

    master = ASSETS / "FINAL_MASTER.docx"
    if master.exists():
        shutil.copy2(master, STAGING)
        shutil.copy2(master, FINAL)
    else:
        shutil.copy2(polished, FINAL)

    # Final pass updates images + verify
    import final_pass as fp

    fp.PAPER = FINAL
    step("9. Final pass (images, captions, verify)", [sys.executable, "final_pass.py"])

    import verify_doctor_revision as vd

    passed, lines = vd.run_checks(FINAL)
    print(f"\n{'='*60}\nVERIFICATION: {passed}/{len(lines)}\n{'='*60}")
    for ln in lines:
        print(ln)
    if passed < len(lines):
        raise SystemExit("Doctor verification FAILED")

    print(f"\nSUCCESS: {FINAL}")
    print(f"Size: {FINAL.stat().st_size:,} bytes")
    print("PDF on Desktop kept unchanged.")


if __name__ == "__main__":
    main()
