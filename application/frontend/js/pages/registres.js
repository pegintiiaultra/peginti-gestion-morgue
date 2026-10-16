// Registres : 1 Dépôt (bleu), 2 Transfert (orange), 3 Levée (orange foncé), 4 Sortie définitive (rouge).
// Seul le thanatopracteur saisit et corrige ; l'administration consulte, exporte et imprime.
import { api, apiBlob, state } from "../api.js";
import { askMotif, badge, clear, downloadCsv, field, fcfa, fmtDate, fmtDt, h, makeForm, nowLocalInput, openForm,
  statutBadge, table, todayInput, toast, withDerogation } from "../ui.js";

const canWrite = () => state.user.role === "thanatopracteur";
const age = (r) => `${r.age_value} ${r.age_unit}`;
const defunt = (r) => [h("b", null, `${r.nom} ${r.prenoms || ""}`.trim()), h("span", { class: "sub" }, age(r) + (r.sexe ? " · " + r.sexe : ""))];
const casCell = (r) => [r.cas === "interne" ? "Interne" : "Externe", r.service ? h("span", { class: "sub" }, r.service) : null];
const respCell = (r) => [r.resp_nom, h("span", { class: "sub" }, r.resp_contact), h("span", { class: "sub" }, r.resp_adresse + (r.resp_visa ? " · visa " + r.resp_visa : ""))];
const thanatoCell = (r) => [r.thanato_nom, r.thanato_visa ? h("span", { class: "sub" }, "visa " + r.thanato_visa) : null];
const numero = (r) => `${r.numero_ordre}/${r.annee}`;
const devise = () => (state.tarifs && state.tarifs.devise) || "FCFA";
const money = (n) => fcfa(n, devise());
const modifie = (r) => (r.modifie_le ? h("span", { class: "sub" }, `✎ corrigé le ${fmtDt(r.modifie_le.replace(" ", "T"))} par ${r.modifie_par}`) : null);

// ---------- page générique d'un registre ----------
async function registerPage(main, cfg) {
  let rows = [], q = "", annee = "";
  const title = h("h2", null, cfg.title);
  const count = h("span", { class: "count" });
  const holder = h("div");
  const search = h("input", { type: "search", placeholder: "Filtrer par nom, responsable, n°…", "aria-label": "Filtrer" });
  const years = h("select", { "aria-label": "Année" });
  const thisYear = new Date().getFullYear();
  years.append(h("option", { value: "" }, "Toutes les années"));
  for (let y = thisYear; y >= thisYear - 6; y--) years.append(h("option", { value: y }, String(y)));

  const exportRows = () => rows.map((r) => cfg.cols.filter((c) => c.csv).map((c) => String(c.csv(r) ?? "")));
  const exportHeads = () => cfg.cols.filter((c) => c.csv).map((c) => c.h);
  const csvBtn = h("button", { class: "btn", onclick: () => downloadCsv(cfg.csvName + ".csv", exportHeads(), exportRows()) }, "⬇ CSV");
  const xlsxBtn = h("button", { class: "btn", onclick: async () => {
    try {
      const blob = await apiBlob("/api/export/xlsx", { method: "POST", body: { titre: cfg.title.replace(/^\d+ - /, ""), headers: exportHeads(), rows: exportRows() } });
      const a = h("a", { href: URL.createObjectURL(blob), download: cfg.csvName + ".xlsx" }); document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    } catch (e) { toast(e.message, true); }
  } }, "⬇ Excel");
  const printHead = h("div", { class: "print-head" },
    h("div", { class: "ph-etab" }, (state.etab && state.etab.nom) || "Morgue", state.etab && state.etab.ville ? " — " + state.etab.ville : ""),
    h("div", { class: "ph-title" }, cfg.title.replace(/^\d+ - /, "").toUpperCase()),
    h("div", { class: "ph-meta" }, "Imprimé le " + new Date().toLocaleString("fr-FR") + " par " + state.user.full_name));
  const printFoot = h("div", { class: "print-foot" },
    h("div", null, "Le thanatopracteur de service", h("br"), h("br"), "Visa et signature"),
    h("div", null, "Le responsable de la morgue", h("br"), h("br"), "Visa et signature"));
  const actions = h("div", { class: "actions" },
    cfg.onNew && canWrite() ? h("button", { class: "btn " + cfg.btn, onclick: () => cfg.onNew(load) }, "+ " + cfg.newLabel) : null,
    csvBtn, xlsxBtn, h("button", { class: "btn", onclick: () => load() }, "⟳"), h("button", { class: "btn", onclick: () => window.print() }, "🖨 Imprimer / PDF"));
  main.append(printHead, h("div", { class: "page-head" }, h("div", null, title, count), actions),
    h("div", { class: "card accent-" + cfg.color }, cfg.banner ? cfg.banner() : null, h("div", { class: "inline" }, search, years), h("div", { class: "hint" }, cfg.hint || ""), holder), printFoot);

  async function cancel(r) {
    const motif = await askMotif(`Supprimer l'enregistrement n° ${numero(r)} (${r.nom}). Par exigence de traçabilité d'un registre officiel, la ligne n'est pas effacée : elle reste visible, barrée et marquée « Annulé » avec votre motif, la date et votre nom. Action irréversible.`, "Suppression motivée");
    if (!motif) return;
    try { await api(`/api/${cfg.kind}/${r.id}/annuler`, { method: "POST", body: { motif } }); toast("Enregistrement annulé."); await load(); }
    catch (e) { toast(e.message, true); }
  }

  function draw() {
    const vis = cfg.cols.filter((c) => !c.hidden);
    const head = [...vis.map((c) => c.h), "Actions"];
    const trs = rows.map((r) => ({
      cls: r.annule ? "annule" : "",
      cells: [...vis.map((c) => c.cell(r, load)), h("div", { class: "actions" },
        r.annule ? badge("Annulé", "grey") : null,
        !r.annule && canWrite() ? h("button", { class: "btn small", onclick: () => editForm(cfg.kind, r, load) }, "✎ Modifier") : null,
        !r.annule && canWrite() ? h("button", { class: "btn small red", onclick: () => cancel(r) }, "Supprimer") : null,
        r.annule ? h("span", { class: "sub" }, "Motif : " + (r.annule_motif || "")) : null,
        ...(cfg.extra ? cfg.extra(r, load) : []))],
    }));
    clear(holder);
    holder.append(table({ color: cfg.color, head, rows: trs, empty: "Aucun enregistrement pour ces critères." }));
    count.textContent = `(${rows.filter((r) => !r.annule).length} enregistrements)`;
  }
  async function load() {
    try {
      const p = new URLSearchParams();
      if (q) p.set("q", q);
      if (annee) p.set("annee", annee);
      rows = await api(`/api/${cfg.kind}?${p}`);
      draw();
    } catch (e) { toast(e.message, true); }
  }
  let timer;
  search.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { q = search.value.trim(); load(); }, 300); });
  years.addEventListener("change", () => { annee = years.value; load(); });
  await load();
}

