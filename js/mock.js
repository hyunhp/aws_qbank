// Mock exam mode for the AWS Question Bank.
// Draws a timed exam from one certification's pool, stratified by the official domain weights and
// preferring questions not yet seen in earlier mock exams. Answers are hidden until submission.
// State lives in localStorage so a reload resumes the running exam.

const KEY_ACTIVE = "aws_qbank_mock_active_v1";
const KEY_HISTORY = "aws_qbank_mock_history_v1";
const KEY_SEEN = "aws_qbank_mock_seen_v1";
const SHORT_N = 20;
const HISTORY_MAX = 200;

let qb = null;           // helpers passed from index.html
let root = null;
let onExit = null;
let specs = null;        // data/_exam_specs.json
let domainMap = null;    // data/_exam_domains.json
let state = null;        // running or finished exam
let view = "setup";
let setupExam = null;
let tick = null;
let reviewFilter = "incorrect";
let lastOpts = null;     // remembered so the error screen can retry a full open

// ---------- storage ----------
const load = (k, d) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* quota or private mode */ } };
const drop = (k) => { try { localStorage.removeItem(k); } catch (e) {} };
// Stored values can be missing, from an older version, or hand-edited; never trust their shape.
const isObj = (v) => v && typeof v === "object" && !Array.isArray(v);
function loadHistory() {
  const v = load(KEY_HISTORY, []);
  return Array.isArray(v) ? v.filter(h => isObj(h) && typeof h.exam === "string" && Number.isFinite(h.correct) && Number.isFinite(h.total) && h.total > 0) : [];
}
function loadSeen() {
  const v = load(KEY_SEEN, {});
  if (!isObj(v)) return {};
  const out = {};
  Object.entries(v).forEach(([k, arr]) => { if (Array.isArray(arr)) out[k] = arr.filter(x => typeof x === "string"); });
  return out;
}
export function resetAllMockData() { [KEY_ACTIVE, KEY_HISTORY, KEY_SEEN].forEach(drop); }

// ---------- helpers ----------
const esc = (s) => (s == null ? "" : String(s)).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const LETTERS = "ABCDEFGH";
function shuffle(a) { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }
function fmtTime(sec) {
  sec = Math.max(0, Math.round(sec));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return (h ? h + ":" + String(m).padStart(2, "0") : String(m)) + ":" + String(s).padStart(2, "0");
}
function examName(code) { const e = (qb.EXAMS || []).find(([c]) => c === code); return e ? e[1] : code; }

export function domainOf(q, exam, map) {
  if (!q.examCodes || q.examCodes[0] === exam) return q.domainCode;
  return (map && map[q.id] && map[q.id][exam]) || q.domainCode;
}

// Largest-remainder allocation of n questions over domains by weight, capped by supply.
export function allocate(n, domains, supply) {
  const total = domains.reduce((s, d) => s + d.weight, 0);
  const alloc = {}, rema = [];
  let used = 0;
  for (const d of domains) {
    const exact = (n * d.weight) / total;
    alloc[d.code] = Math.min(Math.floor(exact), supply[d.code] || 0);
    used += alloc[d.code];
    rema.push({ code: d.code, r: exact - Math.floor(exact), w: d.weight });
  }
  // hand out the remainder, largest fractional part first, then by weight, respecting supply
  let left = n - used;
  while (left > 0) {
    const cand = rema.filter(x => alloc[x.code] < (supply[x.code] || 0)).sort((a, b) => (b.r - a.r) || (b.w - a.w));
    if (!cand.length) break;
    for (const c of cand) { if (left <= 0) break; alloc[c.code]++; left--; c.r -= 1; }
  }
  return alloc;
}

// Draw n question ids: stratified by domain, unseen first, then final order shuffled.
export function draw(exam, n, docs, spec, map, seenIds) {
  const seen = new Set(seenIds || []);
  const groups = {};
  for (const d of spec.domains) groups[d.code] = { unseen: [], seen: [] };
  for (const q of docs) {
    const dom = domainOf(q, exam, map);
    const g = groups[dom];
    if (!g) continue;              // question tagged with a domain this exam doesn't have
    (seen.has(q.id) ? g.seen : g.unseen).push(q.id);
  }
  const supply = {};
  for (const k in groups) supply[k] = groups[k].unseen.length + groups[k].seen.length;
  const alloc = allocate(n, spec.domains, supply);
  let picked = [];
  for (const k in groups) {
    const pool = shuffle(groups[k].unseen).concat(shuffle(groups[k].seen));
    picked = picked.concat(pool.slice(0, alloc[k] || 0));
  }
  return shuffle(picked);
}

