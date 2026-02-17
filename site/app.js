// VedaDiff — app.js
"use strict";

// ---------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------
const cache = {};

async function loadJSON(path) {
  if (cache[path]) return cache[path];
  const resp = await fetch(path);
  const data = await resp.json();
  cache[path] = data;
  return data;
}

async function loadSource(id) {
  return loadJSON(`data/processed/${id}.json`);
}

async function loadAlignment(id) {
  return loadJSON(`data/alignments/${id}.json`);
}

// ---------------------------------------------------------------
// Dual-script view
// ---------------------------------------------------------------
function renderDualScript(source) {
  const devaCont = document.getElementById("deva-content");
  const iastCont = document.getElementById("iast-content");
  devaCont.innerHTML = "";
  iastCont.innerHTML = "";

  for (const verse of source.verses) {
    devaCont.appendChild(makeVerseBlock(verse, "devanagari"));
    iastCont.appendChild(makeVerseBlock(verse, "iast"));
  }
}

function makeVerseBlock(verse, script) {
  const block = document.createElement("div");
  block.className = "verse-block";

  const label = document.createElement("div");
  label.className = "verse-label";
  label.textContent = verse.number;
  block.appendChild(label);

  const text = document.createElement("div");
  text.className = "verse-text";
  for (let i = 0; i < verse.tokens.length; i++) {
    if (i > 0) text.appendChild(document.createTextNode(" "));
    const span = document.createElement("span");
    span.className = "token";
    span.dataset.v = verse.number;
    span.dataset.t = verse.tokens[i].idx;
    span.textContent = verse.tokens[i][script];
    text.appendChild(span);
  }
  block.appendChild(text);
  return block;
}

// ---------------------------------------------------------------
// Hover linking
// ---------------------------------------------------------------
function setupHoverLinking() {
  document.addEventListener("mouseenter", (e) => {
    const t = e.target;
    if (!t.classList || !t.classList.contains("token")) return;
    const v = t.dataset.v;
    const idx = t.dataset.t;
    document.querySelectorAll(`.token[data-v="${v}"][data-t="${idx}"]`)
      .forEach(el => el.classList.add("highlight"));
  }, true);

  document.addEventListener("mouseleave", (e) => {
    const t = e.target;
    if (!t.classList || !t.classList.contains("token")) return;
    const v = t.dataset.v;
    const idx = t.dataset.t;
    document.querySelectorAll(`.token[data-v="${v}"][data-t="${idx}"]`)
      .forEach(el => el.classList.remove("highlight"));
  }, true);
}

// ---------------------------------------------------------------
// Synchronized scrolling
// ---------------------------------------------------------------
function setupSyncScroll(pane1, pane2) {
  let syncing = false;
  function handler(source, target) {
    if (syncing) return;
    syncing = true;
    const ratio = source.scrollTop / (source.scrollHeight - source.clientHeight || 1);
    target.scrollTop = ratio * (target.scrollHeight - target.clientHeight || 1);
    syncing = false;
  }
  pane1.addEventListener("scroll", () => handler(pane1, pane2));
  pane2.addEventListener("scroll", () => handler(pane2, pane1));
}

// ---------------------------------------------------------------
// LCS diff algorithm
// ---------------------------------------------------------------
function lcs(a, b) {
  const m = a.length, n = b.length;
  // DP table
  const dp = Array.from({ length: m + 1 }, () => new Uint16Array(n + 1));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (a[i - 1] === b[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack to get edit script
  const ops = [];
  let i = m, j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      ops.push({ type: "equal", left: i - 1, right: j - 1 });
      i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      ops.push({ type: "insert", right: j - 1 });
      j--;
    } else {
      ops.push({ type: "delete", left: i - 1 });
      i--;
    }
  }
  ops.reverse();
  return ops;
}

function charSimilarity(a, b) {
  // Ratio of common characters
  const setA = new Set(a);
  const setB = new Set(b);
  let common = 0;
  for (const ch of setA) if (setB.has(ch)) common++;
  return common / Math.max(setA.size, setB.size, 1);
}