// ---------- éléments de formulaire communs ----------
function respSection(fm, prefill = {}) {
  return [
    h("div", { class: "fieldset-title" }, "Responsable du corps"),
    field("Nom du responsable *", fm.input("resp_nom", { maxlength: 100, value: prefill.resp_nom || "" })),
    field("Contact (téléphone) *", fm.input("resp_contact", { maxlength: 50, inputMode: "tel", value: prefill.resp_contact || "" })),
    field("Adresse *", fm.input("resp_adresse", { maxlength: 150, value: prefill.resp_adresse || "" })),
    field("Visa", fm.input("resp_visa", { maxlength: 50, value: prefill.resp_visa || "" })),
  ];
}
function fillResp(fm, r) {
  for (const k of ["resp_nom", "resp_contact", "resp_adresse", "resp_visa"]) fm.f[k].value = r[k] || "";
}
function respPayload(fm) {
  return { resp_nom: fm.get("resp_nom"), resp_contact: fm.get("resp_contact"), resp_adresse: fm.get("resp_adresse"), resp_visa: fm.get("resp_visa") };
}
async function thanatoSection(fm) {
  const people = await api("/api/personnel");
  const sel = fm.select("thanato_user_id", people.map((p) => [p.id, p.full_name + (p.visa ? " (visa " + p.visa + ")" : "")]));
  if (people.some((p) => p.id === state.user.id)) sel.value = String(state.user.id);
  fm.serviceHint = h("small", { class: "hint" });
  return [h("div", { class: "fieldset-title" }, "Thanatopracteur de service"), field("Thanatopracteur *", sel, null), fm.serviceHint];
}
const defuntSection = (fm, v = {}) => [
  h("div", { class: "fieldset-title" }, "Défunt"),
  field("Nom *", fm.input("nom", { maxlength: 100, value: v.nom || "" })), field("Prénoms", fm.input("prenoms", { maxlength: 100, value: v.prenoms || "" })),
  field("Âge *", h("div", { class: "inline" }, fm.input("age_value", { type: "number", min: 0, max: 150, inputMode: "numeric", value: v.age_value ?? "" }), fm.select("age_unit", [["ans", "ans"], ["mois", "mois"], ["jours", "jours"]], v.age_unit || "ans"))),
  field("Sexe", fm.select("sexe", [["", "—"], ["M", "Masculin"], ["F", "Féminin"]], v.sexe || "")),
];
const defuntPayload = (fm) => ({ nom: fm.get("nom"), prenoms: fm.get("prenoms"), age_value: fm.num("age_value"), age_unit: fm.get("age_unit"), sexe: fm.get("sexe") });

// Propose le thanatopracteur de service d'après le planning des gardes, selon la date et l'heure saisies.
function bindService(fm, dateName) {
  const sel = fm.f.thanato_user_id, dateIn = fm.f[dateName];
  if (!sel || !dateIn) return;
  let touched = false, seq = 0;
  sel.addEventListener("change", () => { touched = true; });
  const update = async () => {
    const mine = ++seq;
    try {
      const r = await api("/api/rh/service?at=" + encodeURIComponent(dateIn.value));
      if (mine !== seq) return;
      if (!r.equipe) { fm.serviceHint.textContent = "Aucune équipe n'est planifiée à cette date (menu Gardes) : choisissez le thanatopracteur."; return; }
      const linked = r.agents.find((a) => a.user_id && [...sel.options].some((o) => o.value === String(a.user_id)));
      fm.serviceHint.textContent = `Planning : ${r.equipe.nom} — ${r.garde.label}.` + (linked ? "" : " Aucun agent de cette équipe n'a de compte lié : choisissez le thanatopracteur.");
      if (linked && !touched) sel.value = String(linked.user_id);
    } catch { /* le planning est une aide, jamais bloquant */ }
  };
  dateIn.addEventListener("change", update); dateIn.addEventListener("input", update);
  update();
}

const radioGroup = (name, options, value, onChange) => {
  const wrap = h("div", { class: "radios" });
  for (const [v, label] of options) {
    const input = h("input", { type: "radio", name, value: v, checked: v === value });
    input.addEventListener("change", () => onChange(v));
    wrap.append(h("label", { class: "radio" }, input, h("span", null, label)));
  }
  return wrap;
};