function timeFor(spec, n) { return Math.ceil((spec.minutes * n) / spec.questions) * 60; }

function verdictFor(level, pct) {
  const hi = (level === "professional" || level === "specialty") ? 85 : 80;
  const mid = hi - 10;
  if (pct >= hi) return { key: "ready", label: "Pass-ready", note: `${hi}%+ on first attempts is a comfortable margin.` };
  if (pct >= mid) return { key: "border", label: "Borderline", note: `Aim for ${hi}%+ before booking the exam.` };
  return { key: "work", label: "Needs work", note: `Focus on the weakest domains below, then retake.` };
}

// ---------- styles ----------
function injectStyles() {
  if (document.getElementById("mock-styles")) return;
  const s = document.createElement("style");
  s.id = "mock-styles";
  s.textContent = `
.mk{max-width:760px;margin:0 auto;padding:calc(env(safe-area-inset-top,0px) + 16px) 0 80px}
.mk h2{font-size:1.3rem;margin:4px 0 6px}
.mk .sub{color:var(--muted);font-size:.9rem;margin:0 0 14px}
.mk .panel{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow);margin-bottom:12px}
.mk label.row{display:flex;gap:10px;align-items:center;font-size:.92rem;margin:6px 0}
.mk select{font:inherit;font-size:.95rem;padding:7px 10px;border-radius:8px;border:1px solid var(--line);background:var(--surface);color:var(--ink);width:100%}
.mk .modes{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:10px 0}
.mk .mode{border:1px solid var(--line);border-radius:10px;padding:12px;cursor:pointer;background:var(--surface);text-align:left;font:inherit;color:var(--ink)}
.mk .mode.on{border-color:var(--accent);background:var(--accent-bg)}
.mk .mode b{display:block;font-size:.95rem}
.mk .mode span{font-size:.8rem;color:var(--muted)}
.mk .btn{font:inherit;font-size:.9rem;font-weight:600;padding:9px 16px;border-radius:9px;border:1px solid var(--accent);background:var(--accent);color:var(--surface);cursor:pointer}
.mk .btn.ghost{background:var(--surface);color:var(--accent-ink);border-color:var(--line)}
.mk .btn.warn{background:var(--bad);border-color:var(--bad)}
.mk .btn:disabled{opacity:.45;cursor:default}
.mk .btnrow{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.mk .meta{font-size:.82rem;color:var(--muted)}
.mk .linkbtn{background:none;border:none;color:var(--accent);font:inherit;font-size:.85rem;cursor:pointer;padding:0}
.mk table{width:100%;border-collapse:collapse;font-size:.84rem}
.mk td,.mk th{padding:6px 4px;border-bottom:1px solid var(--line);text-align:left}
.mk th{color:var(--muted);font-weight:500}
.mk .v-ready{color:var(--good)} .mk .v-border{color:var(--amber)} .mk .v-work{color:var(--bad)}
.mkbar{position:sticky;top:0;z-index:15;background:var(--bg);border-bottom:1px solid var(--line);padding:calc(env(safe-area-inset-top,0px) + 8px) 0 8px;margin-bottom:12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.mkbar .code{font-family:"IBM Plex Mono",monospace;font-weight:600;font-size:.82rem}
.mkbar .prog{font-size:.85rem;color:var(--muted)}
.mkbar .timer{font-family:"IBM Plex Mono",monospace;font-weight:600;font-size:.95rem;margin-left:auto;font-variant-numeric:tabular-nums}
.mkbar .timer.low{color:var(--bad)}
.mkbar .btn{padding:6px 12px;font-size:.8rem}
.mk .qnum{font-size:.8rem;color:var(--muted);margin-bottom:6px;display:flex;align-items:center;gap:8px}
.mk .flag{margin-left:auto;font:inherit;font-size:.8rem;border:1px solid var(--line);background:var(--surface);color:var(--muted);border-radius:7px;padding:4px 10px;cursor:pointer}
.mk .flag.on{border-color:var(--amber);color:var(--amber);background:var(--amber-bg)}
.mk .selnote{font-size:.8rem;color:var(--amber);margin:-4px 0 10px;font-weight:600}
.mk .nav{display:flex;justify-content:space-between;gap:8px;margin-top:12px}
.mk .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(44px,1fr));gap:6px;margin:10px 0}
.mk .cell{font:inherit;font-size:.82rem;font-family:"IBM Plex Mono",monospace;padding:8px 0;border-radius:7px;border:1px solid var(--line);background:var(--surface);color:var(--muted);cursor:pointer;position:relative}
.mk .cell.ans{background:var(--accent-bg);color:var(--accent-ink);border-color:var(--accent)}
.mk .cell.flg::after{content:"";position:absolute;top:3px;right:3px;width:7px;height:7px;border-radius:50%;background:var(--amber)}
.mk .cell.cur{outline:2px solid var(--ink);outline-offset:1px}
.mk .legend{display:flex;gap:14px;flex-wrap:wrap;font-size:.78rem;color:var(--muted)}
.mk .confirm{border:1px solid var(--bad-line);background:var(--bad-bg);border-radius:10px;padding:12px;margin-top:10px;font-size:.9rem}
.mk .score{font-size:2.4rem;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.1}
.mk .verdict{font-weight:700;font-size:1.05rem;margin:4px 0}
.mk .dom{margin:8px 0}
.mk .dom .top{display:flex;justify-content:space-between;font-size:.84rem;gap:8px}
.mk .dom .bar{height:7px;border-radius:4px;background:var(--surface-2);overflow:hidden;margin-top:4px}
.mk .dom .fill{height:100%;background:var(--accent)}
.mk .dom.weak .fill{background:var(--bad)}
.mk .tabs{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0 12px}
.mk .tab{font:inherit;font-size:.8rem;padding:5px 11px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--muted);cursor:pointer}
.mk .tab.on{border-color:var(--accent);color:var(--accent-ink);background:var(--accent-bg)}
.mk .rv{margin-bottom:12px}
.mk .rvhead{display:flex;align-items:center;gap:8px;font-size:.8rem;color:var(--muted);margin-bottom:8px}
.mk .yours{font-size:.75rem;font-weight:600;color:var(--muted);white-space:nowrap}
.mk .rvhead .ok{color:var(--good);font-weight:700} .mk .rvhead .no{color:var(--bad);font-weight:700}
@media (max-width:480px){.mk .modes{grid-template-columns:1fr}}
`;
  document.head.appendChild(s);
}

