/* Curriculum Book Assistant — หน้าเว็บของ curriculum_app (Lab 11).
   ครึ่งบนของไฟล์ = ตรรกะล้วน (ทดสอบด้วย Node); ครึ่งล่าง = ส่วนที่แตะ DOM */
(function () {
  "use strict";

  var QUESTION_MIN = 2;
  var QUESTION_MAX = 500;
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
      submit.textContent = t(state === "loading" ? submit.dataset.i18nBusy : submit.dataset.i18n);
      // ปุ่มที่เพิ่งถูก disable ทำให้โฟกัสหลุดไปที่ body: คืนโฟกัสให้ปุ่มส่ง ผู้ใช้คีย์บอร์ดจะได้ทำต่อได้ทันที
      var active = document.activeElement;
      if (wasLoading && state !== "loading" && (!active || active === document.body)) submit.focus();
    }
    // live region ถาวร: โปรแกรมอ่านหน้าจอประกาศการเปลี่ยนสถานะ (บล็อกที่ซ่อนอยู่ประกาศเองไม่น่าเชื่อถือ)
    var heading = panel.querySelector("h2");
    var say = { loading: t("live.busy"), success: t("live.ok"), error: t("live.err"), idle: "" }[state];
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
        if (!data[key].length) list.appendChild(el("li", { text: t("withdraw.none") }));
        data[key].forEach(function (course) {
          var path = [data.course.code].concat(course.path.map(function (edge) { return edge.code; })).join(" → ");
          var conditions = course.path.map(function (edge) {
            return edge.code + ": " + (edge.kind === "co" ? t("withdraw.co") : t("withdraw.pre")) + (edge.alternative ? t("withdraw.alt") : "");
          }).join("; ");
          list.appendChild(el("li", {}, [
            el("p", { text: courseDisplay(course) }),
            el("p", { className: "muted", text: t("withdraw.path", { path: path, cond: conditions }) })
          ]));
        });
      });
      $("withdraw-citations").textContent = data.citations.length ? t("withdraw.cite") + data.citations.map(function (c) { return "PDF " + c.pdf_page + " (" + c.courses.join(", ") + ")"; }).join("; ") : t("withdraw.noCite");
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
    answer.appendChild(el("details", { className: "original-answer" }, [
      el("summary", { text: t("elective.original") }),
      el("p", { text: answerText(data) })
    ]));
  }

  function renderAnswer(data, seconds) {
    var items = citationItems(data);

    var tabs = $("cite-tabs");
    if (tabs) {
      clear(tabs);
      items.forEach(function (c) {
        var tab = el("li", { className: "cite-tab" }, [
          el("span", { className: "page", text: c.printed !== null ? t("cite.page", { n: c.printed }) : "PDF " + c.pdf }),
          c.printed !== null ? el("span", { className: "pdf", text: "PDF " + c.pdf }) : null
        ].filter(Boolean));
        tabs.appendChild(tab);
      });
    }

    var detail = $("cite-detail");
    if (detail) {
      clear(detail);
      items.forEach(function (c) {
        if (!c.courses.length) return;
        detail.appendChild(el("li", { text: (c.printed !== null ? "หน้า " + c.printed + " (PDF " + c.pdf + ")" : "PDF " + c.pdf) +
          ": " + c.courses.map(function (code) { return [c.names[code] ? code + " " + c.names[code] : code, c.namesEn[code]].filter(Boolean).join(" / "); }).join(", ") }));
      });
      var detailsWrap = $("citation-details");
      if (detailsWrap) detailsWrap.hidden = !items.some(function (c) { return c.courses.length; });
    }

    var cards = $("cite-cards");                             // 1 หน้าอ้างอิง = 1 การ์ด: เลขหน้า + วิชาที่พบในหน้านั้น
    if (cards) {
      clear(cards);
      items.forEach(function (c) {
        var head = el("div", { className: "cite-card-head" }, [
          el("span", { className: "cite-page", text: c.printed !== null ? t("cite.page", { n: c.printed }) : "PDF " + c.pdf })
        ]);
        if (c.printed !== null) head.appendChild(el("span", { className: "cite-pdf", text: "PDF " + c.pdf }));
        var card = el("li", { className: "cite-card" }, [head]);
        if (c.courses.length) {
          var chipList = el("ul", { className: "cite-chip-list" });
          c.courses.forEach(function (code) {
            var label = [c.names[code] ? code + " " + c.names[code] : code, c.namesEn[code]].filter(Boolean).join(" / ");
            chipList.appendChild(el("li", { className: "cite-chip", text: label }));
          });
          card.appendChild(chipList);
        }
        cards.appendChild(card);
      });
    }

    $("answer-box").classList.toggle("is-empty", isEmptyResult(data));
    var answer = $("answer-text");
    clear(answer);
    var groupedQuestion = (/วิชาเลือก|กลุ่มวิชา/.test(data.question || "") && /อะไรบ้าง|วิชาอะไร|รายชื่อ|ให้เลือก/.test(data.question || "")) ||
      /\belective/i.test(data.question || "");      // ถามเป็นอังกฤษ ("What are the elective courses...") ก็จัดกลุ่มเหมือนกัน
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
    $("answer-hint").hidden = !isEmptyResult(data);       // ผลว่าง: แนะนำให้ระบุปีหรือเทอมให้ชัดขึ้น
    $("answer-cite").textContent = !items.length && typeof data.citation_text === "string" ? data.citation_text : "";
    var select = $("program");
    $("answer-source").textContent = select.value && select.selectedOptions[0]
      ? t("answer.source", { name: select.selectedOptions[0].textContent })
      : t("answer.sourceDefault");
    $("sql-text").textContent = data.sql || "-";
    $("rows-text").textContent = JSON.stringify(data.rows == null ? [] : data.rows, null, 2);
    $("elapsed-text").textContent = t("elapsed", { s: seconds.toFixed(2) }) + (seconds < 5.0 ? " (< 5s Bonus ⭐)" : "");
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
      if (data === null) { setState(askPanel, "idle", askControls); return; }
      var seconds = (performance.now() - started) / 1000;
      lastResult = buildCopyPayload(check.value, program, data, seconds);
      renderAnswer(data, seconds);          // ถ้า render พัง จะตกลง catch แล้วขึ้น Error ไม่ค้าง Loading
      lastAnswer = { data: data, seconds: seconds };
      setState(askPanel, "success", askControls);
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
        document.createTextNode(courseDisplay(course).slice((course.code || "").length))
      ]));
    });
  }

  var lastPrereq = null;             // เก็บผลล่าสุดไว้แสดงใหม่เมื่อสลับภาษา (ไม่ต้องเรียก API ซ้ำ)

  function renderPrereq(data) {
    lastPrereq = data;
    var names = courseNames(data);
    $("prereq-course").textContent = "[" + (data.code || "") + "] " + names.primary + (names.secondary ? " / " + names.secondary : "");
    $("prereq-meta").textContent =
      (data.credits_display || (data.credits != null ? data.credits : "")) + " " + t("credits.unit") +
      (data.credits_display ? t("prereq.hours") : "");
    fillCourseList($("prereq-required"), data.prerequisites_required, prerequisiteEmptyText(data));
    fillCourseList($("prereq-unlocks"), data.unlocked_courses, t("prereq.noneUnlocks"));
    var citeEl = $("prereq-citations");
    if (citeEl) {
      citeEl.textContent = data.citations && data.citations.length
        ? t("withdraw.cite") + data.citations.map(function (c) {
            return (c.printed_page !== null ? "หน้า " + c.printed_page + " (PDF " + c.pdf_page + ")" : "PDF " + c.pdf_page) +
              (c.courses && c.courses.length ? " (" + c.courses.join(", ") + ")" : "");
          }).join("; ")
        : "";
    }
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
      var initial = usable.find(function (o) { return o.value === INITIAL_PROGRAM; }) || usable[0];
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
    var planBadge = $("dash-program-badge");
    if (planBadge && option) planBadge.textContent = select.value || t("dash.default");
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
  var SEARCH_LIMIT = 20;
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

  function applyTheme(name) {
    var theme = name === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = theme;
    $("theme-toggle").textContent = t(theme === "dark" ? "theme.toLight" : "theme.toDark");   // ปุ่มบอกธีมที่จะสลับไป
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
    applyTheme(document.documentElement.dataset.theme);

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

  // ---------- ผูกเหตุการณ์ ----------
  $("ask-form").addEventListener("submit", function (event) { event.preventDefault(); runAsk(); });
  $("question").addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {   // Enter = ถาม, Shift+Enter = ขึ้นบรรทัดใหม่
      event.preventDefault();
      runAsk();
    }
  });
  $("ask-retry").addEventListener("click", runAsk);
  $("copy-button").addEventListener("click", copyResult);
  document.querySelectorAll("[data-question]").forEach(function (button) {
    button.addEventListener("click", function () {
      var english = I18N && I18N.getLang() === "en" && button.dataset.questionEn;    // อังกฤษ = ส่งคำถามภาษาอังกฤษ (backend ตอบได้ แต่ตัวคำตอบยังเป็นไทย)
      $("question").value = english ? button.dataset.questionEn : button.dataset.question;
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
    runPrereq();
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
    applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  });

  applyLang(document.documentElement.lang === "en" ? "en" : "th");   // ภาษา/ธีมที่บันทึกไว้ถูกตั้งบน <html> ตั้งแต่ก่อนวาดหน้า
  loadPrograms().then(function () { updateScope(); loadCourses(); });
})();
