// Architecture diagram renderer for the AWS Question Bank.
// Renders a grid-based spec (diagrams/<QID>.json) into an inline SVG inside the explanation box.
// Spec format is documented in tools/diagrams/README.md.

const NS = "http://www.w3.org/2000/svg";
const ICON = 48;          // icon size
const NODE_H = 100;       // vertical room for icon + up to 2 label lines
const LINE = 16;          // label line height
const MARGIN = 12;        // canvas margin
const HEAD = 24;          // room for a group's title bar, per nesting level
const SIDE = 12;          // horizontal inset per nesting level
const FOOT = 10;          // bottom inset per nesting level
const ROW_GAP = 18;       // extra space between rows (edge labels live here)
const EDGE = "#545B64";
const INK = "#16191F";
const FONT = "'IBM Plex Sans', 'Helvetica Neue', Helvetica, Arial, sans-serif";

const GROUP_STYLE = {
  "aws-cloud":      { stroke: "#232F3E", dash: null,  fill: "none",    text: "#232F3E" },
  "region":         { stroke: "#00A4A6", dash: "6 4", fill: "none",    text: "#007A7C" },
  "az":             { stroke: "#147EBA", dash: "6 4", fill: "none",    text: "#147EBA" },
  "vpc":            { stroke: "#8C4FFF", dash: null,  fill: "none",    text: "#7A3EE8" },
  "public-subnet":  { stroke: "#7AA116", dash: null,  fill: "#F2F6E8", text: "#4E6A0B" },
  "private-subnet": { stroke: "#00A4A6", dash: null,  fill: "#E6F6F7", text: "#007A7C" },
  "security-group": { stroke: "#DD344C", dash: null,  fill: "none",    text: "#C0213A" },
  "onprem":         { stroke: "#7D8998", dash: null,  fill: "#F5F6F7", text: "#414D5C" },
  "edge":           { stroke: "#8C4FFF", dash: "2 3", fill: "#F7F2FF", text: "#7A3EE8" },
  "account":        { stroke: "#E7157B", dash: null,  fill: "none",    text: "#B0105E" },
  "generic":        { stroke: "#7D8998", dash: "6 4", fill: "none",    text: "#414D5C" },
};

let uid = 0;
let spritePromise = null;
let stylesInjected = false;

function el(name, attrs, parent) {
  const n = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs || {})) if (v !== null && v !== undefined) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
}

function injectStyles() {
  if (stylesInjected) return;
  stylesInjected = true;
  const css = `
.qb-diagram{margin:12px 0 2px;background:#fff;border:1px solid #D5DBDB;border-radius:8px;padding:10px 8px 8px;cursor:zoom-in}
.qb-diagram svg{display:block;width:100%;height:auto;margin:0 auto}
.qb-diagram figcaption{font-size:.78rem;line-height:1.4;color:#545B64;text-align:center;margin-top:6px}
.qb-zoom{position:fixed;inset:0;z-index:1000;background:rgba(10,14,20,.9);overflow:auto;
  padding:calc(env(safe-area-inset-top,0px) + 52px) 12px calc(env(safe-area-inset-bottom,0px) + 16px)}
.qb-zoom-inner{background:#fff;border-radius:8px;padding:10px;margin:0 auto;cursor:zoom-in}
.qb-zoom.big .qb-zoom-inner{cursor:zoom-out}
.qb-zoom-inner svg{display:block;width:100%;height:auto}
.qb-zoom-bar{position:fixed;left:0;right:0;top:env(safe-area-inset-top,0px);display:flex;justify-content:space-between;align-items:center;
  padding:10px 12px;color:#fff;font-size:.8rem;background:rgba(10,14,20,.9)}
.qb-zoom-close{font:inherit;font-size:1rem;color:#fff;background:transparent;border:1px solid rgba(255,255,255,.4);border-radius:6px;padding:4px 12px;cursor:pointer}
@media (max-width:480px){.qb-diagram{margin-inline:-8px;padding:8px 4px 6px}}`;
  const s = document.createElement("style");
  s.textContent = css;
  document.head.appendChild(s);
}

export function loadSprite(url) {
  if (!spritePromise) {
    spritePromise = fetch(url)
      .then(r => { if (!r.ok) throw new Error("sprite " + r.status); return r.text(); })
      .then(txt => {
        const holder = document.createElement("div");
        holder.setAttribute("aria-hidden", "true");
        holder.style.cssText = "position:absolute;width:0;height:0;overflow:hidden";
        holder.innerHTML = txt;
        document.body.appendChild(holder);
      })
      .catch(err => { spritePromise = null; throw err; });
  }
  return spritePromise;
}

// ---------- layout ----------