// ---------- data ----------
async function ensureData() {
  if (!specs) {
    const [s, m] = await Promise.all([
      fetch("./data/_exam_specs.json", { cache: "no-cache" }).then(r => r.json()),
      fetch("./data/_exam_domains.json", { cache: "no-cache" }).then(r => r.ok ? r.json() : {}).catch(() => ({})),
    ]);
    specs = s; domainMap = m;
  }
}
async function docsFor(exam) { return (await qb.loadExam(exam)) || []; }

// ---------- lifecycle ----------
export async function open(opts) {
  lastOpts = opts;
  qb = opts.qb; root = opts.root; onExit = opts.onExit;
  injectStyles();
  state = null; view = "setup";
  try {
    await ensureData();
    const active = await validActive(load(KEY_ACTIVE, null));
    setupExam = (opts.exam && specs[opts.exam]) ? opts.exam : (active && active.exam) || "SAA-C03";
    if (active) { state = active; view = "exam"; await startTicking(); }
  } catch (err) {
    if (!specs) { showError(new Error("Could not load exam settings. Check your connection and reload. (" + (err && err.message) + ")")); return; }
    drop(KEY_ACTIVE); state = null; view = "setup";
    setupExam = (opts.exam && specs[opts.exam]) ? opts.exam : "SAA-C03";
  }
  await render();
}

