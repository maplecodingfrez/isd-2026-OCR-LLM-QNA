#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 lab7b_curriculum.py
 Lab 7B — สกัดแผนการศึกษาจากเล่มหลักสูตร ด้วย LLM ที่รันบนเครื่องตัวเอง
================================================================================

 วิชา 06026240 การพัฒนาระบบอัจฉริยะ  |  เทคโนโลยีสารสนเทศ สจล.
 --------------------------------------------------------------------------
 ⚠️  ข้อบังคับ: รันแบบออฟไลน์ 100% ไม่มีค่าใช้จ่าย
 --------------------------------------------------------------------------
 แม้เล่มหลักสูตรจะเป็นเอกสารสาธารณะ (ไม่เข้าข่าย PDPA) แต่แล็บนี้กำหนดให้
 ทุกกลุ่มใช้โมเดลที่รันบนเครื่องเท่านั้น ด้วยเหตุผล 3 ข้อ:
   1. นักศึกษาต้องไม่มีค่าใช้จ่าย
   2. ผลลัพธ์ต้องทำซ้ำได้ (API ภายนอกเปลี่ยนโมเดลเงียบ ๆ เมื่อไรก็ได้)
   3. เป็นทักษะที่ใช้ได้จริงเมื่อไปทำงานกับข้อมูลที่ห้ามออกนอกองค์กร

 --------------------------------------------------------------------------
 วิธีใช้
 --------------------------------------------------------------------------
   python3 lab7b_curriculum.py --check

   python3 lab7b_curriculum.py \
       --input data/DSBA_plan.pdf \
       --gt    gt/DSBA_academic_plan_coop.json \
       --pipeline all --out output/

   # เล่มหลักสูตรยาวมาก ให้ระบุเฉพาะหน้าที่เป็นตารางแผนการศึกษา
   python3 lab7b_curriculum.py -i data/DSBA.pdf --pages 42-58 -g gt/x.json

   # มี pred_*.json (ผล OCR) อยู่แล้ว อยากแค่คำนวณ P/R/F1/CER/WER ใหม่กับ GT อีกไฟล์
   # โดยไม่เรียก Typhoon-OCR/qwen3 ซ้ำ (แค่ print ผลออกจอ ไม่เขียนไฟล์ — ถ้าต้องการเขียนไฟล์
   # evaluation.json/comparison.csv ทับด้วย ใช้ regenerate_evaluation.py ที่โฟลเดอร์นี้แทน)
   python3 lab7b_curriculum.py --eval-only output/pred_vlm.json -g gt/x.json

================================================================================
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import lab7_metrics as M  # noqa: E402


# ==============================================================================
#  ส่วนที่ 0 — ค่าตั้งต้น
# ==============================================================================

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL_OCR = os.getenv("LAB7_MODEL_OCR", "scb10x/typhoon-ocr1.5-3b")
MODEL_TEXT = os.getenv("LAB7_MODEL_TEXT", "qwen3:4b")
DPI = int(os.getenv("LAB7_DPI", "150"))
# บนเครื่อง CPU-only การเรียก qwen3:4b หนึ่งครั้งอาจใช้เวลาหลายร้อยวินาที
# (กลุ่ม B วัดได้ ~400-460 วิ/ครั้ง) ค่า 900 วิเดิมจึงตัดงานทิ้งกลางคันได้
# --> เปิดให้ตั้งผ่าน env LAB7B_REQUEST_TIMEOUT (กลุ่ม B ใช้ 7200)
REQUEST_TIMEOUT = int(os.getenv("LAB7B_REQUEST_TIMEOUT", "900"))
NUM_CTX = int(os.getenv("LAB7B_NUM_CTX", "8192"))
NUM_PREDICT = int(os.getenv("LAB7B_NUM_PREDICT", "4096"))
OCR_NUM_CTX = int(os.getenv("LAB7B_OCR_NUM_CTX", "4096"))
OCR_NUM_PREDICT = int(os.getenv("LAB7B_OCR_NUM_PREDICT", "1200"))

# ⭐ ค่าเฉพาะของกลุ่ม B
# เล่มหลักสูตรมี 50-150 หน้า ส่งเข้าโมเดลทีเดียวไม่ได้แน่นอน
# เราจึง "แบ่งเป็นก้อน" (chunk) ทีละไม่กี่หน้า แล้วรวมผลทีหลัง
PAGES_PER_CHUNK = int(os.getenv("LAB7_CHUNK", "3"))

# ข้าม pipeline baseline (Tesseract) ทั้งหมด
#     export LAB7_SKIP_BASELINE=1
# ⚠️ ผลที่ตามมา: จะไม่มีเส้นฐานไว้เปรียบเทียบ ทำให้ตอบคำถามท้ายบท
#    ชุดที่ 2 (เปรียบเทียบ pipeline) ไม่ได้ และเสียคะแนนส่วนที่ 3
SKIP_BASELINE = os.getenv("LAB7_SKIP_BASELINE", "").strip() in ("1", "true", "yes")


# ==============================================================================
#  ส่วนที่ 1 — ตรวจความพร้อม / ยืนยันออฟไลน์
# ==============================================================================


def _need(mod: str, pipname: str = "") -> Any:
    try:
        return __import__(mod)
    except ImportError:
        raise SystemExit(f"\n❌ ไม่พบไลบรารี '{mod}'\n   ติดตั้ง: pip install {pipname or mod}\n")


def assert_offline() -> None:
    """ตรวจว่า Ollama ชี้ไปที่เครื่องตัวเอง — fail closed ถ้าไม่แน่ใจ"""
    allowed = ("127.0.0.1", "localhost", "0.0.0.0", "::1")
    host = OLLAMA_HOST.replace("http://", "").replace("https://", "").split(":")[0]
    if host not in allowed:
        raise SystemExit(
            f"\n❌ OLLAMA_HOST = {OLLAMA_HOST} ไม่ใช่เครื่องภายใน\n"
            f"   แล็บนี้กำหนดให้รันออฟไลน์เท่านั้น  แก้โดย: unset OLLAMA_HOST\n")
    print(f"✓ ยืนยันโหมดออฟไลน์: {OLLAMA_HOST}")


def check_environment() -> bool:
    ok = True
    print("\n" + "=" * 70)
    print("  ตรวจความพร้อมของเครื่อง")
    print("=" * 70)

    if shutil.which("ollama"):
        try:
            v = subprocess.run(["ollama", "--version"], capture_output=True,
                               text=True, timeout=10).stdout.strip()
            print(f"  ✓ พบ Ollama: {v}")
        except Exception:
            print("  ✓ พบ Ollama")
    else:
        print("  ✗ ไม่พบคำสั่ง ollama --> ดูเอกสารแล็บ ส่วนที่ 2")
        ok = False

    try:
        requests = _need("requests")
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        installed = [m["name"] for m in r.json().get("models", [])]
        print(f"  ✓ Ollama service ทำงานที่ {OLLAMA_HOST}")
        for tag, role in [(MODEL_OCR, "อ่านภาพ"), (MODEL_TEXT, "จัด JSON")]:
            hit = any(i == tag or i.split(":")[0] == tag for i in installed)
            print(f"  {'✓' if hit else '✗'} [{role}] {tag}"
                  + ("" if hit else f"   --> ollama pull {tag}"))
            if not hit:
                ok = False
    except Exception as e:
        print(f"  ✗ ต่อ Ollama ไม่ได้: {e}\n    --> สั่ง: ollama serve")
        ok = False

    for mod, pip in [("fitz", "pymupdf"), ("PIL", "pillow"),
                     ("requests", "requests"), ("pdfplumber", "pdfplumber"),
                     ("pythainlp", "pythainlp")]:
        try:
            __import__(mod)
            print(f"  ✓ python: {mod}")
        except ImportError:
            print(f"  ✗ python: {mod} --> pip install {pip}")
            ok = False

    # --- ของที่ไม่จำเป็น — ขาดได้ ไม่ทำให้ --check ตก ---
    #
    # ⚠️ สังเกตว่าส่วนนี้ "ไม่มี ok = False" เลย
    #    สิ่งที่ทำให้ผลตรวจ "ไม่พร้อม" ต้องเป็นสิ่งที่ขาดแล้วรันไม่ได้จริงเท่านั้น
    print("\n  ส่วนเสริม (ขาดได้ ไม่ทำให้ --check ตก):")

    if SKIP_BASELINE:
        print("  ○ tesseract — ข้ามตามค่า LAB7_SKIP_BASELINE=1")
    else:
        has_exe = shutil.which("tesseract") is not None
        try:
            __import__("pytesseract")
            has_lib = True
        except ImportError:
            has_lib = False

        if has_exe and has_lib:
            print("  ✓ tesseract (จาก Lab 5-6) — ใช้กับ pipeline baseline")
        else:
            miss = []
            if not has_lib:
                miss.append("pip install pytesseract")
            if not has_exe:
                miss.append("ติดตั้งตัว engine (ดูเอกสาร Lab 5)")
            print(f"  ✗ tesseract — {' + '.join(miss)}")
            print("      pipeline baseline จะถูกข้ามไป (text และ vlm ยังใช้ได้ตามปกติ)")
            print("      ถ้าไม่ต้องการใช้ baseline เลย:  export LAB7_SKIP_BASELINE=1")

    print("=" * 70)
    print("  พร้อมใช้งาน ✓" if ok else "  ยังไม่พร้อม ✗")
    print("=" * 70 + "\n")
    return ok


# ==============================================================================
#  ส่วนที่ 2 — เตรียม input
# ==============================================================================


def parse_page_range(spec: str, total: int) -> list[int]:
    """
    แปลงข้อความอย่าง "42-58" หรือ "3,7,10-12" เป็น list ของ index (เริ่มที่ 0)

    ทำไมต้องมี? เพราะเล่มหลักสูตรมี 150 หน้า แต่ตารางแผนการศึกษาอยู่แค่ 10-20 หน้า
    การส่งทั้งเล่มเข้าโมเดลคือการเผาเวลาไปกับหน้าที่ไม่เกี่ยวข้อง
    (ในระบบที่จ่ายเงินตาม token นี่คือการเผาเงินด้วย)
    """
    idx: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            idx.update(range(int(a) - 1, int(b)))    # ผู้ใช้พิมพ์เลขหน้าเริ่มที่ 1
        elif part:
            idx.add(int(part) - 1)
    return sorted(i for i in idx if 0 <= i < total)


# scb10x/typhoon-ocr1.5-3b (qwen2.5-vl) ปฏิเสธภาพที่ใหญ่เกินไปด้วย HTTP 400
# ภาพสแกน 300 DPI (~2481x3509) เกินเพดาน — หน้าที่อ่านได้จริงกว้าง ~660-1600 px
# ย่อด้านที่ยาวที่สุดให้ไม่เกินค่านี้ก่อนส่งเข้าโมเดล (ตั้งค่าได้ด้วย env)
MAX_IMAGE_DIM = int(os.getenv("LAB7B_MAX_IMAGE_DIM", "1280"))


# ตราน้ำของมหาวิทยาลัยบนหน้าเล่มหลักสูตรเป็นสีส้ม-แดงทับกลางหน้า ทำให้ Typhoon-OCR อ่านแถวใต้ตราน้ำ
# ตกหรือสะกดผิดแบบไม่นิ่ง (AIT หน้า 19 อ่านได้ 2 ใน 4 รอบ) — ช่องสีแดง (R) ของภาพเห็นสีส้มเป็นเกือบขาว
# แต่หมึกดำยังเข้ม จึงใช้ช่อง R อย่างเดียวเป็นภาพขาวดำแล้วดึงระดับให้ส่วนที่จางเป็นขาวสนิท
# ปิดไว้เป็นค่าเริ่มต้น (LAB7B_DEWATERMARK=1 เพื่อเปิด) เพื่อไม่ให้ผลรันเดิมเปลี่ยนโดยไม่ตั้งใจ
DEWATERMARK = os.getenv("LAB7B_DEWATERMARK", "0") == "1"
DEWATERMARK_WHITE = int(os.getenv("LAB7B_DEWATERMARK_WHITE", "225"))


# ตัวกันรายหน้า: ตัดตราน้ำเฉพาะหน้าที่ "มีตราน้ำจริง" — นับพิกเซลสีส้ม-แดงจาง (R สูง แต่ G/B ต่ำกว่า R อย่างน้อย 25)
# ถ้าสัดส่วนน้อยกว่าเกณฑ์ (ค่าเริ่มต้น 1%) ถือว่าหน้าสะอาด ส่งภาพเดิมไม่แตะ — วัดจากภาพจริง: AIT/BIT/IT ราว 8.7% ต่อหน้า
# ส่วน DSBA 0.00% (ช่องว่างกว้าง) เล่มที่ไม่มีตราน้ำจึงได้ภาพไบต์เดิม ผลไม่เปลี่ยนตามโครงสร้าง
# LAB7B_DEWATERMARK_MIN_TINT=0 = ตัดทุกหน้าเหมือนเดิมก่อนมีตัวกัน
DEWATERMARK_MIN_TINT = float(os.getenv("LAB7B_DEWATERMARK_MIN_TINT", "0.01"))


def _watermark_fraction(im) -> float:
    """สัดส่วนพิกเซลสีส้ม-แดงจาง (ตราน้ำ) ของภาพ — ย่อด้วย NEAREST เพื่อไม่ให้สีจางถูกเฉลี่ยจนหาย"""
    import numpy as np
    from PIL import Image
    small = im.convert("RGB").copy()
    small.thumbnail((600, 600), Image.NEAREST)
    a = np.asarray(small).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return float(((r >= 200) & ((r - g) >= 25) & ((r - b) >= 25)).mean())


def _remove_watermark(im):
    """คืนภาพ RGB ที่เหลือเฉพาะหมึก: ใช้ช่อง R; ค่า R >= DEWATERMARK_WHITE ถือเป็นพื้นขาว"""
    r = im.convert("RGB").getchannel("R")
    w = DEWATERMARK_WHITE
    r = r.point([min(255, round(v * 255 / w)) for v in range(256)])
    return r.convert("RGB")