function computeLayout(spec) {
  const cols = spec.cols || 3;
  const W = spec.width || 440;
  const padRight = spec.padRight || 0;
  const colW = (W - 2 * MARGIN - padRight) / cols;
  const groups = spec.groups || [];
  const nodes = spec.nodes || [];

  // nesting depth: number of earlier groups that fully contain this one
  const contains = (a, b) => a.rows[0] <= b.rows[0] && a.rows[1] >= b.rows[1] && a.cols[0] <= b.cols[0] && a.cols[1] >= b.cols[1];
  groups.forEach((g, i) => { g._depth = groups.slice(0, i).filter(o => contains(o, g)).length; });

  const nRows = Math.max(0, ...nodes.map(n => Math.ceil(n.row)), ...groups.map(g => g.rows[1])) + 1;
  const topPad = Array(nRows).fill(0), botPad = Array(nRows).fill(0);
  for (const g of groups) {
    topPad[g.rows[0]] = Math.max(topPad[g.rows[0]], HEAD * (g._depth + 1));
    botPad[g.rows[1]] = Math.max(botPad[g.rows[1]], FOOT * (g._depth + 1));
  }
  const rowTop = [MARGIN];
  for (let r = 0; r < nRows; r++) rowTop.push(rowTop[r] + topPad[r] + NODE_H + botPad[r] + (r < nRows - 1 ? ROW_GAP : 0));
  const H = rowTop[nRows] + MARGIN;

  const rowYi = r => rowTop[r] + topPad[r] + 8 + ICON / 2;
  const rowY = r => {
    if (r <= 0) return rowYi(0) + r * (NODE_H + ROW_GAP);
    if (r >= nRows - 1) return rowYi(nRows - 1) + (r - (nRows - 1)) * (NODE_H + ROW_GAP);
    const f = Math.floor(r), t = r - f;
    return rowYi(f) * (1 - t) + rowYi(f + 1) * t;
  };
  // fractional rows between two node rows land in the visual gap, not on icon centres
  const gapY = r => {
    const f = Math.floor(r), t = r - f;
    if (t === 0 || f + 1 >= nRows) return rowY(r);
    const a = rowYi(f) + ICON / 2 + 6 + LINE * 2;    // below labels of row f
    const b = rowTop[f + 1] + topPad[f + 1];          // above row f+1 (after group headers)
    return a + (b - a) * t;
  };
  const colX = c => MARGIN + (c + 0.5) * colW;

  for (const g of groups) {
    const d = g._depth;
    g._x0 = MARGIN + g.cols[0] * colW + 4 + SIDE * d;
    g._x1 = MARGIN + (g.cols[1] + 1) * colW - 4 - SIDE * d;
    g._y0 = rowTop[g.rows[0]] + HEAD * d + 4;
    g._y1 = rowTop[g.rows[1]] + topPad[g.rows[1]] + NODE_H + botPad[g.rows[1]] - FOOT * d - 4;
  }
  for (const n of nodes) { n._x = colX(n.col); n._y = rowY(n.row); }
  return { W, H, colX, rowY, gapY };
}

// ---------- geometry ----------

function clip(p, q, box) {
  // point where segment p->q leaves box (p is assumed inside the box)
  const [x0, y0, x1, y1] = box;
  const dx = q[0] - p[0], dy = q[1] - p[1];
  let best = 1;
  const ts = [];
  if (dx) ts.push((x0 - p[0]) / dx, (x1 - p[0]) / dx);
  if (dy) ts.push((y0 - p[1]) / dy, (y1 - p[1]) / dy);
  for (const t of ts) {
    if (t > 0 && t <= 1) {
      const x = p[0] + t * dx, y = p[1] + t * dy;
      if (x >= x0 - .01 && x <= x1 + .01 && y >= y0 - .01 && y <= y1 + .01) best = Math.min(best, t);
    }
  }
  return [p[0] + best * dx, p[1] + best * dy];
}

// ---------- render ----------