// ---------- 1 - DÉPÔT (entrées) ----------
function entreeForm(reload) {
  return Promise.all([api("/api/plan"), api("/api/services"), api("/api/parametres")]).then(async ([plan, services, tarifs]) => {
    state.tarifs = tarifs;
    const fm = makeForm();
    let mode = "conservation";
    const thanato = await thanatoSection(fm);
    const shelfSel = fm.select("shelf", plan.shelves.map((s) => [s.id, "Box " + s.name + (s.saturated ? " (saturé)" : "")]));
    const divSel = fm.select("division_id", []);
    const slotSel = fm.select("slot", []);
    const svcOptions = [["", "— choisir —"], ...services.map((s) => [s.id, s.nom])];
    const serviceField = field("Service du décès *", fm.select("service_id", svcOptions));
    const casSel = fm.select("cas", [["externe", "Externe (décès hors de l'hôpital)"], ["interne", "Interne (décès à l'hôpital)"]]);
    const chambreSel = fm.select("type_chambre", [["", "— choisir —"], ["commune", `Chambre commune (${money(tarifs.prix_nuitee_commune)} / nuit)`], ["individuelle", `Chambre individuelle (${money(tarifs.prix_nuitee_individuelle)} / nuit)`]]);
    const hintDiv = h("small", { class: "hint" });

    const shelf = () => plan.shelves.find((s) => String(s.id) === shelfSel.value);
    const division = () => shelf()?.divisions.find((d) => String(d.id) === divSel.value);
    function refreshDivs() {
      const s = shelf();
      fm.fill(divSel, s.divisions.map((d) => [d.id,
        d.is_floor ? `${d.label} — sol (${d.free} libre${d.free > 1 ? "s" : ""}${s.saturated ? "" : ", réservé à la saturation"})`
          : `${d.label} — ${d.free} libre${d.free > 1 ? "s" : ""} / ${d.capacity}`, d.free === 0]));
      const firstOk = s.divisions.find((d) => d.free > 0 && !d.is_floor) || s.divisions.find((d) => d.free > 0);
      if (firstOk) divSel.value = String(firstOk.id);
      refreshSlots();
    }
    function refreshSlots() {
      const d = division();
      fm.fill(slotSel, [["", "Premier emplacement libre (automatique)"], ...(d ? d.slots.filter((x) => !x.occupied).map((x) => [x.letter, x.label]) : [])]);
      hintDiv.textContent = d && d.is_floor && !shelf().saturated
        ? "⚠ Le sol n'est utilisable que si toutes les divisions du box sont pleines : une dérogation motivée sera demandée." : "";
      hintDiv.className = "hint warn";
    }
    shelfSel.addEventListener("change", refreshDivs); divSel.addEventListener("change", refreshSlots);
    if (plan.shelves.length) refreshDivs();

    // Mode « entrée directe pour transfert » : pas de chambre froide, seulement des frais de transfert
    const serviceOrigine = field("Service d'origine *", fm.select("service_origine_id", svcOptions));
    const destination = field("Destination du transfert *", fm.input("destination_transfert", { maxlength: 150, placeholder: "Ex. Morgue centrale, Douala" }));
    const fraisHint = h("small", { class: "hint" }, `Frais de transfert : ${money(tarifs.prix_transfert)} (pas de frais de conservation).`);
    const conservationBlock = h("div", { class: "grid span" },
      field("Cas *", casSel), serviceField,
      h("div", { class: "fieldset-title" }, "Chambre froide et emplacement"),
      field("Type de chambre froide *", chambreSel),
      field("Box *", shelfSel), field("Division *", divSel, null), field("Emplacement (lettre)", slotSel), hintDiv);
    const raisonsDirect = await api("/api/raisons");
    const raisonSelD = fm.select("raison_id", raisonsDirect.filter((r) => !r.reserve).map((r) => [r.id, r.libelle]));
    const precD = field("Précisez la raison *", fm.input("raison_precision", { maxlength: 200 }));
    const togglePrec = () => precD.classList.toggle("hidden", !raisonsDirect.find((r) => String(r.id) === raisonSelD.value)?.est_autre);
    raisonSelD.addEventListener("change", togglePrec); togglePrec();
    const directBlock = h("div", { class: "grid span hidden" }, serviceOrigine, field("Raison du transfert *", raisonSelD), precD, destination, fraisHint);
    const toggleService = () => serviceField.classList.toggle("hidden", casSel.value !== "interne");
    casSel.addEventListener("change", toggleService); toggleService();
    const setMode = (m) => {
      mode = m;
      conservationBlock.classList.toggle("hidden", m !== "conservation");
      directBlock.classList.toggle("hidden", m !== "transfert_direct");
    };

    const content = h("div", { class: "grid" },
      plan.alerts.length ? h("div", { class: "alert" }, plan.alerts.join(" ")) : null,
      h("div", { class: "fieldset-title" }, "Type d'entrée"),
      radioGroup("type_entree", [["conservation", "Conservation chambre froide"], ["transfert_direct", "Entrée directe pour transfert (service interne)"]], "conservation", setMode),
      ...defuntSection(fm),
      field("Date et heure d'entrée *", fm.input("date_entree", { type: "datetime-local", value: nowLocalInput() })),
      conservationBlock, directBlock,
      ...respSection(fm), ...thanato);
    bindService(fm, "date_entree");
    if (!plan.shelves.length) {
      const canConfig = state.user.role !== "thanatopracteur";
      content.prepend(h("div", { class: "form-error" },
        "Aucun box n'est encore paramétré : en mode « Conservation », l'emplacement est obligatoire. Choisissez « Entrée directe » ou demandez à l'administration de créer les box (menu Paramétrage). ",
        canConfig ? h("button", { class: "btn small blue", type: "button", onclick: () => { document.querySelector(".overlay")?.remove(); window.dispatchEvent(new CustomEvent("goto-page", { detail: "config" })); } }, "Créer les box maintenant") : null));
    }

    openForm({
      title: "Nouveau dépôt — registre d'entrée", color: "blue", content, submitClass: "blue", submitLabel: "Enregistrer le dépôt",
      onSubmit: async () => {
        const common = { ...defuntPayload(fm), type_entree: mode, date_entree: fm.get("date_entree"), thanato_user_id: fm.num("thanato_user_id"), ...respPayload(fm) };
        const base = mode === "transfert_direct"
          ? { ...common, cas: "interne", service_id: fm.num("service_origine_id"), destination_transfert: fm.get("destination_transfert"), raison_id: fm.num("raison_id"), raison_precision: fm.get("raison_precision") }
          : { ...common, cas: fm.get("cas"), service_id: fm.num("service_id"), type_chambre: fm.get("type_chambre"), division_id: fm.num("division_id"), slot: fm.get("slot") };
        const r = await withDerogation((m) => api("/api/entrees", { method: "POST", body: m ? { ...base, derogation_motif: m } : base }));
        toast(mode === "transfert_direct" ? `Entrée n° ${r.numero} + transfert n° ${r.transfert_numero} enregistrés (frais : ${money(r.frais_transfert)}).`
          : `Dépôt n° ${r.numero} enregistré — emplacement ${r.emplacement}.`);
        reload();
      },
    });
  }).catch((e) => toast(e.message, true));
}
export const entrees = (main) => registerPage(main, {
  kind: "entrees", title: "1 - Registre d'entrée (dépôt)", color: "blue", btn: "blue", newLabel: "Nouveau dépôt", csvName: "registre-entrees",
  hint: "Chaque dépôt reçoit un n° d'ordre annuel. En conservation : emplacement (box + division + lettre) et type de chambre.", onNew: entreeForm,
  cols: [
    { h: "N° d'ordre", cell: (r) => h("b", null, numero(r)), csv: numero },
    { h: "Date et heure", cell: (r) => fmtDt(r.date_entree), csv: (r) => fmtDt(r.date_entree) },
    { h: "Défunt", cell: (r) => [...defunt(r), h("span", { class: "sub" }, statutBadge(r.statut)), modifie(r)], csv: (r) => `${r.nom} ${r.prenoms}, ${age(r)}` },
    { h: "Type", cell: (r) => r.type_entree === "transfert_direct" ? [badge("Transfert direct", "orange"), h("span", { class: "sub" }, `${r.service_origine || ""} → ${r.destination_transfert || ""}`)]
        : [badge("Conservation", "green"), h("span", { class: "sub" }, r.type_chambre === "individuelle" ? "Chambre individuelle" : "Chambre commune")],
      csv: (r) => r.type_entree === "transfert_direct" ? `Transfert direct (${r.service_origine} -> ${r.destination_transfert})` : `Conservation (${r.type_chambre || ""})` },
    { h: "Cas", cell: casCell, csv: (r) => r.cas + (r.service ? " - " + r.service : "") },
    { h: "Responsable du corps", cell: respCell, csv: (r) => `${r.resp_nom}; ${r.resp_contact}; ${r.resp_adresse}; ${r.resp_visa}` },
    { h: "Emplacement", cell: (r) => h("b", null, r.emplacement), csv: (r) => r.emplacement },
    { h: "Thanatopracteur", cell: thanatoCell, csv: (r) => `${r.thanato_nom} ${r.thanato_visa}` },
    { h: "Statut", hidden: true, cell: () => null, csv: (r) => r.statut },
  ],
});

