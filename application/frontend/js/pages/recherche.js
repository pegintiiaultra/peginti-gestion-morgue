// 5 - Recherche rapide : par n°, nom du défunt, responsable ou téléphone.
import { api } from "../api.js";
import { clear, fmtDt, h, statutBadge, table, toast } from "../ui.js";

export async function recherche(main, arg = "") {
  const input = h("input", { type: "search", value: arg, placeholder: "Tapez N°, nom ou téléphone", "aria-label": "Recherche" });
  const out = h("div");
  main.append(h("div", { class: "page-head" }, h("h2", null, "5 - Recherche rapide")),
    h("div", { class: "card" }, h("div", { class: "field" }, input), out));

  async function run() {
    const q = input.value.trim();
    clear(out);
    if (q.length < 2) { out.append(h("p", { class: "hint" }, "Saisissez au moins 2 caractères.")); return; }
    try {
      const p = "?limit=50&q=" + encodeURIComponent(q);
      const [e, t, l, s] = await Promise.all([api("/api/entrees" + p), api("/api/transferts" + p), api("/api/levees" + p), api("/api/sorties" + p)]);
      const num = (r) => `${r.numero_ordre}/${r.annee}`;
      const who = (r) => [h("b", null, `${r.nom} ${r.prenoms || ""}`.trim()), h("span", { class: "sub" }, `${r.age_value} ${r.age_unit}`)];
      out.append(
        h("h3", null, `Entrées (${e.length})`),
        table({ color: "blue", head: ["N°", "Défunt", "Responsable", "Emplacement", "Entrée", "Statut"],
          rows: e.map((r) => ({ cls: r.annule ? "annule" : "", cells: [num(r), who(r), [r.resp_nom, h("span", { class: "sub" }, r.resp_contact)], r.emplacement, fmtDt(r.date_entree), r.annule ? "Annulé" : statutBadge(r.statut)] })) }),
        h("h3", null, `Transferts (${t.length})`),
        table({ color: "orange", head: ["N°", "Défunt", "Date", "Raison", "Lieu"],
          rows: t.map((r) => ({ cls: r.annule ? "annule" : "", cells: [num(r), who(r), fmtDt(r.date_transfert), r.raison, r.lieu] })) }),
        h("h3", null, `Levées (${l.length})`),
        table({ color: "orange", head: ["N°", "Défunt", "Date", "Paiement"],
          rows: l.map((r) => ({ cls: r.annule ? "annule" : "", cells: [num(r), who(r), fmtDt(r.date_levee), r.est_solde ? "Soldée" : `Reste ${r.reste_a_payer}`] })) }),
        h("h3", null, `Sorties définitives (${s.length})`),
        table({ color: "red", head: ["N°", "Défunt", "Date", "Inhumation"],
          rows: s.map((r) => ({ cls: r.annule ? "annule" : "", cells: [num(r), who(r), fmtDt(r.date_sortie), `${r.village}, ${r.arrondissement} (${r.region})`] })) }));
    } catch (err) { toast(err.message, true); }
  }
  let timer;
  input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(run, 300); });
  input.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { clearTimeout(timer); run(); } });
  input.focus();
  await run();
}
