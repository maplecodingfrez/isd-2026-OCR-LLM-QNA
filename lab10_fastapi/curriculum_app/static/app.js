/* Curriculum Book Assistant — หน้าเว็บของ curriculum_app (Lab 11).
   ครึ่งบนของไฟล์ = ตรรกะล้วน (ทดสอบด้วย Node); ครึ่งล่าง = ส่วนที่แตะ DOM */
(function () {
  "use strict";

  var QUESTION_MIN = 2;
  var QUESTION_MAX = 500;
  var NETWORK_ACTION = "ตรวจว่ารัน uvicorn อยู่ แล้วลองใหม่อีกครั้ง";
  var RETRY_ACTION = "ลองใหม่อีกครั้ง";

  // kind: "network" | "timeout" | "http" | "server"
  // status: เลข HTTP (0 = ไม่ได้คำตอบ) · detail: ข้อความอ่านได้ · raw: detail ดิบจากเซิร์ฟเวอร์
  class ApiError extends Error {
    constructor(kind, status, detail, raw) {
      super(detail || kind);
      this.name = "ApiError";
      this.kind = kind;
      this.status = status;
      this.detail = detail || "";
      this.raw = raw === undefined ? null : raw;
    }
  }

  // detail ของ FastAPI: string (HTTPException) หรือ array ของ {loc, msg, type} (Pydantic)
  function formatDetail(detail) {
    if (typeof detail === "string") return detail;
    if (!Array.isArray(detail)) return "";
    return detail.map(function (item) {
      if (typeof item === "string") return item;
      if (item && typeof item.msg === "string") return item.msg;
      return "";
    }).filter(Boolean).join("; ");
  }

  // ข้อความที่ผู้ใช้เห็น: title = เกิดอะไรขึ้น, action = ต้องทำอะไรต่อ (ตรงกับตารางใน README §13)
  function describeError(err, where) {
    var isAsk = where === "ask";
    if (!(err instanceof ApiError)) {
      return {
        title: "เกิดข้อผิดพลาดที่ไม่คาดคิดในหน้าเว็บ",
        action: "รีเฟรชหน้าแล้วลองใหม่ (ถ้ายังเป็นอีก เปิด Console ดูข้อความ error)"
      };
    }
    if (err.kind === "timeout") return { title: "หมดเวลารอคำตอบ (เกิน 180 วินาที)", action: NETWORK_ACTION };
    if (err.kind === "network") return { title: "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้", action: NETWORK_ACTION };
    if (err.kind === "server") return { title: "เซิร์ฟเวอร์ขัดข้อง", action: RETRY_ACTION };
    if (err.status === 422) {
      if (!isAsk) return { title: "รหัสวิชาไม่ถูกต้อง (ต้องเป็นตัวเลข 8 หลัก)", action: "แก้รหัสแล้วกดตรวจอีกครั้ง" };
      if (Array.isArray(err.raw)) {
        return { title: "คำถามไม่ผ่านการตรวจ (ต้องยาว 2–500 ตัวอักษร)", action: "แก้คำถามแล้วกดถามอีกครั้ง" };
      }
      return { title: "ระบบแปลงคำถามเป็นคำค้นไม่ได้", action: "ลองถามให้เจาะจงขึ้น เช่น ระบุปีหรือเทอม" };
    }
    if (err.status === 404) {
      return isAsk
        ? { title: "ไม่พบหลักสูตรที่เลือก", action: "รีเฟรชหน้าแล้วเลือกหลักสูตรใหม่" }
        : { title: "ไม่พบรายวิชารหัสนี้ในหลักสูตรเริ่มต้น", action: "ตรวจรหัส หรือเลือกจากรายการแนะนำ" };
    }
    if (err.status === 503) {
      return {
        title: "ระบบยังไม่พร้อม (ฐานข้อมูลหรือโมเดล)",
        action: "แจ้งผู้ดูแล หรือเปิดหน้า /api/health เพื่อดูว่าส่วนไหนไม่ทำงาน"
      };
    }
    if (err.status >= 500) return { title: "เซิร์ฟเวอร์ขัดข้อง", action: RETRY_ACTION };
    return { title: "ส่งคำขอไม่สำเร็จ (รหัส " + err.status + ")", action: RETRY_ACTION };
  }

  function validateQuestion(raw) {
    var value = String(raw == null ? "" : raw).trim();
    var length = Array.from(value).length;   // นับเป็น code point ให้ตรงกับ Pydantic (Python len)
    if (length < QUESTION_MIN || length > QUESTION_MAX) {
      return { ok: false, value: value, message: "คำถามต้องยาว 2–500 ตัวอักษร (ตอนนี้ " + length + ")" };
    }
    return { ok: true, value: value, message: "" };
  }

  function validateCode(raw) {
    var value = String(raw == null ? "" : raw).trim();
    if (/^[0-9]{8}$/.test(value)) return { ok: true, value: value, message: "" };
    return { ok: false, value: value, message: "รหัสวิชาต้องเป็นตัวเลข 0–9 จำนวน 8 หลัก เช่น 06016407" };
  }

  // citations จาก backend = [{pdf_page: int, printed_page: int | null}]; ข้อมูลเพี้ยน = ข้าม (ไม่เดา)
  function citationItems(data) {
    var list = data && Array.isArray(data.citations) ? data.citations : [];
    var items = [];
    list.forEach(function (c) {
      if (!c || !Number.isInteger(c.pdf_page)) return;
      items.push({ printed: Number.isInteger(c.printed_page) ? c.printed_page : null, pdf: c.pdf_page });
    });
    return items;
  }

  function answerText(data) {
    var text = data && typeof data.answer === "string" ? data.answer.trim() : "";
    return text || "(เซิร์ฟเวอร์ไม่ได้ส่งคำตอบกลับมา)";
  }

  function isEmptyResult(data) {
    return !(data && Array.isArray(data.rows) && data.rows.length > 0);
  }

  // สิ่งที่ปุ่ม "คัดลอกผล" ส่งออก — 5 คีย์ตายตัว (ไม่รวม sql/rows ให้สั้นพอวางใน Discord)
  function buildCopyPayload(question, program, data, elapsedSeconds) {
    return {
      question: question,
      program: program || null,
      answer: answerText(data),
      citation_text: data && typeof data.citation_text === "string" ? data.citation_text : "",
      elapsed_seconds: Math.round(elapsedSeconds * 10) / 10
    };
  }

  var api = {
    ApiError: ApiError,
    formatDetail: formatDetail,
    describeError: describeError,
    validateQuestion: validateQuestion,
    validateCode: validateCode,
    citationItems: citationItems,
    answerText: answerText,
    isEmptyResult: isEmptyResult,
    buildCopyPayload: buildCopyPayload
  };

  // รันใน Node (ไม่มี document) = export ให้เทสต์แล้วจบ ไม่แตะ DOM
  if (typeof document === "undefined") {
    if (typeof module !== "undefined") { module.exports = api; }
    return;
  }
})();