// ---------- sélection du défunt ----------
async function dossierPicker(fm, onPick, { url = "/api/dossiers/en-conservation", label, empty }) {
  const list = await api(url);
  const sel = fm.select("dossier_id", []);
  const filter = h("input", { type: "search", placeholder: "Rechercher un défunt…" });
  const info = h("small", { class: "hint" });
  const render = () => {
    const t = filter.value.trim().toLowerCase();
    const items = list.filter((d) => !t || `${d.nom} ${d.prenoms}`.toLowerCase().includes(t));
    fm.fill(sel, items.length ? items.map((d) => [d.id, label(d)]) : [["", empty]]);
    pick();
  };
  const pick = () => {
    const d = list.find((x) => String(x.id) === sel.value);
    info.textContent = d ? (d.emplacement ? `Emplacement actuel : ${d.emplacement}. Entré le ${fmtDt(d.date_entree)}.` : `Levé le ${fmtDt(d.date_levee)}.`) : "";
    if (d) onPick(d);
  };
  filter.addEventListener("input", render); sel.addEventListener("change", pick);
  return { nodes: [field("Défunt *", h("div", null, filter, sel), null), info], init: render, count: list.length };
}
const enConservation = { label: (d) => `${d.nom} ${d.prenoms} — ${d.emplacement} (n° ${d.numero_ordre}/${d.annee})`, empty: "Aucun corps en conservation" };

// ---------- 2 - TRANSFERTS ----------
async function transfertForm(reload) {
  try {
    const [raisons, tarifs, services] = await Promise.all([api("/api/raisons"), api("/api/parametres"), api("/api/services")]);
    state.tarifs = tarifs;
    const fm = makeForm();
    let source = "conservation";
    const picker = await dossierPicker(fm, (d) => { if (source === "conservation") fillResp(fm, d); }, enConservation);
    const raisonSel = fm.select("raison_id", raisons.filter((r) => !r.reserve).map((r) => [r.id, r.libelle]));
    const precField = field("Précisez la raison *", fm.input("raison_precision", { maxlength: 200 }));
    const toggle = () => precField.classList.toggle("hidden", !raisons.find((r) => String(r.id) === raisonSel.value)?.est_autre);
    raisonSel.addEventListener("change", toggle);

    // Deux origines possibles : un corps en chambre froide, ou un corps qui n'y est jamais entré (transfert direct
    // depuis un service de l'hôpital, à la demande de la famille, pour un motif religieux…).
    const conservationBlock = h("div", { class: "grid span" }, h("div", { class: "fieldset-title" }, "Défunt"), ...picker.nodes);
    const serviceOrigine = field("Service d'origine (où le décès a eu lieu) *", fm.select("service_origine_id", [["", "— choisir —"], ...services.map((x) => [x.id, x.nom])]));
    const directBlock = h("div", { class: "grid span hidden" },
      h("div", { class: "hint" }, "Le corps n'entre pas en chambre froide : une entrée directe est créée au registre de dépôt, avec ce transfert. Aucun frais de conservation."),
      ...defuntSection(fm), serviceOrigine);
    const noBody = h("div", { class: "form-error" + (picker.count ? " hidden" : "") }, "Aucun corps n'est actuellement en conservation : utilisez « Corps non conservé » pour un transfert direct.");
    const setSource = (v) => {
      source = v;
      conservationBlock.classList.toggle("hidden", v !== "conservation");
      directBlock.classList.toggle("hidden", v !== "direct");
      noBody.classList.toggle("hidden", v !== "conservation" || picker.count > 0);
    };
    const radios = radioGroup("source", [["conservation", "Corps en chambre froide"], ["direct", "Corps non conservé (transfert direct depuis un service)"]], picker.count ? "conservation" : "direct", setSource);
    const content = h("div", { class: "grid" },
      h("div", { class: "fieldset-title" }, "Origine du corps"), radios, noBody,
      conservationBlock, directBlock,
      field("Date et heure du transfert *", fm.input("date_transfert", { type: "datetime-local", value: nowLocalInput() })),
      h("div", { class: "fieldset-title" }, "Transfert"), field("Raison du transfert *", raisonSel), precField,
      field("Lieu du transfert *", fm.input("lieu", { maxlength: 150, placeholder: "Ex. Morgue centrale, Douala" })),
      h("small", { class: "hint" }, `Frais de transfert : ${money(tarifs.prix_transfert)}.`),
      ...respSection(fm), ...(await thanatoSection(fm)));
    picker.init(); toggle(); setSource(picker.count ? "conservation" : "direct"); bindService(fm, "date_transfert");
    openForm({
      title: "Nouveau transfert — registre de transfert", color: "orange", content, submitClass: "orange", submitLabel: "Enregistrer le transfert",
      onSubmit: async () => {
        const raison = { raison_id: fm.num("raison_id"), raison_precision: fm.get("raison_precision") };
        if (source === "direct") {
          const r = await api("/api/entrees", { method: "POST", body: { ...defuntPayload(fm), type_entree: "transfert_direct", cas: "interne",
            service_id: fm.num("service_origine_id"), date_entree: fm.get("date_transfert"), destination_transfert: fm.get("lieu"), ...raison,
            thanato_user_id: fm.num("thanato_user_id"), ...respPayload(fm) } });
          toast(`Transfert n° ${r.transfert_numero} enregistré (entrée directe n° ${r.numero}, sans conservation). Frais : ${money(r.frais_transfert)}.`);
        } else {
          const r = await api("/api/transferts", { method: "POST", body: { dossier_id: fm.num("dossier_id"), date_transfert: fm.get("date_transfert"),
            ...raison, lieu: fm.get("lieu"), thanato_user_id: fm.num("thanato_user_id"), ...respPayload(fm) } });
          toast(`Transfert n° ${r.numero} enregistré — emplacement ${r.libere} libéré.`);
        }
        reload();
      },
    });
  } catch (e) { toast(e.message, true); }
}