// A saved in-progress exam can go stale (question bank updated, storage edited, older app version).
// Keep whatever still matches the current pool; discard it only if nothing usable is left.
async function validActive(active) {
  if (!active || active.submitted || typeof active !== "object") return null;
  if (!specs[active.exam] || !Array.isArray(active.ids)) { drop(KEY_ACTIVE); return null; }
  const docs = await docsFor(active.exam);
  const byId = new Map(docs.map(q => [q.id, q]));
  const ids = active.ids.filter(id => byId.has(id));
  if (!ids.length) { drop(KEY_ACTIVE); return null; }
  if (ids.length !== active.ids.length) {
    const keep = new Set(ids);
    active.ids = ids;
    active.answers = Object.fromEntries(Object.entries(active.answers || {}).filter(([k]) => keep.has(k)));
    active.flags = (active.flags || []).filter(k => keep.has(k));
  }
  active.order = active.order || {};
  ids.forEach(id => {
    const keys = (byId.get(id).choices || []).map(c => c.key);
    const o = active.order[id];
    if (!Array.isArray(o) || o.length !== keys.length || !o.every(k => keys.includes(k))) active.order[id] = shuffle(keys);
  });
  active.answers = active.answers || {};
  active.flags = active.flags || [];
  active.cur = Math.min(Math.max(0, active.cur | 0), ids.length - 1);
  save(KEY_ACTIVE, active);
  return active;
}

function exit() {
  stopTicking();
  const ex = (state && state.exam) || setupExam;
  if (onExit) onExit(ex);
}

function persist() { if (state && !state.submitted) save(KEY_ACTIVE, state); }

async function startExam(mode, timed) {
  const spec = specs[setupExam];
  const docs = await docsFor(setupExam);
  const n = mode === "short" ? Math.min(SHORT_N, docs.length) : Math.min(spec.questions, docs.length);
  const seenAll = loadSeen();
  const ids = draw(setupExam, n, docs, spec, domainMap, seenAll[setupExam]);
  const byId = new Map(docs.map(q => [q.id, q]));
  const order = {};
  ids.forEach(id => { order[id] = shuffle((byId.get(id).choices || []).map(c => c.key)); });
  const dur = timeFor(spec, ids.length);
  state = {
    v: 1, exam: setupExam, mode, ids, order, answers: {}, flags: [], cur: 0,
    startedAt: Date.now(), duration: dur, timed: !!timed, deadline: timed ? Date.now() + dur * 1000 : null,
    submitted: false,
  };
  persist();
  view = "exam";
  await startTicking();
  render();
  window.scrollTo(0, 0);
}

async function startTicking() {
  stopTicking();
  if (!state || !state.timed || state.submitted) return;
  tick = setInterval(() => {
    const left = (state.deadline - Date.now()) / 1000;
    const el = root.querySelector(".mkbar .timer");
    if (el) { el.textContent = fmtTime(left); el.classList.toggle("low", left < 300); }
    if (left <= 0) submit(true);
  }, 1000);
  if (state.deadline - Date.now() <= 0) await submit(true);
}
function stopTicking() { if (tick) { clearInterval(tick); tick = null; } }

async function submit(auto) {
  if (!state || state.submitted) return;
  stopTicking();
  const docs = await docsFor(state.exam);
  const byId = new Map(docs.map(q => [q.id, q]));
  const spec = specs[state.exam];
  const dom = {};
  spec.domains.forEach(d => { dom[d.code] = [0, 0]; });
  let correct = 0;
  const results = {};
  for (const id of state.ids) {
    const q = byId.get(id);
    if (!q) continue;
    const want = new Set(q.correctKeys || []);
    const got = new Set(state.answers[id] || []);
    const ok = got.size === want.size && [...got].every(k => want.has(k));
    results[id] = ok;
    if (ok) correct++;
    const d = domainOf(q, state.exam, domainMap);
    if (dom[d]) { dom[d][1]++; if (ok) dom[d][0]++; }
  }
  const used = Math.min(state.duration, Math.round((Date.now() - state.startedAt) / 1000));
  state.submitted = true;
  state.auto = !!auto;
  state.results = results;
  state.summary = { correct, total: state.ids.length, dom, used };
  // history + seen
  const hist = loadHistory();
  hist.push({ exam: state.exam, mode: state.mode, at: Date.now(), correct, total: state.ids.length, dom, used, timed: state.timed, auto: state.auto });
  save(KEY_HISTORY, hist.slice(-HISTORY_MAX));
  const seen = loadSeen();
  seen[state.exam] = Array.from(new Set((seen[state.exam] || []).concat(state.ids)));
  save(KEY_SEEN, seen);
  drop(KEY_ACTIVE);
  view = "results";
  reviewFilter = correct < state.ids.length ? "incorrect" : "all";
  render();
  window.scrollTo(0, 0);
}

