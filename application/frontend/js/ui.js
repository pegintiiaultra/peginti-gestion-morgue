// Outils d'interface. Aucun innerHTML : tout le texte passe par des nœuds texte (protection XSS).
export function h(tag, props, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "style" || k === "innerHTML" || k === "outerHTML") continue;
    else if (k in el && k !== "list" && k !== "form") { try { el[k] = v; } catch { el.setAttribute(k, v); } }
    else el.setAttribute(k, v === true ? "" : v);
  }
  append(el, children);
  return el;
}
function append(el, children) {
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}
export const clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); };

// ----- dates -----
export function fmtDt(s) {
  if (!s) return "";
  const [d, t = ""] = String(s).split("T");
  const [y, m, j] = d.split("-");
  return `${j}/${m}/${y}${t ? " " + t.slice(0, 5) : ""}`;
}
export const fmtDate = (s) => fmtDt(String(s || "").slice(0, 10));
export function nowLocalInput() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}
export const todayInput = () => nowLocalInput().slice(0, 10);

// ----- notifications -----
export function toast(message, error = false) {
  const box = document.getElementById("toasts");
  const t = h("div", { class: "toast" + (error ? " error" : ""), role: "status" }, message);
  box.append(t);
  setTimeout(() => t.remove(), error ? 7000 : 4000);
}

// ----- badges -----
export const badge = (text, color) => h("span", { class: "badge b-" + color }, text);
const STATUTS = {
  EN_CONSERVATION: ["En conservation", "green"], LEVE: ["Levé (funérarium)", "orange"], TRANSFERE: ["Transféré", "orange"],
  SORTI: ["Sorti", "red"], ANNULE: ["Annulé", "grey"],
};
export function statutBadge(statut) {
  const [label, color] = STATUTS[statut] || [statut, "grey"];
  return badge(label, color);
}

// ----- formulaires -----
export function makeForm() {
  const f = {};
  const api = {
    f,
    input(name, o = {}) {
      const { type = "text", ...rest } = o;
      return (f[name] = h("input", { name, type, autocomplete: "off", ...rest }));
    },
    select(name, options, value) {
      const el = (f[name] = h("select", { name }));
      api.fill(el, options, value);
      return el;
    },
    textarea(name, o = {}) { return (f[name] = h("textarea", { name, rows: 3, ...o })); },
    fill(el, options, value) {
      clear(el);
      for (const [v, label, disabled] of options) {
        const opt = h("option", { value: v, disabled: !!disabled }, label);
        el.append(opt);
      }
      if (value !== undefined) el.value = String(value);
    },
    get: (name) => (f[name] ? f[name].value.trim() : ""),
    num: (name) => (f[name] && f[name].value !== "" ? Number(f[name].value) : undefined),
  };
  return api;
}
export const field = (label, control, hint) =>
  h("label", { class: "field" }, h("span", null, label), control, hint ? h("small", { class: "hint" }, hint) : null);

// ----- fenêtres modales -----
export function modal({ title, color = "", body, footer, narrow = false }) {
  const prevFocus = document.activeElement;
  const overlay = h("div", { class: "overlay", role: "dialog", "aria-modal": "true" });
  const box = h("div", { class: "modal" + (narrow ? " narrow" : "") },
    h("div", { class: "modal-head " + color }, title), h("div", { class: "modal-body" }, body),
    footer ? h("div", { class: "modal-foot" }, footer) : null);
  overlay.append(box);
  const close = () => { overlay.remove(); if (prevFocus && prevFocus.focus) prevFocus.focus(); };
  overlay.addEventListener("mousedown", (e) => { if (e.target === overlay && !overlay.dataset.lock) close(); });
  document.body.append(overlay);
  const first = box.querySelector("input:not([type=hidden]), select, textarea");
  if (first) first.focus();
  return { close, box, overlay };
}

// Formulaire dans une fenêtre : gère l'envoi, les erreurs et le blocage du double clic.
export function openForm({ title, color, content, submitLabel = "Enregistrer", submitClass = "primary", onSubmit, narrow }) {
  const errBox = h("div", { class: "form-error hidden", role: "alert" });
  const submit = h("button", { class: "btn " + submitClass, type: "submit" }, submitLabel);
  const cancel = h("button", { class: "btn", type: "button" }, "Annuler");
  const form = h("form", { novalidate: true }, errBox, content);
  const m = modal({ title, color, body: form, footer: [cancel, submit], narrow });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errBox.classList.add("hidden");
    submit.disabled = true;
    try {
      await onSubmit();
      m.close();
    } catch (err) {
      errBox.textContent = err.message || "Erreur.";
      errBox.classList.remove("hidden");
      errBox.scrollIntoView({ block: "nearest" });
    } finally { submit.disabled = false; }
  });
  cancel.addEventListener("click", m.close);
  // Les boutons sont dans le pied de la modale, hors du <form> : on relie le bouton d'envoi.
  submit.addEventListener("click", (e) => { e.preventDefault(); form.requestSubmit(); });
  return m;
}

export function askMotif(message, title = "Motif obligatoire") {
  return new Promise((resolve) => {
    const ta = h("textarea", { rows: 3, maxlength: 300, placeholder: "Motif (5 caractères minimum)" });
    const err = h("div", { class: "form-error hidden" });
    const ok = h("button", { class: "btn primary", type: "button" }, "Valider");
    const no = h("button", { class: "btn", type: "button" }, "Annuler");
    const m = modal({ title, narrow: true, body: [h("p", null, message), err, field("Motif", ta)], footer: [no, ok] });
    m.overlay.dataset.lock = "1";
    no.addEventListener("click", () => { m.close(); resolve(null); });
    ok.addEventListener("click", () => {
      if (ta.value.trim().length < 5) { err.textContent = "Le motif est trop court."; err.classList.remove("hidden"); return; }
      m.close(); resolve(ta.value.trim());
    });
  });
}

// Relance l'opération avec un motif lorsque le serveur exige une dérogation.
export async function withDerogation(run) {
  try { return await run(null); }
  catch (e) {
    if (e.code !== "DEROGATION_REQUISE") throw e;
    const motif = await askMotif(e.message, "Dérogation");
    if (!motif) throw new Error("Opération annulée : aucun motif de dérogation saisi.");
    return await run(motif);
  }
}

// ----- tableaux -----
export function table({ color, head, rows, empty = "Aucun enregistrement." }) {
  const body = rows.length
    ? rows.map((r) => h("tr", { class: r.cls || "" }, r.cells.map((c) => h("td", null, c))))
    : [h("tr", null, h("td", { class: "empty", colSpan: head.length }, empty))];
  return h("div", { class: "table-wrap" },
    h("table", { class: "th-" + color }, h("thead", null, h("tr", null, head.map((t) => h("th", null, t)))), h("tbody", null, body)));
}

// ----- export CSV (compatible Excel) -----
export function downloadCsv(filename, headers, rows) {
  const esc = (v) => {
    let s = String(v ?? "");
    if (/^[=+\-@\t\r]/.test(s)) s = "'" + s; // empêche l'exécution de formules dans Excel
    return /[;"\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const text = [headers, ...rows].map((r) => r.map(esc).join(";")).join("\r\n");
  const blob = new Blob(["﻿" + text], { type: "text/csv;charset=utf-8" });
  const a = h("a", { href: URL.createObjectURL(blob), download: filename });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

// ----- montants -----
export const fcfa = (n, devise = "FCFA") => `${new Intl.NumberFormat("fr-FR").format(Number(n) || 0).replace(/\u202f|\u00a0/g, " ")} ${devise}`;
