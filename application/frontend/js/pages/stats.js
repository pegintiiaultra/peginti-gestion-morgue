// 5 - Tableau de bord statistique (calculé sur le trafic enregistré).
import { api, state } from "../api.js";
import { barChart, COLORS, flowChart, hbarChart, legend, pieChart, responsive } from "../charts.js";
import { clear, fcfa, field, h, makeForm, table, toast } from "../ui.js";

const GENRES = { naturelle: "Naturelle", accidentelle: "Accidentelle", criminelle: "Criminelle", indeterminee: "Indéterminée" };

export async function stats(main) {
  const fm = makeForm();
  const services = await api("/api/services").catch(() => []);
  const bar = h("div", { class: "card" }, h("div", { class: "grid" },
    field("Du", fm.input("from", { type: "date" })), field("Au", fm.input("to", { type: "date" })),
    field("Cas", fm.select("cas", [["", "Tous"], ["externe", "Externes"], ["interne", "Internes"]])),
    field("Service", fm.select("service_id", [["", "Tous"], ...services.map((s) => [s.id, s.nom])])),
    field("Mois (finances)", fm.input("mois", { type: "month", value: new Date().toISOString().slice(0, 7) }))));
  const body = h("div");
  main.append(h("div", { class: "page-head" }, h("h2", null, "6 - Statistiques"),
    h("div", { class: "actions" }, h("button", { class: "btn", onclick: () => window.print() }, "🖨 Imprimer / PDF"))), bar, body);

  const card = (title, svg, extra, wide) => h("div", { class: "card chart-card" + (wide ? " wide" : "") }, h("h3", null, title), svg, extra);
  const kpi = (c, n, label) => h("div", { class: "kpi " + c }, h("b", null, n), h("span", null, label));

  async function load() {
    const p = new URLSearchParams();
    for (const k of ["from", "to", "cas", "service_id"]) if (fm.get(k)) p.set(k, fm.get(k));
    try {
      const mois = fm.get("mois") || new Date().toISOString().slice(0, 7);
      const [d, plan, fin, impayes] = await Promise.all([api("/api/stats/global?" + p), api("/api/plan"), api("/api/stats/finances?mois=" + mois), api("/api/levees?non_soldees=1&limit=200")]);
      const dv = (state.tarifs && state.tarifs.devise) || "FCFA", money = (n) => fcfa(n, dv);
      const ca = d.chiffre_affaire_mensuel || [];
      clear(body);
      const f = d.flux, t = plan.totaux, libres = t.capacite_etageres - t.occupes_etageres;
      body.append(
        h("div", { class: "kpis" },
          kpi("blue", f.entrees, "Corps enregistrés"), kpi("orange", f.transferts, "Transferts"), kpi("red", f.sorties, "Sorties"),
          kpi("green", d.corps_presents_actuellement, "Corps présents actuellement"),
          kpi("grey", d.raison_dominante ? d.raison_dominante.nom : "—", "Raison dominante des transferts"),
          kpi("blue", money(fin.total_mois), `Chiffre d'affaires — ${mois}`), kpi("green", fin.nombre_soldees, "Levées soldées (mois)"), kpi("red", fin.nombre_non_soldees, "Levées non soldées (mois)"),
          kpi("grey", d.service_dominant ? d.service_dominant.nom : "—", "Service ayant enregistré le plus de décès")),
        h("div", { class: "charts" },
          card("Corps enregistrés, transferts et sorties par mois",
            responsive((w) => barChart({ labels: d.mois, series: [{ name: "Entrées", color: COLORS.blue, values: d.entrees_par_mois }, { name: "Transferts", color: COLORS.orange, values: d.transferts_par_mois }, { name: "Sorties", color: COLORS.red, values: d.sorties_par_mois }] }, w)),
            legend([[COLORS.blue, "Entrées"], [COLORS.orange, "Transferts"], [COLORS.red, "Sorties"]]), true),
          card("Cas externes et internes", responsive((w) => pieChart({ items: [{ label: "Externes", value: d.cas.externe || 0, color: COLORS.blue }, { label: "Internes", value: d.cas.interne || 0, color: COLORS.red }] }, w))),
          card("Décès par service hospitalier (cas internes)", responsive((w) => hbarChart({ items: d.services.map((x) => ({ label: x.nom, value: x.n })), color: COLORS.blue }, w))),
          card("Raisons des transferts", responsive((w) => hbarChart({ items: d.raisons.map((x) => ({ label: x.nom, value: x.n })), color: COLORS.orange }, w))),
          card("Genres de mort (sorties)", responsive((w) => barChart({ labels: Object.keys(d.genres_mort).map((k) => GENRES[k]), monthLabels: false, series: [{ name: "Sorties", color: COLORS.red, values: Object.values(d.genres_mort) }] }, w))),
          card("Devenir des corps enregistrés", responsive((w) => flowChart({ entrees: f.entrees, transferes: f.devenir_des_entrees.transferes, sortis: f.devenir_des_entrees.sortis, presents: f.devenir_des_entrees.en_conservation }, w))),
          card("Chiffre d'affaires par mois (12 derniers mois)", responsive((w) => barChart({ labels: ca.map((x) => x.mois), series: [{ name: "CA", color: COLORS.darkgreen, values: ca.map((x) => x.total) }] }, w)), h("p", { class: "hint" }, "Conservations + majorations + chapelles + frais de transfert, en " + dv + "."), true),
          card(`Répartition du chiffre d'affaires — ${mois}`, responsive((w) => pieChart({ items: [
            { label: "Conservations", value: fin.total_conservations, color: COLORS.blue }, { label: "Majorations", value: fin.total_majorations, color: COLORS.orange },
            { label: "Chapelles", value: fin.total_chapelles, color: COLORS.red }, { label: "Transferts", value: fin.total_transferts, color: COLORS.grey }] }, w)),
            h("p", { class: "hint" }, `Petites chapelles : ${fin.chapelles.petite.nombre} (${money(fin.chapelles.petite.montant)}) · grandes : ${fin.chapelles.grande.nombre} (${money(fin.chapelles.grande.montant)})`)),
          card("Occupation actuelle des étagères", responsive((w) => pieChart({ items: [{ label: "Occupés", value: t.occupes_etageres, color: COLORS.red }, { label: "Libres", value: libres, color: COLORS.green }] }, w)),
            h("p", { class: "hint" }, `${t.occupes_etageres} / ${t.capacite_etageres} emplacements (sol exclu). Information de contexte : les autres statistiques reposent sur le trafic enregistré.`))),
        h("h3", null, `Levées non soldées (${impayes.length})`),
        table({ color: "red", head: ["N°", "Défunt", "Date de levée", "Total", "Versé", "Reste à payer"],
          rows: impayes.map((r) => ({ cells: [`${r.numero_ordre}/${r.annee}`, `${r.nom} ${r.prenoms || ""}`.trim(), String(r.date_levee).slice(0, 10), money(r.montant_total), money(r.montant_verse), h("b", null, money(r.reste_a_payer))] })), empty: "Toutes les levées sont soldées." }));
    } catch (e) { toast(e.message, true); }
  }
  for (const el of Object.values(fm.f)) el.addEventListener("change", load);
  await load();
}