// ---------- rendering ----------
function render() {
  if (!root) return Promise.resolve();
  const fn = { setup: renderSetup, exam: renderExam, grid: renderGrid, results: renderResults, review: renderReview }[view];
  return Promise.resolve().then(() => fn && fn()).catch(showError);
}

// Shown instead of a blank screen when anything goes wrong; works without help from index.html.
function showError(err) {
  stopTicking();
  console.warn("Mock exam error", err);
  const msg = (err && (err.message || String(err))) || "unknown error";
  root.innerHTML = `<div class="mk"><button class="linkbtn" data-act="exit">← Question bank</button>
    <h2>Mock exam could not be displayed</h2>
    <div class="panel"><p>Saved mock exam data in this browser seems to be damaged or from an older version.</p>
    <p>Resetting clears this browser's mock exam progress, history, and seen-question list. Bookmarks are not affected.</p>
    <div class="btnrow"><button class="btn" data-act="resetall">Reset mock exam data</button></div>
    <div class="meta">Details: ${esc(msg)}</div></div></div>`;
  root.onclick = (e) => {
    const t = e.target.closest("[data-act]");
    if (!t) return;
    if (t.dataset.act === "exit") { state = null; view = "setup"; exit(); }
    else if (t.dataset.act === "resetall") { resetAllMockData(); state = null; view = "setup"; if (lastOpts) open(lastOpts); }
  };
}

async function renderSetup(extra) {
  const spec = specs[setupExam];
  const docs = await docsFor(setupExam);
  const seen = new Set(loadSeen()[setupExam] || []);
  const unseen = docs.filter(q => !seen.has(q.id)).length;
  const fullN = Math.min(spec.questions, docs.length);
  const shortN = Math.min(SHORT_N, docs.length);
  const hist = loadHistory().filter(h => h.exam === setupExam).slice(-10).reverse();
  const opts = (qb.EXAMS || []).filter(([c]) => specs[c]).map(([c, n]) => `<option value="${c}"${c === setupExam ? " selected" : ""}>${c} · ${esc(n)}</option>`).join("");
  const mode = (extra && extra.mode) || root.dataset.mode || "full";
  root.dataset.mode = mode;
  root.innerHTML = `<div class="mk">
    <button class="linkbtn" data-act="exit">← Question bank</button>
    <h2>Mock Exam</h2>
    <p class="sub">Timed, answers hidden until you submit. Questions follow the official domain weights, and ones you haven't seen in earlier mock exams come first.</p>
    <div class="panel">
      <select id="mkExam" aria-label="Certification">${opts}</select>
      <div class="modes">
        <button class="mode${mode === "full" ? " on" : ""}" data-mode="full" type="button"><b>Full exam</b><span>${fullN} questions · ${Math.round(timeFor(spec, fullN) / 60)} min</span></button>
        <button class="mode${mode === "short" ? " on" : ""}" data-mode="short" type="button"><b>Short practice</b><span>${shortN} questions · ${Math.round(timeFor(spec, shortN) / 60)} min</span></button>
      </div>
      <label class="row"><input type="checkbox" id="mkTimed" checked> Timer (auto-submits at 0:00)</label>
      <div class="meta">Pool: ${docs.length} questions · ${unseen} not yet seen in mock exams · official pass mark ${spec.passingScore}/1000</div>
      ${unseen < (mode === "short" ? shortN : fullN) ? `<div class="meta" style="color:var(--amber)">Fewer unseen questions than needed, so some repeats will be included.</div>` : ""}
      <div class="btnrow"><button class="btn" data-act="start">Start exam</button>
      ${seen.size ? `<button class="linkbtn" data-act="resetseen">Reset seen questions for ${setupExam}</button>` : ""}</div>
    </div>
    <div class="panel"><b>Recent attempts · ${setupExam}</b>
      ${hist.length ? `<table><tr><th>Date</th><th>Mode</th><th>Score</th><th>Result</th></tr>${hist.map(h => {
        const pct = Math.round((h.correct / h.total) * 100); const v = verdictFor(spec.level, pct);
        return `<tr><td>${new Date(h.at).toLocaleDateString()}</td><td>${h.mode === "short" ? "Short" : "Full"}</td><td>${h.correct}/${h.total} (${pct}%)</td><td class="v-${v.key}">${v.label}</td></tr>`;
      }).join("")}</table>` : `<div class="meta">No attempts yet.</div>`}
    </div></div>`;
  root.onclick = async (e) => {
    const t = e.target.closest("[data-act],[data-mode]");
    if (!t) return;
    if (t.dataset.mode) { renderSetup({ mode: t.dataset.mode }); return; }
    const act = t.dataset.act;
    if (act === "exit") exit();
    else if (act === "start") startExam(root.dataset.mode, root.querySelector("#mkTimed").checked);
    else if (act === "resetseen") { const s = loadSeen(); delete s[setupExam]; save(KEY_SEEN, s); renderSetup(); }
  };
  root.querySelector("#mkExam").onchange = (e) => { setupExam = e.target.value; renderSetup(); };
}

