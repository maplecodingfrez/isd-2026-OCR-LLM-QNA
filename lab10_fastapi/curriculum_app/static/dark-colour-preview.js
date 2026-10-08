(function () {
  "use strict";
  var directions = {
    k: { title: "K · Pure charcoal", description: "Your charcoal reference: black canvas, #101010 cards, #171717 panels, #272727 hover surfaces and #393939 dividers. Light grey text and controls keep this neutral palette readable.", tokens: {
      bg: "#000000", surface: "#101010", "surface-2": "#171717", "surface-hover": "#272727", line: "#393939", "field-line": "#858585", text: "#f5f5f5", muted: "#bdbdbd", accent: "#dedede", "accent-hover": "#ffffff", "on-accent": "#101010", "choice-bg": "#272727", "choice-fg": "#dedede"
    } },
    j: { title: "J · Green Lantern", description: "Near-black canvas, dark forest cards, and emerald actions. Bright green marks buttons, links and focus; soft green-white text keeps long answers comfortable.", tokens: {
      bg: "#050b08", surface: "#0e1b14", "surface-2": "#173025", "surface-hover": "#203c2e", line: "#385b47", "field-line": "#779f87", text: "#e6f5eb", muted: "#afcbb8", accent: "#39e878", "accent-hover": "#79f5a4", "on-accent": "#050b08", "choice-bg": "#173025", "choice-fg": "#afcbb8"
    } },
    i: { title: "I · Midnight plum", description: "Your second reference: almost-black canvas, deep plum cards, violet panels, and muted purple details. Pale lavender text and actions keep the dark palette readable. No mint.", tokens: {
      bg: "#050205", surface: "#140919", "surface-2": "#23162e", "surface-hover": "#2e2b4d", line: "#4e325c", "field-line": "#a899b8", text: "#eee7f5", muted: "#c8bbd7", accent: "#c8bbd7", "accent-hover": "#eee7f5", "on-accent": "#140919", "choice-bg": "#4e325c", "choice-fg": "#eee7f5", "reference-purple": "#4e325c"
    } },
    h: { title: "H · Reference purple palette", description: "The four colours from your reference: charcoal canvas, graphite cards, muted purple details, and pale lavender text and actions.", tokens: {
      bg: "#1e202c", surface: "#31323e", "surface-2": "#1e202c", "surface-hover": "#31323e", line: "#60519b", "field-line": "#bfc0d1", text: "#bfc0d1", muted: "#bfc0d1", accent: "#bfc0d1", "accent-hover": "#bfc0d1", "on-accent": "#1e202c", "choice-bg": "#31323e", "choice-fg": "#bfc0d1", "reference-purple": "#60519b"
    } },
    a: { title: "A · Current", description: "Existing violet-navy surfaces and full topic fills.", tokens: {
      bg: "#12142b", surface: "#1c1f45", "surface-2": "#171a3a", "surface-hover": "#262a5c", line: "#3a3f78", "field-line": "#7a80c4", accent: "#a78bfa"
    } },
    b: { title: "B · Clearer navy", description: "Keep the violet-navy identity; brighten cards and separate nested groups. Recommended.", tokens: {
      bg: "#101225", surface: "#252a48", "surface-2": "#1b2039", "surface-hover": "#303653", line: "#58618b", "field-line": "#8b93c5", accent: "#a78bfa", "choice-bg": "#4d302c", "choice-fg": "#ffcfb3"
    } },
    c: { title: "C · Quiet slate", description: "A calmer blue-slate canvas with less violet in the surfaces. Lilac still marks actions and citations.", tokens: {
      bg: "#111522", surface: "#232c3e", "surface-2": "#192234", "surface-hover": "#303c54", line: "#526583", "field-line": "#8c9ab8", accent: "#a78bfa", "choice-bg": "#4d302c", "choice-fg": "#ffcfb3"
    } },
    d: { title: "D · Charcoal & mint", description: "Neutral charcoal cards, crisp mint actions, and warm choice badges. Less purple; clean and cool.", tokens: {
      bg: "#121718", surface: "#252b2d", "surface-2": "#1b2223", "surface-hover": "#333d3e", line: "#596f69", "field-line": "#829d93", text: "#f1f5f4", muted: "#b7c4c0", accent: "#72e0bf", "accent-hover": "#a0ecd5", "on-accent": "#10221c", "choice-bg": "#4d302c", "choice-fg": "#ffcfb3"
    } },
    e: { title: "E · Deep forest", description: "Dark pine surfaces with soft sage actions. Calm, earthy, and distinct from the navy theme.", tokens: {
      bg: "#0d1915", surface: "#20362d", "surface-2": "#15271f", "surface-hover": "#2b493b", line: "#5b8070", "field-line": "#90b9a5", text: "#edf6ed", muted: "#b8cebe", accent: "#bce394", "accent-hover": "#d3edb7", "on-accent": "#14210f", "choice-bg": "#4d302c", "choice-fg": "#ffcfb3"
    } },
    g: { title: "G · Midnight & mint", description: "Batman-dark: near-black canvas, graphite cards, and crisp mint actions. Darker than charcoal without losing readable text or visible controls.", tokens: {
      bg: "#080a0b", surface: "#15191b", "surface-2": "#0e1214", "surface-hover": "#22292b", line: "#414d50", "field-line": "#718581", text: "#f1f5f4", muted: "#b7c4c0", accent: "#72e0bf", "accent-hover": "#a0ecd5", "on-accent": "#10221c", "choice-bg": "#35251f", "choice-fg": "#ffcfb3"
    } },
    f: { title: "F · Warm espresso", description: "Coffee-brown surfaces, cream text, and peach actions. Warm and comfortable for long reading.", tokens: {
      bg: "#1d1512", surface: "#382a24", "surface-2": "#2b201b", "surface-hover": "#49362c", line: "#8e6854", "field-line": "#c4987c", text: "#fff1e6", muted: "#d5bcaa", accent: "#ffba8e", "accent-hover": "#ffd1b3", "on-accent": "#29170d", "choice-bg": "#4c3428", "choice-fg": "#ffcfb3"
    } }
  };
  var requested = new URLSearchParams(window.location.search).get("variant");
  var current = Object.prototype.hasOwnProperty.call(directions, requested) ? requested : "k";
  var frame = document.getElementById("app-preview");
  var status = document.getElementById("preview-status");
  function showSwatches(direction) {
    var list = document.getElementById("swatches");
    list.replaceChildren();
    ["bg", "surface", "surface-2", "surface-hover", "line", "reference-purple", "accent"].forEach(function (key) {
      if (!direction.tokens[key]) return;
      var item = document.createElement("li");
      var swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.backgroundColor = direction.tokens[key];
      item.append(swatch, document.createTextNode(key + " " + direction.tokens[key]));
      list.appendChild(item);
    });
  }
  function applyDirection() {
    var direction = directions[current];
    document.getElementById("direction-title").textContent = direction.title;
    document.getElementById("direction-description").textContent = direction.description;
    document.querySelectorAll("[data-variant]").forEach(function (button) { button.setAttribute("aria-pressed", String(button.dataset.variant === current)); });
    showSwatches(direction);
    var doc = frame.contentDocument;
    if (!doc || !doc.getElementById("question")) return;
    doc.documentElement.dataset.theme = "dark";
    // Reset every preview override so switching palettes never leaks old colours.
    Object.values(directions).forEach(function (option) {
      Object.keys(option.tokens).forEach(function (key) { doc.documentElement.style.removeProperty("--" + key); });
    });
    Object.keys(direction.tokens).forEach(function (key) { doc.documentElement.style.setProperty("--" + key, direction.tokens[key]); });
    var overrides = doc.getElementById("colour-preview-overrides");
    if (!overrides) { overrides = doc.createElement("style"); overrides.id = "colour-preview-overrides"; doc.head.appendChild(overrides); }
    overrides.textContent = '#theme-toggle { display: none; }' + (current === "a" ? "" :
      '.topic-pill[aria-pressed="false"] { background: var(--surface-2); border-color: var(--line); }' +
      '.topic-pill[aria-pressed="false"]:hover { background: var(--surface-hover); }' +
      '.slot-tag { background: var(--choice-bg); color: var(--choice-fg); }') + (current === "h" || current === "i" ?
      '.slot-tag { border: 1px solid var(--reference-purple); }' +
      '.topic-pill { background: var(--surface-2); color: var(--text); }' +
      '.topic-pill[aria-pressed="true"] { background: var(--surface); color: var(--text); border-color: var(--reference-purple); box-shadow: inset 0 -2px var(--reference-purple); }' : "") + (current === "j" || current === "k" ?
      '.slot-tag { border: 1px solid var(--line); }' +
      '.topic-pill { background: var(--surface-2); color: var(--text); }' +
      '.topic-pill[aria-pressed="true"] { background: var(--surface-2); color: var(--accent); border-color: var(--accent); }' : "");
    status.textContent = direction.title + " · Interactive preview. Try the topic buttons, tools and elective groups.";
  }
  function showAnswer() {
    var doc = frame.contentDocument;
    if (!doc || !doc.getElementById("ask-form")) return;
    var box = doc.getElementById("answer-box");
    var observer = new MutationObserver(function () {
      var panel = doc.getElementById("ask-panel");
      if (panel && panel.dataset.state === "success") { box.scrollIntoView({ block: "start" }); observer.disconnect(); }
      else if (panel && panel.dataset.state === "error") { observer.disconnect(); }
    });
    observer.observe(doc.getElementById("ask-panel"), { attributes: true, attributeFilter: ["data-state"] });
    doc.getElementById("question").value = "ปี 3 เทอม 1 มีวิชาอะไรบ้าง และรวมกี่หน่วยกิต";
    doc.getElementById("ask-form").requestSubmit();
  }
  document.querySelectorAll("[data-variant]").forEach(function (button) { button.addEventListener("click", function () { current = button.dataset.variant; applyDirection(); }); });
  document.querySelectorAll("[data-width]").forEach(function (button) { button.addEventListener("click", function () {
    document.getElementById("preview-canvas").classList.toggle("mobile", button.dataset.width === "mobile");
    document.querySelectorAll("[data-width]").forEach(function (other) { other.setAttribute("aria-pressed", String(other === button)); });
  }); });
  document.getElementById("show-answer").addEventListener("click", showAnswer);
  frame.addEventListener("load", function () {
    applyDirection();
    var doc = frame.contentDocument;
    if (!doc || !doc.getElementById("program")) { status.textContent = "App unavailable. Start the curriculum server and reload this preview."; return; }
    // Keep preview interactions from saving theme, history or tool preferences.
    try {
      Object.defineProperty(frame.contentWindow, "localStorage", { value: {
        getItem: function (key) { return window.localStorage.getItem(key); },
        setItem: function () {}, removeItem: function () {}, clear: function () {}
      }, configurable: true });
    } catch (error) { status.textContent = "Preview loaded; preference isolation is unavailable in this browser."; }
    doc.getElementById("program").value = "it_coop";
    doc.getElementById("program").dispatchEvent(new frame.contentWindow.Event("change", { bubbles: true }));
    showAnswer();
  });
  applyDirection();
})();
