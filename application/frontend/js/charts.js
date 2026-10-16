// Graphiques en SVG pur (sans bibliothèque) : fonctionnent hors connexion et respectent la politique de sécurité.
// Chaque graphique est redessiné à la largeur réelle de son cadre, donc lisible sur téléphone comme sur ordinateur.
const NS = "http://www.w3.org/2000/svg";
export const COLORS = { blue: "#1F4E79", orange: "#D97600", red: "#8B0000", grey: "#595959", green: "#90EE90", darkgreen: "#2E9E4F" };

function s(tag, attrs, ...children) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  for (const c of children.flat()) if (c !== null && c !== undefined) el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return el;
}
const txt = (x, y, str, attrs = {}) => s("text", { x, y, "font-size": 13, fill: "#4b5563", "font-family": "system-ui, sans-serif", ...attrs }, str);
const svgRoot = (W, H) => s("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img" });
const empty = (W, msg = "Aucune donnée sur la période.") => { const v = svgRoot(W, 110); v.append(txt(W / 2, 58, msg, { "text-anchor": "middle", "font-size": 14 })); return v; };

function niceMax(v) {
  if (v <= 5) return 5;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  return Math.ceil(v / p) * p;
}
const monthLabel = (m) => { const [y, mo] = m.split("-"); return `${mo}/${y.slice(2)}`; };
const short = (str, n) => (str.length > n ? str.slice(0, n - 1) + "…" : str);

// Histogramme groupé : labels = mois (ou catégories), series = [{name,color,values}]
export function barChart({ labels, series, monthLabels = true }, W = 600) {
  const total = series.reduce((a, x) => a + x.values.reduce((p, q) => p + q, 0), 0);
  if (!labels.length || !total) return empty(W);
  const H = 260, R = 8, T = 16, B = 40;
  const max = niceMax(Math.max(...series.flatMap((x) => x.values)));
  const L = Math.max(34, String(Math.round(max)).length * 8 + 14);
  const pw = W - L - R, ph = H - T - B, group = pw / labels.length, bw = Math.min(34, (group * 0.8) / series.length);
  const svg = svgRoot(W, H);
  for (let i = 0; i <= 5; i++) {
    const y = T + ph - (ph * i) / 5;
    svg.append(s("line", { x1: L, x2: W - R, y1: y, y2: y, stroke: "#e5e7eb" }), txt(L - 6, y + 4, Math.round((max * i) / 5), { "text-anchor": "end", "font-size": 12 }));
  }
  const maxChars = Math.max(4, Math.floor(group / 7));
  labels.forEach((lab, i) => {
    const gx = L + i * group + (group - bw * series.length) / 2;
    series.forEach((se, j) => {
      const v = se.values[i], bh = (ph * v) / max, x = gx + j * bw, y = T + ph - bh;
      svg.append(s("rect", { x, y, width: bw - 2, height: bh, fill: se.color, rx: 2 }, s("title", null, `${se.name} : ${v}`)));
      if (v) svg.append(txt(x + (bw - 2) / 2, y - 4, v, { "text-anchor": "middle", "font-size": 12, "font-weight": 700 }));
    });
    svg.append(txt(L + i * group + group / 2, H - B + 18, monthLabels ? monthLabel(lab) : short(lab, maxChars), { "text-anchor": "middle" }));
  });
  return svg;
}

// Barres horizontales classées : items = [{label,value}]
export function hbarChart({ items, color }, W = 600) {
  if (!items.length) return empty(W);
  const rows = items.slice(0, 8), rowH = 40, H = rows.length * rowH + 12, R = 34;
  const L = Math.min(190, Math.round(W * 0.42)), chars = Math.floor((L - 10) / 7.2);
  const max = niceMax(Math.max(...rows.map((r) => r.value)));
  const svg = svgRoot(W, H);
  rows.forEach((r, i) => {
    const y = 8 + i * rowH, w = ((W - L - R) * r.value) / max;
    svg.append(txt(L - 8, y + 21, short(r.label, chars), { "text-anchor": "end" }),
      s("rect", { x: L, y, width: Math.max(w, 2), height: 30, fill: color, rx: 3 }, s("title", null, `${r.label} : ${r.value}`)),
      txt(L + w + 6, y + 20, r.value, { "font-weight": 700 }));
  });
  return svg;
}

