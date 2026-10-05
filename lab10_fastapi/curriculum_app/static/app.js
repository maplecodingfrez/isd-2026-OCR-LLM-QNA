/* Curriculum Book Assistant — หน้าเว็บของ curriculum_app (Lab 11).
   ครึ่งบนของไฟล์ = ตรรกะล้วน (ทดสอบด้วย Node); ครึ่งล่าง = ส่วนที่แตะ DOM */
(function () {
  "use strict";

  var QUESTION_MIN = 2;
  var QUESTION_MAX = 500;
  var NETWORK_ACTION = "ตรวจว่ารัน uvicorn อยู่ แล้วลองใหม่อีกครั้ง";
  var RETRY_ACTION = "ลองใหม่อีกครั้ง";
  var INITIAL_PROGRAM = "dsba_coop";   // หลักสูตรที่เลือกไว้ตอนเปิดหน้า (ตรงกับ DB ที่เซิร์ฟเวอร์ใช้อยู่) — ผู้ใช้เปลี่ยนเองได้
  var TIMEOUT_ACTION = "โมเดลอาจยังประมวลผลอยู่ รอสักครู่ แล้วกดลองอีกครั้ง (ถ้ายังเป็นอีก เปิดหน้า /api/health)";
  var NOT_READY_ACTION = "แจ้งผู้ดูแล หรือเปิดหน้า /api/health เพื่อดูว่าส่วนไหนไม่ทำงาน";
  // backend ส่ง "Ollama ล่มตอนสร้าง SQL" เป็น 422 ที่ detail ขึ้นต้นด้วยชื่อ error ของ requests
  // (lab8b.ask จับ exception ขั้นสร้าง SQL เอง) — ต้องไม่บอกผู้ใช้ให้ไปถามใหม่
  var MODEL_DOWN = /^(ConnectionError|ConnectTimeout|ReadTimeout|Timeout|ProxyError|SSLError|ChunkedEncodingError|RequestException)\b/;

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

  // ระบบฝั่งโมเดล/ฐานข้อมูลยังไม่พร้อม: 503 ทุกแผง หรือ 422 ของแผงถามที่เป็น Ollama ล่มตอนสร้าง SQL
  function isModelDown(err, where) {
    if (!(err instanceof ApiError) || err.kind !== "http") return false;
    if (err.status === 503) return true;
    return where === "ask" && err.status === 422 && typeof err.raw === "string" && MODEL_DOWN.test(err.raw);
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
    if (err.kind === "timeout") return { title: "หมดเวลารอคำตอบ (เกิน 180 วินาที)", action: TIMEOUT_ACTION };
    if (err.kind === "network") return { title: "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้", action: NETWORK_ACTION };
    if (err.kind === "server") return { title: "เซิร์ฟเวอร์ขัดข้อง", action: RETRY_ACTION };
    if (isModelDown(err, where)) {
      return { title: "ระบบยังไม่พร้อม (ฐานข้อมูลหรือโมเดล)", action: NOT_READY_ACTION };
    }
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
        : { title: "ไม่พบรายวิชารหัสนี้ในหลักสูตรที่ค้น", action: "ตรวจรหัส หรือเลือกจากรายการแนะนำ" };
    }
    if (err.status >= 500) return { title: "เซิร์ฟเวอร์ขัดข้อง", action: RETRY_ACTION };
    return { title: "ส่งคำขอไม่สำเร็จ (รหัส " + err.status + ")", action: RETRY_ACTION };
  }

  function validateQuestion(raw) {
    var value = String(raw == null ? "" : raw).trim();
    var length = Array.from(value).length;   // นับเป็น code point ให้ตรงกับ Pydantic (Python len)
    if (length < QUESTION_MIN || length > QUESTION_MAX) {
      return { ok: false, value: value, message: "ตอนนี้ " + length + " ตัวอักษร" };
    }
    return { ok: true, value: value, message: "" };
  }

  function validateCode(raw) {
    var value = String(raw == null ? "" : raw).trim();
    if (/^[0-9]{8}$/.test(value)) return { ok: true, value: value, message: "" };
    return { ok: false, value: value, message: "ต้องเป็นตัวเลข 0–9 จำนวน 8 หลัก" };
  }

  // ต่อ ?program=<id> (หรือ &program=) ให้ endpoint ที่ตามหลักสูตรที่ผู้ใช้เลือก; ไม่มีค่า = ไม่ต่อ
  function withProgram(url, program) {
    if (!program) return url;
    return url + (url.indexOf("?") === -1 ? "?" : "&") + "program=" + encodeURIComponent(program);
  }

  // เลขหน้าที่พิมพ์: backend ส่งเป็นสตริงตัวเลข ("334") หรือจำนวนเต็ม; อย่างอื่น = ไม่รู้ (null)
  function printedPage(value) {
    if (Number.isInteger(value)) return value;
    if (typeof value === "string" && /^\s*\d{1,4}\s*$/.test(value)) return parseInt(value, 10);
    return null;
  }

  // citations จาก backend = [{pdf_page: int, printed_page: "334" | int | null, courses: ["รหัสวิชา", ...]}];
  // courses = วิชาของคำตอบที่พบในหน้านั้น; ข้อมูลเพี้ยน = ข้าม (ไม่เดา)
  function citationItems(data) {
    var list = data && Array.isArray(data.citations) ? data.citations : [];
    var items = [];
    list.forEach(function (c) {
      if (!c || !Number.isInteger(c.pdf_page)) return;
      var courses = Array.isArray(c.courses) ? c.courses.filter(function (x) { return typeof x === "string"; }) : [];
      var names = {};                                        // รหัส -> ชื่อวิชา (ถ้าเซิร์ฟเวอร์ส่งมา)
      if (c.course_names && typeof c.course_names === "object") {
        courses.forEach(function (code) { if (typeof c.course_names[code] === "string") names[code] = c.course_names[code]; });
      }
      var namesEn = {};
      if (c.course_names_en && typeof c.course_names_en === "object") {
        courses.forEach(function (code) { if (typeof c.course_names_en[code] === "string") namesEn[code] = c.course_names_en[code]; });
      }
      items.push({ printed: printedPage(c.printed_page), pdf: c.pdf_page, courses: courses, names: names, namesEn: namesEn });
    });
    return items;
  }

  function answerText(data) {
    var text = data && typeof data.answer === "string" ? data.answer.trim() : "";
    return text || "(เซิร์ฟเวอร์ไม่ได้ส่งคำตอบกลับมา)";
  }

  // แยกเฉพาะตัวคั่นนอกวงเล็บ ไม่ตัด comma ในตัวเลขหรือรายละเอียดภายในชื่อวิชา
  function splitAnswerParts(text, courses) {
    var parts = [];
    var start = 0;
    var depth = 0;
    for (var i = 0; i < text.length; i++) {
      var ch = text[i];
      if ("([{（".indexOf(ch) !== -1) depth++;
      if (")]}）".indexOf(ch) !== -1) depth = Math.max(0, depth - 1);
      var boundary = courses
        ? ch === "," && /^\s*\d{8}\b/.test(text.slice(i + 1))
        : ch === ";" || (ch === "|" && /\s/.test(text[i - 1] || "") && /\s/.test(text[i + 1] || ""));
      if (depth === 0 && boundary) {
        parts.push(text.slice(start, i).trim());
        start = i + 1;
      }
    }
    parts.push(text.slice(start).trim());
    return parts.filter(Boolean);
  }

  function answerBlocks(data) {
    var blocks = [];
    answerText(data).split(/\r?\n/).forEach(function (line) {
      splitAnswerParts(line, false).forEach(function (part) {
        var bullet = /^[-*•]\s+(.+)$/.exec(part);
        if (bullet) {
          var previous = blocks[blocks.length - 1];
          if (previous && previous.type === "list") previous.items.push(bullet[1]);
          else blocks.push({ type: "list", items: [bullet[1]] });
          return;
        }
        var heading = /^(.*?:)\s*(\d{8}\b[\s\S]*)$/.exec(part);
        var body = heading ? heading[2] : part;
        var courses = splitAnswerParts(body, true);
        if (courses.length > 1 && courses.every(function (item) { return /^\d{8}\b/.test(item); })) {
          if (heading) blocks.push({ type: "paragraph", text: heading[1] });
          blocks.push({ type: "list", items: courses });
        } else {
          blocks.push({ type: "paragraph", text: part });
        }
      });
    });
    return blocks;
  }

  function isEmptyResult(data) {
    return !(data && Array.isArray(data.rows) && data.rows.length > 0);
  }

  function electiveGroups(data) {
    var rows = data && Array.isArray(data.rows) ? data.rows : [];
    if (!rows.length || !rows.every(function (row) {
      return row && typeof row.group_name_th === "string" && row.group_name_th.trim() &&
        typeof row.code === "string" && /^\d{8}$/.test(row.code) &&
        ((typeof row.course_name_th === "string" && row.course_name_th.trim()) ||
         (typeof row.name_th === "string" && row.name_th.trim()));
    })) return [];
    var groups = [];
    var byKey = new Map();
    rows.forEach(function (row) {
      var slot = typeof row.plan_slot === "string" ? row.plan_slot : "";
      var key = JSON.stringify([row.group_no, row.group_name_th, slot]);
      var group = byKey.get(key);
      if (!group) {
        group = { name: row.group_name_th, slot: slot, courses: [] };
        byKey.set(key, group);
        groups.push(group);
      }
      group.courses.push({
        code: row.code,
        name: typeof row.course_name_th === "string" && row.course_name_th.trim() ? row.course_name_th : row.name_th,
        nameEn: typeof row.course_name_en === "string" && row.course_name_en.trim() ? row.course_name_en.trim() :
          (typeof row.name_en === "string" ? row.name_en.trim() : ""),
        credits: Number.isFinite(row.credits) ? row.credits : null,
        creditLabel: typeof row.credits_display === "string" && /^\d+ \(\d+-\d+-\d+\)$/.test(row.credits_display) ? row.credits_display : null
      });
    });
    return groups;
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

  var TIMEOUT_MS = 180000;   // เพดานรอของหน้าเว็บเอง (backend ไม่มีเพดานเท่ากัน: Ollama รอได้ถึง 600 วินาทีต่อครั้ง)

  // จุดเดียวที่คุยกับเครือข่าย: ทุกความล้มเหลวกลายเป็น ApiError ที่ describeError อธิบายได้
  async function apiFetch(url, options, deps) {
    options = options || {};
    deps = deps || {};
    // เรียก fetch ตอนใช้งานจริง (ไม่จับไว้ตอนโหลดไฟล์) เพื่อให้ทับ window.fetch ใน Console ตอนทดสอบได้
    var doFetch = deps.fetch || function (u, init) { return fetch(u, init); };
    var controller = new AbortController();
    var timedOut = false;
    var timer = setTimeout(function () { timedOut = true; controller.abort(); }, deps.timeoutMs || TIMEOUT_MS);
    var res;
    var text;
    try {
      res = await doFetch(url, {
        method: options.method || "GET",
        headers: options.headers,
        body: options.body,
        signal: controller.signal
      });
      text = await res.text();
    } catch (e) {
      throw new ApiError(timedOut ? "timeout" : "network", 0, "", null);
    } finally {
      clearTimeout(timer);
    }
    var body = null;
    var parsed = false;
    try { body = JSON.parse(text); parsed = true; } catch (e) { parsed = false; }
    if (!res.ok) {
      if (!parsed) throw new ApiError("server", res.status, String(text).slice(0, 200), null);
      var raw = body && typeof body === "object" && !Array.isArray(body) ? body.detail : undefined;
      if (raw === undefined) raw = null;
      throw new ApiError("http", res.status, formatDetail(raw), raw);
    }
    if (!parsed) throw new ApiError("server", res.status, "ตอบกลับไม่ใช่ JSON", null);
    return body;
  }

  function prerequisiteEmptyText(data) {
    return data && data.prerequisite_status === "none"
      ? "ไม่มีวิชาบังคับก่อนตามข้อมูลหลักสูตร"
      : "ยังไม่ทราบข้อมูลวิชาบังคับก่อน กรุณาตรวจเล่มหลักสูตร";
  }

  async function currentProgramResult(request, program, currentProgram) {
    try {
      var data = await request;
      return program === currentProgram() ? data : null;
    } catch (err) {
      if (program === currentProgram()) throw err;
      return null;
    }
  }

  function prerequisiteDisplay(course) {
    return courseDisplay(course) + (course.kind === "co" ? " (เรียนร่วมกัน)"
      : course.alternative_group != null ? " (ทางเลือกกลุ่ม " + course.alternative_group + ": ผ่านอย่างใดอย่างหนึ่ง)" : "");
  }

  var api = {
    prerequisiteEmptyText: prerequisiteEmptyText,
    prerequisiteDisplay: prerequisiteDisplay,
    currentProgramResult: currentProgramResult,
    ApiError: ApiError,
    apiFetch: apiFetch,
    withProgram: withProgram,
    isModelDown: isModelDown,
    formatDetail: formatDetail,
    describeError: describeError,
    validateQuestion: validateQuestion,
    validateCode: validateCode,
    citationItems: citationItems,
    answerText: answerText,
    answerBlocks: answerBlocks,
    electiveGroups: electiveGroups,
    isEmptyResult: isEmptyResult,
    buildCopyPayload: buildCopyPayload
  };

  // รันใน Node (ไม่มี document) = export ให้เทสต์แล้วจบ ไม่แตะ DOM
  if (typeof document === "undefined") {
    if (typeof module !== "undefined") { module.exports = api; }
    return;
  }

  // ---------- ส่วนที่แตะ DOM ----------
  var $ = function (id) { return document.getElementById(id); };

  // สร้าง node ด้วย textContent เท่านั้น — ข้อความจากเซิร์ฟเวอร์/โมเดลจึงเป็นตัวอักษรเสมอ ไม่ถูกตีความเป็น HTML
  function el(tag, opts, children) {
    var node = document.createElement(tag);
    opts = opts || {};
    if (opts.className) node.className = opts.className;
    if (opts.text != null) node.textContent = String(opts.text);
    if (opts.attrs) {
      Object.keys(opts.attrs).forEach(function (key) { node.setAttribute(key, opts.attrs[key]); });
    }
    (children || []).forEach(function (child) { node.appendChild(child); });
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  // JS ตั้ง "สถานะ" อย่างเดียว; CSS เป็นคนซ่อน/แสดงบล็อก .state-* ตาม data-state
  function setState(panel, state, controls) {
    var wasLoading = panel.dataset.state === "loading";
    panel.dataset.state = state;
    panel.setAttribute("aria-busy", state === "loading" ? "true" : "false");
    controls.forEach(function (control) { control.disabled = state === "loading"; });
    var submit = panel.querySelector('button[type="submit"]');      // ป้ายปุ่มบอกว่ากำลังทำงาน แล้วกลับเป็นชื่อเดิม
    if (submit) {
      if (!submit.dataset.label) submit.dataset.label = submit.textContent;
      submit.textContent = state === "loading" ? submit.dataset.busyLabel : submit.dataset.label;
      // ปุ่มที่เพิ่งถูก disable ทำให้โฟกัสหลุดไปที่ body: คืนโฟกัสให้ปุ่มส่ง ผู้ใช้คีย์บอร์ดจะได้ทำต่อได้ทันที
      var active = document.activeElement;
      if (wasLoading && state !== "loading" && (!active || active === document.body)) submit.focus();
    }
    // live region ถาวร: โปรแกรมอ่านหน้าจอประกาศการเปลี่ยนสถานะ (บล็อกที่ซ่อนอยู่ประกาศเองไม่น่าเชื่อถือ)
    var heading = panel.querySelector("h2");
    var say = { loading: "กำลังประมวลผล", success: "ได้ผลลัพธ์แล้ว", error: "เกิดข้อผิดพลาด", idle: "" }[state];
    $("live-status").textContent = say ? (heading ? heading.textContent + ": " : "") + say : "";
  }

  var askPanel = $("ask-panel");
  var askControls = [$("ask-button"), $("question"), $("program")];
  var prereqPanel = $("prereq-panel");
  var prereqControls = [$("prereq-button"), $("course-code")];
  var lastResult = null;
  var copyTimer = null;
  var withdrawPanel = $("withdraw-panel");
  var withdrawControls = [$("withdraw-button"), $("withdraw-code")];

  async function runWithdrawal() {
    if (withdrawPanel.dataset.state === "loading") return;
    var check = validateCode($("withdraw-code").value);
    if (!check.ok) {
      showError(withdrawPanel, withdrawControls, "withdraw", new ApiError("http", 422, check.message, check.message), "prereq", { local: true });
      $("withdraw-code").focus();
      return;
    }
    var program = $("program").value;
    setState(withdrawPanel, "loading", withdrawControls);
    try {
      var data = await apiFetch(withProgram("/api/courses/" + encodeURIComponent(check.value) + "/withdrawal-impact", program));
      if (program !== $("program").value) { setState(withdrawPanel, "idle", withdrawControls); return; }
      $("withdraw-course").textContent = courseDisplay(data.course);
      $("withdraw-note").textContent = data.note;
      ["direct", "indirect"].forEach(function (key) {
        var list = $("withdraw-" + key);
        clear(list);
        if (!data[key].length) list.appendChild(el("li", { text: "ไม่พบความสัมพันธ์ตัวต่อประเภทนี้ในข้อมูลหลักสูตร" }));
        data[key].forEach(function (course) {
          var path = [data.course.code].concat(course.path.map(function (edge) { return edge.code; })).join(" → ");
          var conditions = course.path.map(function (edge) {
            return edge.code + ": " + (edge.kind === "co" ? "เรียนร่วมกัน" : "วิชาบังคับก่อน") + (edge.alternative ? " (มีทางเลือกอื่นในเงื่อนไขเดียวกัน)" : "");
          }).join("; ");
          list.appendChild(el("li", {}, [
            el("p", { text: courseDisplay(course) }),
            el("p", { className: "muted", text: "ตัวอย่างเส้นทาง: " + path + " — " + conditions })
          ]));
        });
      });
      $("withdraw-citations").textContent = data.citations.length ? "อ้างอิง: " + data.citations.map(function (c) { return "PDF " + c.pdf_page + " (" + c.courses.join(", ") + ")"; }).join("; ") : "ไม่พบเลขหน้าอ้างอิงที่ยืนยันได้";
      setState(withdrawPanel, "success", withdrawControls);
    } catch (err) {
      if (program !== $("program").value) { setState(withdrawPanel, "idle", withdrawControls); return; }
      showError(withdrawPanel, withdrawControls, "withdraw", err, "prereq");
    }
  }

  // opts.local = ตรวจไม่ผ่านในหน้าเว็บเอง (ไม่ได้ส่งคำขอ): ไม่มี "รายละเอียดจากเซิร์ฟเวอร์" และไม่มีปุ่มลองอีกครั้ง
  // (ส่งซ้ำก็ผิดเหมือนเดิม) — ให้แก้ช่องแล้วกดปุ่มหลักแทน
  function showError(panel, controls, prefix, err, where, opts) {
    var local = !!(opts && opts.local);
    var message = describeError(err, where);
    var detail = err instanceof ApiError ? err.detail : (err && err.message ? String(err.message) : "");
    var action = local && detail ? message.action + " (" + detail + ")" : message.action;
    $(prefix + "-error-title").textContent = message.title;
    $(prefix + "-error-action").textContent = action;
    $(prefix + "-error-detail").textContent = local ? "" : detail;
    $(prefix + "-error-more").hidden = local || !detail;
    $(prefix + "-retry").hidden = local;
    setState(panel, "error", controls);
    $("live-status").textContent = message.title + ". " + action;
    if (err instanceof ApiError && (err.kind === "network" || err.kind === "timeout" || isModelDown(err, where))) {
      loadHealth();
    }
  }

  // ---------- แผง 1: ถามเรื่องหลักสูตร ----------
  function renderElectiveGroups(answer, groups, data) {
    var total = groups.reduce(function (n, group) { return n + group.courses.length; }, 0);
    answer.appendChild(el("p", { className: "group-overview", text: groups.length + " กลุ่ม รวม " + total + " รายการ — กดชื่อกลุ่มเพื่อดูรายวิชา" }));
    if (groups.some(function (group) { return group.courses.some(function (course) { return course.creditLabel; }); })) {
      answer.appendChild(el("p", { className: "muted", text: "หน่วยกิต (ชั่วโมงบรรยาย–ปฏิบัติ–ศึกษาด้วยตนเองต่อสัปดาห์)" }));
    }
    var firstGroup = answerText(data).indexOf(groups[0].name);
    var preamble = firstGroup > 0 ? answerText(data).slice(0, firstGroup).trim() : "";
    if (/[ก-๙]/.test(preamble) && !/\d{8}/.test(preamble)) {
      answer.appendChild(el("p", { className: "group-overview", text: preamble }));
    }
    groups.forEach(function (group) {
      var section = el("details", { className: "elective-section" });
      section.open = groups.length === 1;
      section.appendChild(el("summary", {}, [
        el("span", { className: "elective-title", text: group.name }),
        el("span", { className: "elective-count", text: group.courses.length + " รายการ" })
      ]));
      if (group.slot) section.appendChild(el("p", { className: "muted elective-slot", text: group.slot }));
      section.appendChild(el("ul", { className: "elective-courses" }, group.courses.map(function (course) {
        var content = [
          el("span", { className: "code", text: course.code }),
          el("span", { className: "elective-name", text: course.name })
        ];
        if (course.nameEn) content.push(el("span", { className: "elective-name-en", text: course.nameEn, attrs: { lang: "en" } }));
        if (course.credits !== null) content.push(el("span", { className: "elective-credits", text: (course.creditLabel || course.credits) + " หน่วยกิต" }));
        return el("li", {}, content);
      })));
      answer.appendChild(section);
    });
    answer.appendChild(el("details", { className: "original-answer" }, [
      el("summary", { text: "ดูคำตอบต้นฉบับ" }),
      el("p", { text: answerText(data) })
    ]));
  }

  function renderAnswer(data, seconds) {
    var tabs = $("cite-tabs");
    clear(tabs);
    var items = citationItems(data);
    items.forEach(function (c) {
      var tab = el("li", { className: "cite-tab" }, [
        el("span", { text: c.printed !== null ? "หน้า " + c.printed : "PDF " + c.pdf })
      ]);
      if (c.printed !== null) tab.appendChild(el("span", { className: "pdf", text: "PDF " + c.pdf }));
      tabs.appendChild(tab);
    });
    var detail = $("cite-detail");                           // หน้าไหนอ้างวิชาไหน (ไม่มีรหัสวิชา = ไม่แสดงบรรทัดนั้น)
    clear(detail);
    items.forEach(function (c) {
      if (!c.courses.length) return;
      detail.appendChild(el("li", { text: (c.printed !== null ? "หน้า " + c.printed + " (PDF " + c.pdf + ")" : "PDF " + c.pdf) +
        ": " + c.courses.map(function (code) { return [c.names[code] ? code + " " + c.names[code] : code, c.namesEn[code]].filter(Boolean).join(" / "); }).join(", ") }));
    });
    $("answer-box").classList.toggle("is-empty", isEmptyResult(data));
    var answer = $("answer-text");
    clear(answer);
    var groupedQuestion = /วิชาเลือก|กลุ่มวิชา/.test(data.question || "") && /อะไรบ้าง|วิชาอะไร|รายชื่อ|ให้เลือก/.test(data.question || "");
    var groups = groupedQuestion ? electiveGroups(data) : [];
    if (groups.length) renderElectiveGroups(answer, groups, data);
    else answerBlocks(data).forEach(function (block) {
      if (block.type === "list") {
        answer.appendChild(el("ul", { className: "answer-list" }, block.items.map(function (item) {
          return el("li", { text: item });
        })));
      } else {
        answer.appendChild(el("p", { text: block.text }));
      }
    });
    $("citation-details").hidden = detail.childElementCount === 0;
    $("citation-details").open = groups.length === 0;
    $("answer-hint").hidden = !isEmptyResult(data);       // ผลว่าง: แนะนำให้ระบุปีหรือเทอมให้ชัดขึ้น
    $("answer-cite").textContent = !items.length && typeof data.citation_text === "string" ? data.citation_text : "";
    var select = $("program");
    $("answer-source").textContent = select.value && select.selectedOptions[0]
      ? "ตอบจาก " + select.selectedOptions[0].textContent
      : "ตอบจากหลักสูตรที่เซิร์ฟเวอร์ตั้งไว้";
    $("sql-text").textContent = data.sql || "-";
    $("rows-text").textContent = JSON.stringify(data.rows == null ? [] : data.rows, null, 2);
    $("elapsed-text").textContent = "ใช้เวลา " + seconds.toFixed(1) + " วินาที";
    resetCopyUi();
  }

  async function runAsk() {
    if (askPanel.dataset.state === "loading") return;        // กันกดซ้ำ (นอกเหนือจากการ disable ปุ่ม)
    var check = validateQuestion($("question").value);
    if (!check.ok) {
      showError(askPanel, askControls, "ask", new ApiError("http", 422, check.message, [{ msg: check.message }]), "ask", { local: true });
      $("question").focus();          // พาผู้ใช้ไปที่ช่องที่ต้องแก้
      return;
    }
    var program = $("program").value || null;
    var started = performance.now();
    setState(askPanel, "loading", askControls);
    try {
      var data = await currentProgramResult(apiFetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: check.value, program: program })
      }), program, function () { return $("program").value || null; });
      if (data === null) { setState(askPanel, "idle", askControls); return; }
      var seconds = (performance.now() - started) / 1000;
      lastResult = buildCopyPayload(check.value, program, data, seconds);
      renderAnswer(data, seconds);          // ถ้า render พัง จะตกลง catch แล้วขึ้น Error ไม่ค้าง Loading
      setState(askPanel, "success", askControls);
    } catch (err) {
      showError(askPanel, askControls, "ask", err, "ask");
    }
  }

  // ---------- ปุ่ม "คัดลอกผล" ----------
  function resetCopyUi() {
    clearTimeout(copyTimer);
    $("copy-button").textContent = "คัดลอกผล";
    $("copy-button").classList.remove("is-copied");
    $("copy-fallback").hidden = true;
    $("copy-hint").hidden = true;
  }

  function legacyCopy(text) {
    var area = el("textarea", { className: "offscreen", attrs: { readonly: "", "aria-hidden": "true", tabindex: "-1" } });
    area.value = text;
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(area);
    return ok;
  }

  async function copyResult() {
    if (!lastResult) return;
    var text = JSON.stringify(lastResult, null, 2);
    var ok = false;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        ok = true;
      }
    } catch (e) { ok = false; }
    if (!ok) ok = legacyCopy(text);
    if (ok) {
      $("copy-fallback").hidden = true;
      $("copy-hint").hidden = true;
      $("copy-button").textContent = "คัดลอกแล้ว";
      $("copy-button").classList.add("is-copied");
      $("live-status").textContent = "คัดลอกผลแล้ว";     // ป้ายปุ่มเปลี่ยนอย่างเดียวโปรแกรมอ่านหน้าจอไม่ประกาศ
      clearTimeout(copyTimer);
      copyTimer = setTimeout(function () {
        $("copy-button").textContent = "คัดลอกผล";
        $("copy-button").classList.remove("is-copied");
      }, 2000);
      return;
    }
    var box = $("copy-fallback");     // คัดลอกอัตโนมัติไม่ได้ (เช่น เปิดผ่านที่อยู่ IP ของเครื่อง ไม่ใช่ localhost) → ให้เลือกไว้ให้แล้ว
    box.value = text;
    box.hidden = false;
    $("copy-hint").hidden = false;
    $("live-status").textContent = "คัดลอกอัตโนมัติไม่ได้ กด Ctrl+C เพื่อคัดลอกเอง";
    box.focus();
    box.select();
  }

  // ---------- แผง 2: ตรวจวิชาบังคับก่อน ----------
  function courseDisplay(course) {
    var title = (course.name_th || "วิชาในหลักสูตร") + (course.name_en ? " / " + course.name_en : "");
    var credits = course.credits_display || (course.credits != null ? String(course.credits) : "");
    return (course.code || "") + " " + title + (credits ? " — " + credits + " หน่วยกิต" : "");
  }

  function fillCourseList(list, items, emptyText) {
    clear(list);
    var courses = Array.isArray(items) ? items : [];
    if (!courses.length) {
      list.appendChild(el("li", { className: "muted", text: emptyText }));
      return;
    }
    courses.forEach(function (course) {
      list.appendChild(el("li", {}, [
        el("span", { className: "code", text: course.code || "" }),
        document.createTextNode(prerequisiteDisplay(course).slice((course.code || "").length))
      ]));
    });
  }

  function renderPrereq(data) {
    $("prereq-course").textContent = "[" + (data.code || "") + "] " + (data.name_th || "") + (data.name_en ? " / " + data.name_en : "");
    $("prereq-meta").textContent =
      (data.credits_display || (data.credits != null ? data.credits : "")) + " หน่วยกิต" +
      (data.credits_display ? " · (บรรยาย-ปฏิบัติ-ศึกษาด้วยตนเอง)" : "");
    fillCourseList($("prereq-required"), data.prerequisites_required, prerequisiteEmptyText(data));
    fillCourseList($("prereq-unlocks"), data.unlocked_courses, "ไม่พบวิชาตัวต่อในข้อมูลที่มี");
    var citations = citationItems(data);
    $("prereq-citations").textContent = citations.length ? "อ้างอิง: " + citations.map(function (c) {
      return "PDF " + c.pdf + (c.printed ? " / หน้าพิมพ์ " + c.printed : "");
    }).join("; ") : "ไม่พบเลขหน้าอ้างอิงที่ยืนยันได้";
  }

  async function runPrereq() {
    if (prereqPanel.dataset.state === "loading") return;
    var check = validateCode($("course-code").value);
    if (!check.ok) {
      showError(prereqPanel, prereqControls, "prereq", new ApiError("http", 422, check.message, check.message), "prereq", { local: true });
      $("course-code").focus();
      return;
    }
    setState(prereqPanel, "loading", prereqControls);
    var program = $("program").value;
    try {
      var data = await currentProgramResult(apiFetch(withProgram("/api/courses/" + encodeURIComponent(check.value) + "/prerequisites", program)),
        program, function () { return $("program").value; });
      if (data === null) { setState(prereqPanel, "idle", prereqControls); return; }
      renderPrereq(data);
      setState(prereqPanel, "success", prereqControls);
    } catch (err) {
      showError(prereqPanel, prereqControls, "prereq", err, "prereq");
    }
  }

  // ---------- โหลดข้อมูลเริ่มต้น (ล้มได้ทุกตัว หน้ายังใช้งานต่อได้) ----------
  async function loadHealth() {
    var box = $("health");
    try {
      var health = await apiFetch("/api/health", {}, { timeoutMs: 10000 });
      var ready = health.status === "ok";
      var problems = [];
      if (!health.database_ready) problems.push("ไม่พบฐานข้อมูล");
      if (!health.ollama_ready) problems.push("ติดต่อ Ollama ไม่ได้");
      box.dataset.health = ready ? "ok" : "degraded";
      box.textContent = ready ? "ระบบพร้อมใช้งาน" : "ระบบยังไม่พร้อม: " + problems.join(", ");
    } catch (e) {
      box.dataset.health = "down";
      box.textContent = "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้";
    }
  }

  async function loadPrograms() {
    var select = $("program");
    try {
      var programs = await apiFetch("/api/programs", {}, { timeoutMs: 15000 });
      clear(select);
      programs.forEach(function (program) {
        var option = el("option", {
          text: (program.label || program.id) + (program.available ? "" : " (ไม่มีข้อมูล)"),
          attrs: { value: program.id }
        });
        option.disabled = !program.available;
        select.appendChild(option);
      });
      var usable = Array.from(select.options).filter(function (o) { return !o.disabled; });
      var initial = usable.find(function (o) { return o.value === INITIAL_PROGRAM; }) || usable[0];
      if (initial) select.value = initial.value;
    } catch (e) {
      clear(select);
      select.appendChild(el("option", { text: "โหลดรายชื่อหลักสูตรไม่ได้ (ใช้หลักสูตรที่เซิร์ฟเวอร์ตั้งไว้)", attrs: { value: "" } }));
    }
  }

  // บอกว่าแผงตรวจวิชากำลังค้นจากหลักสูตรไหน (ตามช่องเลือกด้านบน)
  function updateScope() {
    var select = $("program");
    var option = select.selectedOptions[0];
    var show = !!(select.value && option);
    $("prereq-scope").hidden = !show;
    if (show) $("prereq-scope").textContent = "ค้นจากหลักสูตร: " + option.textContent;
    $("withdraw-scope").textContent = show ? "ตรวจจากหลักสูตร: " + option.textContent : "ตรวจจากหลักสูตรที่เซิร์ฟเวอร์ตั้งไว้";
  }

  var coursesRequest = 0;

  async function loadCourses() {
    var mine = ++coursesRequest;           // เปลี่ยนหลักสูตรเร็ว ๆ: ใช้เฉพาะผลของคำขอล่าสุด
    try {
      var courses = await apiFetch(withProgram("/api/courses?limit=100", $("program").value), {}, { timeoutMs: 15000 });
      if (mine !== coursesRequest) return;
      var datalist = $("courses-list");
      clear(datalist);
      courses.forEach(function (course) {
        var names = [course.name_th, course.name_en].filter(function (name) {
          return typeof name === "string" && name.trim();
        }).map(function (name) { return name.trim(); });
        var label = [course.code || "", names.join(" / ")].filter(Boolean).join(" ");
        datalist.appendChild(el("option", { text: label, attrs: { value: course.code || "", label: label } }));
      });
      var samples = $("prereq-samples");
      clear(samples);
      courses.slice(0, 3).forEach(function (course) {
        samples.appendChild(el("button", { className: "link-button", text: course.code || "", attrs: { type: "button", "data-code": course.code || "" } }));
      });
      $("prereq-samples-wrap").hidden = courses.length === 0;
    } catch (e) {
      if (mine !== coursesRequest) return;
      clear($("courses-list"));            // ไม่มี autocomplete ก็ใช้งานได้ (และไม่ค้างรายการของหลักสูตรก่อนหน้า)
      clear($("prereq-samples"));
      $("prereq-samples-wrap").hidden = true;
    }
  }

  // ---------- ผูกเหตุการณ์ ----------
  $("ask-form").addEventListener("submit", function (event) { event.preventDefault(); runAsk(); });
  $("ask-retry").addEventListener("click", runAsk);
  $("copy-button").addEventListener("click", copyResult);
  document.querySelectorAll("[data-question]").forEach(function (button) {
    button.addEventListener("click", function () {
      $("question").value = button.dataset.question;
      $("question").focus();
    });
  });
  $("program").addEventListener("change", function () {
    updateScope();
    loadCourses();
    // ผลที่แสดงอยู่เป็นของหลักสูตรก่อนหน้า: กลับไปสถานะ Idle (ถ้ากำลังตรวจอยู่ปล่อยให้เสร็จก่อน)
    if (prereqPanel.dataset.state !== "loading") setState(prereqPanel, "idle", prereqControls);
    if (withdrawPanel.dataset.state !== "loading") setState(withdrawPanel, "idle", withdrawControls);
  });
  $("prereq-form").addEventListener("submit", function (event) { event.preventDefault(); runPrereq(); });
  $("prereq-retry").addEventListener("click", runPrereq);
  $("withdraw-form").addEventListener("submit", function (event) { event.preventDefault(); runWithdrawal(); });
  $("withdraw-retry").addEventListener("click", runWithdrawal);
  $("prereq-samples").addEventListener("click", function (event) {
    var button = event.target.closest("[data-code]");
    if (!button) return;
    $("course-code").value = button.dataset.code;
    runPrereq();
  });

  loadHealth();
  loadPrograms().then(function () { updateScope(); loadCourses(); });
})();
