"""
Rebuild the Desktop thesis from the PDF-era baseline (WORKING_LOF.docx):
- Same template, Harvard references, figure/table order, Appendix H
- Apply only the latest app-alignment updates (16 pages, 12k eval, Company, etc.)
- Smart layout tidy + Word TOC refresh
- Run verify_paper_10x before saving final copy
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / "WORKING_LOF.docx"
OUTPUT = Path(
    r"C:\Users\mohamad\OneDrive\Desktop\AI_Powered_Network_Traffic_Analyser_Anomaly_Detector_AUCE_FINAL_UPDATED.docx"
)
STAGING = ROOT / "_BUILD_STAGING.docx"


def patch_and_run(module_name: str, paper: Path) -> None:
    mod = __import__(module_name)
    mod.PAPER = paper
    if hasattr(mod, "BACKUP"):
        mod.BACKUP = paper.with_name(paper.stem + "_build_backup.docx")
    mod.main()


def main() -> None:
    if not BASELINE.exists():
        raise SystemExit(f"Missing baseline template: {BASELINE}")

    print("1/6 Copy baseline (PDF-era structure + Harvard + LoF/LoT)...")
    shutil.copy2(BASELINE, STAGING)

    print("2/6 Regenerate evaluation figures from metrics.json...")
    subprocess.run(
        [sys.executable, str(ROOT / "render_eval_figures.py")],
        check=True,
        cwd=str(ROOT),
    )

    print("3/6 App realism content (12k, 16 pages, XAI, Company, Live Evidence)...")
    patch_and_run("update_paper_realism", STAGING)

    print("4/6 Tables/objectives/tech stack + figure image swap...")
    patch_and_run("align_paper_to_app", STAGING)

    print("5/6 Smart layout (readable figures, spacing, Word TOC)...")
    patch_and_run("tidy_paper_layout", STAGING)

    print("6/6 Ten verification passes...")
    from verify_paper_10x import run_checks

    passed, lines = run_checks(STAGING)
    for line in lines:
        print(" ", line)
    if passed < len(lines):
        raise SystemExit(
            f"Verification failed ({passed}/{len(lines)}). Staging kept at {STAGING}"
        )

    shutil.copy2(STAGING, OUTPUT)
    print("Saved:", OUTPUT)
    print(f"All {passed} checks passed.")


if __name__ == "__main__":
    main()