export const transferts = (main) => registerPage(main, {
  kind: "transferts", title: "2 - Registre de transfert", color: "orange", btn: "orange", newLabel: "Nouveau transfert", csvName: "registre-transferts",
  hint: "Un transfert libère l'emplacement du corps. Un corps non conservé (transfert direct depuis un service) s'enregistre aussi ici ; il apparaît alors au registre de dépôt.", onNew: transfertForm,
  cols: [
    { h: "N° d'ordre", cell: (r) => h("b", null, numero(r)), csv: numero },
    { h: "Date et heure", cell: (r) => fmtDt(r.date_transfert), csv: (r) => fmtDt(r.date_transfert) },
    { h: "Défunt", cell: (r) => [...defunt(r), modifie(r)], csv: (r) => `${r.nom} ${r.prenoms}, ${age(r)}` },
    { h: "Cas", cell: casCell, csv: (r) => r.cas + (r.service ? " - " + r.service : "") },
    { h: "Raison", cell: (r) => [r.raison, r.raison_precision ? h("span", { class: "sub" }, r.raison_precision) : null], csv: (r) => r.raison + (r.raison_precision ? " : " + r.raison_precision : "") },
    { h: "Lieu du transfert", cell: (r) => r.lieu, csv: (r) => r.lieu },
    { h: "Frais", cell: (r) => money(r.montant_transfert), csv: (r) => r.montant_transfert },
    { h: "Responsable du corps", cell: respCell, csv: (r) => `${r.resp_nom}; ${r.resp_contact}; ${r.resp_adresse}; ${r.resp_visa}` },
    { h: "Ancien emplacement", cell: (r) => r.emplacement, csv: (r) => r.emplacement },
    { h: "Thanatopracteur", cell: thanatoCell, csv: (r) => `${r.thanato_nom} ${r.thanato_visa}` },
  ],
});

// ---------- 3 - LEVÉES (chambre froide -> funérarium), facturation et solde ----------
const MODES = [["", "— choisir —"], ["especes", "Espèces"], ["momo", "MTN MoMo"], ["om", "Orange Money"], ["virement", "Virement"]];
const MODE_LABEL = { especes: "Espèces", momo: "MoMo", om: "Orange Money", virement: "Virement" };

async function levee(reload) {
  try {
    const tarifs = await api("/api/parametres");
    state.tarifs = tarifs;
    const fm = makeForm();
    const picker = await dossierPicker(fm, (d) => { fillResp(fm, d); refresh(); }, enConservation);
    const dateIn = fm.input("date_levee", { type: "datetime-local", value: nowLocalInput() });
    const chap = h("input", { type: "checkbox", name: "chapelle_louee" });
    const chapType = radioGroup("type_chapelle", [["petite", `Petite chapelle (${money(tarifs.prix_chapelle_petite)})`], ["grande", `Grande chapelle (${money(tarifs.prix_chapelle_grande)})`]], "petite", () => refresh());
    const chapBlock = h("div", { class: "hidden" }, chapType);
    const majAlert = h("div", { class: "alert warn hidden", role: "status" });
    const recap = h("div", { class: "recap" });
    const verse = fm.input("montant_verse", { type: "number", min: 0, inputMode: "numeric", value: "0" });
    const solde = h("input", { type: "checkbox", name: "est_solde" });
    const modeSel = fm.select("mode_paiement", MODES);
    const reste = h("b", { class: "reste" });
    let total = 0, seq = 0;
    const chapitre = () => (chap.checked ? (chapBlock.querySelector("input:checked")?.value || "petite") : "");

    async function refresh() {
      chapBlock.classList.toggle("hidden", !chap.checked);
      const id = fm.num("dossier_id");
      if (!id || !dateIn.value) return;
      const mine = ++seq;
      try {
        const p = new URLSearchParams({ dossier_id: id, date_levee: dateIn.value });
        if (chapitre()) p.set("chapelle", chapitre());
        const c = await api("/api/levees/apercu?" + p);
        if (mine !== seq) return;
        total = c.montant_total;
        majAlert.classList.toggle("hidden", !c.est_majore);
        majAlert.textContent = c.est_majore ? `Majoration applicable : ${c.motif_majoration} (+ ${money(c.montant_majoration)})` : "";
        clear(recap);
        recap.append(
          h("div", null, `Nuitées : ${c.nuitees} × ${money(c.prix_nuitee)} (chambre ${c.type_chambre}) = `, h("b", null, money(c.montant_conservation))),
          c.est_majore ? h("div", null, "Majoration : ", h("b", null, money(c.montant_majoration))) : null,
          c.prix_chapelle ? h("div", null, "Chapelle : ", h("b", null, money(c.prix_chapelle))) : null,
          h("div", { class: "total" }, "Total à payer : ", h("b", null, money(c.montant_total))));
        sync();
      } catch (e) { clear(recap); recap.append(h("div", { class: "hint err" }, e.message)); }
    }
    function sync() {
      const v = Number(verse.value) || 0;
      reste.textContent = money(Math.max(total - v, 0));
      solde.checked = total > 0 ? v >= total : v >= 0 && total === 0;
      reste.className = "reste " + (total - v > 0 ? "due" : "ok");
    }
    verse.addEventListener("input", sync);
    solde.addEventListener("change", () => { if (solde.checked) { verse.value = String(total); } sync(); });
    chap.addEventListener("change", refresh); dateIn.addEventListener("change", refresh); dateIn.addEventListener("input", refresh);

    const content = h("div", { class: "grid" },
      picker.count ? null : h("div", { class: "form-error" }, "Aucun corps n'est actuellement en chambre froide."),
      h("div", { class: "alert info" }, "Mercredi : levée / vidange systématique de la chambre froide vers le funérarium. Horaires des levées : " + `${tarifs.heure_debut_levee}h à ${tarifs.heure_fin_levee}h.`),
      h("div", { class: "fieldset-title" }, "Défunt"), ...picker.nodes,
      field("Date et heure de la levée *", dateIn), majAlert,
      h("div", { class: "fieldset-title" }, "Chapelle"),
      h("label", { class: "check" }, chap, h("span", null, "Chapelle consignée / louée pour la famille (cérémonie du jour de la levée)")), chapBlock,
      h("div", { class: "fieldset-title" }, "Facturation et paiement"), recap,
      field("Montant versé *", verse), h("label", { class: "check" }, solde, h("span", null, "Soldé (montant versé = total à payer)")),
      field("Mode de paiement (si versement)", modeSel),
      h("div", { class: "total" }, "Reste à payer : ", reste),
      ...respSection(fm), ...(await thanatoSection(fm)));
    picker.init(); bindService(fm, "date_levee");
    openForm({
      title: "Nouvelle levée — chambre froide → funérarium", color: "orange", content, submitClass: "orange", submitLabel: "Enregistrer la levée",
      onSubmit: async () => {
        const body = { dossier_id: fm.num("dossier_id"), date_levee: fm.get("date_levee"), chapelle_louee: chap.checked, type_chapelle: chapitre() || undefined,
          montant_verse: Number(verse.value) || 0, est_solde: solde.checked && (Number(verse.value) || 0) >= total && total > 0 ? true : undefined,
          mode_paiement: fm.get("mode_paiement") || undefined, thanato_user_id: fm.num("thanato_user_id"), ...respPayload(fm) };
        if (body.montant_verse > 0 && !body.mode_paiement) throw new Error("Choisissez le mode de paiement du montant versé.");
        const r = await api("/api/levees", { method: "POST", body });
        toast(`Levée n° ${r.numero} — ${r.est_solde ? "soldée" : "reste à payer : " + money(r.reste_a_payer)}${r.est_majore ? " (majorée)" : ""}.`);
        reload();
      },
    });
  } catch (e) { toast(e.message, true); }
}