def _fit_image(raw: bytes, name: str = "") -> bytes:
    """ย่อภาพลงถ้าด้านยาวเกิน MAX_IMAGE_DIM (คงสัดส่วน) — ป้องกัน 400 จาก VLM"""
    try:
        from PIL import Image
    except ImportError:
        return raw
    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
    except Exception:
        return raw
    dewm_applied = False
    if DEWATERMARK:
        frac = _watermark_fraction(im)
        if frac >= DEWATERMARK_MIN_TINT:
            im = _remove_watermark(im)   # ตัดตราน้ำก่อนย่อภาพ (ย่อแล้วลายตราน้ำจะปนกับหมึก)
            dewm_applied = True
            print(f"      ตัดตราน้ำ {name}: พบพิกเซลตราน้ำ {frac * 100:.1f}%")
        else:
            print(f"      ไม่ตัดตราน้ำ {name}: ไม่พบตราน้ำ ({frac * 100:.2f}% < {DEWATERMARK_MIN_TINT * 100:g}%) ใช้ภาพเดิม")
    longest = max(im.size)
    if longest <= MAX_IMAGE_DIM and not dewm_applied:
        return raw                       # ภาพเล็กอยู่แล้ว/หน้าสะอาด — ส่งไบต์เดิม ไม่แตะ
    scale = min(1.0, MAX_IMAGE_DIM / longest)
    new = (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
    if new != im.size:
        im = im.resize(new, Image.LANCZOS)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    print(f"      ย่อภาพ {name}: {longest}px -> {max(im.size)}px")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def load_pages(path: str, page_spec: str | None = None) -> list[bytes]:
    """แปลง PDF เป็นภาพ PNG รายหน้า"""
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"❌ ไม่พบไฟล์: {path}")

    if p.is_dir():
        image_exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
        files = sorted(x for x in p.iterdir() if x.suffix.lower() in image_exts)
        if not files:
            raise SystemExit(f"❌ ไม่พบไฟล์ภาพในโฟลเดอร์: {path}")
        print(f"  อ่านภาพจากโฟลเดอร์ {len(files)} หน้า: "
              + ", ".join(x.name for x in files))
        return [_fit_image(x.read_bytes(), x.name) for x in files]

    if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        return [_fit_image(p.read_bytes(), p.name)]

    fitz = _need("fitz", "pymupdf")
    doc = fitz.open(str(p))
    wanted = parse_page_range(page_spec, len(doc)) if page_spec else range(len(doc))

    if page_spec:
        print(f"  เล่มมี {len(doc)} หน้า — เลือกใช้ {len(list(wanted))} หน้า")

    mat = fitz.Matrix(DPI / 72, DPI / 72)
    pages = []
    for i in wanted:
        pix = doc[i].get_pixmap(matrix=mat)
        pages.append(pix.tobytes("png"))
    doc.close()
    print(f"  แปลงเป็นภาพแล้ว {len(pages)} หน้า @ {DPI} DPI")
    return pages


def extract_pdf_text(path: str, page_spec: str | None = None) -> str:
    """
    ดึงข้อความจาก PDF โดยตรง (ถ้าเป็น PDF ที่ฝังข้อความไว้ ไม่ใช่ภาพสแกน)

    ⚠️ ประเด็นสำคัญของกลุ่ม B:
       เล่มหลักสูตรจำนวนมากเป็น "digital PDF" ที่มีข้อความอยู่แล้ว
       ถ้าเป็นแบบนั้น การเอาไปทำ OCR คือการทำงานซ้ำซ้อนโดยไม่จำเป็น
       และยังทำให้ผลแย่ลง เพราะ OCR มีโอกาสอ่านผิด แต่ข้อความที่ฝังมาไม่ผิด

       --> ตรวจก่อนเสมอ ว่าดึงข้อความตรง ๆ ได้ไหม
       เกณฑ์ที่ใช้: ถ้าดึงได้เกิน 500 ตัวอักษรต่อหน้า ถือว่าเป็น digital PDF

    ⚠️ แต่มีข้อควรระวัง: extract_text() ธรรมดา "ทำตารางพัง"
       คอลัมน์จะปนกันมั่ว --> ต้องใช้ layout=True เพื่อรักษาตำแหน่ง
       นี่คือเหตุผลที่ตาราง "แผนการศึกษา" มักอ่านผิดแม้เป็น digital PDF
    """
    pdfplumber = _need("pdfplumber")
    out = []
    with pdfplumber.open(path) as pdf:
        wanted = parse_page_range(page_spec, len(pdf.pages)) if page_spec \
            else range(len(pdf.pages))
        for i in wanted:
            # layout=True รักษาระยะห่างแนวนอน ทำให้คอลัมน์ยังเรียงกันอยู่
            t = pdf.pages[i].extract_text(layout=True) or ""
            out.append(f"\n=== หน้า {i + 1} ===\n{t}")
    return "\n".join(out)


# ==============================================================================
#  ส่วนที่ 3 — JSON SCHEMA
# ==============================================================================
#
#  Schema ต้องตรงกับ ground truth (DSBA_academic_plan_coop.json) เป๊ะ ๆ
#
#  ⚠️ ข้อสังเกตจาก ground truth จริง ที่ต้องสะท้อนใน schema:
#
#   1. `year` และ `semester` เป็น "0" ได้ ซึ่งไม่ได้แปลว่าปี 0
#      แต่แปลว่า "วิชาเลือก ที่ยังไม่กำหนดว่าจะลงปีไหน/ภาคไหน"
#      กรณีนี้ต้องกรอก flexible_year_semester แทน เช่น "3/1, 3/2, 4/1"
#
#   2. (ตัดออกแล้ว) เดิม schema มีฟิลด์ `prerequisite` ตาม GT แต่หน้าตารางแผนการศึกษา
#      ("ปีที่ N ภาคที่ M") ที่ป้อนเข้า pipeline นี้จริง ๆ ไม่มีคอลัมน์วิชาบังคับก่อนอยู่เลย
#      (ข้อมูลจริงถ้ามีอยู่ที่ภาคผนวก "3.4 คำอธิบายรายวิชา" คนละหน้าที่ไม่ได้ป้อนเข้ามา)
#      qwen3:4b เคยเดาความสัมพันธ์เองจากลำดับวิชาในตาราง (ผิดชัดเจน — อ้างว่าวิชาในภาคเดียวกัน
#      ต้องเรียนก่อนกัน) ทั้งที่ prompt สอนไว้แล้วว่าห้าม จึงตัดฟิลด์นี้ออกจาก schema ไปเลย
#      ดีกว่าพึ่งให้โมเดลเลือกไม่กรอกเอง — `convert_lab7b()` ฝั่ง Lab 8B อ่านฟิลด์นี้ด้วย .get()
#      อยู่แล้ว จึงไม่พังเมื่อไม่มีฟิลด์นี้ (แค่ไม่เคย insert แถวเข้าตาราง prerequisite เลย)
#      (อัปเดต 2026-09-21) ใบงาน §3.4 ให้ผลของ Lab 7B มีฟิลด์ prerequisite ("ไม่มี" ถ้าไม่มี) — จึงเติมฟิลด์นี้ **หลังโมเดล**
#      ด้วยกฎเชิงกำหนดจากข้อความ OCR ของภาคผนวก (`--book-ocr` / `--fill-prerequisites`, apply_book_prerequisites +
#      prereq_from_book.py; ไม่ใช้ LLM/เฉลย) โมเดลยังไม่เคยกรอกเอง (ยังทิ้งคีย์นี้ที่หลุดมาเหมือนเดิม) และ **ไม่เดา**:
#      อ่านไม่เจอ/อ่านไม่ออก/รหัส wildcard = ไม่ใส่ฟิลด์ (ไม่ทราบ) ไม่ใช่ "ไม่มี"
#
#   3. `credits` เป็น string รูปแบบ "3(3-0-6)"
#      แปลว่า 3 หน่วยกิต = บรรยาย 3 ชม. - ปฏิบัติ 0 ชม. - ศึกษาเอง 6 ชม.
#      บางวิชาเป็น "3(3-0-6) หรือ 3(2-2-5)" ได้ด้วย
#
#   4. `name_en` ใน GT มีอักขระขึ้นบรรทัดใหม่ (\n) ฝังอยู่
#      เพราะชื่อยาวเกินความกว้างคอลัมน์ใน PDF แล้วถูกตัดบรรทัด
#      --> เราจะจัดการด้วย normalization ไม่ใช่บังคับให้โมเดลเดาว่าตัดตรงไหน
# ==============================================================================

_S = {"type": "string"}
_SN = {"type": ["string", "null"]}

COURSE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "program": _SN,          # เช่น "DSBA"
        "plan": _SN,             # เช่น "coop" หรือ "normal"
        "courses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": _S,           # รหัสวิชา 8 หลัก
                    "name_th": _SN,
                    "name_en": _SN,
                    "credits": _SN,       # "3(3-0-6)"
                    "year": {"type": ["integer", "string", "null"]},
                    "semester": {"type": ["integer", "string", "null"]},
                    "category": _SN,      # หมวดวิชาศึกษาทั่วไป / เฉพาะ / เลือกเสรี
                    "type": _SN,          # บังคับ / เลือก
                    # ไม่มี "prerequisite" แล้วโดยตั้งใจ — ดูคำอธิบายเหตุผลด้านบน (ส่วนที่ 3)
                    "flexible_year_semester": _SN,
                    "note": _SN,
                },
                "required": ["code", "name_th", "credits", "year", "semester"],
            },
        },
    },
    "required": ["courses"],
}


# ==============================================================================
#  ส่วนที่ 4 — PROMPT
# ==============================================================================

SYSTEM_PROMPT = """You are a precise document extraction system for Thai university curriculum documents.
You transcribe exactly what is printed. You never invent courses that are not in the document.
You never stop early. When a field is absent you output null."""

EXTRACT_PROMPT = """ต่อไปนี้คือข้อความจากเล่มหลักสูตรของสถาบันในประเทศไทย
จงสกัดรายวิชาทั้งหมดออกมาเป็น JSON ตาม schema ที่กำหนด

=== กติกา ===

[1] สกัดทุกวิชาที่ปรากฏ ห้ามข้าม ห้ามหยุดกลางทาง
    ดูให้ครบทุกหมวด:
      - หมวดวิชาศึกษาทั่วไป
      - หมวดวิชาเฉพาะ (กลุ่มวิชาแกน / กลุ่มวิชาเฉพาะด้าน / กลุ่มวิชาบังคับ / กลุ่มวิชาเลือก)
      - หมวดวิชาเลือกเสรี
      - รายวิชาสหกิจศึกษา (ถ้ามี)

[2] ปี/ภาคการศึกษา — อ่านให้ดี ตรงนี้ผิดกันบ่อย
    - วิชาบังคับที่ตารางแผนการศึกษาระบุปี/ภาคชัดเจน
        --> ใส่ year = 1..4 และ semester = 1..3 ตามที่ระบุ
        --> flexible_year_semester = null
    - วิชาเลือก ที่ตารางบอกว่าลงได้หลายภาค
        --> ใส่ year = 0 และ semester = 0
        --> แล้วระบุตัวเลือกใน flexible_year_semester เช่น "3/1, 3/2, 4/1"
    ห้ามเดาปี/ภาคให้วิชาเลือกที่เอกสารไม่ได้ระบุ
    - ⭐ ถ้าข้อความหน้านี้ "ไม่มี" หัวข้อ "ปีที่ X ภาคการศึกษาที่ Y"
      (เช่น เป็นส่วนคำอธิบายรายวิชา หรือรายการวิชาเลือกล้วน ๆ ที่ไม่ใช่ตารางแผน)
      --> ใส่ year = null และ semester = null ทั้ง flexible_year_semester = null
      ห้ามเดา year = 1 หรือใส่ 0 ให้วิชาที่หน้านั้นไม่ได้อยู่ในตารางแผนเลย

[3] credits ให้คัดลอกตามที่พิมพ์ เช่น "3(3-0-6)" หรือ "3(2-2-5)"
    ห้ามแปลงเป็นตัวเลขเดี่ยว  ถ้าเอกสารเขียนสองแบบ ให้คงไว้ทั้งสอง
    เช่น "3(3-0-6) หรือ 3(2-2-5)"

[4] category ต้องเป็นหนึ่งใน 3 ค่านี้เท่านั้น:
    "หมวดวิชาศึกษาทั่วไป" | "หมวดวิชาเฉพาะ" | "หมวดวิชาเลือกเสรี"

[5] type ต้องเป็น "บังคับ" หรือ "เลือก" เท่านั้น

[6] ชื่อวิชา — แยกไทยกับอังกฤษให้ชัด
    - name_th ใส่เฉพาะอักษรไทย  name_en ใส่เฉพาะอักษรโรมัน (ตัวพิมพ์ใหญ่ตามพิมพ์)
    - ถ้า OCR รวมชื่อไทยกับอังกฤษมาไว้ในช่องเดียว เช่น
        "พีชคณิตเชิงเส้น LINEAR ALGEBRA"
      ให้แยกเป็น name_th = "พีชคณิตเชิงเส้น", name_en = "LINEAR ALGEBRA"
      ห้ามปล่อยให้มีอักษรอังกฤษค้างใน name_th
    - ถ้าหน้ามีเฉพาะชื่ออังกฤษ (ไทยหลุดหาย) ให้ name_th = null ห้ามเอาชื่ออังกฤษไปใส่ name_th
    - ถ้าชื่อถูกตัดขึ้นบรรทัดใหม่ ให้ต่อเป็นบรรทัดเดียวโดยเว้นวรรค 1 ครั้ง
    - ตัดข้อความที่ไม่ใช่ชื่อวิชาออก เช่น "มคอ. 2", เลขหน้า, "(บรรยาย-ปฏิบัติ-ศึกษาด้วยตนเอง)"
    - ⭐⭐ "label หัวข้อกลุ่มวิชา" ไม่ใช่ชื่อวิชา — ต้องทิ้งเสมอ ห้ามใช้เป็นชื่อวิชา
      และห้ามต่อเข้ากับชื่อวิชาจริง
      นิยาม (ใช้ได้ทั่วไป ไม่ผูกกับถ้อยคำใดถ้อยคำหนึ่ง): ข้อความส่วนใดที่
        (ก) ขึ้นต้นด้วย "กลุ่มวิชา..." หรือ "หมวดวิชา..." (ตามด้วยคำอะไรก็ได้) หรือลงท้าย
            ด้วย "*"  และ
        (ข) ตัวมันเอง "ไม่มี" รหัสวิชา 8 หลัก และ "ไม่มี" หน่วยกิตรูปแบบ N(N-N-N) กำกับ
      ถือเป็น "หัวข้อคั่นกลุ่ม" ของแถววิชาที่อยู่ถัดไป ให้ตัดทิ้งทุกกรณี ไม่ว่ามันจะอยู่ในรูป
        (1) บรรทัดลอย ๆ ของตัวเอง คั่นอยู่ระหว่างแถววิชาสองแถว
        (2) บรรทัดแรกในเซลล์เดียวกับชื่อวิชา (คั่นด้วย <br/> หรือขึ้นบรรทัดใหม่)
        (3) ⭐ ต่อกับชื่อวิชาอยู่ใน "บรรทัดเดียวกัน" โดยคั่นแค่ช่องว่าง
            (OCR ตารางมักยุบเซลล์มารวมกันแบบนี้ — พบบ่อยที่สุดและพลาดง่ายที่สุด)
      ตัวอย่างที่ต้องได้:
        เซลล์ "กลุ่มวิชาที่กำหนดโดยคณะ*
               การสื่อสารและการนำเสนออย่างมืออาชีพ
               PROFESSIONAL COMMUNICATION AND PRESENTATION"
          --> name_th = "การสื่อสารและการนำเสนออย่างมืออาชีพ",
              name_en = "PROFESSIONAL COMMUNICATION AND PRESENTATION"
        เซลล์ "กลุ่มวิชาด้านการพัฒนาซอฟต์แวร์ วิศวกรรมความต้องการ REQUIREMENT ENGINEERING"
          --> name_th = "วิศวกรรมความต้องการ", name_en = "REQUIREMENT ENGINEERING"
              (ไม่ใช่ "กลุ่มวิชาด้านการพัฒนาซอฟต์แวร์ วิศวกรรมความต้องการ")
        บรรทัดลอย "กลุ่มวิชาด้านโครงสร้างพื้นฐานเทคโนโลยีสารสนเทศ" ที่คั่นก่อนแถว
          "06016419 โครงสร้างพื้นฐานเครือข่ายการสื่อสาร 3(2-2-5)"
          --> ทิ้งบรรทัด label ทั้งบรรทัด แล้ววิชา 06016419 ต้องได้
              name_th = "โครงสร้างพื้นฐานเครือข่ายการสื่อสาร" เท่านั้น
      ถ้าตัด label ออกแล้ว "ไม่เหลือ" ชื่อวิชาภาษาไทยเลย ให้ name_th = null
      ห้ามใช้ label เป็นชื่อสำรองเด็ดขาด

[7] ⭐ แถว "ช่องวิชาเลือก" ที่ยังไม่ระบุวิชาเจาะจง
    ในตารางแผนการศึกษา บางแถวไม่ได้ระบุรหัสวิชาจริง แต่เขียนว่า
    "วิชาเลือกกลุ่ม..." หรือ "วิชาเลือกเสรี" พร้อมรหัสที่มี x เช่น
        06026xxx  9064xxxx  xxxxxxxx
    แถวเหล่านี้ "เป็นข้อมูลจริง" ต้องสกัดออกมาด้วย ห้ามข้าม
    ให้คัดลอกรหัสตามที่พิมพ์ (เก็บตัว x ไว้) และคัดลอกชื่อตามที่พิมพ์
    ถ้ามีหลายแถวชื่อคล้ายกัน ให้แยกเป็นคนละรายการ เช่น
        "วิชาเลือกกลุ่มวิทยาการข้อมูล 1" และ "วิชาเลือกกลุ่มวิทยาการข้อมูล 2"

[8] ห้ามสร้างวิชาที่ไม่มีในเอกสาร ห้ามเติมวิชาที่ "น่าจะมี"
    ถ้าไม่แน่ใจว่าแถวนั้นเป็นวิชาหรือไม่ ให้ข้าม ดีกว่าใส่ข้อมูลผิด
    (แต่แถวช่องวิชาเลือกตามข้อ [7] ถือเป็นวิชา ต้องเก็บ)

    หมายเหตุ: schema ของงานนี้ไม่มีฟิลด์ prerequisite (วิชาบังคับก่อน) แล้ว เพราะตารางแผนการศึกษา
    ("ปีที่ N ภาคที่ M") ไม่มีคอลัมน์นี้อยู่เลย ไม่ต้องพยายามเดา/อนุมานจากลำดับวิชาในตาราง

=== ข้อความจากเอกสาร ===
{document_text}

=== สิ้นสุดข้อความ ===
ตอบเป็น JSON เท่านั้น"""