export function buildSvg(spec) {
  const L = computeLayout(spec);
  const id = ++uid;
  const svg = el("svg", {
    xmlns: NS, viewBox: `0 0 ${L.W} ${L.H}`, role: "img",
    "aria-label": spec.title || spec.id, "font-family": FONT, "data-width": L.W,
  });
  svg.style.maxWidth = L.W + "px";
  const defs = el("defs", {}, svg);
  const mk = (mid, d) => {
    const m = el("marker", { id: mid, viewBox: "0 0 10 10", refX: d === "end" ? 9 : 1, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto" }, defs);
    el("path", { d: d === "end" ? "M0,0 L10,5 L0,10 z" : "M10,0 L0,5 L10,10 z", fill: EDGE }, m);
  };
  mk(`qbA${id}`, "end"); mk(`qbS${id}`, "start");
  el("rect", { width: L.W, height: L.H, fill: "#FFFFFF" }, svg);

  const gGroups = el("g", { class: "qb-groups" }, svg);
  const gEdges = el("g", { class: "qb-edges" }, svg);
  const gNodes = el("g", { class: "qb-nodes" }, svg);
  const gLabels = el("g", { class: "qb-edge-labels" }, svg);

  for (const g of spec.groups || []) {
    const st = GROUP_STYLE[g.type] || GROUP_STYLE.generic;
    el("rect", {
      class: "qb-group", "data-id": g.id, x: g._x0, y: g._y0, width: g._x1 - g._x0, height: g._y1 - g._y0, rx: 2,
      fill: st.fill, stroke: st.stroke, "stroke-width": 1.5, "stroke-dasharray": st.dash,
    }, gGroups);
    if (g.label) {
      const t = el("text", { class: "qb-group-label", x: g._x0 + 8, y: g._y0 + 17, fill: st.text, "font-size": 12, "font-weight": 600,
        "data-x1": g._x1 - 8 }, gGroups);
      t.textContent = g.label;
    }
  }

  for (const n of spec.nodes || []) {
    const g = el("g", { class: "qb-node", "data-id": n.id }, gNodes);
    el("use", { href: `#i-${n.icon}`, x: n._x - ICON / 2, y: n._y - ICON / 2, width: ICON, height: ICON }, g);
    (n.label ? String(n.label).split("\n") : []).forEach((line, i) => {
      const t = el("text", { class: "qb-node-label", x: n._x, y: n._y + ICON / 2 + 16 + i * LINE, "text-anchor": "middle", "font-size": 13, fill: INK }, g);
      t.textContent = line;
    });
  }
  svg._layout = L;
  return svg;
}

// Edges need real text measurements (node label widths), so they are drawn after the svg is in the DOM.
function drawEdges(svg, spec) {
  const L = svg._layout;
  const id = svg.querySelector("marker").id.slice(3);
  const gEdges = svg.querySelector(".qb-edges");
  const gLabels = svg.querySelector(".qb-edge-labels");
  const nodes = new Map((spec.nodes || []).map(n => [n.id, n]));
  const groups = new Map((spec.groups || []).map(g => [g.id, g]));

  const boxOf = key => {
    if (nodes.has(key)) {
      const n = nodes.get(key);
      const ng = svg.querySelector(`.qb-node[data-id="${CSS.escape(key)}"]`);
      let x0 = n._x - ICON / 2, x1 = n._x + ICON / 2, y0 = n._y - ICON / 2, y1 = n._y + ICON / 2;
      ng.querySelectorAll("text").forEach(t => {
        const b = t.getBBox();
        x0 = Math.min(x0, b.x); x1 = Math.max(x1, b.x + b.width); y1 = Math.max(y1, b.y + b.height);
      });
      return { c: [n._x, n._y], box: [x0 - 3, y0 - 3, x1 + 3, y1 + 3] };
    }
    const g = groups.get(key);
    if (!g) throw new Error("unknown edge endpoint " + key);
    return { c: [(g._x0 + g._x1) / 2, (g._y0 + g._y1) / 2], box: [g._x0, g._y0, g._x1, g._y1] };
  };
  const pt = ([r, c]) => [L.colX(c), Number.isInteger(r) ? L.rowY(r) : L.gapY(r)];

  for (const e of spec.edges || []) {
    const a = boxOf(e.from), b = boxOf(e.to);
    let mids = (e.via || []).map(pt);
    if (e.route === "hv") mids = [[b.c[0], a.c[1]]];
    if (e.route === "vh") mids = [[a.c[0], b.c[1]]];
    const pts = [a.c, ...mids, b.c];
    pts[0] = clip(pts[0], pts[1], a.box);
    pts[pts.length - 1] = clip(pts[pts.length - 1], pts[pts.length - 2], b.box);
    const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
    el("path", {
      class: "qb-edge", "data-from": e.from, "data-to": e.to, d, fill: "none", stroke: EDGE, "stroke-width": 1.6,
      "stroke-dasharray": e.style === "dashed" ? "6 4" : null,
      "marker-end": e.noarrow ? null : `url(#qbA${id})`,
      "marker-start": e.both ? `url(#qbS${id})` : null,
    }, gEdges);

    if (e.label) {
      let mx, my;
      if (e.labelAt) [mx, my] = pt(e.labelAt);
      else {
        let best = null;
        for (let i = 0; i < pts.length - 1; i++) {
          const len = Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]);
          if (!best || len > best.len) best = { len, x: (pts[i][0] + pts[i + 1][0]) / 2, y: (pts[i][1] + pts[i + 1][1]) / 2 };
        }
        mx = best.x; my = best.y;
      }
      const lines = String(e.label).split("\n");
      const lg = el("g", { class: "qb-edge-label" }, gLabels);
      const bg = el("rect", { rx: 3, fill: "#FFFFFF", stroke: "#D5DBDB", "stroke-width": 1 }, lg);
      const h = lines.length * 14 + 6;
      let w = 0;
      lines.forEach((line, i) => {
        const t = el("text", { x: mx, y: my - h / 2 + 14 + i * 14, "text-anchor": "middle", "font-size": 11.5, fill: "#414D5C" }, lg);
        t.textContent = line;
        w = Math.max(w, t.getBBox().width);
      });
      w += 10;
      bg.setAttribute("x", (mx - w / 2).toFixed(1)); bg.setAttribute("y", (my - h / 2).toFixed(1));
      bg.setAttribute("width", w.toFixed(1)); bg.setAttribute("height", h);
    }
  }
}