async function renderExam() {
  const docs = await docsFor(state.exam);
  const byId = new Map(docs.map(q => [q.id, q]));
  const id = state.ids[state.cur];
  const q = byId.get(id);
  if (!q) {  // should not happen after validActive(), but never leave a blank screen
    state.ids = state.ids.filter(x => byId.has(x));
    if (!state.ids.length) { drop(KEY_ACTIVE); state = null; view = "setup"; return render(); }
    state.cur = Math.min(state.cur, state.ids.length - 1); persist(); return renderExam();
  }
  const n = state.ids.length;
  const answered = Object.keys(state.answers).filter(k => (state.answers[k] || []).length).length;
  const multi = (q.correctKeys || []).length > 1;
  const picked = new Set(state.answers[id] || []);
  const flagged = state.flags.includes(id);
  const choiceByKey = new Map((q.choices || []).map(c => [c.key, c]));
  const left = state.timed ? (state.deadline - Date.now()) / 1000 : null;
  root.innerHTML = `<div class="mk">
    <div class="mkbar"><span class="code">${state.exam}</span><span class="prog">${answered}/${n} answered</span>
      <span class="timer${left !== null && left < 300 ? " low" : ""}">${left !== null ? fmtTime(left) : "untimed"}</span>
      <button class="btn ghost" data-act="grid">Review</button><button class="btn" data-act="grid">Finish</button></div>
    <div class="qcard">
      <div class="qnum">Question ${state.cur + 1} of ${n}${multi ? ' · <span class="badge multi">Multiple Answers</span>' : ""}
        <button class="flag${flagged ? " on" : ""}" data-act="flag" type="button">${flagged ? "⚑ Flagged" : "⚐ Flag for review"}</button></div>
      <div class="stem">${esc(q.stem)}</div>
      ${multi ? `<div class="selnote">Select ${q.correctKeys.length}.</div>` : ""}
      <div class="choices">${state.order[id].map((k, i) => {
        const c = choiceByKey.get(k);
        return `<div class="choice${picked.has(k) ? " picked" : ""}" role="button" tabindex="0" data-key="${esc(k)}"><span class="bubble"></span><span><span class="key">${LETTERS[i]}.</span> ${esc(c ? c.text : "")}</span></div>`;
      }).join("")}</div>
    </div>
    <div class="nav"><button class="btn ghost" data-act="prev"${state.cur === 0 ? " disabled" : ""}>← Previous</button>
      ${state.cur < n - 1 ? `<button class="btn" data-act="next">Next →</button>` : `<button class="btn" data-act="grid">Review &amp; submit</button>`}</div>
  </div>`;
  root.onclick = (e) => {
    const ch = e.target.closest(".choice");
    if (ch) {
      const k = ch.dataset.key;
      let cur = new Set(state.answers[id] || []);
      if (multi) { cur.has(k) ? cur.delete(k) : cur.add(k); }
      else cur = new Set([k]);
      state.answers[id] = [...cur];
      persist(); renderExam(); return;
    }
    const t = e.target.closest("[data-act]");
    if (!t || t.disabled) return;
    const act = t.dataset.act;
    if (act === "flag") { state.flags = flagged ? state.flags.filter(x => x !== id) : state.flags.concat(id); persist(); renderExam(); }
    else if (act === "prev") { state.cur = Math.max(0, state.cur - 1); persist(); renderExam(); window.scrollTo(0, 0); }
    else if (act === "next") { state.cur = Math.min(n - 1, state.cur + 1); persist(); renderExam(); window.scrollTo(0, 0); }
    else if (act === "grid") { view = "grid"; render(); window.scrollTo(0, 0); }
  };
  root.onkeydown = (e) => { if ((e.key === "Enter" || e.key === " ") && e.target.closest(".choice")) { e.preventDefault(); e.target.click(); } };
}