function paiementForm(r, reload) {
  const fm = makeForm();
  openForm({ title: `Versement — levée n° ${numero(r)} (${r.nom})`, color: "orange", narrow: true, submitLabel: "Enregistrer le versement", submitClass: "orange",
    content: h("div", { class: "grid" }, h("p", null, `Reste à payer : `, h("b", null, money(r.reste_a_payer))),
      field("Montant versé *", fm.input("montant", { type: "number", min: 1, max: r.reste_a_payer, inputMode: "numeric", value: String(r.reste_a_payer) })),
      field("Mode de paiement *", fm.select("mode_paiement", MODES)), field("Date du paiement", fm.input("date_paiement", { type: "date", value: todayInput() }))),
    onSubmit: async () => {
      if (!fm.get("mode_paiement")) throw new Error("Choisissez le mode de paiement.");
      const x = await api(`/api/levees/${r.id}/paiement`, { method: "POST", body: { montant: fm.num("montant"), mode_paiement: fm.get("mode_paiement"), date_paiement: fm.get("date_paiement") } });
      toast(x.est_solde ? "Levée soldée." : `Reste à payer : ${money(x.reste_a_payer)}`);
      reload();
    } });
}
async function paiementsList(r) {
  try {
    const list = await api(`/api/levees/${r.id}/paiements`);
    const { modal } = await import("../ui.js");
    modal({ title: `Paiements — levée n° ${numero(r)}`, narrow: true, body: table({ color: "orange", head: ["Date", "Montant", "Mode", "Par"],
      rows: list.map((p) => ({ cells: [fmtDate(p.date_paiement), money(p.montant), MODE_LABEL[p.mode_paiement], p.par] })), empty: "Aucun versement." }),
      footer: h("button", { class: "btn", onclick: (e) => e.target.closest(".overlay").remove() }, "Fermer") });
  } catch (e) { toast(e.message, true); }
}
const levAction = (r, reload) => r.annule ? [] : [
  r.reste_a_payer > 0 && canWrite() ? h("button", { class: "btn small orange", onclick: () => paiementForm(r, reload) }, "+ Versement") : null,
  h("button", { class: "btn small", onclick: () => paiementsList(r) }, "Paiements")].filter(Boolean);

export const levees = (main) => registerPage(main, {
  kind: "levees", title: "3 - Levée (chambre froide → funérarium)", color: "orange", btn: "orange", newLabel: "Nouvelle levée", csvName: "registre-levees",
  hint: "MERCREDI : levée / vidange systématique de la chambre froide. Horaires 7h-18h ; majoration automatique le dimanche et hors horaires.", onNew: levee, extra: levAction,
  cols: [
    { h: "N° d'ordre", cell: (r) => h("b", null, numero(r)), csv: numero },
    { h: "Date et heure", cell: (r) => [fmtDt(r.date_levee), r.est_majore ? badge("Majorée", "orange") : null], csv: (r) => fmtDt(r.date_levee) },
    { h: "Défunt", cell: (r) => [...defunt(r), modifie(r)], csv: (r) => `${r.nom} ${r.prenoms}, ${age(r)}` },
    { h: "Responsable du corps", cell: respCell, csv: (r) => `${r.resp_nom}; ${r.resp_contact}; ${r.resp_adresse}; ${r.resp_visa}` },
    { h: "Nuitées", cell: (r) => [`${r.nuitees} × ${money(r.prix_nuitee)}`, h("span", { class: "sub" }, `chambre ${r.type_chambre}`)], csv: (r) => `${r.nuitees} (${r.type_chambre})` },
    { h: "Montant conservation", cell: (r) => money(r.montant_conservation), csv: (r) => r.montant_conservation },
    { h: "Majoration", cell: (r) => r.est_majore ? [money(r.montant_majoration), h("span", { class: "sub" }, r.motif_majoration)] : "—", csv: (r) => r.montant_majoration },
    { h: "Chapelle", cell: (r) => r.chapelle_louee ? [r.type_chapelle === "grande" ? "Grande" : "Petite", h("span", { class: "sub" }, money(r.prix_chapelle))] : "—", csv: (r) => r.chapelle_louee ? `${r.type_chapelle} (${r.prix_chapelle})` : "" },
    { h: "Total", cell: (r) => h("b", null, money(r.montant_total)), csv: (r) => r.montant_total },
    { h: "Versé", cell: (r) => [money(r.montant_verse), r.mode_paiement ? h("span", { class: "sub" }, MODE_LABEL[r.mode_paiement]) : null], csv: (r) => r.montant_verse },
    { h: "Reste / Soldé", cell: (r) => r.reste_a_payer > 0 ? [badge("Non soldé", "red"), h("span", { class: "sub" }, money(r.reste_a_payer))] : badge("Soldé", "green"), csv: (r) => r.reste_a_payer > 0 ? r.reste_a_payer : "Soldé" },
    { h: "Thanatopracteur", cell: thanatoCell, csv: (r) => `${r.thanato_nom} ${r.thanato_visa}` },
  ],
});

