/* Curriculum Book Assistant — หน้าเว็บของ curriculum_app (Lab 11).
   ครึ่งบนของไฟล์ = ตรรกะล้วน (ทดสอบด้วย Node); ครึ่งล่าง = ส่วนที่แตะ DOM */
(function () {
  "use strict";

  var QUESTION_MIN = 2;
  var QUESTION_MAX = 500;
  var urlParams = (typeof location !== "undefined" && typeof URLSearchParams !== "undefined") ? new URLSearchParams(location.search) : null;   // ลิงก์แชร์: ?plan=…&q=…
  var INITIAL_PROGRAM = "dsba_coop";   // หลักสูตรที่เลือกไว้ตอนเปิดหน้า (ตรงกับ DB ที่เซิร์ฟเวอร์ใช้อยู่) — ผู้ใช้เปลี่ยนเองได้

  try {
    if (typeof document !== "undefined" && document.documentElement) {
      var docEl = document.documentElement;
      var savedTheme = localStorage.getItem("theme");
      if (savedTheme === "light" || savedTheme === "dark") docEl.dataset.theme = savedTheme;
      var savedLang = localStorage.getItem("lang");
      if (savedLang === "en" || savedLang === "th") docEl.lang = savedLang;
    }
  } catch (e) {}

  // ข้อความทุกตัวที่ผู้ใช้เห็นมาจาก i18n.js (ไทย/อังกฤษ) — ในเบราว์เซอร์ใช้ window.I18N, ใน Node (เทสต์) require ตรง ๆ
  var I18N = (typeof window !== "undefined" && window.I18N) || (typeof require === "function" ? require("./i18n.js") : null);
  function t(key, vars) { return I18N ? I18N.t(key, vars) : key; }
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
      return { title: t("err.unexpected"), action: t("err.unexpected.act") };
    }
    if (err.kind === "timeout") return { title: t("err.timeout"), action: t("err.timeout.act") };
    if (err.kind === "network") return { title: t("err.network"), action: t("err.network.act") };
    if (err.kind === "server") return { title: t("err.server"), action: t("err.retry") };
    if (isModelDown(err, where)) {
      return { title: t("err.notReady"), action: t("err.notReady.act") };
    }
    if (err.status === 422) {
      if (!isAsk) return { title: t("err.code"), action: t("err.code.act") };
      if (Array.isArray(err.raw)) {
        return { title: t("err.question"), action: t("err.question.act") };
      }
      return { title: t("err.sql"), action: t("err.sql.act") };
    }
    if (err.status === 404) {
      return isAsk
        ? { title: t("err.noProgram"), action: t("err.noProgram.act") }
        : { title: t("err.noCourse"), action: t("err.noCourse.act") };
    }
    if (err.status >= 500) return { title: t("err.server"), action: t("err.retry") };
    return { title: t("err.http", { status: err.status }), action: t("err.retry") };
  }

  function validateQuestion(raw) {
    var value = String(raw == null ? "" : raw).trim();
    var length = Array.from(value).length;   // นับเป็น code point ให้ตรงกับ Pydantic (Python len)
    if (length < QUESTION_MIN || length > QUESTION_MAX) {
      return { ok: false, value: value, message: t("err.chars", { n: length }) };
    }
    return { ok: true, value: value, message: "" };
  }

  function validateCode(raw) {
    var value = String(raw == null ? "" : raw).trim();
    if (/^[0-9]{8}$/.test(value)) return { ok: true, value: value, message: "" };
    return { ok: false, value: value, message: t("err.digits") };
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
    return text || t("answer.none");
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

  // ไม่มีคำตอบจริง: ไม่มีข้อความ หรือเป็นประโยค "ไม่พบข้อมูลนี้ในเล่มหลักสูตร" — ต่างจาก isEmptyResult ที่ดูแค่ว่าไม่มีแถว
  // (คำตอบแบบกฎ เช่น "มีแผนเดียว" ไม่มีแถวแต่เป็นคำตอบจริง ต้องมีปุ่มคัดลอก/ไม่โชว์คำแนะนำปีเทอม)
  function noRealAnswer(data) {
    if (!data) return true;
    var text = typeof data.answer === "string" ? data.answer.trim() : "";      // ข้อความดิบ (answerText ใส่ข้อความแทนเมื่อว่าง)
    return text === "" || (isEmptyResult(data) && text.indexOf("ไม่พบข้อมูลนี้ในเล่มหลักสูตร") !== -1);
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
    if (!parsed) throw new ApiError("server", res.status, t("err.badJson"), null);
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
    return courseDisplay(course) + (course.kind === "co" ? t("prereq.co")
      : course.alternative_group != null ? t("prereq.alt").replace("{n}", course.alternative_group) : "");
  }

  // หัวข้อคำถามตัวอย่าง: [รหัสป้ายใน i18n, คำถามไทย, คำถามอังกฤษ] — เลข n เลือกสีคู่ที่ 1-6 ใน style.css
  var SAMPLE_TOPICS = [
    { key: "credits", n: 1, emoji: "🎓", examples: [
      ["chip.1", "หลักสูตรนี้มีหน่วยกิตรวมตลอดหลักสูตรกี่หน่วยกิต", "How many credits in total does the program have?"],
      ["chip.2", "ปี 1 เทอม 1 เรียนกี่หน่วยกิต", "How many credits in year 1 semester 1?"],
      ["chip.9", "หมวดวิชาเฉพาะเลือกเก็บกี่หน่วยกิต", "How many credits are required in each course category?"]] },
    { key: "term", n: 2, emoji: "📅", examples: [
      ["chip.3", "ปี 2 เทอม 1 เรียนวิชาอะไรบ้าง", "What courses are in year 2 semester 1?"],
      ["chip.10", "ปี 3 เทอม 1 มีวิชาอะไรบ้าง และรวมกี่หน่วยกิต", "What courses are in year 3 semester 1 and how many credits in total?"],
      ["chip.11", "ปี 4 เทอม 2 เรียนวิชาอะไรบ้าง", "What courses are in year 4 semester 2?"]] },
    { key: "course", n: 3, emoji: "📘", examples: [
      ["chip.4", "วิชาเลือกของหลักสูตรนี้มีอะไรบ้าง", "What are the elective courses of this program?"],
      ["chip.5", "มีวิชาเกี่ยวกับฐานข้อมูลไหม", "Are there any database courses?"]] },
    { key: "prereq", n: 4, emoji: "🔗", examples: [
      ["chip.7", "วิชา 06026201 ต้องผ่านวิชาใดก่อน", "What are the prerequisites of 06026201?"],
      ["chip.8", "วิชาที่ต้องผ่านแคลคูลัส 1 ก่อนมีอะไรบ้าง", "Which courses require Calculus 1 first?"]] },
    { key: "withdraw", n: 5, emoji: "↩", examples: [
      ["chip.12", "ถ้าถอนวิชา 06026200 จะกระทบกับอะไร", "What is affected if I withdraw from 06026200?"],
      ["chip.13", "วิชา 06026200 มีวิชาต่อไหม", "Does 06026200 have follow-up courses?"]] },
    { key: "compare", n: 6, emoji: "⚖", examples: [
      ["chip.6", "แผนสหกิจกับไม่สหกิจต่างกันอย่างไร", "How do the co-op and non co-op plans differ?"]] }
  ];

  // ตัวอย่างคำถามจาก /api/sample-questions (สร้างจากข้อมูลของแผนที่เลือก) -> รูปแบบเดียวกับ SAMPLE_TOPICS
  // ตัวอย่างหนึ่งข้อ = { label: { th, en }, q: { th, en } }; ว่าง/ผิดรูป = null (หน้าใช้รายการสำรองในไฟล์)
  function sampleTopicsFromApi(apiTopics) {
    if (!Array.isArray(apiTopics)) return null;
    var out = [];
    apiTopics.forEach(function (topic) {
      var meta = SAMPLE_TOPICS.filter(function (item) { return item.key === (topic && topic.key); })[0];
      if (!meta || !Array.isArray(topic.examples)) return;
      var examples = topic.examples.filter(function (e) { return e && e.th && e.en && e.label_th && e.label_en; }).map(function (e) {
        return { label: { th: e.label_th, en: e.label_en }, q: { th: e.th, en: e.en } };
      });
      if (examples.length) out.push({ key: meta.key, n: meta.n, emoji: meta.emoji, examples: examples });
    });
    return out.length ? out : null;
  }

  // ลูกศร/Home/End บนแถบแท็บหรือแถบหัวข้อ → ตำแหน่งใหม่ (-1 = ไม่ใช่ปุ่มเลื่อน)
  function nextTabIndex(current, count, key) {
    if (!count) return -1;
    if (key === "ArrowRight" || key === "ArrowDown") return (current + 1) % count;
    if (key === "ArrowLeft" || key === "ArrowUp") return (current - 1 + count) % count;
    if (key === "Home") return 0;
    if (key === "End") return count - 1;
    return -1;
  }

  // คำตอบที่เป็นเลขเดี่ยวชัดเจน เช่น "ปี 1 เทอม 1 รวม 18 หน่วยกิต" → {before, n, after} สำหรับเลขนับขึ้น; ยาวหรือหลายบรรทัด = null
  function countUpParts(text) {
    if (typeof text !== "string" || text.length > 60 || text.indexOf("\n") !== -1) return null;
    var m = /^(.*?(?:รวม|ทั้งหมด)[^\d\n]{0,20})(\d{1,3})(\s*หน่วยกิต.*)$/.exec(text.trim());
    return m ? { before: m[1], n: parseInt(m[2], 10), after: m[3] } : null;
  }

  // บรรทัดวิชาจาก backend: "06016403 ชื่อไทย / ENGLISH NAME — 3 (2-2-5) หน่วยกิต" (+ หัวข้อนำหน้า "ปี 2 เทอม 1:" และหมายเหตุท้าย "(รวม …)")
  var COURSE_LINE = /^(\d{8})\s+(.+?)(?:\s+\/\s+(.+?))?\s+—\s+(\d+)(?:\s+\((\d+)-(\d+)-(\d+)\))?\s+หน่วยกิต$/;
  var SLOT_LINE = /^ช่องที่นักศึกษาเลือกเอง:\s*(.+?)\s+(\d+(?:\s+\(\d+-\d+-\d+\))?(?:\s+หรือ\s+\d+(?:\s+\(\d+-\d+-\d+\))?)*)\s+หน่วยกิต$/;

  function parseCourseLine(text) {
    var s = String(text == null ? "" : text).trim();
    var note = null;
    var tail = /\s*\((รวม[^)]*)\)\s*$/.exec(s);
    if (tail) { note = tail[1]; s = s.slice(0, tail.index).trim(); }
    var path = null;
    var via = /\s*\(เส้นทาง\s+([^)]+)\)\s*$/.exec(s);
    if (via) { path = via[1].trim(); s = s.slice(0, via.index).trim(); }
    var lead = "";
    var head = /^(.{1,40}?:)\s+(?=\d{8}\s)/.exec(s);
    if (head) { lead = head[1]; s = s.slice(head[0].length); }
    var m = COURSE_LINE.exec(s);
    if (m) {
      return { kind: "course", lead: lead, code: m[1], name: m[2].trim(), nameEn: (m[3] || "").trim(), credits: m[4],
        hours: m[5] !== undefined ? [m[5], m[6], m[7]] : null, path: path, note: note };
    }
    var bare = /^(\d{8})\s+\((.+)\)$/.exec(s);        // "06026200 (แคลคูลัส 1)": รหัส + ชื่อ ไม่มีหน่วยกิต
    if (bare) {
      var names = bare[2].split(/\s+\/\s+/);
      return { kind: "course", lead: lead, code: bare[1], name: names[0].trim(), nameEn: names.slice(1).join(" / ").trim(), credits: null, hours: null, path: path, note: note };
    }
    var slot = SLOT_LINE.exec(s);
    if (slot) return { kind: "slot", lead: lead, name: slot[1].trim(), credits: slot[2].trim(), note: note };
    return null;
  }

  // โครงสร้างหน่วยกิต: "หมวด: N หน่วยกิต — ประกอบด้วย กลุ่ม n, กลุ่ม n (หมายเหตุ)" -> {title, credits, parts:[{name, credits}], note}
  // ไม่ตรงรูปแบบ (รวมถึงส่วนย่อยที่ไม่มีตัวเลขท้าย) = null แล้วแสดงเป็นข้อความเดิม
  var CREDIT_LINE = /^([^:()]+?):\s*(\d+)\s*หน่วยกิต(?:\s*—\s*ประกอบด้วย\s*(.+?))?(?:\s*\(([^)]*)\))?\s*$/;

  function parseCreditLine(text) {
    var m = CREDIT_LINE.exec(String(text == null ? "" : text).trim());
    if (!m) return null;
    var parts = [];
    if (m[3]) {
      var pieces = m[3].split(/,\s*/);
      for (var i = 0; i < pieces.length; i++) {
        var p = /^(.+?)\s+(\d+)$/.exec(pieces[i].trim());
        if (!p) return null;
        parts.push({ name: p[1], credits: parseInt(p[2], 10) });
      }
    }
    return { title: m[1].trim(), credits: parseInt(m[2], 10), parts: parts, note: m[4] ? m[4].trim() : null };
  }

  // ย่อหน้าโครงสร้างหน่วยกิตที่ติดกันรวมเป็นบล็อก {type:"credits", entries} เดียว
  function groupCreditBlocks(blocks) {
    var out = [];
    blocks.forEach(function (block) {
      var entry = block.type === "paragraph" ? parseCreditLine(block.text) : null;
      if (!entry) { out.push(block); return; }
      var last = out[out.length - 1];
      if (last && last.type === "credits") last.entries.push(entry);
      else out.push({ type: "credits", entries: [entry] });
    });
    return out;
  }

  // แถว rows[0] ของคำตอบ answer_type "course_overview" -> ข้อมูลที่วาดการ์ดภาพรวมวิชา (ไม่มีแถว/ไม่มีรหัส = null)
  function overviewParts(row) {
    if (!row || !row.code) return null;
    var hours = row.lecture_h != null && row.lab_h != null && row.self_h != null
      ? [String(row.lecture_h), String(row.lab_h), String(row.self_h)] : null;
    var named = function (list) {
      return (Array.isArray(list) ? list : []).map(function (item) { return { code: item.code, name: item.name_th || "" }; });
    };
    return {
      entry: { kind: "course", code: row.code, name: row.name_th || "", nameEn: row.name_en || "",
        credits: row.credits != null ? String(row.credits) : null, hours: hours, path: null, note: null },
      terms: (Array.isArray(row.terms) ? row.terms : []).map(function (pair) { return { year: pair[0], semester: pair[1] }; }),
      status: row.prerequisite_status || "unknown",
      source: row.source || "plan",
      prerequisites: named(row.prerequisites),
      unlocks: named(row.unlocks)
    };
  }

  // "3 (2-2-5)" จาก API → { credits: "3", hours: ["2","2","5"] | null }
  function splitCredits(display) {
    var m = /^\s*(\d+)(?:\s*\((\d+)-(\d+)-(\d+)\))?\s*$/.exec(String(display == null ? "" : display));
    return m ? { credits: m[1], hours: m[2] !== undefined ? [m[2], m[3], m[4]] : null } : { credits: String(display == null ? "" : display).trim(), hours: null };
  }

  // ป้ายสั้น ๆ ข้างวิชาบังคับก่อน: เรียนร่วมกัน / ทางเลือกกลุ่ม N (ผ่านอย่างใดอย่างหนึ่ง); ไม่มี = ""
  function prereqTag(course) {
    if (course && course.kind === "co") return t("prereq.tagCo");
    if (course && course.alternative_group != null) return t("prereq.tagAlt", { n: course.alternative_group });
    return "";
  }

  // รวมย่อหน้าที่เป็นบรรทัดวิชาติดกันเป็นบล็อก {type:"courses", entries} เดียว; ย่อหน้าอื่นคงเดิม
  function groupCourseBlocks(blocks) {
    var out = [];
    blocks.forEach(function (block) {
      if (block.type === "list" && block.items.length) {                       // รายการหัวข้อย่อย: ทุกข้อเป็นบรรทัดวิชา = แสดงเป็นชั้น
        var entries = block.items.map(parseCourseLine);
        if (entries.every(Boolean)) { out.push({ type: "courses", entries: entries }); return; }
      }
      var entry = block.type === "paragraph" ? parseCourseLine(block.text) : null;
      if (!entry) { out.push(block); return; }
      var last = out[out.length - 1];
      if (last && last.type === "courses") last.entries.push(entry);
      else out.push({ type: "courses", entries: [entry] });
    });
    return out;
  }

  // คำถามเปรียบเทียบที่ได้แถววิชาสองแถว (มีรหัสทั้งคู่) -> สองแถวนั้น วาดเป็นการ์ดภาพรวมสองใบเคียงกัน; ไม่ใช่ = null
  function compareRows(data) {
    if (!data || !Array.isArray(data.rows) || data.rows.length !== 2) return null;
    if (!/เปรียบเทียบ|compare/i.test(data.question || "")) return null;
    return overviewParts(data.rows[0]) && overviewParts(data.rows[1]) ? data.rows : null;
  }

  // Term rows preserve elective slots and their alternatives without parsing prose.
  function termAnswerParts(data) {
    var rows = data && Array.isArray(data.rows) ? data.rows : [];
    var question = data && data.question || "";
    if (!/(?:ปี\s*\d|year\s*\d)/i.test(question) || !/(?:เทอม\s*\d|ภาคการศึกษาที่\s*\d|semester\s*\d)/i.test(question) ||
        !/อะไรบ้าง|วิชาอะไร|รายชื่อ|what courses/i.test(question)) return null;
    var slots = rows.filter(function (row) { return row && typeof row.slot === "string"; });
    if (!slots.length || !rows.every(function (row) {
      return row && Number.isFinite(row.total_credits) && row.total_credits === rows[0].total_credits &&
        (typeof row.slot === "string" || typeof row.code === "string");
    })) return null;
    return { year: slots[0].year, semester: slots[0].semester, total: rows[0].total_credits,
      courses: rows.filter(function (row) { return !row.slot; }),
      slots: slots.map(function (slot) {
        var groups = [];
        (Array.isArray(slot.alternatives) ? slot.alternatives : []).forEach(function (course) {
          var group = groups.find(function (item) { return item.number === course.group_no; });
          if (!group) { group = { number: course.group_no, name: course.group_name, courses: [] }; groups.push(group); }
          group.courses.push(course);
        });
        return { name: slot.slot, kind: slot.kind, credits: slot.credits_display || String(slot.credits), groups: groups };
      }) };
  }

  var api = {
    renderTermAnswer: renderTermAnswer,
    termAnswerParts: termAnswerParts,
    compareRows: compareRows,
    overviewParts: overviewParts,
    parseCreditLine: parseCreditLine,
    groupCreditBlocks: groupCreditBlocks,
    sampleTopicsFromApi: sampleTopicsFromApi,
    noRealAnswer: noRealAnswer,
    splitCredits: splitCredits,
    prereqTag: prereqTag,
    parseCourseLine: parseCourseLine,
    groupCourseBlocks: groupCourseBlocks,
    SAMPLE_TOPICS: SAMPLE_TOPICS,
    nextTabIndex: nextTabIndex,
    countUpParts: countUpParts,
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
  // เปลี่ยนหลักสูตร = ผลที่แสดงอยู่ถูกถามซ้ำกับหลักสูตรใหม่ (คำถาม/รหัสวิชาล่าสุดที่ผู้ใช้ส่งไป)
  var lastAsked = "";
  var lastPrereqCode = "";
  var lastWithdrawCode = "";
  var pendingRefresh = { ask: false, prereq: false, withdraw: false };   // ตอนเปลี่ยนหลักสูตร คำขอเดิมยังวิ่งอยู่: รอให้ถูกทิ้งแล้วถามใหม่

  // คำขอที่ถูกทิ้งเพราะเปลี่ยนหลักสูตรกลางทาง: กลับ Idle แล้ว (ถ้ามีคำสั่งรอ) ถามใหม่กับหลักสูตรที่เลือกอยู่
  function settleDiscarded(key, panel, controls, run) {
    setState(panel, "idle", controls);
    if (pendingRefresh[key]) { pendingRefresh[key] = false; run(); }
  }

  function setState(panel, state, controls) {
    var wasLoading = panel.dataset.state === "loading";
    panel.dataset.state = state;
    panel.setAttribute("aria-busy", state === "loading" ? "true" : "false");
    controls.forEach(function (control) { control.disabled = state === "loading"; });
    var submit = panel.querySelector('button[type="submit"]');      // ป้ายปุ่มบอกว่ากำลังทำงาน แล้วกลับเป็นชื่อเดิม
    if (submit) {
      submit.textContent = t(state === "loading" ? submit.dataset.i18nBusy : submit.dataset.i18n);
      // ปุ่มที่เพิ่งถูก disable ทำให้โฟกัสหลุดไปที่ body: คืนโฟกัสให้ปุ่มส่ง ผู้ใช้คีย์บอร์ดจะได้ทำต่อได้ทันที
      var active = document.activeElement;
      if (wasLoading && state !== "loading" && (!active || active === document.body)) submit.focus();
    }
    // live region ถาวร: โปรแกรมอ่านหน้าจอประกาศการเปลี่ยนสถานะ (บล็อกที่ซ่อนอยู่ประกาศเองไม่น่าเชื่อถือ)
    var heading = panel.querySelector("h2");
    var say = { loading: t("live.busy"), success: t("live.ok"), error: t("live.err"), idle: "" }[state];
    $("live-status").textContent = say ? (heading ? heading.textContent + ": " : "") + say : "";
    if (panel === askPanel) {
      if (state !== "loading") $("examples-drawer").open = state !== "success";   // มีคำตอบแล้ว พับตัวอย่างให้เห็นคำตอบเร็วขึ้น; กลับมาเปิดเมื่อล้าง/ผิดพลาด
      syncClearButton();
    }
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
    lastWithdrawCode = check.value;
    var program = $("program").value;
    setState(withdrawPanel, "loading", withdrawControls);
    try {
      var data = await apiFetch(withProgram("/api/courses/" + encodeURIComponent(check.value) + "/withdrawal-impact", program));
      if (program !== $("program").value) { settleDiscarded("withdraw", withdrawPanel, withdrawControls, runWithdrawal); return; }
      var rootNames = courseNames(data.course);
      $("withdraw-course").textContent = (data.course.code || "") + " " + rootNames.primary;
      $("withdraw-summary").textContent = t("withdraw.summary", { d: data.direct.length, i: data.indirect.length });
      $("withdraw-note").textContent = data.note;
      ["direct", "indirect"].forEach(function (key) {
        var list = $("withdraw-" + key);
        clear(list);
        if (!data[key].length) list.appendChild(el("li", { className: "muted", text: t("withdraw.none") }));
        data[key].forEach(function (course) {
          var path = [data.course.code].concat(course.path.map(function (edge) { return edge.code; })).join(" → ");
          var notes = course.path.filter(function (edge) { return edge.kind === "co" || edge.alternative; }).map(function (edge) {
            return edge.code + ": " + (edge.kind === "co" ? t("withdraw.co") : t("withdraw.pre")) + (edge.alternative ? t("withdraw.alt") : "");
          }).join("; ");     // เงื่อนไขปกติ (วิชาบังคับก่อน) ไม่ต้องบอกซ้ำ: โชว์เฉพาะเรียนร่วมกัน/มีทางเลือก
          list.appendChild(buildCourseLine(entryFromCourse(course, { path: path, pathNote: notes })));
        });
      });
      fillCiteCards($("withdraw-citations"), data.citations, t("withdraw.noCite"));
      setState(withdrawPanel, "success", withdrawControls);
    } catch (err) {
      if (program !== $("program").value) { settleDiscarded("withdraw", withdrawPanel, withdrawControls, runWithdrawal); return; }
      showError(withdrawPanel, withdrawControls, "withdraw", err, "prereq");
    }
  }

  // opts.local = ตรวจไม่ผ่านในหน้าเว็บเอง (ไม่ได้ส่งคำขอ): ไม่มี "รายละเอียดจากเซิร์ฟเวอร์" และไม่มีปุ่มลองอีกครั้ง
  // (ส่งซ้ำก็ผิดเหมือนเดิม) — ให้แก้ช่องแล้วกดปุ่มหลักแทน
  function showError(panel, controls, prefix, err, where, opts) {
    var local = !!(opts && opts.local);
    var message = describeError(err, where);
    var detail = err instanceof ApiError ? err.detail : (err && err.message ? String(err.message) : "");
    if (err instanceof ApiError && err.kind === "network") detail = (detail ? String(detail) + "\n" : "") + t("err.network.dev");   // hint for the operator lives in the details, not the main message
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
    answer.appendChild(el("p", { className: "group-overview", text: t("elective.overview", { g: groups.length, n: total }) }));
    if (groups.some(function (group) { return group.courses.some(function (course) { return course.creditLabel; }); })) {
      answer.appendChild(el("p", { className: "muted", text: t("elective.hours") }));
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
        el("span", { className: "elective-count", text: t("elective.count", { n: group.courses.length }) })
      ]));
      if (group.slot) section.appendChild(el("p", { className: "muted elective-slot", text: group.slot }));
      section.appendChild(el("ul", { className: "elective-courses" }, group.courses.map(function (course) {
        var content = [
          el("span", { className: "code", text: course.code }),
          el("span", { className: "elective-name", text: course.name })
        ];
        if (course.nameEn) content.push(el("span", { className: "elective-name-en", text: course.nameEn, attrs: { lang: "en" } }));
        if (course.credits !== null) content.push(el("span", { className: "elective-credits", text: (course.creditLabel || course.credits) + " " + t("credits.unit") }));
        return el("li", {}, content);
      })));
      answer.appendChild(section);
    });
  }

  // รายวิชาเป็นชั้น ๆ: รหัส | ชื่อภาษาที่เลือก (อีกภาษาเล็กและจาง) | หน่วยกิต + ชั่วโมงบรรยาย/ปฏิบัติ/ศึกษาเอง
  // บรรทัดวิชา 1 บรรทัด: รหัส | ชื่อ (ภาษาที่เลือก + อีกภาษาจาง + ป้ายเส้นทาง/เงื่อนไข) | หน่วยกิต + ชั่วโมง
  // entry: จากข้อความคำตอบ (parseCourseLine) หรือจาก API ผ่าน entryFromCourse; ชื่อที่ resolve แล้วอยู่ใน primary/secondary
  function buildCourseLine(entry) {
    var english = I18N && I18N.getLang() === "en";
    if (entry.kind === "slot") {
      return el("li", { className: "course-line is-slot" }, [
        el("span", { className: "slot-tag", text: t("slot.tag") }),
        el("span", { className: "course-main" }, [el("span", { className: "course-name", text: entry.name })]),
        el("span", { className: "course-meta" }, [el("span", { className: "course-credits", text: entry.credits + " " + t("credits.unit") })])
      ]);
    }
    var swap = entry.primary === undefined && english && entry.nameEn;
    var primary = entry.primary !== undefined ? entry.primary : (swap ? entry.nameEn : entry.name);
    var secondary = entry.primary !== undefined ? entry.secondary : (swap ? entry.name : entry.nameEn);
    var main = [el("span", { className: "course-name", text: primary })];
    if (secondary) main.push(el("span", { className: "course-name-alt", text: secondary, attrs: swap || entry.primary !== undefined ? {} : { lang: "en" } }));
    var tags = [];
    if (entry.tag) tags.push(el("span", { className: "line-tag", text: entry.tag }));
    if (entry.path) tags.push(el("span", { className: "path-tag", text: entry.path }));
    if (entry.pathNote) tags.push(el("span", { className: "path-note", text: entry.pathNote }));
    if (tags.length) main.push(el("span", { className: "course-tags" }, tags));
    var meta = [];
    if (entry.credits) meta.push(el("span", { className: "course-credits", text: entry.credits + " " + t("credits.unit") }));
    if (entry.hours) meta.push(el("span", { className: "course-hours", text: t("hours.fmt", { l: entry.hours[0], p: entry.hours[1], s: entry.hours[2] }) }));
    return el("li", { className: "course-line" }, [
      el("span", { className: "code", text: entry.code }),
      el("span", { className: "course-main" }, main),
      el("span", { className: "course-meta" }, meta)
    ]);
  }

  // วิชาจาก API (code, name_th, name_en, credits_display) → entry สำหรับ buildCourseLine
  function entryFromCourse(course, extra) {
    var names = courseNames(course);
    var split = splitCredits(course.credits_display != null ? course.credits_display : course.credits);
    var entry = { kind: "course", code: course.code || "", primary: names.primary, secondary: names.secondary,
      credits: split.credits || null, hours: split.hours };
    Object.keys(extra || {}).forEach(function (key) { entry[key] = extra[key]; });
    return entry;
  }

  function renderTermAnswer(answer, parts) {
    answer.appendChild(el("p", { className: "group-overview", text:
      t("term.summary", { y: parts.year, s: parts.semester, n: parts.total }) }));
    if (parts.courses.length) renderCourseLines(answer, parts.courses.map(function (course) { return entryFromCourse(course); }));
    parts.slots.forEach(function (slot) {
      if (!slot.groups.length) {
        renderCourseLines(answer, [{ kind: "slot", name: slot.name, credits: slot.credits }]);
        return;
      }
      var section = el("section", { className: "elective-section" });
      section.appendChild(el("h3", { className: "elective-title", text: slot.name + " — " + slot.credits + " " + t("credits.unit") }));
      section.appendChild(el("p", { className: "muted", text: t(slot.kind === "choose_group" ? "term.chooseGroup" : "term.chooseCourse") }));
      slot.groups.forEach(function (group) {
        section.appendChild(el("h4", { className: "term-group-heading" }, [
          el("span", { className: "slot-tag", text: t("slot.tag") }),
          el("span", { text: group.name || t("term.group", { n: group.number }) })
        ]));
        renderCourseLines(section, group.courses.map(function (course) { return entryFromCourse(course); }));
      });
      answer.appendChild(section);
    });
  }

  // การ์ดหน้าอ้างอิง (printed_page/pdf_page + วิชาที่พบ) จาก citations ของ API ใช้ซ้ำในเครื่องมือตรวจวิชา/ผลกระทบการถอน
  function fillCiteCards(list, citations, emptyText) {
    clear(list);
    if (!Array.isArray(citations) || !citations.length) {
      if (emptyText) list.appendChild(el("li", { className: "muted", text: emptyText }));
      return;
    }
    citations.forEach(function (c) {
      var printed = c.printed_page !== null && c.printed_page !== undefined && c.printed_page !== "";
      var head = el("div", { className: "cite-card-head" }, [
        el("span", { className: "cite-page", text: printed ? t("cite.page", { n: c.printed_page }) : "PDF " + c.pdf_page })
      ]);
      if (printed) head.appendChild(el("span", { className: "cite-pdf", text: "PDF " + c.pdf_page }));
      var card = el("li", { className: "cite-card" }, [head]);
      var codes = Array.isArray(c.courses) ? c.courses : [];
      if (codes.length) {
        var chips = el("ul", { className: "cite-chip-list" });
        codes.forEach(function (code) {
          var name = c.course_names && c.course_names[code];
          chips.appendChild(el("li", { className: "cite-chip", text: name ? code + " " + name : code }));
        });
        card.appendChild(chips);
      }
      list.appendChild(card);
    });
  }

  // การ์ดโครงสร้างหน่วยกิต: ชื่อหมวด + หน่วยกิตรวมตัวใหญ่ + แถบเทียบแต่ละกลุ่ม (ตัวเลขอยู่ในข้อความเสมอ แถบเป็นภาพประกอบ)
  function buildCreditCard(entry) {
    var children = [el("div", { className: "credit-head" }, [
      el("span", { className: "credit-title", text: entry.title }),
      el("span", { className: "credit-total" }, [
        el("span", { className: "count-big", text: String(entry.credits) }),
        document.createTextNode(" " + t("credits.unit"))
      ])
    ])];
    if (entry.parts.length) {
      children.push(el("ul", { className: "credit-parts" }, entry.parts.map(function (part) {
        return el("li", { className: "credit-part" }, [
          el("span", { className: "credit-name", text: part.name }),
          el("progress", { className: "credit-bar", attrs: { max: String(entry.credits), value: String(part.credits), "aria-hidden": "true" } }),
          el("span", { className: "credit-value", text: String(part.credits) })
        ]);
      })));
    }
    if (entry.note) children.push(el("p", { className: "credit-note muted", text: entry.note }));
    return el("section", { className: "credit-card" }, children);
  }

  // การ์ดภาพรวมวิชา: บรรทัดวิชาแบบชั้น ๆ + เรียนเมื่อไร / ต้องผ่านก่อน / วิชาต่อ (ชิปกดแล้วถามภาพรวมวิชานั้นต่อ)
  function buildOverviewCard(row) {
    var parts = overviewParts(row);
    var chips = function (list) {
      return el("span", { className: "overview-chips" }, list.map(function (item) {
        return el("button", { className: "overview-chip", text: item.name ? item.code + " " + item.name : item.code,
          attrs: { type: "button", "data-overview-code": item.code } });
      }));
    };
    var fact = function (labelKey, value) {
      return el("div", { className: "overview-fact" }, [el("dt", { text: t(labelKey) }), el("dd", {}, [value])]);
    };
    var text = function (key) { return el("span", { className: "muted", text: t(key) }); };
    var facts = [];
    if (parts.source !== "plan") {
      facts.push(el("p", { className: "credit-note muted", text: t("prereq.notInPlan") }));
    } else {
      facts.push(fact("overview.terms", parts.terms.length
        ? el("span", { className: "overview-chips" }, parts.terms.map(function (term) {
          return el("span", { className: "line-tag", text: t("overview.termFmt", { y: term.year, s: term.semester }) });
        }))
        : text("overview.noTerm")));
      facts.push(fact("overview.prereq", parts.prerequisites.length ? chips(parts.prerequisites)
        : text(parts.status === "none" ? "overview.none" : "overview.unknown")));
      facts.push(fact("overview.unlocks", parts.unlocks.length ? chips(parts.unlocks) : text("overview.noUnlocks")));
    }
    return el("section", { className: "overview-card" }, [
      el("ul", { className: "course-lines" }, [buildCourseLine(parts.entry)]),
      el("dl", { className: "overview-facts" }, facts)
    ]);
  }

  function renderCourseLines(answer, entries) {
    var lead = entries[0].lead;
    if (lead) answer.appendChild(el("p", { className: "course-lead", text: lead }));
    answer.appendChild(el("ul", { className: "course-lines" }, entries.map(buildCourseLine)));
    var note = entries[entries.length - 1].note;
    if (note) answer.appendChild(el("p", { className: "course-tail muted", text: "(" + note + ")" }));
  }

  // เลขเดี่ยวในคำตอบนับขึ้นจาก 0 ใน 0.7 วินาที; ตัวเลขสุดท้ายตรงกับข้อมูลเสมอ และข้ามเมื่อผู้ใช้ปิดแอนิเมชัน
  function animateCount(node, target) {
    if (!window.requestAnimationFrame || document.hidden || (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches)) return;   // แท็บซ่อนอยู่ rAF หยุด: โชว์เลขจริงเลย ไม่ค้างที่ 0
    var start = null;
    node.textContent = "0";
    function tick(now) {
      if (start === null) start = now;
      var p = Math.min((now - start) / 700, 1);
      node.textContent = String(Math.round(target * (1 - Math.pow(1 - p, 3))));
      if (p < 1) window.requestAnimationFrame(tick);
    }
    window.requestAnimationFrame(tick);
  }

  function renderAnswer(data, seconds) {
    var items = citationItems(data);

    var tabs = $("cite-tabs");
    if (tabs) {
      clear(tabs);
      items.forEach(function (c) {        // 1 หน้าอ้างอิง = 1 แถว: ตราเลขหน้า + วิชาที่พบในหน้านั้น
        var stamp = el("span", { className: "cite-tab" }, [
          el("span", { className: "page", text: c.printed !== null ? t("cite.page", { n: c.printed }) : "PDF " + c.pdf }),
          c.printed !== null ? el("span", { className: "pdf", text: "PDF " + c.pdf }) : null
        ].filter(Boolean));
        var row = el("li", { className: "cite-row" }, [stamp]);
        if (c.courses.length) {
          var chipList = el("ul", { className: "cite-chip-list" });
          c.courses.forEach(function (code) {
            var label = [c.names[code] ? code + " " + c.names[code] : code, c.namesEn[code]].filter(Boolean).join(" / ");
            chipList.appendChild(el("li", { className: "cite-chip", text: label }));
          });
          row.appendChild(chipList);
        }
        tabs.appendChild(row);
      });
    }

    var cards = $("cite-cards");
    if (cards) clear(cards);

    $("answer-box").classList.toggle("is-empty", isEmptyResult(data));
    $("answer-box").dataset.question = typeof data.question === "string" ? data.question : "";   // ใช้ตอนพิมพ์: หน้ากระดาษต้องมีคำถามกำกับคำตอบ
    var answer = $("answer-text");
    clear(answer);
    var groupedQuestion = (/วิชาเลือก|กลุ่มวิชา/.test(data.question || "") && /อะไรบ้าง|วิชาอะไร|รายชื่อ|ให้เลือก/.test(data.question || "")) ||
      /\belective/i.test(data.question || "");      // ถามเป็นอังกฤษ ("What are the elective courses...") ก็จัดกลุ่มเหมือนกัน
    var groups = groupedQuestion ? electiveGroups(data) : [];
    var comparison = compareRows(data);
    var term = termAnswerParts(data);
    if (data.answer_type === "course_overview" && Array.isArray(data.rows) && overviewParts(data.rows[0])) {
      answer.appendChild(buildOverviewCard(data.rows[0]));       // รหัส/ชื่อวิชาเฉยๆ = ภาพรวมวิชาจากฐานข้อมูล
    } else if (comparison) {
      answer.appendChild(el("div", { className: "overview-compare" }, comparison.map(buildOverviewCard)));   // เปรียบเทียบสองวิชา = สองการ์ดเคียงกัน
    } else if (term) renderTermAnswer(answer, term);
    else if (groups.length) renderElectiveGroups(answer, groups, data);
    else groupCreditBlocks(groupCourseBlocks(answerBlocks(data))).forEach(function (block, _i, blocks) {
      var counted = blocks.length === 1 && block.type === "paragraph" ? countUpParts(block.text) : null;
      if (block.type === "courses") {
        renderCourseLines(answer, block.entries);
      } else if (block.type === "credits") {
        block.entries.forEach(function (entry) { answer.appendChild(buildCreditCard(entry)); });
      } else if (counted) {
        var number = el("span", { className: "count-big", text: String(counted.n) });
        answer.appendChild(el("p", {}, [document.createTextNode(counted.before), number, document.createTextNode(counted.after)]));
        animateCount(number, counted.n);
      } else if (block.type === "list") {
        answer.appendChild(el("ul", { className: "answer-list" }, block.items.map(function (item) {
          return el("li", { text: item });
        })));
      } else {
        answer.appendChild(el("p", { text: block.text }));
      }
    });
    $("answer-hint").hidden = !isEmptyResult(data);       // ผลว่าง: แนะนำให้ระบุปีหรือเทอมให้ชัดขึ้น
    var noAnswer = noRealAnswer(data);
    $("answer-hint").hidden = !noAnswer;                  // ...แต่คำตอบแบบกฎที่ไม่มีแถวเป็นคำตอบจริง: ไม่ต้องแนะนำ
    $("answer-box").classList.toggle("is-notfound", noAnswer);   // "ไม่พบ" เป็นคำตอบที่ถูกต้อง: หน้าตาสงบ ไม่ใช่คำเตือน
    $("notfound-note").hidden = !noAnswer;
    var yearTermQuestion = /ปี|เทอม|ภาค|year|semester|term/i.test(data.question || "");   // คำแนะนำปี/เทอมใช้เฉพาะคำถามที่พูดถึงปี/เทอม
    $("answer-hint").textContent = t(yearTermQuestion ? "answer.hint" : "answer.hintGeneric");
    // กล่องแหล่งอ้างอิงด้านล่างเหลือไว้เฉพาะกรณีมีแค่ข้อความอ้างอิง (ไม่มีเลขหน้า); เลขหน้าอยู่ในแถวตราด้านบนแล้ว
    var hasCitations = items.length === 0 && typeof data.citation_text === "string" && data.citation_text !== "";
    $("answer-box").querySelector(".citation-box").hidden = !hasCitations;          // ไม่มีหน้าอ้างอิง = ไม่โชว์หัวข้อเปล่า ๆ
    $("answer-box").querySelector(".answer-footer").hidden = noAnswer;   // ไม่มีคำตอบ = ไม่ต้องมีปุ่มคัดลอก
    $("answer-cite").textContent = !items.length && typeof data.citation_text === "string" ? data.citation_text : "";
    var select = $("program");
    $("answer-source").textContent = select.value && select.selectedOptions[0]
      ? t("answer.source", { name: select.selectedOptions[0].textContent })
      : t("answer.sourceDefault");
    $("original-text").textContent = answerText(data) || "-";
    $("sql-text").textContent = data.sql || "-";
    $("rows-text").textContent = JSON.stringify(data.rows == null ? [] : data.rows, null, 2);
    $("elapsed-text").textContent = t("elapsed", { s: seconds.toFixed(2) });
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
    lastAsked = check.value;
    var program = $("program").value || null;
    var started = performance.now();
    setState(askPanel, "loading", askControls);

    var loadingMsgs = [                                      // ข้อความระหว่างรอ หมุนเวียนทุก 1.8 วินาที
      t("loading.1"), t("loading.2"), t("loading.3")
    ];
    var msgIdx = 0;
    var msgEl = $("loading-msg-text");
    if (msgEl) msgEl.textContent = loadingMsgs[0];
    var msgInterval = setInterval(function () {
      msgIdx = (msgIdx + 1) % loadingMsgs.length;
      if (msgEl) msgEl.textContent = loadingMsgs[msgIdx];
    }, 1800);

    try {
      var data = await currentProgramResult(apiFetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: check.value, program: program })
      }), program, function () { return $("program").value || null; });
      clearInterval(msgInterval);
      if (data === null) { settleDiscarded("ask", askPanel, askControls, runAsk); return; }
      var seconds = (performance.now() - started) / 1000;
      lastResult = buildCopyPayload(check.value, program, data, seconds);
      renderAnswer(data, seconds);          // ถ้า render พัง จะตกลง catch แล้วขึ้น Error ไม่ค้าง Loading
      lastAnswer = { data: data, seconds: seconds };
      setState(askPanel, "success", askControls);
      rememberQuestion(check.value);
      syncShareUrl(check.value, program);
    } catch (err) {
      clearInterval(msgInterval);
      showError(askPanel, askControls, "ask", err, "ask");
    }
  }

  // ---------- ปุ่ม "คัดลอกผล" ----------
  function resetCopyUi() {
    clearTimeout(copyTimer);
    $("copy-button").textContent = t("copy.btn");
    $("copy-button").classList.remove("is-copied");
    $("link-copy-button").textContent = t("link.btn");
    $("link-copy-button").classList.remove("is-copied");
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
      $("copy-button").textContent = t("copy.done");
      $("copy-button").classList.add("is-copied");
      $("live-status").textContent = "คัดลอกผลแล้ว";     // ป้ายปุ่มเปลี่ยนอย่างเดียวโปรแกรมอ่านหน้าจอไม่ประกาศ
      clearTimeout(copyTimer);
      copyTimer = setTimeout(function () {
        $("copy-button").textContent = t("copy.btn");
        $("copy-button").classList.remove("is-copied");
      }, 2000);
      return;
    }
    var box = $("copy-fallback");     // คัดลอกอัตโนมัติไม่ได้ (เช่น เปิดผ่านที่อยู่ IP ของเครื่อง ไม่ใช่ localhost) → ให้เลือกไว้ให้แล้ว
    box.value = text;
    box.hidden = false;
    $("copy-hint").hidden = false;
    $("live-status").textContent = "คัดลอกอัตโนมัติไม่ได้ โปรดคัดลอกจากกล่องด้านล่าง";
    box.focus();
    box.select();
  }

  // คัดลอกลิงก์ของคำถามนี้ (ที่อยู่หน้าเว็บมี ?plan=…&q=… อยู่แล้วหลังถามสำเร็จ)
  var linkTimer = null;
  async function copyLink() {
    var text = window.location.href;
    var ok = false;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) { await navigator.clipboard.writeText(text); ok = true; }
    } catch (e) { ok = false; }
    if (!ok) ok = legacyCopy(text);
    var button = $("link-copy-button");
    if (ok) {
      button.textContent = t("link.done");
      button.classList.add("is-copied");
      $("live-status").textContent = t("link.done");
      clearTimeout(linkTimer);
      linkTimer = setTimeout(function () { button.textContent = t("link.btn"); button.classList.remove("is-copied"); }, 2000);
      return;
    }
    var box = $("copy-fallback");        // คัดลอกอัตโนมัติไม่ได้: โชว์ลิงก์ในกล่องที่เลือกไว้ให้
    box.value = text;
    box.hidden = false;
    $("copy-hint").hidden = false;
    box.focus();
    box.select();
  }

  // ---------- แผง 2: ตรวจวิชาบังคับก่อน ----------
  // ชื่อวิชาตามภาษาที่เลือก: ภาษาหลักก่อน ภาษารองตามหลัง (ถ้าไม่มีภาษาที่เลือกก็ใช้อีกภาษาแทน)
  function courseNames(course) {
    var th = typeof course.name_th === "string" ? course.name_th.trim() : "";
    var en = typeof course.name_en === "string" ? course.name_en.trim() : "";
    var english = I18N && I18N.getLang() === "en";
    var primary = (english ? en || th : th || en) || t("course.fallback");
    var secondary = english ? (en ? th : "") : en;
    return { primary: primary, secondary: secondary && secondary !== primary ? secondary : "" };
  }

  function courseDisplay(course) {
    var names = courseNames(course);
    var title = names.primary + (names.secondary ? " / " + names.secondary : "");
    var credits = course.credits_display || (course.credits != null ? String(course.credits) : "");
    return (course.code || "") + " " + title + (credits ? " — " + credits + " " + t("credits.unit") : "");
  }

  function fillCourseList(list, items, emptyText, tagOf) {
    clear(list);
    var courses = Array.isArray(items) ? items : [];
    if (!courses.length) {
      list.appendChild(el("li", { className: "muted", text: emptyText }));
      return;
    }
    courses.forEach(function (course) {
      list.appendChild(buildCourseLine(entryFromCourse(course, { tag: tagOf ? tagOf(course) : "" })));
    });
  }

  var lastPrereq = null;             // เก็บผลล่าสุดไว้แสดงใหม่เมื่อสลับภาษา (ไม่ต้องเรียก API ซ้ำ)

  function renderPrereq(data) {
    lastPrereq = data;
    var names = courseNames(data);
    $("prereq-course").textContent = (data.code || "") + " " + names.primary;
    var own = splitCredits(data.credits_display != null ? data.credits_display : data.credits);
    var metaBox = $("prereq-meta");
    clear(metaBox);
    [names.secondary, own.credits ? own.credits + " " + t("credits.unit") : "",
      own.hours ? t("hours.fmt", { l: own.hours[0], p: own.hours[1], s: own.hours[2] }) : ""].filter(Boolean).forEach(function (part, i) {
      if (i) metaBox.appendChild(document.createTextNode(" · "));
      metaBox.appendChild(el("span", { className: "meta-part", text: part }));     // แต่ละส่วนไม่ตัดบรรทัดกลางคำ
    });
    fillCourseList($("prereq-required"), data.prerequisites_required,
      data.prerequisite_status === "not_in_plan" ? t("prereq.notInPlan") : prerequisiteEmptyText(data), prereqTag);
    fillCourseList($("prereq-unlocks"), data.unlocked_courses, data.prerequisite_status === "not_in_plan" ? t("prereq.notInPlan") : t("prereq.noneUnlocks"));
    fillCiteCards($("prereq-citations"), data.citations, "");
  }

  async function runPrereq() {
    if (prereqPanel.dataset.state === "loading") return;
    var check = validateCode($("course-code").value);
    if (!check.ok) {
      showError(prereqPanel, prereqControls, "prereq", new ApiError("http", 422, check.message, check.message), "prereq", { local: true });
      $("course-code").focus();
      return;
    }
    lastPrereqCode = check.value;
    setState(prereqPanel, "loading", prereqControls);
    var program = $("program").value;
    try {
      var data = await currentProgramResult(apiFetch(withProgram("/api/courses/" + encodeURIComponent(check.value) + "/prerequisites", program)),
        program, function () { return $("program").value; });
      if (data === null) { settleDiscarded("prereq", prereqPanel, prereqControls, runPrereq); return; }
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
      if (!health.database_ready) problems.push(t("health.noDb"));
      if (!health.ollama_ready) problems.push(t("health.noOllama"));
      box.dataset.health = ready ? "ok" : "degraded";
      box.textContent = ready ? t("health.ok") : t("health.notReady") + problems.join(", ");
    } catch (e) {
      box.dataset.health = "down";
      box.textContent = t("health.down");
    }
  }

  async function loadPrograms() {
    var select = $("program");
    try {
      var programs = await apiFetch("/api/programs", {}, { timeoutMs: 15000 });
      clear(select);
      programs.forEach(function (program) {
        programInfo[program.id] = program;
        var option = el("option", { attrs: { value: program.id } });
        option.disabled = !program.available;
        select.appendChild(option);
      });
      programsLoaded = true;
      relabelPrograms();
      var usable = Array.from(select.options).filter(function (o) { return !o.disabled; });
      var wantedPlan = urlParams && urlParams.get("plan");
      var initial = usable.find(function (o) { return o.value === wantedPlan; }) ||
        usable.find(function (o) { return o.value === INITIAL_PROGRAM; }) || usable[0];
      if (initial) select.value = initial.value;
    } catch (e) {
      clear(select);
      select.appendChild(el("option", { text: t("program.loadFail"), attrs: { value: "" } }));
    }
  }

  // ชื่อแผนที่โชว์: ไม่สหกิจ = ชื่อเปล่า (DSBA), สหกิจ = ต่อท้าย "สหกิจ" / "Co-op" ตามภาษา
  function programLabel(program) {
    var label = String(program.label || program.id).replace(/\s*ไม่สหกิจ$/, "");
    if (I18N && I18N.getLang() === "en") label = label.replace(/\s*สหกิจ$/, " Co-op");
    return label + (program.available ? "" : t("program.noData"));
  }

  function relabelPrograms() {
    Array.from($("program").options).forEach(function (option) {
      var info = programInfo[option.value];
      if (info) option.textContent = programLabel(info);
    });
  }

  // บอกว่าแผงตรวจวิชากำลังค้นจากหลักสูตรไหน (ตามช่องเลือกด้านบน)
  function updateScope() {
    var select = $("program");
    var option = select.selectedOptions[0];
    var show = !!(select.value && option);
    $("prereq-scope").hidden = !show;
    if (show) $("prereq-scope").textContent = t("prereq.scope", { name: option.textContent });
    $("withdraw-scope").textContent = show ? t("withdraw.scope", { name: option.textContent }) : t("withdraw.scopeDefault");
    $("search-scope").hidden = !show;
    if (show) $("search-scope").textContent = t("search.scope", { name: option.textContent });
    var planName = $("dash-plan-name");
    if (planName && option) planName.textContent = option.textContent;
    var info = programInfo[select.value];                     // หน่วยกิต/ปีการศึกษาจริงจาก /api/programs (ไม่ฮาร์ดโค้ด)
    $("dash-credits").textContent = info && info.total_credits != null ? t("dash.creditsVal", { n: info.total_credits }) : "-";
    $("dash-years").textContent = info && info.years != null ? t("dash.yearsVal", { n: info.years }) : "-";
  }

  var programInfo = {};
  var coursesRequest = 0;
  var loadedCourses = [];

  // รายการ autocomplete + ตัวอย่างรายวิชาในการ์ดภาพรวม (วาดใหม่ได้เมื่อสลับภาษา)
  function renderCourseLists() {
    var datalist = $("courses-list");
    clear(datalist);
    loadedCourses.forEach(function (course) {
      var names = courseNames(course);
      var label = [course.code || "", names.primary + (names.secondary ? " / " + names.secondary : "")].filter(Boolean).join(" ");
      datalist.appendChild(el("option", { text: label, attrs: { value: course.code || "", label: label } }));
    });
    var previewBox = $("dash-course-preview");
    clear(previewBox);
    loadedCourses.slice(0, 4).forEach(function (course) {
      previewBox.appendChild(el("div", { className: "course-mini-row" }, [
        el("span", { className: "mini-code", text: course.code || "" }),
        el("span", { className: "mini-name", text: courseNames(course).primary }),
        el("span", { className: "mini-credits", text: course.credits != null ? t("dash.unit", { n: course.credits }) : "" })
      ]));
    });
    if (loadedCourses.length > 4) previewBox.appendChild(el("p", { className: "muted", text: t("dash.more", { n: loadedCourses.length - 4 }) }));
    $("dash-course-count").textContent = t("dash.count", { n: loadedCourses.length });
  }

  async function loadCourses() {
    var mine = ++coursesRequest;           // เปลี่ยนหลักสูตรเร็ว ๆ: ใช้เฉพาะผลของคำขอล่าสุด
    try {
      var courses = await apiFetch(withProgram("/api/courses?limit=100", $("program").value), {}, { timeoutMs: 15000 });
      if (mine !== coursesRequest) return;
      loadedCourses = courses;
      renderCourseLists();
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

  // ---------- ค้นหารายวิชา (GET /api/courses?search=) ----------
  var SEARCH_LIMIT = 50;
  var SEARCH_MAX_CHARS = 100;      // ตรงกับ max_length ของ backend
  var SEARCH_DELAY_MS = 250;
  var searchPanel = $("search-panel");
  var searchTimer = null;
  var searchRequest = 0;

  var lastSearch = null;             // { courses, query } — วาดใหม่เมื่อสลับภาษา

  function renderSearch(courses, query) {
    lastSearch = { courses: courses, query: query };
    var list = $("search-results");
    clear(list);
    courses.forEach(function (course) {
      var names = courseNames(course);
      var children = [
        el("span", { className: "code", text: course.code || "" }),
        el("span", { className: "name", text: names.primary }),
        el("span", { className: "credits", text: course.credits != null ? course.credits + " " + t("credits.unit") : "" })
      ];
      if (course.source === "elective" || course.source === "catalog") {      // วิชานอกแผน: บอกว่ามาจากไหน
        children.splice(2, 0, el("span", { className: "source-tag", text: t(course.source === "elective" ? "search.tagElective" : "search.tagCatalog") }));
      }
      if (names.secondary) children.push(el("span", { className: "name-en", text: names.secondary }));
      list.appendChild(el("li", {}, [
        el("button", { className: "search-result", attrs: { type: "button", "data-code": course.code || "" } }, children)
      ]));
    });
    $("search-meta").textContent = !courses.length
      ? t("search.none", { q: query })
      : courses.length >= SEARCH_LIMIT
        ? t("search.many", { n: courses.length })
        : t("search.count", { n: courses.length });
  }

  // พิมพ์ทีละตัว: ไม่ใช้ setState (มันปิดช่องพิมพ์ตอน loading) และไม่ประกาศทุกตัวอักษรให้โปรแกรมอ่านหน้าจอ
  async function runSearch() {
    clearTimeout(searchTimer);
    var query = Array.from($("search-input").value.trim()).slice(0, SEARCH_MAX_CHARS).join("");
    var mine = ++searchRequest;         // ใช้เฉพาะผลของคำขอล่าสุด
    if (!query) {
      searchPanel.dataset.state = "idle";
      return;
    }
    if (searchPanel.dataset.state !== "success") searchPanel.dataset.state = "loading";   // มีผลเก่าอยู่ให้ค้างไว้ ไม่กะพริบ
    try {
      var courses = await apiFetch(
        withProgram("/api/courses?limit=" + SEARCH_LIMIT + "&search=" + encodeURIComponent(query), $("program").value),
        {}, { timeoutMs: 15000 });
      if (mine !== searchRequest) return;
      renderSearch(Array.isArray(courses) ? courses : [], query);
      searchPanel.dataset.state = "success";
      $("live-status").textContent = t("search.live", { msg: $("search-meta").textContent });
    } catch (err) {
      if (mine !== searchRequest) return;
      showError(searchPanel, [], "search", err, "prereq");
    }
  }

  // ---------- ภาษา (ไทย/อังกฤษ) + ธีม (มืด/สว่าง) ----------
  var lastAnswer = null;             // { data, seconds } — วาดคำตอบใหม่เมื่อสลับภาษา
  var programsLoaded = false;        // false = ตัวเลือก "กำลังโหลด…" ยังอยู่ (ยังไม่ได้รายชื่อหลักสูตร)

  function store(key, value) {
    try { localStorage.setItem(key, value); } catch (e) { /* โหมดส่วนตัว: ไม่บันทึกก็ใช้งานได้ */ }
  }

  function currentTheme() {
    var chosen = document.documentElement.dataset.theme;
    if (chosen === "light" || chosen === "dark") return chosen;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";   // ยังไม่เลือก = ตามระบบ
  }

  function syncThemeButton() {
    $("theme-toggle").textContent = t(currentTheme() === "dark" ? "theme.toLight" : "theme.toDark");   // ปุ่มบอกธีมที่จะสลับไป
  }

  function applyTheme(name) {
    var theme = name === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = theme;
    syncThemeButton();
    store("theme", theme);
  }

  function applyLang(code) {
    I18N.setLang(code);
    var lang = I18N.getLang();
    store("lang", lang);
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-lang]").forEach(function (button) {
      button.setAttribute("aria-pressed", button.dataset.lang === lang ? "true" : "false");
    });
    document.querySelectorAll("[data-i18n]").forEach(function (node) {
      var panel = node.closest("[data-state]");
      var busy = node.dataset.i18nBusy && panel && panel.dataset.state === "loading";    // ปุ่มที่กำลังทำงานโชว์ป้าย "กำลัง…"
      node.textContent = t(busy ? node.dataset.i18nBusy : node.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-ph]").forEach(function (node) { node.placeholder = t(node.dataset.i18nPh); });
    document.querySelectorAll("[data-i18n-aria]").forEach(function (node) { node.setAttribute("aria-label", t(node.dataset.i18nAria)); });
    syncThemeButton();
    renderTopics();

    if ($("health").dataset.health === "unknown") $("health").textContent = t("health.checking");
    var firstOption = $("program").options[0];
    if ($("program").options.length === 1 && firstOption && firstOption.value === "" && !programsLoaded) firstOption.textContent = t("program.loading");
    relabelPrograms();
    updateScope();
    renderCourseLists();
    loadHealth();
    if (lastSearch && searchPanel.dataset.state === "success") {
      renderSearch(lastSearch.courses, lastSearch.query);
    }
    if (lastPrereq && prereqPanel.dataset.state === "success") renderPrereq(lastPrereq);
    if (lastAnswer && askPanel.dataset.state === "success") renderAnswer(lastAnswer.data, lastAnswer.seconds);
    if (withdrawPanel.dataset.state === "success") runWithdrawal();              // ข้อความประกอบมาจากเซิร์ฟเวอร์ เรียกใหม่ให้ตรงภาษา
    [[askPanel, askControls], [prereqPanel, prereqControls], [withdrawPanel, withdrawControls]].forEach(function (pair) {
      if (pair[0].dataset.state === "error") setState(pair[0], "idle", pair[1]);   // ข้อความ error เป็นภาษาเดิม: ล้างทิ้งดีกว่าปล่อยค้าง
    });
    if (searchPanel.dataset.state === "error") searchPanel.dataset.state = "idle";
    $("live-status").textContent = "";
  }

  // ---------- หัวข้อคำถามตัวอย่าง ----------
  var currentTopic = -1;                     // -1 = ยังไม่เลือกหัวข้อ: หน้าแรกโชว์แค่ปุ่มหัวข้อ ตัวอย่างโผล่เมื่อกดหัวข้อ
  var sampleTopics = SAMPLE_TOPICS;          // รายการสำรองในไฟล์ จนกว่า /api/sample-questions จะตอบ (หรือถ้าเรียกไม่ได้)
  var samplesRequest = 0;

  // ข้อมูลของตัวอย่างหนึ่งข้อ: รายการสำรองเป็น [รหัสป้าย i18n, ไทย, อังกฤษ]; จาก API เป็น { label: {th,en}, q: {th,en} }
  function exampleParts(example) {
    var english = I18N && I18N.getLang() === "en";
    if (Array.isArray(example)) return { label: t(example[0]), question: english ? example[2] : example[1] };
    return { label: english ? example.label.en : example.label.th, question: english ? example.q.en : example.q.th };
  }

  async function loadSamples() {
    var mine = ++samplesRequest;             // ใช้เฉพาะผลของคำขอล่าสุด (เปลี่ยนแผนเร็ว ๆ)
    try {
      var data = await apiFetch(withProgram("/api/sample-questions", $("program").value), {}, { timeoutMs: 10000 });
      if (mine !== samplesRequest) return;
      sampleTopics = sampleTopicsFromApi(data && data.topics) || SAMPLE_TOPICS;
    } catch (err) {
      if (mine !== samplesRequest) return;
      sampleTopics = SAMPLE_TOPICS;          // เรียกไม่ได้ = ใช้รายการสำรอง ไม่ต้องรบกวนผู้ใช้
    }
    if (currentTopic >= sampleTopics.length) currentTopic = -1;
    renderTopics();
  }

  function renderExamples() {
    var topic = sampleTopics[currentTopic];
    var list = $("examples");
    clear(list);
    if (!topic) { list.className = "examples"; return; }
    list.className = "examples topic-" + topic.n;
    topic.examples.forEach(function (example) {
      var parts = exampleParts(example);
      var button = el("button", { className: "link-button", text: parts.label, attrs: { type: "button" } });
      button.addEventListener("click", function () {
        $("question").value = parts.question;    // อังกฤษ = ส่งคำถามภาษาอังกฤษ (backend แปลงเป็นประโยคไทยที่ตอบได้ แต่ตัวคำตอบยังเป็นไทย)
        runAsk();
      });
      list.appendChild(el("li", {}, [button]));
    });
  }

  function renderTopics() {
    var bar = $("topic-bar");
    clear(bar);
    sampleTopics.forEach(function (topic, i) {
      var pill = el("button", { className: "topic-pill topic-" + topic.n, text: topic.emoji + " " + t("topic." + topic.key),
        attrs: { type: "button", "aria-pressed": i === currentTopic ? "true" : "false" } });
      pill.addEventListener("click", function () { currentTopic = currentTopic === i ? -1 : i; renderTopics(); $("topic-bar").children[i].focus(); });   // กดซ้ำ = พับตัวอย่าง
      bar.appendChild(pill);
    });
    renderExamples();
    renderRecent();
  }

  // ---------- คำถามล่าสุด (เก็บในเบราว์เซอร์ 5 ข้อ) + ปุ่มล้าง ----------
  var RECENT_KEY = "recent-questions";
  var RECENT_MAX = 5;

  function loadRecent() {
    try {
      var list = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
      return Array.isArray(list) ? list.filter(function (q) { return typeof q === "string" && q; }).slice(0, RECENT_MAX) : [];
    } catch (e) { return []; }                               // โหมดส่วนตัว/ข้อมูลเสีย: ไม่มีรายการล่าสุดก็ใช้งานได้
  }

  function rememberQuestion(question) {
    var list = loadRecent().filter(function (q) { return q !== question; });
    list.unshift(question);
    store(RECENT_KEY, JSON.stringify(list.slice(0, RECENT_MAX)));
    renderRecent();
  }

  function renderRecent() {
    var list = $("recent");
    var items = loadRecent();
    clear(list);
    items.forEach(function (question) {
      var button = el("button", { className: "link-button", text: question, attrs: { type: "button" } });
      button.addEventListener("click", function () { $("question").value = question; runAsk(); });
      list.appendChild(el("li", {}, [button]));
    });
    $("recent-wrap").hidden = items.length === 0;
  }

  // ล้างช่องคำถามและผลที่แสดง กลับสู่หน้าตั้งต้น; ปุ่มโผล่เมื่อมีข้อความหรือมีผลค้างอยู่
  function syncClearButton() {
    $("clear-button").hidden = !$("question").value && askPanel.dataset.state === "idle";
  }

  // ที่อยู่หน้าเว็บตามคำถามล่าสุด (แผน + คำถาม) เพื่อคัดลอกแชร์ได้; ล้าง = กลับที่อยู่เปล่า
  function syncShareUrl(question, program) {
    try {
      var query = question ? "?" + new URLSearchParams({ plan: program || "", q: question }).toString() : location.pathname;
      window.history.replaceState(null, "", query);
    } catch (e) { /* ไม่รองรับ history: ใช้งานได้เหมือนเดิม */ }
  }

  function clearAsk() {
    if (askPanel.dataset.state === "loading") return;
    $("question").value = "";
    lastAsked = "";
    lastAnswer = null;
    lastResult = null;
    syncShareUrl("", null);
    setState(askPanel, "idle", askControls);
    $("question").focus();
  }

  // ---------- แท็บเครื่องมือ ----------
  var toolTabs = ["tab-search", "tab-prereq", "tab-withdraw"].map($);
  var toolPanels = ["search-panel", "prereq-panel", "withdraw-panel"].map($);

  function selectTab(index, focus) {
    toolTabs.forEach(function (tab, i) {
      tab.setAttribute("aria-selected", i === index ? "true" : "false");
      tab.tabIndex = i === index ? 0 : -1;
      toolPanels[i].hidden = i !== index;
    });
    if (focus) toolTabs[index].focus();
    store("tool-tab", String(index));
  }

  // ---------- ผูกเหตุการณ์ ----------
  $("ask-form").addEventListener("submit", function (event) { event.preventDefault(); runAsk(); });
  $("clear-button").addEventListener("click", clearAsk);
  $("link-copy-button").addEventListener("click", copyLink);
  document.addEventListener("keydown", function (event) {      // "/" = ไปที่ช่องคำถาม (ไม่แย่งตอนกำลังพิมพ์ในช่องอื่น)
    var tag = event.target && event.target.tagName;
    if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey || event.isComposing) return;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (event.target && event.target.isContentEditable)) return;
    event.preventDefault();
    $("question").focus();
  });
  $("question").addEventListener("input", syncClearButton);
  $("question").addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {   // Enter = ถาม, Shift+Enter = ขึ้นบรรทัดใหม่
      event.preventDefault();
      runAsk();
    }
  });
  $("ask-retry").addEventListener("click", runAsk);
  $("answer-text").addEventListener("click", function (event) {
    var chip = event.target.closest("[data-overview-code]");
    if (!chip) return;
    var code = chip.dataset.overviewCode;
    $("question").value = "วิชา " + code;
    runAsk();
  });
  $("copy-button").addEventListener("click", copyResult);
  $("topic-bar").addEventListener("keydown", function (event) {
    var pills = Array.prototype.slice.call($("topic-bar").children);
    var next = nextTabIndex(pills.indexOf(document.activeElement), pills.length, event.key);
    if (next < 0) return;
    event.preventDefault();
    currentTopic = next;
    renderTopics();
    $("topic-bar").children[next].focus();
  });
  $("tool-tabs").addEventListener("keydown", function (event) {
    var next = nextTabIndex(toolTabs.indexOf(document.activeElement), toolTabs.length, event.key);
    if (next < 0) return;
    event.preventDefault();
    selectTab(next, true);
  });
  toolTabs.forEach(function (tab, index) { tab.addEventListener("click", function () { selectTab(index, false); }); });
  $("program").addEventListener("change", function () {
    updateScope();
    loadCourses();
    loadSamples();                           // ตัวอย่างคำถามตามแผนที่เลือก
    // ผลที่แสดงอยู่เป็นของหลักสูตรก่อนหน้า: ถามซ้ำกับหลักสูตรใหม่ (ถ้ากำลังถามอยู่ รอให้คำขอเดิมถูกทิ้งก่อนแล้วถามใหม่)
    [
      ["ask", askPanel, askControls, runAsk, lastAsked, $("question")],
      ["prereq", prereqPanel, prereqControls, runPrereq, lastPrereqCode, $("course-code")],
      ["withdraw", withdrawPanel, withdrawControls, runWithdrawal, lastWithdrawCode, $("withdraw-code")]
    ].forEach(function (item) {
      var state = item[1].dataset.state;
      if (item[4] && (state === "success" || state === "loading")) {
        item[5].value = item[4];
        if (state === "loading") pendingRefresh[item[0]] = true;
        else item[3]();
      } else if (item[0] !== "ask" && state !== "loading") {
        setState(item[1], "idle", item[2]);          // ผลเก่า/ข้อผิดพลาดของหลักสูตรก่อนหน้า ล้างทิ้ง
      }
    });
  });
  $("search-form").addEventListener("submit", function (event) { event.preventDefault(); runSearch(); });
  $("search-retry").addEventListener("click", runSearch);
  $("search-input").addEventListener("input", function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(runSearch, SEARCH_DELAY_MS);
  });
  $("search-results").addEventListener("click", function (event) {
    var button = event.target.closest("[data-code]");       // กดวิชาที่ค้นเจอ = ตรวจวิชาบังคับก่อนของวิชานั้นต่อเลย
    if (!button) return;
    $("course-code").value = button.dataset.code;
    selectTab(1, false);                                   // ผลตรวจอยู่แท็บ "บังคับก่อน": สลับไปให้เห็น
    runPrereq();
    $("tools-fold").open = true;                           // เครื่องมือพับอยู่: เปิดให้เห็นผลตรวจ
    prereqPanel.scrollIntoView({ block: "nearest" });
  });
  $("program").addEventListener("change", function () {
    if ($("search-input").value.trim()) runSearch();
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

  document.querySelectorAll("[data-lang]").forEach(function (button) {
    button.addEventListener("click", function () { applyLang(button.dataset.lang); });
  });
  $("theme-toggle").addEventListener("click", function () {
    applyTheme(currentTheme() === "dark" ? "light" : "dark");
  });
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", syncThemeButton);
  }

  var savedTab = 0;
  try { savedTab = parseInt(localStorage.getItem("tool-tab"), 10); } catch (e) { savedTab = 0; }
  selectTab(savedTab >= 0 && savedTab < toolTabs.length ? savedTab : 0, false);

  applyLang(document.documentElement.lang === "en" ? "en" : "th");   // ภาษา/ธีมที่บันทึกไว้ถูกตั้งบน <html> ตั้งแต่ก่อนวาดหน้า
  loadPrograms().then(function () {
    updateScope(); loadCourses(); loadSamples();
    var sharedQuestion = urlParams && urlParams.get("q");
    if (sharedQuestion) { $("question").value = sharedQuestion.slice(0, 500); syncClearButton(); runAsk(); }   // เปิดจากลิงก์ที่แชร์: ถามให้เลย
  });
})();