function computeDiff(leftTokens, rightTokens) {
  const leftStrs = leftTokens.map(t => t.iast);
  const rightStrs = rightTokens.map(t => t.iast);
  const raw = lcs(leftStrs, rightStrs);

  // Post-process: consecutive delete+insert → modify if >50% similar
  const result = [];
  let i = 0;
  while (i < raw.length) {
    if (i + 1 < raw.length &&
        raw[i].type === "delete" && raw[i + 1].type === "insert" &&
        charSimilarity(leftStrs[raw[i].left], rightStrs[raw[i + 1].right]) > 0.5) {
      result.push({
        type: "modify",
        left: raw[i].left,
        right: raw[i + 1].right
      });
      i += 2;
    } else {
      result.push(raw[i]);
      i++;
    }
  }
  return result;
}

// ---------------------------------------------------------------
// Diff view rendering
// ---------------------------------------------------------------
let diffScript = "iast"; // or "devanagari"

function renderDiffView(alignment, leftSource, rightSource) {
  const leftCont = document.getElementById("diff-left-content");
  const rightCont = document.getElementById("diff-right-content");
  leftCont.innerHTML = "";
  rightCont.innerHTML = "";

  document.getElementById("diff-left-label").textContent = alignment.left.label;
  document.getElementById("diff-right-label").textContent = alignment.right.label;

  const leftVerseMap = {};
  for (const v of leftSource.verses) leftVerseMap[v.number] = v;
  const rightVerseMap = {};
  for (const v of rightSource.verses) rightVerseMap[v.number] = v;

  for (const pair of alignment.pairs) {
    const leftVerse = pair.left ? leftVerseMap[pair.left] : null;
    const rightVerse = pair.right ? rightVerseMap[pair.right] : null;

    const leftBlock = document.createElement("div");
    leftBlock.className = "diff-pair";
    const rightBlock = document.createElement("div");
    rightBlock.className = "diff-pair";

    // Labels
    const leftLabel = document.createElement("div");
    leftLabel.className = "verse-label";
    leftLabel.textContent = pair.left || "";
    if (pair.note) {
      const note = document.createElement("span");
      note.className = "note";
      note.textContent = pair.note;
      leftLabel.appendChild(note);
    }
    leftBlock.appendChild(leftLabel);

    const rightLabel = document.createElement("div");
    rightLabel.className = "verse-label";
    rightLabel.textContent = pair.right || "";
    rightBlock.appendChild(rightLabel);

    if (!leftVerse && rightVerse) {
      // Left absent
      const ph = document.createElement("div");
      ph.className = "placeholder";
      ph.textContent = `Not present in ${alignment.left.label}`;
      leftBlock.appendChild(ph);
      rightBlock.appendChild(makePlainVerseText(rightVerse, diffScript));
    } else if (leftVerse && !rightVerse) {
      // Right absent
      leftBlock.appendChild(makePlainVerseText(leftVerse, diffScript));
      const ph = document.createElement("div");
      ph.className = "placeholder";
      ph.textContent = `Not present in ${alignment.right.label}`;
      rightBlock.appendChild(ph);
    } else if (leftVerse && rightVerse) {
      // Both present — diff
      const ops = computeDiff(leftVerse.tokens, rightVerse.tokens);
      const leftText = document.createElement("div");
      leftText.className = "verse-text";
      const rightText = document.createElement("div");
      rightText.className = "verse-text";

      let firstLeft = true, firstRight = true;
      for (const op of ops) {
        if (op.type === "equal") {
          if (!firstLeft) leftText.appendChild(document.createTextNode(" "));
          if (!firstRight) rightText.appendChild(document.createTextNode(" "));
          leftText.appendChild(makeDiffToken(leftVerse.tokens[op.left], "diff-equal", diffScript));
          rightText.appendChild(makeDiffToken(rightVerse.tokens[op.right], "diff-equal", diffScript));
          firstLeft = false;
          firstRight = false;
        } else if (op.type === "delete") {
          if (!firstLeft) leftText.appendChild(document.createTextNode(" "));
          leftText.appendChild(makeDiffToken(leftVerse.tokens[op.left], "diff-delete", diffScript));
          firstLeft = false;
        } else if (op.type === "insert") {
          if (!firstRight) rightText.appendChild(document.createTextNode(" "));
          rightText.appendChild(makeDiffToken(rightVerse.tokens[op.right], "diff-insert", diffScript));
          firstRight = false;
        } else if (op.type === "modify") {
          if (!firstLeft) leftText.appendChild(document.createTextNode(" "));
          if (!firstRight) rightText.appendChild(document.createTextNode(" "));
          leftText.appendChild(makeDiffToken(leftVerse.tokens[op.left], "diff-modify", diffScript));
          rightText.appendChild(makeDiffToken(rightVerse.tokens[op.right], "diff-modify", diffScript));
          firstLeft = false;
          firstRight = false;
        }
      }

      leftBlock.appendChild(leftText);
      rightBlock.appendChild(rightText);
    }

    leftCont.appendChild(leftBlock);
    rightCont.appendChild(rightBlock);
  }
}