// ---------- 4 - SORTIES DÉFINITIVES (remise à la famille / inhumation) ----------
const GENRES = { naturelle: "Naturelle", accidentelle: "Accidentelle", criminelle: "Criminelle", indeterminee: "Indéterminée" };

async function uploadPlan(sortieId, file) {
  const form = new FormData();
  form.append("plan", file);
  await api(`/api/sorties/${sortieId}/plan`, { method: "POST", form });
}

async function sortieForm(reload) {
  try {
    const fm = makeForm();
    const picker = await dossierPicker(fm, (d) => fillResp(fm, d), {
      url: "/api/dossiers/leves", label: (d) => `${d.nom} ${d.prenoms} — levé le ${fmtDt(d.date_levee)} (n° ${d.numero_ordre}/${d.annee})`,
      empty: "Aucun corps levé en attente de sortie définitive" });
    const fileIn = h("input", { type: "file", accept: ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" });
    const content = h("div", { class: "grid" },
      picker.count ? null : h("div", { class: "form-error" }, "Aucun corps levé : enregistrez d'abord la levée dans le registre « 3 - Levée »."),
      h("div", { class: "fieldset-title" }, "Défunt (corps levé)"), ...picker.nodes,
      field("Date et heure de la sortie définitive *", fm.input("date_sortie", { type: "datetime-local", value: nowLocalInput() })),
      field("Genre de mort (selon le certificat) *", fm.select("genre_mort", Object.entries(GENRES))),
      h("div", { class: "fieldset-title" }, "Lieu d'inhumation"),
      field("Région *", fm.input("region", { maxlength: 80 })), field("Département *", fm.input("departement", { maxlength: 80 })),
      field("Arrondissement *", fm.input("arrondissement", { maxlength: 80 })), field("Village *", fm.input("village", { maxlength: 80 })),
      field("Date d'inhumation *", fm.input("date_inhumation", { type: "date", value: todayInput() })),
      field("Plan de localisation (PDF, PNG ou JPEG, 5 Mo max)", fileIn),
      ...respSection(fm), ...(await thanatoSection(fm)));
    picker.init(); bindService(fm, "date_sortie");
    openForm({
      title: "Nouvelle sortie définitive — remise à la famille", color: "red", content, submitClass: "red", submitLabel: "Enregistrer la sortie",
      onSubmit: async () => {
        const f = fileIn.files[0];
        if (f && f.size > 5 * 1024 * 1024) throw new Error("Le plan de localisation dépasse 5 Mo.");
        const body = { dossier_id: fm.num("dossier_id"), date_sortie: fm.get("date_sortie"), genre_mort: fm.get("genre_mort"), region: fm.get("region"),
          departement: fm.get("departement"), arrondissement: fm.get("arrondissement"), village: fm.get("village"), date_inhumation: fm.get("date_inhumation"),
          thanato_user_id: fm.num("thanato_user_id"), ...respPayload(fm) };
        const r = await api("/api/sorties", { method: "POST", body });
        let msg = `Sortie définitive n° ${r.numero} enregistrée.` + (r.solde_a_regler > 0 ? ` Attention : reste à payer ${money(r.solde_a_regler)}.` : "");
        if (f) { try { await uploadPlan(r.id, f); } catch (e) { msg += " Plan non archivé : " + e.message; } }
        toast(msg);
        reload();
      },
    });
  } catch (e) { toast(e.message, true); }
}

async function showPlan(r) {
  try {
    const blob = await apiBlob(`/api/sorties/${r.id}/plan`);
    window.open(URL.createObjectURL(blob), "_blank", "noopener");
  } catch (e) { toast(e.message, true); }
}

// Colonne « Localisation » : importer le plan de localisation de l'inhumation / le voir (œil)
function localisationCell(r, reload) {
  if (r.annule) return "—";
  const view = r.plan_fichier ? h("button", { class: "btn small", title: "Voir le plan de localisation", "aria-label": "Voir le plan", onclick: () => showPlan(r) }, "👁 Voir") : null;
  if (r.plan_fichier || !canWrite()) return view || h("span", { class: "sub" }, "Aucun plan");
  const input = h("input", { type: "file", accept: ".pdf,.png,.jpg,.jpeg", class: "hidden" });
  input.addEventListener("change", async () => {
    if (!input.files[0]) return;
    try { await uploadPlan(r.id, input.files[0]); toast("Plan de localisation archivé."); reload(); } catch (e) { toast(e.message, true); }
  });
  return h("div", { class: "actions" }, h("button", { class: "btn small", onclick: () => input.click() }, "Importer plan"), input);
}

export const sorties = (main) => registerPage(main, {
  kind: "sorties", title: "4 - Sortie définitive (remise à la famille / inhumation)", color: "red", btn: "red", newLabel: "Nouvelle sortie", csvName: "registre-sorties",
  hint: "Sortie définitive d'un corps déjà levé. La colonne « Localisation » archive le plan de localisation de l'inhumation.", onNew: sortieForm,
  cols: [
    { h: "N° d'ordre", cell: (r) => h("b", null, numero(r)), csv: numero },
    { h: "Date et heure", cell: (r) => fmtDt(r.date_sortie), csv: (r) => fmtDt(r.date_sortie) },
    { h: "Défunt", cell: (r) => [...defunt(r), modifie(r)], csv: (r) => `${r.nom} ${r.prenoms}, ${age(r)}` },
    { h: "Cas", cell: casCell, csv: (r) => r.cas + (r.service ? " - " + r.service : "") },
    { h: "Genre de mort", cell: (r) => GENRES[r.genre_mort], csv: (r) => GENRES[r.genre_mort] },
    { h: "Lieu d'inhumation", cell: (r) => [`${r.village}, ${r.arrondissement}`, h("span", { class: "sub" }, `${r.departement} · ${r.region}`), h("span", { class: "sub" }, "le " + fmtDate(r.date_inhumation))],
      csv: (r) => `${r.region} / ${r.departement} / ${r.arrondissement} / ${r.village} (${fmtDate(r.date_inhumation)})` },
    { h: "Responsable du corps", cell: respCell, csv: (r) => `${r.resp_nom}; ${r.resp_contact}; ${r.resp_adresse}; ${r.resp_visa}` },
    { h: "Thanatopracteur", cell: thanatoCell, csv: (r) => `${r.thanato_nom} ${r.thanato_visa}` },
    { h: "Localisation", cell: localisationCell },
  ],
});

// ---------- MODIFIER : correction d'un enregistrement (tracée avant/après) ----------
function dtValue(s) { return (s || "").slice(0, 16); }

async function editForm(kind, r, reload) {
  const fm = makeForm();
  const parts = [...defuntSection(fm, r)];
  const extra = {};
  if (kind === "entrees") {
    parts.push(field("Date et heure d'entrée *", fm.input("date_entree", { type: "datetime-local", value: dtValue(r.date_entree) })));
    if (r.type_entree === "transfert_direct") {
      parts.push(field("Service d'origine *", fm.input("service_origine", { maxlength: 100, value: r.service_origine || "" })),
        field("Destination du transfert *", fm.input("destination_transfert", { maxlength: 150, value: r.destination_transfert || "" })));
    } else {
      const services = await api("/api/services");
      const svc = fm.select("service_id", [["", "— choisir —"], ...services.map((s) => [s.id, s.nom])], r.service_id || "");
      parts.push(field("Cas *", fm.select("cas", [["externe", "Externe"], ["interne", "Interne"]], r.cas)), field("Service du décès", svc),
        field("Type de chambre froide", fm.select("type_chambre", [["commune", "Commune"], ["individuelle", "Individuelle"]], r.type_chambre || "commune")),
        h("small", { class: "hint" }, "L'emplacement ne se corrige pas ici : un déplacement passe par un transfert ou une levée."));
    }
  } else if (kind === "transferts") {
    parts.push(field("Date et heure du transfert *", fm.input("date_transfert", { type: "datetime-local", value: dtValue(r.date_transfert) })),
      field("Lieu du transfert *", fm.input("lieu", { maxlength: 150, value: r.lieu || "" })));
    if (!r.entree_id) {
      const raisons = await api("/api/raisons");
      parts.push(field("Raison du transfert *", fm.select("raison_id", raisons.filter((x) => !x.reserve).map((x) => [x.id, x.libelle]), r.raison_id)),
        field("Précision (si « Autre »)", fm.input("raison_precision", { maxlength: 200, value: r.raison_precision || "" })));
    }
  } else if (kind === "levees") {
    const chap = h("input", { type: "checkbox", name: "chapelle_louee", checked: !!r.chapelle_louee });
    extra.chap = chap;
    parts.push(field("Date et heure de la levée *", fm.input("date_levee", { type: "datetime-local", value: dtValue(r.date_levee) })),
      field("Type de chambre froide", fm.select("type_chambre", [["commune", "Commune"], ["individuelle", "Individuelle"]], r.type_chambre)),
      h("label", { class: "check" }, chap, h("span", null, "Chapelle louée")),
      field("Type de chapelle", fm.select("type_chapelle", [["petite", "Petite"], ["grande", "Grande"]], r.type_chapelle || "petite")),
      h("small", { class: "hint" }, `Total actuel : ${money(r.montant_total)} — déjà versé : ${money(r.montant_verse)}. Les montants sont recalculés automatiquement.`));
  } else {
    parts.push(field("Date et heure de la sortie *", fm.input("date_sortie", { type: "datetime-local", value: dtValue(r.date_sortie) })),
      field("Genre de mort *", fm.select("genre_mort", Object.entries(GENRES), r.genre_mort)),
      field("Région *", fm.input("region", { maxlength: 80, value: r.region })), field("Département *", fm.input("departement", { maxlength: 80, value: r.departement })),
      field("Arrondissement *", fm.input("arrondissement", { maxlength: 80, value: r.arrondissement })), field("Village *", fm.input("village", { maxlength: 80, value: r.village })),
      field("Date d'inhumation *", fm.input("date_inhumation", { type: "date", value: r.date_inhumation })));
  }
  parts.push(...respSection(fm, r));
  openForm({
    title: `Modifier — n° ${numero(r)} (${r.nom})`, color: kind === "entrees" ? "blue" : kind === "sorties" ? "red" : "orange", submitLabel: "Enregistrer les corrections",
    content: h("div", { class: "grid" }, h("div", { class: "alert info" }, "Corrigez les erreurs de saisie. Chaque modification est conservée dans le journal (valeur avant / après)."), ...parts),
    onSubmit: async () => {
      const cur = {};
      for (const [name, el] of Object.entries(fm.f)) {
        if (["shelf", "thanato_user_id"].includes(name)) continue;
        cur[name] = el.type === "number" ? (el.value === "" ? undefined : Number(el.value)) : el.value.trim();
      }
      if (extra.chap) { cur.chapelle_louee = extra.chap.checked; if (!extra.chap.checked) delete cur.type_chapelle; }
      const body = {};
      for (const [k, v] of Object.entries(cur)) {
        const before = r[k];
        if (k === "service_id" || k === "raison_id") { if (kind === "entrees" && k === "service_id" && v === "") { /* externe */ } }
        if (String(v ?? "") !== String(before ?? "") && !(k === "chapelle_louee" && !!v === !!before)) body[k] = v;
      }
      if (kind === "entrees" && r.type_entree !== "transfert_direct" && ("cas" in body || "service_id" in body)) { body.cas = cur.cas; body.service_id = cur.cas === "interne" ? Number(cur.service_id) || undefined : undefined; }
      if ("age_value" in body || "age_unit" in body) { body.age_value = cur.age_value; body.age_unit = cur.age_unit; }
      if (kind === "levees" && ("chapelle_louee" in body || "type_chapelle" in body)) { body.chapelle_louee = cur.chapelle_louee; if (cur.chapelle_louee) body.type_chapelle = cur.type_chapelle; }
      if (kind === "transferts" && ("raison_id" in body || "raison_precision" in body)) { body.raison_id = Number(cur.raison_id); body.raison_precision = cur.raison_precision; }
      if (!Object.keys(body).length) throw new Error("Aucune modification : les valeurs sont identiques.");
      await api(`/api/${kind}/${r.id}`, { method: "PATCH", body });
      toast("Corrections enregistrées.");
      reload();
    },
  });
}
