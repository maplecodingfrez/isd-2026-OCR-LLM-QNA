"""Make the Lab 7B/8B modules (plain scripts under src/ocr_system, not an installed package) importable,
plus the Chapter 10 API packages (`ocr_system.api` under src/, `lab10_fastapi` at the repo root)."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAB_SRC = REPO_ROOT / "Lab7B_Lab8B_ocr_system" / "src" / "ocr_system"
for path in (REPO_ROOT, REPO_ROOT / "src", LAB_SRC):  # LAB_SRC inserted last = searched first, as before
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