function makeDiffToken(token, cls, script) {
  const span = document.createElement("span");
  span.className = `token ${cls}`;
  span.textContent = token[script];
  return span;
}

function makePlainVerseText(verse, script) {
  const div = document.createElement("div");
  div.className = "verse-text";
  for (let i = 0; i < verse.tokens.length; i++) {
    if (i > 0) div.appendChild(document.createTextNode(" "));
    const span = document.createElement("span");
    span.className = "token";
    span.textContent = verse.tokens[i][script];
    div.appendChild(span);
  }
  return div;
}

// ---------------------------------------------------------------
// View switching and initialization
// ---------------------------------------------------------------
let currentAlignment = null;
let currentLeftSource = null;
let currentRightSource = null;

function switchView(viewName) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  document.getElementById(`${viewName}-view`).classList.add("active");
  document.querySelector(`.nav-btn[data-view="${viewName}"]`).classList.add("active");
}

async function loadDualScript(sourceId) {
  const source = await loadSource(sourceId);
  renderDualScript(source);
}

async function loadDiff(alignmentId) {
  const alignment = await loadAlignment(alignmentId);
  currentAlignment = alignment;
  const [left, right] = await Promise.all([
    loadSource(alignment.left.source),
    loadSource(alignment.right.source)
  ]);
  currentLeftSource = left;
  currentRightSource = right;
  renderDiffView(alignment, left, right);
}

document.addEventListener("DOMContentLoaded", () => {
  // Hover linking
  setupHoverLinking();

  // Sync scroll for dual-script panes
  setupSyncScroll(
    document.getElementById("deva-content"),
    document.getElementById("iast-content")
  );
  // Sync scroll for diff panes
  setupSyncScroll(
    document.getElementById("diff-left-content"),
    document.getElementById("diff-right-content")
  );

  // Nav buttons
  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const view = btn.dataset.view;
      switchView(view);
      if (view === "diff" && !currentAlignment) {
        loadDiff("purusha-suktam");
      }
    });
  });

  // Text selector
  document.getElementById("text-select").addEventListener("change", (e) => {
    loadDualScript(e.target.value);
  });

  // Diff selector
  document.getElementById("diff-select").addEventListener("change", (e) => {
    loadDiff(e.target.value);
  });

  // Dual/single layout toggle
  document.getElementById("dual-layout-toggle").addEventListener("click", () => {
    const btn = document.getElementById("dual-layout-toggle");
    const panes = document.querySelector("#dual-view .dual-panes");
    const devaPane = document.getElementById("deva-pane");
    const isSingle = panes.classList.toggle("single-pane");
    devaPane.classList.toggle("hidden", isSingle);
    btn.textContent = isSingle ? "Dual Script" : "IAST Only";
  });

  // Script toggle in diff view
  document.getElementById("script-toggle").addEventListener("click", () => {
    const btn = document.getElementById("script-toggle");
    if (diffScript === "iast") {
      diffScript = "devanagari";
      btn.textContent = "Show IAST";
    } else {
      diffScript = "iast";
      btn.textContent = "Show Devanāgarī";
    }
    if (currentAlignment && currentLeftSource && currentRightSource) {
      renderDiffView(currentAlignment, currentLeftSource, currentRightSource);
    }
  });

  // Load default
  loadDualScript("rv10-090");
});
