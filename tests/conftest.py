"""Make the Lab 7B/8B modules (plain scripts under src/ocr_system, not an installed package) importable."""
import sys
from pathlib import Path

LAB_SRC = Path(__file__).resolve().parents[1] / "Lab7B_Lab8B_ocr_system" / "src" / "ocr_system"
if str(LAB_SRC) not in sys.path:
    sys.path.insert(0, str(LAB_SRC))