function renderGrid(confirming) {
  const n = state.ids.length;
  const unanswered = state.ids.filter(id => !(state.answers[id] || []).length).length;
  const left = state.timed ? (state.deadline - Date.now()) / 1000 : null;
  root.innerHTML = `<div class="mk">
    <div class="mkbar"><span class="code">${state.exam}</span><span class="prog">${n - unanswered}/${n} answered</span>
      <span class="timer${left !== null && left < 300 ? " low" : ""}">${left !== null ? fmtTime(left) : "untimed"}</span></div>
    <div class="panel"><b>Review</b>
      <div class="legend"><span>■ answered</span><span>□ unanswered</span><span style="color:var(--amber)">● flagged</span></div>
      <div class="grid">${state.ids.map((id, i) => `<button class="cell${(state.answers[id] || []).length ? " ans" : ""}${state.flags.includes(id) ? " flg" : ""}${i === state.cur ? " cur" : ""}" data-go="${i}" type="button">${i + 1}</button>`).join("")}</div>
      <div class="btnrow"><button class="btn ghost" data-act="back">Return to question ${state.cur + 1}</button><button class="btn" data-act="ask">Submit exam</button></div>
      ${confirming ? `<div class="confirm">${unanswered ? `<b>${unanswered} unanswered</b> question${unanswered > 1 ? "s" : ""} will be marked wrong. ` : ""}Submit now? You can't change answers afterwards.
        <div class="btnrow"><button class="btn warn" data-act="submit">Yes, submit</button><button class="btn ghost" data-act="back">Keep going</button></div></div>` : ""}
    </div></div>`;
  root.onclick = (e) => {
    const g = e.target.closest("[data-go]");
    if (g) { state.cur = +g.dataset.go; persist(); view = "exam"; render(); window.scrollTo(0, 0); return; }
    const t = e.target.closest("[data-act]");
    if (!t) return;
    if (t.dataset.act === "back") { view = "exam"; render(); }
    else if (t.dataset.act === "ask") renderGrid(true);
    else if (t.dataset.act === "submit") submit(false);
  };
}

function renderResults() {
  const spec = specs[state.exam];
  const { correct, total, dom, used } = state.summary;
  const pct = total ? Math.round((correct / total) * 100) : 0;
  const v = verdictFor(spec.level, pct);
  const wrong = total - correct;
  const nflag = state.flags.length;
  root.innerHTML = `<div class="mk">
    <button class="linkbtn" data-act="exit">← Question bank</button>
    <h2>${state.exam} · ${state.mode === "short" ? "Short practice" : "Full mock exam"}</h2>
    <p class="sub">${esc(examName(state.exam))}${state.auto ? " · submitted automatically when time ran out" : ""}</p>
    <div class="panel">
      <div class="score">${pct}%</div>
      <div class="verdict v-${v.key}">${v.label}</div>
      <div class="meta">${correct} of ${total} correct · time used ${fmtTime(used)}${state.timed ? " of " + fmtTime(state.duration) : ""} · ${esc(v.note)}</div>
      <div class="meta">Percent correct is not the AWS scaled score; the official pass mark is ${spec.passingScore}/1000.</div>
    </div>
    <div class="panel"><b>By domain</b>
      ${spec.domains.map(d => {
        const [c, t] = dom[d.code] || [0, 0]; const p = t ? Math.round((c / t) * 100) : null;
        return `<div class="dom${p !== null && p < 70 ? " weak" : ""}"><div class="top"><span>${d.code} ${esc(d.name)}</span><span>${t ? `${c}/${t} · ${p}%` : "—"}</span></div><div class="bar"><div class="fill" style="width:${p || 0}%"></div></div></div>`;
      }).join("")}
    </div>
    <div class="btnrow">
      <button class="btn" data-review="incorrect"${wrong ? "" : " disabled"}>Review incorrect (${wrong})</button>
      <button class="btn ghost" data-review="flagged"${nflag ? "" : " disabled"}>Review flagged (${nflag})</button>
      <button class="btn ghost" data-review="all">Review all</button>
    </div>
    <div class="btnrow"><button class="btn ghost" data-act="new">New mock exam</button><button class="btn ghost" data-act="exit">Back to question bank</button></div>
  </div>`;
  root.onclick = (e) => {
    const r = e.target.closest("[data-review]");
    if (r && !r.disabled) { reviewFilter = r.dataset.review; view = "review"; render(); window.scrollTo(0, 0); return; }
    const t = e.target.closest("[data-act]");
    if (!t) return;
    if (t.dataset.act === "exit") exit();
    else if (t.dataset.act === "new") { setupExam = state.exam; state = null; view = "setup"; render(); window.scrollTo(0, 0); }
  };
}