// Move a group title to the right edge of its group if an edge line runs through it.
function avoidTitleCrossings(svg) {
  const paths = [...svg.querySelectorAll(".qb-edge")].map(p => {
    const len = p.getTotalLength(), pts = [];
    for (let s = 0; s <= len; s += 3) pts.push(p.getPointAtLength(s));
    return pts;
  });
  const crossed = t => {
    const b = t.getBBox();
    return paths.some(pts => pts.some(q => q.x > b.x - 4 && q.x < b.x + b.width + 4 && q.y > b.y - 2 && q.y < b.y + b.height + 2));
  };
  for (const t of svg.querySelectorAll(".qb-group-label")) {
    if (!crossed(t)) continue;
    const x0 = t.getAttribute("x");
    t.setAttribute("x", t.getAttribute("data-x1"));
    t.setAttribute("text-anchor", "end");
    if (crossed(t)) { t.setAttribute("x", x0); t.removeAttribute("text-anchor"); }
  }
}

function openZoom(svg, title) {
  const overlay = document.createElement("div");
  overlay.className = "qb-zoom";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", title || "Diagram");
  const bar = document.createElement("div");
  bar.className = "qb-zoom-bar";
  bar.innerHTML = '<span>Tap the diagram to zoom in or out</span>';
  const btn = document.createElement("button");
  btn.type = "button"; btn.className = "qb-zoom-close"; btn.textContent = "Close";
  bar.appendChild(btn);
  const inner = document.createElement("div");
  inner.className = "qb-zoom-inner";
  const w = Number(svg.getAttribute("data-width")) || 440;
  const fit = () => Math.min(window.innerWidth - 24, w * 2);   // fit to screen
  const big = () => Math.max(w * 2, fit());                     // pan-able close-up
  inner.style.width = fit() + "px";
  const clone = svg.cloneNode(true);
  clone.style.maxWidth = "none";
  inner.appendChild(clone);
  overlay.append(bar, inner);
  const close = () => { overlay.remove(); document.removeEventListener("keydown", onKey); document.body.style.overflow = prevOverflow; };
  const onKey = ev => { if (ev.key === "Escape") close(); };
  inner.addEventListener("click", ev => {
    ev.stopPropagation();
    const on = overlay.classList.toggle("big");
    inner.style.width = (on ? big() : fit()) + "px";
  });
  btn.addEventListener("click", ev => { ev.stopPropagation(); close(); });
  overlay.addEventListener("click", close);
  document.addEventListener("keydown", onKey);
  const prevOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  document.body.appendChild(overlay);
  btn.focus();
}

// Public entry point: fetch sprite once, render spec into a <figure> appended to container.
export async function renderDiagram(spec, container, opts = {}) {
  injectStyles();
  await loadSprite(opts.spriteUrl || "assets/aws-icons.svg");
  if (document.fonts && document.fonts.ready) { try { await document.fonts.ready; } catch (e) { /* ignore */ } }
  const fig = document.createElement("figure");
  fig.className = "qb-diagram";
  fig.dataset.qid = spec.id;
  const svg = buildSvg(spec);
  fig.appendChild(svg);
  if (spec.title) {
    const cap = document.createElement("figcaption");
    cap.textContent = spec.title;
    fig.appendChild(cap);
  }
  if (opts.beforeAppend && opts.beforeAppend() === false) return null;
  container.appendChild(fig);
  drawEdges(svg, spec);  // needs layout for text measurement
  avoidTitleCrossings(svg);
  if (opts.zoom !== false) {
    fig.tabIndex = 0;
    fig.setAttribute("aria-label", "Open larger diagram");
    fig.addEventListener("click", ev => { ev.stopPropagation(); openZoom(svg, spec.title); });
    fig.addEventListener("keydown", ev => { if (ev.key === "Enter") { ev.preventDefault(); openZoom(svg, spec.title); } });
  }
  return fig;
}