TYPHOON_PROMPT = """Extract all text from the image.

Instructions:
- Only return the clean Markdown.
- Do not include any explanation or extra text.
- You must include all information on the page.

Formatting Rules:
- Tables: Render tables using <table>...</table> in clean HTML format.
- Equations: Render equations using LaTeX syntax with inline ($...$) and block ($$...$$).
- Images/Charts/Diagrams: Wrap any clearly defined visual areas (e.g. charts, diagrams, pictures) in:

<figure>
Describe the image's main elements (people, objects, text), note any contextual clues (place, event, culture), mention visible text and its meaning, provide deeper analysis when relevant (especially for financial charts, graphs, or documents), comment on style or architecture if relevant, then give a concise overall summary. Describe in Thai.
</figure>

- Page Numbers: Wrap page numbers in <page_number>...</page_number> (e.g., <page_number>14</page_number>).
- Checkboxes: Use ☐ for unchecked and ☑ for checked boxes."""


# ==============================================================================
#  ส่วนที่ 5 — เรียก Ollama
# ==============================================================================


def ollama_chat(model: str, messages: list[dict], *, fmt: dict | None = None,
                images: list[bytes] | None = None, temperature: float = 0.0,
                retries: int = 2, think: bool | None = None,
                num_ctx: int | None = None,
                num_predict: int | None = None) -> str:
    """เหมือนกับของกลุ่ม A — ดูคำอธิบายละเอียดในเอกสารแล็บ ส่วนที่ 4"""
    requests = _need("requests")

    if images:
        messages = [dict(m) for m in messages]
        messages[-1]["images"] = [base64.b64encode(im).decode() for im in images]

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_ctx": num_ctx or NUM_CTX,
            "num_predict": num_predict or NUM_PREDICT,
        },
    }
    if fmt is not None:
        payload["format"] = fmt
    if think is not None:
        payload["think"] = think

    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            t0 = time.time()
            r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload,
                              timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            body = r.json()
            content = body["message"]["content"]
            # eval_count = จำนวน token ที่โมเดลผลิต — ใช้ดูว่าโดนตัดหรือไม่
            n_out = body.get("eval_count", 0)
            print(f"      ({model}: {time.time() - t0:.1f} วิ, "
                  f"{len(content):,} ตัวอักษร, {n_out:,} tokens)")
            if n_out >= payload["options"]["num_predict"] - 8:
                print("      ⚠ ผลลัพธ์อาจถูกตัดเพราะชน num_predict "
                      "--> ลดจำนวนหน้าต่อ chunk หรือเพิ่ม num_predict")
            if not content.strip():
                raise ValueError("โมเดลตอบว่าง")
            return content
        except Exception as e:
            last = e
            if attempt < retries:
                print(f"      ⚠ ลองใหม่ {attempt + 1}: {e}")
                time.sleep(3)
    raise RuntimeError(f"เรียก {model} ไม่สำเร็จ: {last}")


def parse_json(text: str) -> dict:
    t = re.sub(r"<think>.*?</think>", "", text.strip(), flags=re.DOTALL)
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t.strip(), flags=re.MULTILINE)
    starts = [p for p in (t.find("{"), t.find("[")) if p != -1]
    if not starts:
        raise ValueError(f"ไม่พบ JSON:\n{text[:400]}")
    obj, _ = json.JSONDecoder().raw_decode(t[min(starts):])
    return obj


# ==============================================================================
#  ส่วนที่ 6 — การรวมผลจากหลาย chunk
# ==============================================================================


def merge_chunks(chunks: list[dict]) -> dict:
    """
    รวมผลจากหลาย chunk เข้าเป็นชุดเดียว

    ⚠️ ปัญหาที่ต้องแก้: วิชาซ้ำ
       ถ้าหน้าที่ 5 และหน้าที่ 6 มีตารางที่คาบเกี่ยวกัน วิชาเดียวกันจะถูก
       สกัดออกมาสองครั้ง  ถ้าไม่กรอง จำนวนวิชาจะเกินจริง

    ⚠️ แต่ระวัง! ในหลักสูตร DSBA จริง รหัส 06026259 (สหกิจศึกษา)
       ปรากฏ 2 แถวโดยตั้งใจ:
         แถวหนึ่ง เป็นวิชาบังคับ ปี 4 ภาค 2
         อีกแถวหนึ่ง เป็นวิชาเลือก ที่ยังไม่กำหนดปี/ภาค (year=0)
       --> กุญแจสำหรับกันซ้ำจึงต้องเป็น (รหัส, ปี, ภาค) ไม่ใช่รหัสอย่างเดียว
           ถ้าใช้รหัสอย่างเดียว เราจะ "ลบข้อมูลจริง" ทิ้งไปโดยไม่รู้ตัว

    บทเรียน: การกันซ้ำที่ก้าวร้าวเกินไป อันตรายกว่าการปล่อยให้ซ้ำ
    """
    seen: set[tuple] = set()
    courses: list[dict] = []
    n_dup = 0

    for ch in chunks:
        for c in ch.get("courses") or []:
            # ⚠️ ต้องรวม name_th ในกุญแจด้วย ไม่งั้นแถว "06026xxx" ที่มีสองแถว
            #    ในภาคเดียวกัน (วิชาเลือกกลุ่มฯ 1 และ 2) จะถูกลบทิ้งไปหนึ่ง
            key = (
                M.normalize(c.get("code"), "strict"),
                str(c.get("year")),
                str(c.get("semester")),
                M.normalize(c.get("name_th"), "strict"),
            )
            if key in seen:
                n_dup += 1
                continue
            seen.add(key)
            courses.append(c)

    if n_dup:
        print(f"      กรองวิชาซ้ำออก {n_dup} รายการ (คีย์ = รหัส+ปี+ภาค+ชื่อ)")

    return {
        "program": next((ch.get("program") for ch in chunks if ch.get("program")), None),
        "plan": next((ch.get("plan") for ch in chunks if ch.get("plan")), None),
        "courses": courses,
    }


# ==============================================================================
#  ส่วนที่ 7 — PIPELINE A : Tesseract baseline
# ==============================================================================


def pipeline_baseline(pages: list[bytes]) -> dict:
    """OpenCV -> Tesseract -> regex   (เส้นฐานสำหรับเปรียบเทียบ)"""
    try:
        import pytesseract
        from PIL import Image
        import numpy as np
        import cv2
    except ImportError as e:
        print(f"  ⚠ ข้าม baseline: {e}")
        return {}

    text = ""
    for i, png in enumerate(pages):
        img = np.array(Image.open(io.BytesIO(png)).convert("RGB"))
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        txt = pytesseract.image_to_string(bw, lang="tha+eng", config="--psm 6")
        text += txt + "\n"
        print(f"      Tesseract หน้า {i + 1}: {len(txt):,} ตัวอักษร")
    return _rule_based_parse(text)


def _rule_based_parse(text: str) -> dict:
    """
    regex สำหรับตารางหลักสูตร

    รูปแบบที่คาดหวัง:  <รหัส 8 หลัก> <ชื่อไทย> <ชื่ออังกฤษ> <หน่วยกิต>
    ปัญหาที่ regex แก้ไม่ได้เลย:
      - ชื่อวิชาไทยและอังกฤษอยู่คนละบรรทัด (ตัดบรรทัดตามความกว้างคอลัมน์)
      - บางตารางมีคอลัมน์ "ปี/ภาค" บางตารางไม่มี
      - หัวข้อหมวดวิชาอยู่คนละแถวกับตัววิชา ต้องจำ state ไว้
    --> นี่คือจุดที่ LLM ได้เปรียบชัดเจน เพราะมันเข้าใจ "บริบท" ของทั้งหน้า
    """
    courses: list[dict] = []
    category = None

    cat_re = re.compile(r"(หมวดวิชาศึกษาทั่วไป|หมวดวิชาเฉพาะ|หมวดวิชาเลือกเสรี)")
    # รหัส 8 หลัก + ข้อความ + หน่วยกิตรูปแบบ N(N-N-N)
    row_re = re.compile(r"(\d{8})\s+(.{3,90}?)\s+(\d\([\d\s\-]+\))")

    for line in text.splitlines():
        cm = cat_re.search(line)
        if cm:
            category = cm.group(1)
            continue

        rm = row_re.search(line)
        if rm:
            raw_name = rm.group(2).strip()
            # พยายามแยกชื่อไทยกับชื่ออังกฤษ โดยหาจุดที่เปลี่ยนภาษา
            m2 = re.match(r"([^\x00-\x7F][^A-Z]*)\s*([A-Z][A-Z\s\d\-&,\.]*)?$", raw_name)
            th = (m2.group(1).strip() if m2 else raw_name)
            en = (m2.group(2).strip() if m2 and m2.group(2) else None)
            courses.append({
                "code": rm.group(1),
                "name_th": th,
                "name_en": en,
                "credits": re.sub(r"\s", "", rm.group(3)),
                "year": None, "semester": None,
                "category": category, "type": None,
                "prerequisite": "ไม่มี",
                "flexible_year_semester": None, "note": None,
            })

    print(f"      regex แกะได้ {len(courses)} วิชา")
    return {"program": None, "plan": None, "courses": courses}


# ==============================================================================
#  ส่วนที่ 8 — PIPELINE B : Typhoon-OCR -> text LLM (แบ่ง chunk)
# ==============================================================================


# อ่านหน้าซ้ำเมื่อ "ยอดรวมของเล่มไม่ลงตัวกับแถวที่อ่านได้" (ดู md_plan_slots.page_check)
# ทุกเทอมในตารางแผนการศึกษามีแถว "รวม" พิมพ์ไว้ — ถ้าผลรวมของแถวที่อ่านได้ไม่เท่ายอดนั้น แปลว่าอ่านตก/ผิดแถวหนึ่ง
# ผลทุกรอบยังเป็นผล OCR จริง ไม่มีการแก้ด้วยมือ: เลือกรอบที่ score ต่ำสุด (ลงตัวได้ก่อนก็หยุด)
# ปิดไว้เป็นค่าเริ่มต้น (0) เพื่อไม่ให้ผลรันเดิมเปลี่ยนโดยไม่ตั้งใจ
OCR_RETRIES = int(os.getenv("LAB7B_OCR_RETRIES", "0"))


def _ocr_page_with_checksum(png: bytes, page_no: int) -> tuple[str, list[dict]]:
    """OCR หน้าเดียว (ซ้ำได้ตาม OCR_RETRIES) คืน (markdown ของรอบที่ดีที่สุด, บันทึกทุกรอบ)"""
    check = None
    if OCR_RETRIES > 0:
        try:
            from md_plan_slots import page_check as check
        except ImportError:
            check = None
    best_md, best_score, attempts = "", None, []
    for k in range(1 + (OCR_RETRIES if check else 0)):
        try:
            md = ollama_chat(MODEL_OCR,
                             [{"role": "user", "content": TYPHOON_PROMPT}],
                             images=[png], temperature=0.1,
                             num_ctx=OCR_NUM_CTX,
                             num_predict=OCR_NUM_PREDICT)
        except Exception as e:
            # หน้าเดียวอ่านไม่ได้ ไม่ควรล้มทั้ง pipeline — ใส่ placeholder ว่างไว้
            # แล้วไปทำหน้าถัดไป (ก้อน jsonify ของหน้านี้จะได้ 0 วิชา)
            print(f"      ❌ Typhoon-OCR หน้า {page_no} ล้มเหลว: {e}")
            attempts.append({"attempt": k + 1, "error": str(e)})
            continue
        if check is None:
            return md, [{"attempt": 1}]
        res = check(md)
        attempts.append({"attempt": k + 1, "ok": res["ok"], "score": res["score"],
                         "bad_terms": res["bad_terms"]})
        if best_score is None or res["score"] < best_score:
            best_md, best_score = md, res["score"]
        if res["ok"]:
            break
        print(f"      ⚠ หน้า {page_no} ยอดรวมไม่ลงตัว {res['bad_terms']} — "
              + ("อ่านซ้ำ" if k < OCR_RETRIES else "หมดรอบอ่านซ้ำ ใช้รอบที่ดีที่สุด"))
    return best_md, attempts