async function renderReview() {
  const docs = await docsFor(state.exam);
  const byId = new Map(docs.map(q => [q.id, q]));
  const list = state.ids.map((id, i) => ({ id, i })).filter(({ id }) =>
    reviewFilter === "all" ? true : reviewFilter === "flagged" ? state.flags.includes(id) : !state.results[id]);
  const counts = { incorrect: state.ids.filter(id => !state.results[id]).length, flagged: state.flags.length, all: state.ids.length };
  root.innerHTML = `<div class="mk">
    <button class="linkbtn" data-act="results">← Results</button>
    <h2>Review · ${state.exam}</h2>
    <div class="tabs">${["incorrect", "flagged", "all"].map(f => `<button class="tab${f === reviewFilter ? " on" : ""}" data-filter="${f}">${f[0].toUpperCase() + f.slice(1)} (${counts[f]})</button>`).join("")}</div>
    ${list.length ? "" : `<div class="empty">Nothing to show here.</div>`}
    ${list.map(({ id, i }) => {
      const q = byId.get(id); if (!q) return "";
      const want = new Set(q.correctKeys || []);
      const got = new Set(state.answers[id] || []);
      const ok = state.results[id];
      const choiceByKey = new Map((q.choices || []).map(c => [c.key, c]));
      const letters = state.order[id].map((k, j) => want.has(k) ? LETTERS[j] : null).filter(Boolean).join(", ");
      const bm = qb.isBookmarked(id);
      return `<div class="qcard rv" data-qid="${esc(id)}">
        <div class="rvhead"><span>#${i + 1}</span><span class="mono">${esc(id)}</span><span class="${ok ? "ok" : "no"}">${ok ? "✓ Correct" : got.size ? "✗ Incorrect" : "✗ Unanswered"}</span>${state.flags.includes(id) ? "<span>⚑ flagged</span>" : ""}
          <button class="bookmark-btn${bm ? " active" : ""}" data-bm="${esc(id)}" type="button" aria-label="Bookmark this question">${bm ? "★" : "☆"}</button></div>
        <div class="stem">${esc(q.stem)}</div>
        <div class="choices">${state.order[id].map((k, j) => {
          const c = choiceByKey.get(k);
          const cls = want.has(k) ? "correct" : got.has(k) ? "incorrect" : "dim";
          return `<div class="choice locked ${cls}${got.has(k) ? " picked" : ""}"><span class="bubble"></span><span><span class="key">${LETTERS[j]}.</span> ${esc(c ? c.text : "")}${got.has(k) ? ' <span class="yours">· your answer</span>' : ""}</span></div>`;
        }).join("")}</div>
        <div class="explain show ${ok ? "" : "wrong"}" id="mk-explain-${esc(id)}"><div class="ans-line">Answer: ${letters}</div><div class="exp-body">${esc(q.explanation)}</div></div>
      </div>`;
    }).join("")}
    <div class="btnrow"><button class="btn ghost" data-act="results">Back to results</button></div>
  </div>`;
  list.forEach(({ id }) => { const el = document.getElementById(`mk-explain-${id}`); if (el && qb.attachDiagram) qb.attachDiagram(id, el); });
  root.onclick = (e) => {
    const f = e.target.closest("[data-filter]");
    if (f) { reviewFilter = f.dataset.filter; renderReview(); return; }
    const b = e.target.closest("[data-bm]");
    if (b) { const on = qb.toggleBookmark(b.dataset.bm); b.classList.toggle("active", on); b.textContent = on ? "★" : "☆"; return; }
    const t = e.target.closest("[data-act]");
    if (t && t.dataset.act === "results") { view = "results"; render(); window.scrollTo(0, 0); }
  };
}