// Secteurs : items = [{label,value,color}]
export function pieChart({ items }, W = 600) {
  const data = items.filter((i) => i.value > 0), total = data.reduce((a, i) => a + i.value, 0);
  if (!total) return empty(W);
  const wide = W >= 480;
  const r = wide ? 95 : Math.min(95, (W - 30) / 2);
  const cx = wide ? r + 20 : W / 2, cy = r + 10;
  const H = wide ? Math.max(2 * r + 20, data.length * 30 + 30) : 2 * r + 24 + data.length * 28;
  const svg = svgRoot(W, H);
  let a0 = -Math.PI / 2;
  data.forEach((d) => {
    const frac = d.value / total, a1 = a0 + frac * 2 * Math.PI, pct = Math.round(frac * 100) + " %";
    const title = s("title", null, `${d.label} : ${d.value} (${pct})`);
    if (frac >= 0.9999) svg.append(s("circle", { cx, cy, r, fill: d.color }, title));
    else {
      const [x0, y0, x1, y1] = [cx + r * Math.cos(a0), cy + r * Math.sin(a0), cx + r * Math.cos(a1), cy + r * Math.sin(a1)];
      svg.append(s("path", { d: `M${cx},${cy} L${x0},${y0} A${r},${r} 0 ${frac > 0.5 ? 1 : 0} 1 ${x1},${y1} Z`, fill: d.color, stroke: "#fff", "stroke-width": 2 }, title));
    }
    if (frac > 0.06) {
      const am = (a0 + a1) / 2;
      svg.append(txt(cx + r * 0.62 * Math.cos(am), cy + r * 0.62 * Math.sin(am) + 5, pct, { "text-anchor": "middle", fill: d.color === COLORS.green ? "#1f4d2c" : "#fff", "font-weight": 700, "font-size": 14 }));
    }
    a0 = a1;
  });
  data.forEach((d, i) => {
    const x = wide ? cx + r + 36 : 14, y = wide ? 40 + i * 30 : 2 * r + 36 + i * 28;
    svg.append(s("rect", { x, y: y - 13, width: 16, height: 16, fill: d.color, rx: 3 }), txt(x + 24, y, `${d.label} : ${d.value}`, { "font-size": 14 }));
  });
  return svg;
}

// Schéma de flux : entrées -> transferts / sorties / encore présents
export function flowChart({ entrees, transferes, sortis, presents }, W = 600) {
  const H = 250, lw = Math.round(W * 0.3), rw = Math.round(W * 0.46), rx = W - rw - 4;
  const svg = svgRoot(W, H);
  const box = (x, y, w, h, fill, label, n) => svg.append(s("rect", { x, y, width: w, height: h, fill, rx: 10 }),
    txt(x + w / 2, y + h / 2 - 2, label, { "text-anchor": "middle", fill: "#fff", "font-weight": 800, "font-size": 12 }),
    txt(x + w / 2, y + h / 2 + 19, n, { "text-anchor": "middle", fill: "#fff", "font-weight": 800, "font-size": 20 }));
  svg.append(s("defs", null, s("marker", { id: "arr", markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: "auto" }, s("path", { d: "M0,0 L8,4 L0,8 Z", fill: "#374151" }))));
  box(4, 85, lw, 80, COLORS.blue, "ENTRÉES", entrees);
  [[10, COLORS.orange, "TRANSFÉRÉS", transferes], [90, COLORS.red, "SORTIS", sortis], [170, COLORS.darkgreen, "PRÉSENTS", presents]].forEach(([y, c, l, n]) => {
    svg.append(s("line", { x1: lw + 6, y1: 125, x2: rx - 4, y2: y + 35, stroke: "#374151", "stroke-width": 2, "marker-end": "url(#arr)" }));
    box(rx, y, rw, 70, c, l, n);
  });
  return svg;
}

// Cadre qui redessine son graphique quand sa largeur change (téléphone, rotation, fenêtre).
export function responsive(draw) {
  const box = document.createElement("div");
  let last = 0;
  const render = () => {
    const w = Math.max(260, Math.floor(box.clientWidth || 0));
    if (!box.clientWidth || Math.abs(w - last) < 6) return;
    last = w;
    box.replaceChildren(draw(w));
  };
  if (typeof ResizeObserver !== "undefined") new ResizeObserver(() => requestAnimationFrame(render)).observe(box);
  else window.addEventListener("resize", render);
  requestAnimationFrame(render);
  return box;
}

export const legend = (items) => {
  const wrap = document.createElement("div");
  wrap.className = "legend";
  items.forEach(([c, l]) => {
    const i = document.createElement("i"); i.style.background = c;
    const sp = document.createElement("span"); sp.append(i, document.createTextNode(l)); wrap.append(sp);
  });
  return wrap;
};