def pipeline_vlm(pages: list[bytes], outdir: Path) -> dict:
    """
    ขั้น 1: Typhoon-OCR อ่านทุกหน้าเป็น Markdown
    ขั้น 2: แบ่ง Markdown เป็นก้อนละ 1 ตาราง (ดู _split_page_into_table_chunks)
            ส่งเข้า text LLM ทีละก้อน แล้วรวมผล

    ทำไมต้องแบ่งก้อน?
      ถ้าส่งทั้งเล่ม (150 หน้า ~ 200,000 token) เข้าไปทีเดียว:
        - เกิน context window ของโมเดลขนาดเล็ก --> ตัดท้ายทิ้งเงียบ ๆ
        - แม้ context พอ output ก็จะยาวเกิน num_predict --> JSON ขาดกลางคัน
        - ยิ่ง context ยาว โมเดลยิ่ง "ลืมกลาง" (lost in the middle)
          ซึ่งเป็นปรากฏการณ์ที่พบในงานวิจัยหลายชิ้น

      การแบ่งก้อนแลกมาด้วย: โมเดลไม่เห็นภาพรวมทั้งเล่ม
      เช่น อาจไม่รู้ว่าวิชานี้อยู่หมวดไหน ถ้าหัวข้อหมวดอยู่คนละก้อน
      --> ทางแก้ในระบบจริงคือใส่ "overlap" ให้ก้อนซ้อนกัน 1 หน้า
          หรือส่งหัวข้อหมวดที่เจอล่าสุดไปกับก้อนถัดไป (โจทย์ท้าทายข้อ 1)
    """
    md_pages: list[str] = []
    ocr_log: list[dict] = []
    for i, png in enumerate(pages):
        print(f"    [ขั้น 1/2] Typhoon-OCR หน้า {i + 1}/{len(pages)}")
        md, attempts = _ocr_page_with_checksum(png, i + 1)
        md_pages.append(md)
        ocr_log.append({"page": i + 1, "attempts": attempts})
    (outdir / "ocr_checks.json").write_text(
        json.dumps({"dewatermark": DEWATERMARK, "ocr_retries": OCR_RETRIES, "pages": ocr_log},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    (outdir / "intermediate_vlm.md").write_text(
        "\n\n---\n\n".join(md_pages), encoding="utf-8")
    print(f"    บันทึก Markdown กลางทาง: {outdir / 'intermediate_vlm.md'}")

    return _text_to_json_chunked(md_pages)


def _split_page_into_table_chunks(page_text: str) -> list[str]:
    """แยกหน้าที่มีหลายตาราง <table>...</table> ออกเป็นก้อนละ 1 ตาราง

    ทำไมต้องแยก: Typhoon-OCR บางหน้าคาย "ปีที่ 1 ภาคที่ 1" กับ "ปีที่ 1 ภาคที่ 2"
    มารวมกันใน <table> เดียว (กรณีนี้ปล่อยผ่านเป็นก้อนเดียวได้ โมเดลอ่านจบทั้งก้อน)
    แต่บางหน้าคายเป็นคนละ <table>...</table> แยกกันสองก้อนในหน้าเดียว (มีข้อความ
    "ปีที่ N ภาคที่ M" คั่นกลาง) — เจอจริงกับ AIT (หน้าที่มีปี 2 ภาค 1 และภาค 2 คนละ
    ตาราง) ว่าโมเดลขนาดเล็ก (qwen3:4b) อ่านตารางแรกจบแล้ว "หยุดเอง" ทั้งที่ output
    token เหลือเยอะ (ใช้ไปแค่ 584/8192) ไม่ยอมอ่านตารางที่สองต่อ ทั้งที่ prompt บอก
    "ห้ามหยุดกลางทาง" ไว้แล้ว — สรุปคือไม่ใช่ปัญหา token limit แต่เป็นข้อจำกัดของ
    โมเดลเล็กตอนเจอตารางหน้าตาเดียวกันสองก้อนติดกันในอินพุตเดียว

    ทางแก้ที่นี่: ถ้าหน้าหนึ่งมี <table> มากกว่า 1 ก้อนจริง ๆ (นับจาก tag ไม่ใช่นับจาก
    ข้อความหัวข้อภาษาไทย เพราะบางทีหัวข้อฝังอยู่ใน <th> กลางตารางเดียวที่ไม่ต้องแยก)
    ให้ตัดเป็นก้อนละ 1 <table> เสมอ (พร้อมข้อความหัวข้อที่คั่นอยู่ก่อนตารางนั้น
    ผูกไปกับก้อนของตารางนั้น) แล้วส่งเข้า LLM แยกกันทีละก้อน ไม่ต้องพึ่งให้โมเดล
    ประมวลผลหลายตารางในคำขอเดียวอีกต่อไป"""
    table_spans = [m.span() for m in re.finditer(r"<table>.*?</table>", page_text, re.DOTALL)]
    if len(table_spans) <= 1:
        return _split_table_by_term(page_text)

    chunks: list[str] = []
    start = 0
    for _, end in table_spans:
        chunks.append(page_text[start:end])
        start = end
    if page_text[start:].strip():
        chunks[-1] += page_text[start:]
    return [piece for c in chunks for piece in _split_table_by_term(c)]


_TERM_HEADING = re.compile(r"ปีที่\s*\d\s*ภาค(?:การศึกษา|เรียน)?\s*ที่\s*\d")


def _split_table_by_term(chunk: str) -> list[str]:
    """แยก <table> เดียวที่มีหลายเทอม (หัว "ปีที่ N ภาคการศึกษาที่ M" ฝังเป็นแถวกลางตาราง) เป็นก้อนละ 1 เทอม

    เจอจริงเมื่อตัดตราน้ำก่อน OCR: Typhoon เขียนเทอม 1/1 และ 1/2 ไว้ใน <table> เดียว แล้ว qwen3:4b
    ทำเทอมที่สองพัง (ยัดรหัสผิดเทอม/หายทั้งเทอม) — ให้โมเดลเห็นทีละเทอม เหมือนที่แยกตามแท็ก <table> อยู่แล้ว
    ตัดที่ต้นแถว <tr> ที่ถือหัวเทอม แล้วปิด/เปิดแท็ก table ให้แต่ละชิ้นเป็น HTML ครบ
    หัวเทอมนอก <table> (ข้อความนำหน้า) ไม่ถูกแตะ — นับเฉพาะหัวที่อยู่ "ในตาราง"
    """
    m_table = re.search(r"<table>.*</table>", chunk, re.DOTALL)
    if not m_table:
        return [chunk]
    inner_start = m_table.start()
    cuts = []
    for h in _TERM_HEADING.finditer(chunk, m_table.start(), m_table.end()):
        row_start = chunk.rfind("<tr>", inner_start, h.start())
        if row_start > inner_start + len("<table>") and row_start not in cuts:   # แถวแรกของตารางไม่ต้องตัด
            cuts.append(row_start)
    if not cuts:
        return [chunk]
    bounds = [0, *cuts, len(chunk)]
    pieces = []
    for i in range(len(bounds) - 1):
        piece = chunk[bounds[i]:bounds[i + 1]]
        if i > 0:
            piece = "<table>" + piece
        if i < len(bounds) - 2:
            piece = piece + "</table>"
        pieces.append(piece)
    return pieces


def _blank_year_sem(value: Any) -> bool:
    """True เมื่อ year/semester ยัง "ไม่รู้ค่า" — คือ null, ว่าง, หรือ 0
    (schema ยอมให้เป็นได้ทั้ง int, str และ null จึงต้องแปลงก่อนเทียบ
    ระวัง: สตริง "0" เป็น truthy ใน Python ใช้ `not value` เช็คตรง ๆ ไม่ได้)"""
    try:
        return int(value) == 0
    except (TypeError, ValueError):
        return True


_HEAD_RE = re.compile(r"ปีที่\s*(\d+)\s*ภาค(?:การศึกษา)?ที่\s*(\d+)")
# แถว "รวม N" ปิดท้ายตารางแผน (อยู่ต้นเซลล์เสมอ: <td colspan="3">รวม 18</td>)
# ใช้ ">" นำหน้าเพื่อไม่ให้ไปโดนคำที่มี "รวม" อยู่กลางประโยค เช่น "รวมถึง"
_TOTAL_ROW_RE = re.compile(r">\s*รวม")
# แถวหัวคอลัมน์ของตารางแผน — ก้อนที่ "ขึ้นตารางใหม่" จะมีคำนี้เสมอ
_TABLE_HEADER_HINT = "รหัสวิชา"


def _fill_year_sem(courses: list[dict], hy: str, hs: str, *, force: bool = False) -> None:
    """เติม year/semester จากหัวข้อ "ปีที่ hy ภาคที่ hs" ให้เฉพาะแถวที่ปลอดภัยจะเติม

    ขอบเขตที่จงใจไม่แตะ (กันไปทับของที่ถูกอยู่แล้ว):
      - แถวที่มี flexible_year_semester --> เป็นวิชาเลือกหลายภาคจริง
      - แถวรหัส wildcard ("9664xxxx", "xxxxxxxx") --> ground truth กำหนดให้เป็น 0/0
        อยู่แล้ว เติมปีให้จะกลายเป็นผิด

    `force=False` (ค่าเดิม, ใช้กับก้อนที่ "มีหัวข้อของตัวเอง" 1 อัน) — เติมเฉพาะแถวที่
    year/semester ยังว่าง เชื่อค่าที่โมเดลกรอกมาแล้วถ้ามี

    `force=True` (ใช้กับก้อน "หางตาราง" ที่ไม่มีหัวข้อเลย ยกมาจาก `_continuation_head`)
    — เขียนทับ "ทุกแถว" แม้โมเดลจะกรอก year/semester มาแล้วก็ตาม เพราะก้อนนี้ไม่มีหัวข้อ
    ของตัวเองเลย ค่าที่โมเดลกรอกมาจึงเป็นการเดาล้วนๆ ไม่ใช่อ่านจากบริบทจริง (เจอจริงกับ IT
    แผนไม่สหกิจรอบที่สอง: โมเดลเดา year=1/semester=1 ให้หน้าหางตารางของปี 3/2 แทนที่จะคืน
    null ทั้งที่ไม่มีหัวข้อในก้อนนั้นเลย — ตรงกับพฤติกรรม "เดา 1/1" ที่กฎ "ไม่มีหัวข้อ -->
    ล้างเป็น null" เดิมตั้งใจกันไว้อยู่แล้ว ถ้าใช้ blank-only fill ค่าที่เดาผิดจะรอดไปเงียบๆ)

    ข้อยกเว้นของ `flexible_year_semester` ตอน `force=True`: ยกเว้นก็ต่อเมื่อค่านั้น "ดูเหมือน
    ตัวเลือกหลายภาคจริง" (มี "," คั่นมากกว่า 1 ตัวเลือก เช่น "3/1, 3/2, 4/1") ถ้าเป็นค่าเดี่ยว
    ไม่มี "," (เช่น "1/1") ให้ถือว่าเป็นการเดาเดียวกับที่ year/semester เดาผิด — เขียนทับและ
    ล้าง flexible_year_semester ทิ้งไปด้วย (เจอจริงกับ IT แผนสหกิจ: วิชา `06016482` สหกิจศึกษา
    ต่างประเทศ อยู่หางตารางของปี 3/2 แต่โมเดลใส่ flexible_year_semester="1/1" มาด้วย ทำให้
    เงื่อนไข "มี flexible --> ไม่แตะ" เดิมป้องกันค่าที่เดาผิดไว้แทนที่จะแก้)
    """
    for c in courses or []:
        flex = c.get("flexible_year_semester")
        if flex and not (force and "," not in str(flex)):
            continue
        if not re.search(r"(?<!\d)\d{8}(?!\d)", str(c.get("code") or "")):
            continue
        if force or _blank_year_sem(c.get("year")) or _blank_year_sem(c.get("semester")):
            c["year"] = int(hy)
            c["semester"] = int(hs)
            if force and flex:
                c["flexible_year_semester"] = None


def _continuation_head(part_text: str, prev_text: str | None) -> tuple[str, str] | None:
    """คืนหัวข้อ "ปีที่ N ภาคที่ M" ที่ควร "ยกมาจากก้อนก่อนหน้า" ให้ก้อนที่ไม่มีหัวข้อเลย
    หรือคืน None ถ้าไม่เข้าเงื่อนไข (แปลว่าให้ล้างเป็น null ตามกฎเดิม)

    ปัญหาที่แก้: ตารางแผนของภาคหนึ่งบางทียาวข้ามหน้า หัวข้อ "ปีที่ N ภาคการศึกษาที่ M"
    พิมพ์ไว้แค่หน้าแรกของตาราง หน้าถัดไปเป็น "หางตาราง" ล้วน ๆ ไม่มีหัวข้อซ้ำ
    กฎเดิม (ก้อนไม่มีหัวข้อ --> ล้าง year/semester เป็น null) จึงทิ้งวิชาทั้งหน้านั้น
    เจอจริงกับ IT แผนไม่สหกิจ มคอ.2 หน้า 31: เป็นหางของตาราง "ปีที่ 3 ภาคการศึกษาที่ 2"
    ที่เริ่มในหน้า 30 --> 06066100 กับ 90642033 โดนล้างทิ้ง ทำให้ปี 3/2 หายทั้งภาค

    เงื่อนไขต้องครบทุกข้อ (ตั้งใจให้แคบ เพื่อไม่ไปแตะหน้าที่ "ไม่ใช่ตารางแผน" จริง ๆ
    เช่น หน้าคำอธิบายรายวิชา/หน้าเมนูวิชาเลือก ซึ่งกฎเดิมล้างถูกแล้ว):
      1. ก้อนก่อนหน้ามีหัวข้อ "ปีที่ N ภาคที่ M" เพียงหัวข้อเดียว (รู้แน่ว่าหางของภาคไหน)
      2. ก้อนก่อนหน้า "ไม่มี" แถว "รวม" ปิดท้าย --> ตารางถูกตัดกลางคัน มีหางแน่
      3. ก้อนนี้ "ไม่มี" แถวหัวคอลัมน์ "รหัสวิชา" --> ไม่ได้ขึ้นตารางใหม่ เป็นหางจริง
      4. ก้อนนี้ "มี" แถว "รวม" --> เป็นท้ายตารางที่ยกมา (ปิดจบพอดี)
    """
    if prev_text is None:
        return None
    prev_heads = set(_HEAD_RE.findall(prev_text))
    if len(prev_heads) != 1:
        return None
    if _TOTAL_ROW_RE.search(prev_text):
        return None
    if _TABLE_HEADER_HINT in part_text:
        return None
    if not _TOTAL_ROW_RE.search(part_text):
        return None
    return next(iter(prev_heads))


_TH_CHAR_RE = re.compile(r"[฀-๿]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_CODE_CELL_RE = re.compile(r"^\s*((?:[0-9Xx]{8,9})(?:\s*หรือ\s*[0-9Xx]{8,9})?)\s*(.*)$", re.S)
_CREDIT_TOKEN_RE = re.compile(r"^\d+\s*\([\dxX\-]*\)?")   # เช่น "3(3-0-6)" ที่เซลล์รวมพ่วงมาท้ายชื่อ


def _split_th_en(text: str) -> tuple[str, str | None]:
    """แยกข้อความในเซลล์ชื่อวิชา (ไทย + อังกฤษ) : ส่วนหลังอักษรไทยตัวสุดท้ายคือชื่ออังกฤษ
    โดยข้ามโทเคนที่เป็นตัวเลข/สัญลักษณ์ล้วนที่นำหน้า (เช่น "แคลคูลัส 1 CALCULUS 1" ->
    ไทย "แคลคูลัส 1", อังกฤษ "CALCULUS 1") ไม่มีอักษรไทยเลย -> (ข้อความ, None)
    ข้อจำกัด: ชื่อไทยที่ลงท้ายด้วยคำอังกฤษ (เช่น "ระบบ IoT") จะถูกนับส่วนท้ายเป็นชื่ออังกฤษ"""
    txt = re.sub(r"\s+", " ", text).strip()
    txt = re.sub(r"(?:\s*(?:หรือ|/))+$", "", txt).strip()    # ตัวเชื่อม "หรือ" ท้ายแถวคู่ (A หรือ B) ไม่ใช่ชื่อ
    th_idx = [m.start() for m in _TH_CHAR_RE.finditer(txt)]
    if not th_idx:
        return txt, None
    last = th_idx[-1]
    toks = txt[last + 1:].split()
    lead: list[str] = []                  # โทเคนตัวเลข/สัญลักษณ์ระหว่างชื่อไทยกับชื่ออังกฤษ (เช่น "1" ใน "โครงงานกลุ่ม 1 TEAM-PROJECT 1")
    while toks and not _LATIN_RE.search(toks[0]):
        lead.append(toks.pop(0))
    if lead and all(re.fullmatch(r"[0-9]+", t) for t in lead):
        last_txt = txt[:last + 1].strip() + " " + " ".join(lead)   # ตามที่ docstring บอก: เลขท้ายชื่อไทยเป็นส่วนของชื่อไทย
    else:
        last_txt = txt[:last + 1].strip()
    for i, t in enumerate(toks):          # ตัดหน่วยกิตที่ OCR พ่วงท้ายชื่อในเซลล์รวม
        if _CREDIT_TOKEN_RE.match(t):
            toks = toks[:i]
            break
    return last_txt, (" ".join(toks) or None)


_CODE_ONLY_RE = re.compile(r"(?:[0-9Xx]{8,9}\s*)+(?:หรือ\s*(?:[0-9Xx]{8,9}\s*)+)?")
_NAME_MATCH_MIN = 0.6     # ความคล้ายขั้นต่ำของชื่อไทย (Markdown vs ที่ LLM ให้) ก่อนยอมเติม name_en


def _markdown_name_en_rows(part_text: str) -> dict[str, list[tuple[str, str | None]]]:
    """อ่านแถว <tr> ของตาราง Markdown (Typhoon-OCR) แล้วคืน {รหัส(พิมพ์เล็ก ช่องว่างเดียว): [(ชื่อไทย, ชื่ออังกฤษ), ...]}
    ตามลำดับแถว รองรับรูปแบบที่พบจริง: (ก) [รหัส | ชื่อ | หน่วยกิต] (ข) เซลล์รวม colspan
    "รหัส ชื่อ" (ค) รหัส "A หรือ B" ที่ rowspan=N โดยแถวถัดมามีแต่เซลล์ชื่อ (ใช้รหัสเดียวกัน)
    (ง) เซลล์รหัสหลายตัว (`06016416<br/>06016417<br/>06016418`) rowspan=N — ไม่รู้ว่าชื่อแถวไหนของรหัสไหน
    จึงลงทะเบียนทุกแถวชื่อไว้ใต้ "ทุกรหัสในกลุ่ม" แล้วให้ _fill_name_en เลือกด้วยความคล้ายของชื่อไทย
    กฎเชิงกำหนด ไม่เรียก LLM ไม่ใช้เฉลย"""
    out: dict[str, list[tuple[str, str]]] = {}
    carry_keys: list[str] = []      # รหัสของ rowspan ที่ยังไม่หมด
    carry_left = 0
    for tr in re.findall(r"<tr>(.*?)</tr>", part_text, flags=re.S):
        tds = re.findall(r"<td([^>]*)>(.*?)</td>", tr, flags=re.S)
        if not tds:
            continue
        cells = [(attrs, re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip())
                 for attrs, body in tds]
        keys: list[str] = []
        name_text: str | None = None
        first = cells[0][1]
        if len(cells) >= 2 and _CODE_ONLY_RE.fullmatch(first):
            # (ก)/(ค แถวแรก)/(ง แถวแรก): เซลล์แรกคือรหัสล้วน เซลล์ที่สองคือชื่อ
            if "หรือ" in first:
                keys = [re.sub(r"\s+", " ", first).lower()]
            else:
                keys = [c.lower() for c in re.findall(r"[0-9Xx]{8,9}", first)]
            name_text = cells[1][1]
            rs = re.search(r'rowspan="(\d+)"', cells[0][0])
            carry_keys, carry_left = (keys, int(rs.group(1)) - 1) if rs else ([], 0)
        elif (m0 := _CODE_CELL_RE.match(first)) and m0.group(2):
            # (ข) เซลล์รวม "รหัส ชื่อ ..."
            keys = [re.sub(r"\s+", " ", m0.group(1)).lower()]
            name_text = m0.group(2)
            carry_keys, carry_left = [], 0
        elif len(cells) == 1 and carry_keys and carry_left > 0:
            # แถวถัดมาของ rowspan: มีแต่เซลล์ชื่อ
            keys, name_text = carry_keys, first
            carry_left -= 1
        if keys and name_text:
            th, en = _split_th_en(name_text)
            # เก็บแถวที่ไม่มีชื่ออังกฤษไว้ด้วย (en=None) เพื่อให้ _fill_name_en เลือกแถวที่ "ถูกตัว"
            # ไม่ใช่ไปหยิบชื่ออังกฤษของแถวข้างเคียงที่ชื่อไทยคล้ายกัน (เช่น สหกิจศึกษา vs สหกิจศึกษาต่างประเทศ)
            for k in keys:
                out.setdefault(k, []).append((th, en))
    return out


def _th_similarity(a: str, b: str) -> float:
    import difflib
    a, b = re.sub(r"\s+", "", a), re.sub(r"\s+", "", b)
    if not a or not b:
        return 0.0
    if len(min(a, b, key=len)) >= 4 and (a in b or b in a):
        return 1.0            # LLM ตัด label "กลุ่มวิชา…" ออกจากชื่อ แต่ Markdown ยังมี label ติดอยู่
    return difflib.SequenceMatcher(None, a, b).ratio()


_LABEL_START_RE = re.compile(r"^\s*(?:กลุ่มวิชา|หมวดวิชา)")
_REAL_CODE_RE = re.compile(r"^[0-9]{8}$")


def _is_group_label(name: str) -> bool:
    """ข้อความที่ "หน้าตาเหมือน label หัวข้อกลุ่มวิชา" (นิยามเดียวกับ prompt ข้อ [6]):
    ขึ้นต้นด้วย กลุ่มวิชา/หมวดวิชา หรือลงท้ายด้วย "*" """
    n = (name or "").strip()
    return bool(_LABEL_START_RE.match(n)) or n.endswith("*")


def _fix_label_name_th(part_text: str, courses: list[dict]) -> int:
    """ตัวกันเชิงกำหนด: วิชาที่มี "รหัส 8 หลักจริง" แต่ LLM ให้ name_th เป็น label หัวข้อกลุ่มวิชา
    (เช่น 90641004 ได้ "กลุ่มวิชาเลือก" ทั้งที่ Markdown เป็น "90641004 โครงงานกลุ่ม 1 TEAM-PROJECT 1")
    --> ใช้ชื่อไทยจาก Markdown ของแถวรหัสเดียวกันแทน
    เงื่อนไข (ตั้งใจแคบ กันไปทับชื่อที่ถูกอยู่แล้ว): (1) รหัสเป็นเลข 8 หลักล้วน (ไม่ใช่ wildcard/คู่ "หรือ")
    (2) name_th ของ LLM เข้านิยาม label (3) Markdown ก้อนนี้มีแถวของรหัสนั้น "แถวเดียว"
    (4) ชื่อไทยจาก Markdown ตัด label หน้า "*" แล้วยังเหลืออยู่ และไม่ได้ขึ้นต้นด้วย label
    (ถ้ากำกวมว่าตรงไหนคือ label ปล่อยตามที่ LLM ให้) ไม่ใช้เฉลย ไม่เรียก LLM คืนจำนวนวิชาที่แก้"""
    rows = None
    fixed = 0
    for c in courses:
        code = re.sub(r"\s+", "", str(c.get("code") or ""))
        if not _REAL_CODE_RE.match(code) or not _is_group_label(str(c.get("name_th") or "")):
            continue
        if rows is None:
            rows = _markdown_name_en_rows(part_text)
        cands = rows.get(code)
        if not cands or len(cands) != 1:
            continue
        th = cands[0][0]
        if "*" in th:
            th = th.split("*", 1)[1].strip()
        if not th or _is_group_label(th):
            continue
        c["name_th"] = th
        fixed += 1
    return fixed


def _fill_name_en(part_text: str, courses: list[dict]) -> int:
    """เติม name_en ให้วิชาที่ LLM ไม่ส่งมา (qwen3:4b ตัดชื่ออังกฤษทิ้งเองทั้งที่ schema/prompt สั่ง)
    โดยอ่านตรง ๆ จาก Markdown ของก้อนเดียวกัน จับคู่ด้วยรหัส แล้วเลือกแถวที่ "ชื่อไทยคล้ายที่สุด"
    (ต้องคล้าย >= _NAME_MATCH_MIN และแถวนั้นยังไม่ถูกใช้) ไม่เดาตามลำดับ/จำนวนแถว
    ไม่ทับ name_en ที่ LLM ให้มาแล้ว คืนจำนวนวิชาที่เติม"""
    rows = _markdown_name_en_rows(part_text)
    used: dict[str, set[int]] = defaultdict(set)
    filled = 0
    for c in courses:
        if c.get("name_en"):
            continue
        key = re.sub(r"\s+", " ", str(c.get("code") or "")).strip().lower()
        cands = rows.get(key)
        if not cands:
            continue
        nm = str(c.get("name_th") or "")
        best, best_r = None, _NAME_MATCH_MIN
        for i, (th, _en) in enumerate(cands):
            if i in used[key]:
                continue
            r = _th_similarity(th, nm)
            if r >= best_r:
                best, best_r = i, r
        if best is not None:
            used[key].add(best)
            if cands[best][1]:
                c["name_en"] = cands[best][1]
                filled += 1
    return filled


def _text_to_json_chunked(md_pages: list[str]) -> dict:
    """แยกแต่ละหน้าที่มีหลายตารางออกเป็นก้อนละ 1 ตารางก่อน (กัน bug ตารางที่สองหาย)
    แล้วเรียก text LLM ทีละก้อน — ก้อนที่ได้จากขั้นนี้จึงละเอียดกว่า "หน้า" เดิม
    ไม่ใช้ PAGES_PER_CHUNK มารวมก้อนอีกที เพื่อไม่ให้ตารางหลายใบไปปนกันในคำขอเดียว
    เหมือนที่เคยเกิดปัญหา (ค่า LAB7_CHUNK ยังคุมแค่จำนวนหน้าที่ OCR ต่อรอบเดิม ไม่ใช่
    ตรงนี้แล้ว)"""
    all_chunks: list[str] = []
    for page_text in md_pages:
        all_chunks.extend(_split_page_into_table_chunks(page_text))

    chunks: list[dict] = []
    n_chunks = len(all_chunks)
    prev_text: str | None = None

    for ci, part_text in enumerate(all_chunks):
        print(f"    [ขั้น 2/2] จัด JSON ก้อนที่ {ci + 1}/{n_chunks}")
        try:
            raw = ollama_chat(
                MODEL_TEXT,
                [{"role": "system", "content": SYSTEM_PROMPT},
                 {"role": "user", "content": EXTRACT_PROMPT.format(
                     document_text=part_text)}],
                fmt=COURSE_SCHEMA,
                think=False,
            )
            d = parse_json(raw)
            # ตัวกันเชิงกำหนดแน่ (deterministic) — ไม่พึ่ง prompt:
            # ถ้าก้อนนี้ "ไม่มี" หัวข้อ "ปีที่ N ภาคการศึกษาที่ M" เลย
            # แปลว่าไม่ใช่หน้าตารางแผน (เช่น หน้าคำอธิบายรายวิชา)
            # โมเดลมักเดา year=1/semester=1 ให้ทั้งที่หน้านั้นไม่ได้อยู่ในแผน
            # --> ล้าง year/semester/flexible ให้เป็น null เพื่อไม่ให้ปนเข้าตารางแผน
            heads = set(_HEAD_RE.findall(part_text))
            if not heads:
                # ...ยกเว้นก้อนที่เป็น "หางตารางแผนที่ยาวข้ามหน้า" ซึ่งรู้ได้แน่จาก
                # ก้อนก่อนหน้า (ดู _continuation_head) --> ยกหัวข้อของตารางนั้นมาใช้
                carried = _continuation_head(part_text, prev_text)
                if carried:
                    print(f"      ↳ ก้อนนี้เป็นหางตารางของ ปีที่ {carried[0]} "
                          f"ภาคที่ {carried[1]} — ยกหัวข้อจากก้อนก่อนหน้ามาใช้")
                    _fill_year_sem(d.get("courses") or [], *carried, force=True)
                else:
                    for c in d.get("courses") or []:
                        c["year"] = None
                        c["semester"] = None
                        c["flexible_year_semester"] = None
            elif len(heads) == 1:
                # ตัวกันเชิงกำหนดแน่ "ด้านกลับ" ของกฎข้างบน:
                # ถ้าก้อนนี้มีหัวข้อ "ปีที่ N ภาคที่ M" เพียงหัวข้อเดียว แปลว่าทุกแถว
                # ในตารางก้อนนี้อยู่ปี/ภาคนั้นแน่นอน (ไม่ต้องเดา อ่านจากหัวข้อตรง ๆ)
                # --> วิชาที่ "มีรหัส 8 หลักจริง" แต่โมเดลคืน year/semester = null/0
                #     ให้เติมค่าจากหัวข้อ
                # เจอจริงกับ BIT แผนสหกิจหน้า 29: Typhoon-OCR รวมสองรหัสไว้ใน cell
                # rowspan เดียว ("96643021<br/>06036xxx") qwen3:4b เลยตีความว่าเป็นแถว
                # ทางเลือกที่ยังไม่กำหนดปี/ภาค คืน year=null มา ทำให้ convert_lab7b()
                # ฝั่ง Lab 8B ตัดวิชา 96643021 ออกจาก plan_item ทั้งที่หัวข้อหน้านั้น
                # เขียนว่า "ปีที่ 3 ภาคการศึกษาที่ 2" ชัดเจน (ข้อมูลหายเงียบ ๆ)
                #
                # ขอบเขตที่จงใจไม่แตะ (กันไปทับของที่ถูกอยู่แล้ว):
                #   - ก้อนที่มีหัวข้อมากกว่า 1 อัน (OCR รวมสองภาคไว้ตารางเดียว)
                #     --> กำกวมว่าแถวไหนอยู่ภาคไหน ปล่อยตามที่โมเดลอ่าน
                #   - แถวที่มี flexible_year_semester --> เป็นวิชาเลือกหลายภาคจริง
                #   - แถวรหัส wildcard ("9664xxxx", "xxxxxxxx") --> ground truth
                #     กำหนดให้เป็น 0/0 อยู่แล้ว เติมปีให้จะกลายเป็นผิด
                # (รายละเอียดข้อยกเว้นอยู่ใน _fill_year_sem)
                _fill_year_sem(d.get("courses") or [], *next(iter(heads)))
            # ทิ้งกัน — "prerequisite" ไม่อยู่ใน COURSE_SCHEMA แล้ว (ดูเหตุผลที่ส่วน 3 ด้านบน)
            # แต่ COURSE_SCHEMA ไม่ได้ตั้ง additionalProperties: false ไว้ เผื่อโมเดลยังใส่คีย์นี้
            # มาเองอยู่ดี (เคยเจอว่า qwen3:4b เดาความสัมพันธ์จากลำดับวิชาในตารางได้แม้ prompt
            # จะสอนไว้แล้วว่าห้าม) --> ทิ้งคีย์นี้ทิ้งเงียบ ๆ ถ้าหลุดมา ไม่ใช่ตั้งค่าให้มันเลย
            for c in d.get("courses") or []:
                c.pop("prerequisite", None)
            # LLM (qwen3:4b) ตัดชื่ออังกฤษทิ้งเอง ไม่ส่ง name_en มา (ตรวจแล้วทุก run) ทั้งที่ชื่ออังกฤษ
            # อยู่ใน Markdown ครบ --> เติมด้วยกฎเชิงกำหนดจาก Markdown ก้อนเดียวกัน (ไม่ทับที่ LLM ให้มา)
            # LLM (qwen3:4b) บางทีให้ name_th เป็น label หัวข้อกลุ่มวิชาแทนชื่อวิชาจริง (เจอ 90641004 ใน AIT_dewm5)
            # --> ใช้ชื่อไทยจาก Markdown แทน ต้องทำก่อน _fill_name_en (ตัวนั้นจับคู่แถวด้วยความคล้ายของชื่อไทย)
            n_th = _fix_label_name_th(part_text, d.get("courses") or [])
            if n_th:
                print(f"      แก้ name_th ที่เป็น label จาก Markdown {n_th} วิชา")
            n_en = _fill_name_en(part_text, d.get("courses") or [])
            if n_en:
                print(f"      เติมชื่ออังกฤษจาก Markdown {n_en} วิชา")
            print(f"      ได้ {len(d.get('courses') or [])} วิชา")
            chunks.append(d)
        except Exception as e:
            # ก้อนหนึ่งพัง ไม่ควรทำให้ทั้งงานพัง — ข้ามไปทำก้อนถัดไป
            print(f"      ❌ ก้อนที่ {ci + 1} ล้มเหลว: {e}")
        # เก็บ "ข้อความก้อนก่อนหน้า" ไว้ให้ _continuation_head เสมอ แม้ก้อนนี้จะพัง
        # (ต่อให้ LLM ล้ม ตัวข้อความยังบอกได้ว่าตารางถูกตัดกลางคันหรือไม่)
        prev_text = part_text

    return merge_chunks(chunks)


def pipeline_markdown(path: str) -> dict:
    """ทำขั้น Markdown -> JSON ต่อจาก intermediate_vlm.md โดยไม่ OCR ซ้ำ"""
    text = Path(path).read_text(encoding="utf-8")
    pages = [part.strip() for part in re.split(r"\n\s*---\s*\n", text)
             if part.strip()]
    if not pages:
        raise ValueError(f"Markdown ว่างเปล่า: {path}")
    print(f"    ทำต่อจาก Markdown {len(pages)} หน้า (ไม่เรียก Typhoon ซ้ำ)")
    return _text_to_json_chunked(pages)


def pipeline_text(pdf_path: str, page_spec: str | None) -> dict:
    """
    ⭐ pipeline พิเศษของกลุ่ม B: ข้าม OCR ไปเลย

    ถ้า PDF มีข้อความฝังอยู่แล้ว การดึงข้อความตรง ๆ จะ:
      - เร็วกว่า 50-100 เท่า (ไม่ต้องรัน VLM)
      - แม่นกว่า (ไม่มีโอกาสอ่านตัวอักษรผิดเลย)

    บทเรียน: เครื่องมือที่ทันสมัยที่สุดไม่ใช่เครื่องมือที่ดีที่สุดเสมอไป
             ต้องดูก่อนว่าปัญหาที่แท้จริงคืออะไร
    """
    print("    ดึงข้อความจาก PDF โดยตรง (ไม่ผ่าน OCR)...")
    text = extract_pdf_text(pdf_path, page_spec)

    # แยกเป็นรายหน้าตามเครื่องหมายที่ extract_pdf_text ใส่ไว้
    pages_text = re.split(r"\n=== หน้า \d+ ===\n", text)
    pages_text = [p for p in pages_text if p.strip()]
    n_all = len(re.findall(r"=== หน้า \d+ ===", text))
    n_empty = n_all - len(pages_text)

    print(f"    ได้ข้อความ {len(text):,} ตัวอักษร จาก {len(pages_text)}/{n_all} หน้า")

    if not pages_text:
        print("    ⚠ ไม่มีหน้าไหนดึงข้อความได้เลย — เล่มนี้เป็น PDF สแกน")
        print("      ให้ใช้ --pipeline vlm แทน")
        return {}

    # ⚠️ จุดสำคัญ: ถ้ามีหน้าที่ดึงข้อความไม่ได้ปนอยู่ ต้องเตือนให้ดัง
    #    ไม่ใช่ข้ามไปเงียบ ๆ เพราะวิชาในหน้านั้นจะหายทั้งหมด
    #    แล้วนักศึกษาจะเห็นแค่ Recall ต่ำ โดยไม่รู้ว่าข้อมูลไม่เคยถูกส่งเข้าไป
    if n_empty:
        print(f"    ⚠ มี {n_empty} หน้าที่ดึงข้อความไม่ได้ (น่าจะเป็นหน้าสแกน)")
        print("      วิชาในหน้าเหล่านั้นจะหายไป --> Recall จะต่ำกว่าความจริง")
        print("      ถ้าเล่มมีหน้าสแกนปน ให้ใช้ --pipeline vlm แทน")

    return _text_to_json_chunked(pages_text)



# ==============================================================================
#  ส่วนที่ 10 — ตรวจความสอดคล้องภายใน
# ==============================================================================
#
#  กลุ่ม A ใช้ GPA เป็นตัวตรวจ  แต่หลักสูตรไม่มี GPA
#  เราจึงใช้กฎเชิงโครงสร้าง 5 ข้อแทน — ทุกข้อตรวจได้โดยไม่ต้องมีเฉลย
# ==============================================================================

VALID_CATEGORIES = {"หมวดวิชาศึกษาทั่วไป", "หมวดวิชาเฉพาะ", "หมวดวิชาเลือกเสรี"}
VALID_TYPES = {"บังคับ", "เลือก"}
CREDIT_RE = re.compile(r"^\d+\(\d+-\d+-\d+\)$")

# วิชาที่มีหน่วยกิตตั้งแต่เท่านี้ขึ้นไป ถือเป็น "วิชาก้อนใหญ่"
# เช่น สหกิจศึกษา (6 หน่วยกิต) หรือโครงงานพิเศษ
# ภาคที่มีวิชาแบบนี้ มักลงวิชาเดียวทั้งภาค จึงยกเว้นการตรวจหน่วยกิตขั้นต่ำ
BLOCK_COURSE_CREDITS = 6


def _valid_code(code: Any) -> bool:
    """
    ตรวจรูปแบบรหัสวิชา รองรับทั้งรหัสเดี่ยวและรหัสแบบ "เลือกอย่างใดอย่างหนึ่ง"

        "06026240"                -> True
        "06026xxx"                -> True   (ช่องวิชาเลือก)
        "06026259 หรือ 06026260"  -> True   (สหกิจในประเทศ / ต่างประเทศ)
        "หมายเหตุ: คอลัมน์..."     -> False  (แถวขยะจาก Excel)
    """
    raw = str(code or "")
    parts = [x for x in re.split(r"หรือ|/", raw) if x.strip()]
    if not parts:
        return False
    return all(re.fullmatch(r"[0-9x]{8}", M.normalize(x, "strict")) for x in parts)


def verify_internal(data: dict) -> dict:
    """ตรวจ 5 กฎ — เป็นสิ่งที่ทำได้ในระบบจริงที่ไม่มีเฉลย"""
    issues: list[str] = []
    courses = data.get("courses") or []
    # ชุดรหัสทั้งหมด — แตกรหัสแบบ "A หรือ B" ออกเป็นรายตัว
    # เพื่อให้การตรวจ prerequisite (กฎ 5) หาเจอ
    codes: set[str] = set()
    for c in courses:
        for part in re.split(r"หรือ|/", str(c.get("code") or "")):
            n = M.normalize(part, "strict")
            if n:
                codes.add(n)

    # ⚠️ กุญแจนับซ้ำต้องรวม name_th ด้วย ให้ตรงกับ merge_chunks
    #    ถ้าใช้แค่ (รหัส, ปี, ภาค) แถว "06026xxx" ที่มีสองแถวในภาคเดียวกัน
    #    (วิชาเลือกกลุ่มฯ 1 และ 2) จะถูกนับว่าซ้ำทั้งที่เป็นข้อมูลจริง
    dup = Counter((M.normalize(c.get("code"), "strict"),
                   str(c.get("year")), str(c.get("semester")),
                   M.normalize(c.get("name_th"), "strict")) for c in courses)
    credits_by_term: dict[str, int] = defaultdict(int)
    has_block_course: set[str] = set()   # ภาคที่มีวิชาก้อนใหญ่ เช่น สหกิจศึกษา

    for c in courses:
        code = c.get("code")

        # --- กฎ 1: รูปแบบรหัสวิชา ---
        # รูปแบบที่ถูกต้องมี 2 แบบ:
        #   ก) รหัสเดี่ยว 8 ตัว เป็นเลขหรือ x ("06026240", "06026xxx", "xxxxxxxx")
        #   ข) ⭐ รหัสแบบ "เลือกอย่างใดอย่างหนึ่ง" คั่นด้วยคำว่า "หรือ"
        #      เช่น "06026259 หรือ 06026260" (สหกิจศึกษาในประเทศ / ต่างประเทศ)
        #      แบบนี้พบจริงในหลักสูตร DSBA แผนสหกิจ ห้ามนับเป็นข้อผิดพลาด
        #
        # ⚠️ ตอนออกแบบกฎนี้ครั้งแรก เรารองรับแค่แบบ ก) แล้วพบว่ามันแจ้งเตือน
        #    ground truth ของจริงทันที  ซึ่งละเมิดหลักการที่เราวางไว้เองว่า
        #    "ถ้ากฎแจ้งเตือน ต้องแปลว่าผิดจริงแน่นอน"
        #    บทเรียน: ต้องทดสอบกฎกับ ground truth ก่อนเสมอ ถ้ากฎจับเฉลยผิด
        #             แปลว่ากฎผิด ไม่ใช่เฉลยผิด
        if not _valid_code(code):
            issues.append(f"รหัสวิชาผิดรูปแบบ: {code!r}")

        # --- กฎ 2: รูปแบบหน่วยกิต ---
        cr = c.get("credits") or ""
        if cr and not CREDIT_RE.match(cr.replace(" ", "")) and "หรือ" not in cr:
            issues.append(f"หน่วยกิตผิดรูปแบบ: {code} -> {cr!r}")

        # --- กฎ 3: ค่าที่เป็นหมวดหมู่ ต้องอยู่ในชุดที่กำหนด ---
        if c.get("category") and c["category"] not in VALID_CATEGORIES:
            issues.append(f"category ไม่ถูกต้อง: {code} -> {c['category']!r}")
        if c.get("type") and c["type"] not in VALID_TYPES:
            issues.append(f"type ไม่ถูกต้อง: {code} -> {c['type']!r}")

        # --- กฎ 4: ความสอดคล้องของ year=0 กับ flexible_year_semester ---
        y, s = str(c.get("year")), str(c.get("semester"))
        if y == "0" and s == "0" and not c.get("flexible_year_semester"):
            issues.append(f"{code}: ปี/ภาค = 0 แต่ไม่ได้ระบุ flexible_year_semester")
        if y not in ("0", "None") and c.get("flexible_year_semester"):
            issues.append(f"{code}: ระบุปีชัดเจนแล้ว ไม่ควรมี flexible_year_semester")

        # --- กฎ 5: prerequisite ต้องอ้างถึงวิชาที่มีอยู่จริง ---
        # เรียกว่า referential integrity — หลักการเดียวกับ foreign key ในฐานข้อมูล
        pre = (c.get("prerequisite") or "").strip()
        if pre and pre != "ไม่มี":
            for pc in re.findall(r"\d{8}", pre):
                if pc not in codes:
                    issues.append(f"{code}: prerequisite {pc} ไม่มีอยู่ในรายการวิชา "
                                  f"--> อาจอ่านรหัสผิด หรืออ่านตกวิชานั้น")

        # --- สะสมหน่วยกิตรายภาค ---
        m = re.match(r"(\d+)\(", cr)
        if m and y not in ("0", "None") and s not in ("0", "None"):
            n_credit = int(m.group(1))
            credits_by_term[f"{y}/{s}"] += n_credit
            if n_credit >= BLOCK_COURSE_CREDITS:
                has_block_course.add(f"{y}/{s}")

    # --- ตรวจว่าจำนวนหน่วยกิตต่อภาคสมเหตุสมผลไหม ---
    # ระเบียบทั่วไปกำหนดให้ลงได้ 9-22 หน่วยกิตต่อภาค
    # ถ้าน้อยกว่ามาก แปลว่า "อ่านตกวิชา" ในภาคนั้น
    #
    # ⚠️ ข้อยกเว้นสำคัญ: ภาคที่ลงสหกิจศึกษา
    #    แผนสหกิจของ DSBA กำหนดให้ปี 4 ภาค 2 ลงสหกิจศึกษาเพียงวิชาเดียว
    #    6 หน่วยกิต (0-35-0) คือไปทำงานเต็มเวลาทั้งภาค
    #    ถ้าไม่ยกเว้น กฎนี้จะแจ้งเตือน ground truth ของจริงทันที
    for term, tot in sorted(credits_by_term.items()):
        if tot < 9 and term not in has_block_course:
            issues.append(f"ภาค {term} มีแค่ {tot} หน่วยกิต — น่าจะอ่านตกวิชา")
        elif tot > 25:
            issues.append(f"ภาค {term} มีถึง {tot} หน่วยกิต — น่าจะมีวิชาซ้ำ")

    return {
        "ok": len(issues) == 0,
        "n_courses": len(courses),
        "n_duplicate_keys": sum(1 for v in dup.values() if v > 1),
        "credits_by_term": dict(sorted(credits_by_term.items())),
        "total_credits_fixed_terms": sum(credits_by_term.values()),
        "issues": issues,
    }


# ==============================================================================
#  ส่วนที่ 11 — ประเมินผลเทียบ GROUND TRUTH
# ==============================================================================


def clean_gt(gt: dict) -> list[dict]:
    """
    ทำความสะอาด ground truth ก่อนใช้งาน
     ก่อนใช้ ground truth ต้อง "ตรวจ ground truth" เสียก่อน
             และเกณฑ์การกรองต้องแคบที่สุดเท่าที่จะทำได้
    """
    kept, dropped = [], []
    for c in gt.get("courses") or []:
        # เกณฑ์เดียว: ต้องมีชื่อวิชาภาษาไทย  ถ้าไม่มี = ไม่ใช่แถวรายวิชา
        if c.get("name_th"):
            kept.append(c)
        else:
            dropped.append(str(c.get("code"))[:40])
    if dropped:
        print(f"  (กรองแถวที่ไม่ใช่รายวิชาออกจาก ground truth {len(dropped)} แถว)")
    return kept


def key_strict(c: dict) -> str:
    """
    กุญแจเข้ม: รหัส + ปี + ภาค + ชื่อไทย

    ทำไมต้องมีชื่อด้วย? เพราะรหัส placeholder "06026xxx" ปรากฏ 2 แถว
    ในภาคเดียวกัน (วิชาเลือกกลุ่มวิทยาการข้อมูล 1 และ 2)
    ถ้าใช้แค่รหัส+ปี+ภาค ทั้งสองแถวจะชนกัน --> จับคู่ผิดตัว
    """
    return "|".join([
        M.normalize(c.get("code"), "strict"),
        M.normalize(c.get("year"), "strict"),
        M.normalize(c.get("semester"), "strict"),
        M.normalize(c.get("name_th"), "strict"),
    ])


def key_loose(c: dict) -> str:
    """
    กุญแจหลวม: รหัส + ปี + ภาค (ไม่สนชื่อ)

    ใช้ในรอบที่สอง เพื่อเก็บตกกรณีที่โมเดลอ่านชื่อผิดไปนิดหน่อย
    ถ้าไม่มีรอบนี้ วิชาที่อ่านชื่อผิด 1 ตัวอักษรจะถูกนับเป็น
    "ตกแถว 1 + แต่งเกิน 1" ทั้งที่โมเดลอ่านเจอจริง
    --> ทำให้ recall ดูแย่เกินความเป็นจริง
    """
    return "|".join([
        M.normalize(c.get("code"), "strict"),
        M.normalize(c.get("year"), "strict"),
        M.normalize(c.get("semester"), "strict"),
    ])


# ------------------------------------------------------------------------------
#  รอบจับคู่เพิ่มสำหรับแถว wildcard (วิชาเลือกที่รหัสเป็น xx เช่น 9064xxxx, xxxxxxxx)
# ------------------------------------------------------------------------------
#  ปัญหา: แถว wildcard ไม่มี "รหัสวิชา" ที่ระบุตัวตนได้ และ Lab 7B ตั้งใจคืน year/semester = 0/0
#  (ดู _fill_year_sem: ไม่เติมปีให้ wildcard) ขณะที่เฉลยระบุปี/ภาคจริงของช่องนั้น
#  กุญแจ "รหัส|ปี|ภาค" จึงไม่มีทางตรงกัน แถวเดียวกันเลยถูกนับซ้ำเป็น "ตก" (GT) + "เกิน" (pred)
#  ทั้งที่ OCR อ่านเจอ — ตรวจแล้ว 7 แผน: แถวตก 72 มี wildcard 47, แถวเกิน 96 มี wildcard 57
#
#  วิธี: หลังจับคู่ด้วยกุญแจเดิมแล้ว นำ "แถว wildcard ที่ยังเหลือ" ทั้งสองฝั่งมาจับคู่ด้วยชื่อไทยที่คล้ายกัน
#  (จับคู่แบบ greedy เรียงตามความคล้าย; ปฏิเสธถ้าเลขท้ายชื่อคนละเลข หรือปี/ภาคที่ระบุชัดทั้งสองฝั่งไม่ตรงกัน)
#  ผลการจับคู่รอบนี้ถูกนับเป็น matched ปกติ (เข้า CER/WER ของฟิลด์อื่น) ยกเว้น year_sem / flexible
#  ที่ตัดออก เพราะ 0/0 ของ Lab 7B เป็นการออกแบบ ไม่ใช่ความผิดของการอ่าน
#  ตัวเลขแบบเดิม (ไม่มีรอบนี้) เก็บไว้ใน alignment["strict"] เพื่อเทียบย้อนหลัง
_WILD_CODE_RE = re.compile(r"x{2}", re.I)
_WILD_NAME_MIN = 0.6


def _is_wildcard(c: dict) -> bool:
    return bool(_WILD_CODE_RE.search(str(c.get("code") or "")))


def _wild_name(s: object) -> str:
    return re.sub(r"[\s/,;:.()\-]+", "", str(s or "")).lower()


def _wild_name_sim(a: str, b: str) -> float:
    import difflib
    a, b = _wild_name(a), _wild_name(b)
    if not a or not b:
        return 0.0
    da, db = re.findall(r"\d+", a), re.findall(r"\d+", b)
    if da and db and da[-1] != db[-1]:      # "เลือกเสรี 1" vs "เลือกเสรี 2" คนละแถว
        return 0.0
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) >= 6 and short in long_:  # เฉลยรวมชื่อหลายกลุ่มไว้แถวเดียว pred แยกเป็นแถวละกลุ่ม
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _year_sem_of(c: dict) -> tuple[str, str] | None:
    y, s = M.normalize(c.get("year"), "strict"), M.normalize(c.get("semester"), "strict")
    return None if y in ("", "0", "none") or s in ("", "0", "none") else (y, s)


def match_wildcards(align) -> list[tuple[dict, dict]]:
    """จับคู่แถว wildcard ที่ยังเหลือ (align.missed x align.spurious) ด้วยความคล้ายของชื่อไทย
    แก้ align ในที่เดียว (ย้ายคู่ที่จับได้ไป align.matched) คืนรายการคู่ที่จับเพิ่ม"""
    cands = []
    for gi, g in enumerate(align.missed):
        if not _is_wildcard(g):
            continue
        for pi, p in enumerate(align.spurious):
            if not _is_wildcard(p):
                continue
            gy, py = _year_sem_of(g), _year_sem_of(p)
            if gy and py and gy != py:      # ระบุปี/ภาคชัดทั้งสองฝั่งแต่ไม่ตรง = คนละแถว
                continue
            r = _wild_name_sim(g.get("name_th"), p.get("name_th"))
            if r >= _WILD_NAME_MIN:
                cands.append((r, gi, pi))
    cands.sort(key=lambda t: (-t[0], t[1], t[2]))
    used_g: set[int] = set()
    used_p: set[int] = set()
    pairs: list[tuple[dict, dict]] = []
    for _r, gi, pi in cands:
        if gi in used_g or pi in used_p:
            continue
        used_g.add(gi)
        used_p.add(pi)
        pairs.append((align.missed[gi], align.spurious[pi]))
    if pairs:
        align.matched.extend(pairs)
        align.missed = [g for i, g in enumerate(align.missed) if i not in used_g]
        align.spurious = [p for i, p in enumerate(align.spurious) if i not in used_p]
    return pairs


def _align_numbers(align) -> dict:
    return {"matched": len(align.matched), "missed": len(align.missed),
            "spurious": len(align.spurious), "precision": round(align.precision, 4),
            "recall": round(align.recall, 4), "f1": round(align.f1, 4)}


def evaluate(pred: dict, gt: dict) -> tuple[dict, dict]:
    S = M.FieldStat
    stats: dict[str, M.FieldStat] = {
        "code":      S("รหัสวิชา"),
        "name_th":   S("ชื่อวิชา (ไทย) ⭐"),
        "name_en":   S("ชื่อวิชา (อังกฤษ) ⭐"),
        "credits":   S("หน่วยกิต"),
        "year_sem":  S("ปี/ภาค"),
        "category":  S("หมวดวิชา"),
        "ctype":     S("บังคับ/เลือก"),
        "prereq":    S("วิชาบังคับก่อน"),
        "flexible":  S("ปี/ภาคยืดหยุ่น"),
    }

    g_courses = clean_gt(gt)
    p_courses = pred.get("courses") or []

    # จับคู่สองรอบ: เข้มก่อน (รวมชื่อ) แล้วผ่อน (เฉพาะรหัส+ปี+ภาค)
    align = M.align_multipass(g_courses, p_courses, [key_strict, key_loose])
    strict_numbers = _align_numbers(align)            # ตัวเลขแบบเดิม ก่อนรอบจับคู่ wildcard
    wild_pairs = match_wildcards(align)
    wild_ids = {id(g) for g, _p in wild_pairs}         # แถวที่จับได้จากรอบ wildcard

    # ctype/category เป็นฟิลด์ categorical ปิด (ไม่ใช่ free text) — เก็บคู่ (gt, pred)
    # แยกไว้สำหรับทำ confusion matrix ต่างหาก (ดู M.classification_report) เพราะ
    # exact_match_acc ของ FieldStat ด้านบนไม่เผย accuracy paradox (โมเดลเอนเอียง
    # ทาย class ที่มีจำนวนเยอะ) วิชาที่อ่านตก (align.missed) นับเป็น pred=None
    ctype_pairs: list[tuple] = []
    category_pairs: list[tuple] = []

    for g, p in align.matched:
        k = f"{g.get('code')}"

        # --- รหัสวิชา: ไม่วัด WER (เป็นตัวเลข ไม่มีคำ) ---
        stats["code"].add(g.get("code"), p.get("code"), k, track_wer=False)

        # ⭐ ชื่อวิชา: กลุ่ม B วัด WER ได้ เพราะ GT คงช่องว่างไว้
        #    - ภาษาไทย ใช้ pythainlp/newmm ตัดคำ
        #    - ภาษาอังกฤษ ตัดด้วยช่องว่าง
        #    ⚠️ name_en ใน GT มี \n ฝังอยู่ (ชื่อยาวถูกตัดบรรทัดใน PDF)
        #       normalize ระดับ basic ขึ้นไปจะยุบ \n เป็นช่องว่างให้อัตโนมัติ
        stats["name_th"].add(g.get("name_th"), p.get("name_th"), k, track_wer=True)
        stats["name_en"].add(g.get("name_en"), p.get("name_en"), k, track_wer=True)

        stats["credits"].add(g.get("credits"), p.get("credits"), k, track_wer=False)
        if id(g) not in wild_ids:     # wildcard: Lab 7B คืน 0/0 โดยออกแบบ (ดูหัวข้อรอบจับคู่ wildcard)
            stats["year_sem"].add(f"{g.get('year')}/{g.get('semester')}",
                                  f"{p.get('year')}/{p.get('semester')}",
                                  k, track_wer=False)
        stats["category"].add(g.get("category"), p.get("category"), k, track_wer=False)
        stats["ctype"].add(g.get("type"), p.get("type"), k, track_wer=False)
        stats["prereq"].add(g.get("prerequisite"), p.get("prerequisite"),
                            k, track_wer=False)
        if id(g) not in wild_ids:
            stats["flexible"].add(g.get("flexible_year_semester"),
                                  p.get("flexible_year_semester"), k, track_wer=False)
        ctype_pairs.append((g.get("type"), p.get("type")))
        category_pairs.append((g.get("category"), p.get("category")))

    # --- วิชาที่โมเดลอ่านตก: นับเป็น deletion เต็มจำนวน ---
    # ถ้าไม่นับ โมเดลที่อ่านแค่ 10 วิชาจาก 91 วิชาจะได้ CER ต่ำเตี้ย
    # ทั้งที่ใช้งานจริงไม่ได้เลย
    for g in align.missed:
        k = f"{g.get('code')} [ตกแถว]"
        stats["code"].add(g.get("code"), "", k, track_wer=False)
        stats["name_th"].add(g.get("name_th"), "", k, track_wer=True)
        stats["name_en"].add(g.get("name_en"), "", k, track_wer=True)
        stats["credits"].add(g.get("credits"), "", k, track_wer=False)
        stats["year_sem"].add(f"{g.get('year')}/{g.get('semester')}", "",
                              k, track_wer=False)
        stats["category"].add(g.get("category"), "", k, track_wer=False)
        stats["ctype"].add(g.get("type"), "", k, track_wer=False)
        ctype_pairs.append((g.get("type"), None))
        category_pairs.append((g.get("category"), None))

    classification = {
        "ctype": M.classification_report(ctype_pairs),
        "category": M.classification_report(category_pairs),
    }

    align_summary = {
        "matched": len(align.matched),
        "missed": len(align.missed),
        "spurious": len(align.spurious),
        "precision": round(align.precision, 4),
        "recall": round(align.recall, 4),
        "f1": round(align.f1, 4),
        "gt_total": len(g_courses),
        "pred_total": len(p_courses),
        "missed_codes": [g.get("code") for g in align.missed][:20],
        "spurious_codes": [p.get("code") for p in align.spurious][:20],
        "classification": classification,
        # ก่อนรอบจับคู่ wildcard (ตัวเลขแบบเดิม) + จำนวนคู่ที่รอบ wildcard จับเพิ่ม เพื่อเทียบย้อนหลัง
        "strict": strict_numbers,
        "wildcard_pass_matched": len(wild_pairs),
    }
    return stats, align_summary


# ==============================================================================
#  ส่วนที่ 12 — MAIN
# ==============================================================================


def apply_book_prerequisites(data: dict, book_ocr: str) -> dict | None:
    """เติมฟิลด์ prerequisite จากข้อความ OCR ทั้งเล่ม (ภาคผนวก "คำอธิบายรายวิชา") ตามใบงาน §3.4 / §7.1 กฎ 5

    โมเดลไม่เคยเป็นคนกรอกฟิลด์นี้ (ถูกทิ้งใน pipeline_vlm ตามหมายเหตุส่วนที่ 3) — ขั้นนี้เป็นกฎเชิงกำหนดล้วน
    (prereq_from_book.py) ไม่เรียก LLM ไม่ใช้เฉลย ไม่เดา: อ่านไม่เจอ/อ่านไม่ออก = ไม่ใส่ฟิลด์ ไม่ใช่ "ไม่มี"
    คืนจำนวนต่อสถานะ (หรือ None ถ้าไม่มีไฟล์)"""
    path = Path(book_ocr)
    if not path.exists():
        print(f"  ⚠ ไม่พบข้อความ OCR ทั้งเล่ม {path} — ข้ามขั้นเติม prerequisite")
        return None
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from prereq_from_book import fill_prerequisite_field
    lines = path.read_text(encoding="utf-8").splitlines()
    counts = fill_prerequisite_field(data.get("courses") or [], lines)
    print(f"    เติม prerequisite จาก {path.name}: พบ {counts['found']} · ไม่มี {counts['none']} · "
          f"หาไม่เจอ {counts['not_found']} · อ่านไม่ออก {counts['unreadable']} "
          f"(ไม่ใส่ฟิลด์ = ไม่ทราบ ไม่ใช่ 'ไม่มี')")
    return counts


def run_pipeline(name: str, pages: list[bytes], outdir: Path,
                 pdf_path: str | None, page_spec: str | None) -> dict | None:
    print(f"\n{'─' * 70}")
    print(f"  PIPELINE: {name}")
    print(f"{'─' * 70}")
    t0 = time.time()
    try:
        if name == "baseline":
            data = pipeline_baseline(pages)
        elif name == "text":
            if not pdf_path:
                print("  ⚠ pipeline 'text' ใช้ได้กับไฟล์ PDF เท่านั้น")
                return None
            data = pipeline_text(pdf_path, page_spec)
        elif name == "vlm":
            data = pipeline_vlm(pages, outdir)
        elif name == "markdown":
            if not pdf_path:
                return None
            data = pipeline_markdown(pdf_path)
        else:
            raise ValueError(name)
    except Exception as e:
        print(f"  ❌ {name} ล้มเหลว: {e}")
        return None

    if not data or not data.get("courses"):
        print(f"  ⚠ {name} ไม่ได้ผลลัพธ์")
        return None

    book_ocr = os.environ.get("LAB7_BOOK_OCR")
    prereq_counts = (apply_book_prerequisites(data, book_ocr)
                     if book_ocr and name in ("vlm", "markdown") else None)

    data["_meta"] = {
        "pipeline": name,
        "elapsed_sec": round(time.time() - t0, 1),
        "models": {"ocr": MODEL_OCR, "text": MODEL_TEXT},
        "dpi": DPI, "pages_per_chunk": PAGES_PER_CHUNK,
    }
    if prereq_counts is not None:
        data["_meta"]["prerequisite_from_book"] = {"source": book_ocr, **prereq_counts}
    path = outdir / f"pred_{name}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ บันทึก {path}  ({len(data['courses'])} วิชา, "
          f"{data['_meta']['elapsed_sec']} วิ)")
    return data


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Lab 7B — สกัดแผนการศึกษาจากเล่มหลักสูตร ด้วย LLM บนเครื่อง")
    ap.add_argument("-i", "--input", help="ไฟล์เล่มหลักสูตร (.pdf/.png), โฟลเดอร์ภาพ หรือ Markdown")
    ap.add_argument("-g", "--gt", help="ไฟล์ ground truth (.json)")
    ap.add_argument("-o", "--out", default="output")
    ap.add_argument("-p", "--pipeline", default="all",
                    choices=["all", "baseline", "text", "vlm", "markdown"])
    ap.add_argument("--pages", help='เลือกเฉพาะบางหน้า เช่น "42-58" หรือ "3,7,10-12"')
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--eval-only", metavar="PRED_JSON")
    ap.add_argument("--book-ocr", metavar="TXT",
                    help="ข้อความ OCR ทั้งเล่ม (outputs/<หลักสูตร>/*_curriculum_ocr.txt) — เติมฟิลด์ prerequisite "
                         "ด้วยกฎเชิงกำหนด (ไม่ใช้ LLM/เฉลย ไม่เดา) หลังสกัด pipeline vlm/markdown")
    ap.add_argument("--fill-prerequisites", metavar="PRED_JSON",
                    help="เติม prerequisite ให้ไฟล์ผล (pred_*.json) ที่มีอยู่แล้ว โดยไม่ OCR ใหม่ (ต้องมี --book-ocr); "
                         "เก็บสำเนาก่อนแก้เป็น <ไฟล์>.before_prereq.json")
    ap.add_argument("--fill-missing-rows", metavar="PRED_JSON",
                    help="เติมวิชารหัสจริงที่ intermediate_vlm.md (โฟลเดอร์เดียวกัน) มีครบแต่ LLM ทิ้งไป "
                         "ด้วยกฎเชิงกำหนด (md_plan_slots.fill_missing_rows — ไม่ใช้ LLM/เฉลย); "
                         "เก็บสำเนาก่อนแก้เป็น <ไฟล์>.before_fillrows.json")
    ap.add_argument("--recover-codes", metavar="PRED_JSON",
                    help="กู้รหัสวิชาที่ OCR ทำหายจากตารางแผน (แถวมีชื่อ+หน่วยกิตแต่ไม่มีเซลล์รหัส) โดยค้นชื่อใน "
                         "ข้อความ OCR ทั้งเล่ม (--book-ocr) ด้วยกฎเชิงกำหนด (code_from_book.py — ไม่ใช้ LLM/เฉลย); "
                         "เก็บสำเนาก่อนแก้เป็น <ไฟล์>.before_codes.json")
    args = ap.parse_args()

    if args.check:
        sys.exit(0 if check_environment() else 1)

    if args.book_ocr:
        os.environ["LAB7_BOOK_OCR"] = args.book_ocr

    if args.fill_missing_rows:
        target = Path(args.fill_missing_rows)
        md_path = target.with_name("intermediate_vlm.md")
        if not md_path.exists():
            print(f"  ⚠ ไม่พบ {md_path} — ข้ามขั้นเติมแถวที่ LLM ทิ้ง")
            return
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from md_plan_slots import fill_missing_rows
        pred = json.loads(target.read_text(encoding="utf-8"))
        backup = target.with_name(target.stem + ".before_fillrows.json")
        if not backup.exists():           # ไม่ทับสำเนาต้นฉบับถ้ารันซ้ำ
            backup.write_text(json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8")
        added = fill_missing_rows(md_path.read_text(encoding="utf-8"), pred.setdefault("courses", []))
        # รันซ้ำได้ (วิชาที่เติมแล้วอยู่ใน courses จะไม่ถูกเติมซ้ำ) — สะสมรายการ ไม่ทับของรอบก่อน
        pred.setdefault("_meta", {}).setdefault("filled_from_markdown", []).extend(added)
        target.write_text(json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    เติมแถวที่ LLM ทิ้งจาก {md_path.name}: {len(added)} วิชา "
              f"{[a['code'] for a in added]} (สำเนาก่อนแก้: {backup.name})")
        return

    if args.recover_codes:
        if not args.book_ocr:
            raise SystemExit("❌ --recover-codes ต้องระบุ --book-ocr ด้วย")
        target = Path(args.recover_codes)
        md_path = target.with_name("intermediate_vlm.md")
        if not md_path.exists() or not Path(args.book_ocr).exists():
            print(f"  ⚠ ไม่พบ {md_path.name} หรือ {args.book_ocr} — ข้ามขั้นกู้รหัสจากเล่ม")
            return
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from code_from_book import recover_codes, repair_with_book
        pred = json.loads(target.read_text(encoding="utf-8"))
        backup = target.with_name(target.stem + ".before_codes.json")
        if not backup.exists():           # ไม่ทับสำเนาต้นฉบับถ้ารันซ้ำ
            backup.write_text(json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8")
        md_text = md_path.read_text(encoding="utf-8")
        book_text = Path(args.book_ocr).read_text(encoding="utf-8")
        courses = pred.setdefault("courses", [])
        # รหัสหายในแถว -> แยกรหัสที่ LLM รวม -> ชื่อที่อยู่ในตารางแต่รหัสหาย -> ชื่อว่าง/ป้ายวิชาเลือกบนรหัสจริง
        done = recover_codes(md_text, courses, book_text) + repair_with_book(md_text, courses, book_text)
        # รันซ้ำได้ (รหัสที่กู้แล้วอยู่ใน courses จะไม่ถูกทำซ้ำ) — สะสมรายการ ไม่ทับของรอบก่อน
        pred.setdefault("_meta", {}).setdefault("code_from_book", []).extend(done)
        target.write_text(json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    กู้รหัสวิชาจากข้อความ OCR ทั้งเล่ม: {len(done)} รายการ "
              f"{[(d['action'], d.get('from'), d['to']) for d in done]} (สำเนาก่อนแก้: {backup.name})")
        return

    if args.fill_prerequisites:
        if not args.book_ocr:
            raise SystemExit("❌ --fill-prerequisites ต้องระบุ --book-ocr ด้วย")
        target = Path(args.fill_prerequisites)
        pred = json.loads(target.read_text(encoding="utf-8"))
        backup = target.with_name(target.stem + ".before_prereq.json")
        if not backup.exists():           # ไม่ทับสำเนาต้นฉบับถ้ารันซ้ำ
            backup.write_text(json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8")
        counts = apply_book_prerequisites(pred, args.book_ocr)
        if counts is None:
            raise SystemExit(1)
        pred.setdefault("_meta", {})["prerequisite_from_book"] = {"source": args.book_ocr, **counts}
        target.write_text(json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ เขียน {target} (สำเนาก่อนแก้: {backup.name})")
        return

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    if args.eval_only:
        if not args.gt:
            raise SystemExit("❌ --eval-only ต้องระบุ --gt ด้วย")
        pred = json.loads(Path(args.eval_only).read_text(encoding="utf-8"))
        gt = json.loads(Path(args.gt).read_text(encoding="utf-8"))
        stats, align = evaluate(pred, gt)
        M.print_table(stats, f"ผลประเมิน: {Path(args.eval_only).name}")
        print(f"\n  จับคู่วิชา: เจอ {align['matched']}/{align['gt_total']} "
              f"| ตก {align['missed']} | แต่งเกิน {align['spurious']}")
        print(f"  P={align['precision']:.3f}  R={align['recall']:.3f}  "
              f"F1={align['f1']:.3f}")
        if align["missed_codes"]:
            print(f"  วิชาที่อ่านตก: {', '.join(map(str, align['missed_codes'][:10]))}")
        M.print_errors(stats)
        M.print_classification_report(align["classification"]["ctype"], "ctype (บังคับ/เลือก)")
        M.print_classification_report(align["classification"]["category"], "category (หมวดวิชา)")
        return

    if not args.input:
        raise SystemExit("❌ ต้องระบุ --input")

    print("\n" + "=" * 70)
    print("  Lab 7B — สกัดแผนการศึกษา ด้วย LLM ที่รันบนเครื่องตัวเอง")
    print("=" * 70)
    assert_offline()

    print(f"\nเตรียมข้อมูลจาก: {args.input}")
    pages = [] if args.pipeline == "markdown" else load_pages(args.input, args.pages)

    if args.pipeline == "all":
        names = ["text", "vlm"] if SKIP_BASELINE else ["baseline", "text", "vlm"]
        if SKIP_BASELINE:
            print("\n(ข้าม pipeline baseline ตามค่า LAB7_SKIP_BASELINE=1)")
    else:
        names = [args.pipeline]

    results: dict[str, dict] = {}
    for n in names:
        r = run_pipeline(n, pages, outdir, args.input, args.pages)
        if r:
            results[n] = r

    # ---------- ตรวจความสอดคล้องภายใน ----------
    print("\n" + "=" * 70)
    print("  ตรวจความสอดคล้องภายใน (ไม่ใช้เฉลย)")
    print("=" * 70)
    for n, data in results.items():
        v = verify_internal(data)
        print(f"\n  {'✓' if v['ok'] else '✗'} {n}: {v['n_courses']} วิชา, "
              f"รวม {v['total_credits_fixed_terms']} หน่วยกิต (เฉพาะภาคที่ระบุชัด)")
        for msg in v["issues"][:6]:
            print(f"      • {msg}")
        if len(v["issues"]) > 6:
            print(f"      ... และอีก {len(v['issues']) - 6} รายการ")

    # ---------- เทียบ ground truth ----------
    if not args.gt:
        print("\n(ไม่ได้ระบุ --gt จึงข้ามการเทียบกับเฉลย)")
        return

    gt = json.loads(Path(args.gt).read_text(encoding="utf-8"))
    csv_path = outdir / "comparison.csv"
    combined: dict[str, Any] = {}
    first = True

    for n, data in results.items():
        stats, align = evaluate(data, gt)
        M.print_table(stats, f"PIPELINE = {n}")
        print(f"  จับคู่วิชา: เจอ {align['matched']}/{align['gt_total']} "
              f"| ตก {align['missed']} | แต่งเกิน {align['spurious']}   "
              f"P={align['precision']:.3f} R={align['recall']:.3f} "
              f"F1={align['f1']:.3f}")
        M.print_errors(stats, limit=2)
        M.print_classification_report(align["classification"]["ctype"], "ctype (บังคับ/เลือก)")
        M.print_classification_report(align["classification"]["category"], "category (หมวดวิชา)")

        d = M.stats_to_dict(stats)
        d["alignment"] = align
        d["internal_check"] = verify_internal(data)
        combined[n] = d

        tmp = outdir / f"_tmp_{n}.csv"
        M.save_csv(stats, str(tmp), extra={"pipeline": n})
        lines = tmp.read_text(encoding="utf-8-sig").splitlines()
        with open(csv_path, "w" if first else "a", encoding="utf-8-sig") as f:
            f.write("\n".join(lines if first else lines[1:]) + "\n")
        tmp.unlink()
        first = False

    (outdir / "evaluation.json").write_text(
        json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n✓ เสร็จสิ้น")
    print(f"  ตารางเปรียบเทียบ (เปิดใน Excel): {csv_path}")
    print(f"  ผลละเอียด: {outdir / 'evaluation.json'}")


if __name__ == "__main__":
    main()
