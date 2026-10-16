// Plan d'occupation : box -> divisions -> emplacements (le sol X0 est signalé).
import { api } from "../api.js";
import { clear, fmtDt, h, modal, toast } from "../ui.js";

export async function plan(main) {
  const holder = h("div");
  main.append(h("div", { class: "page-head" }, h("h2", null, "Plan d'occupation des box"),
    h("div", { class: "actions" }, h("button", { class: "btn", onclick: () => load() }, "⟳ Actualiser"), h("button", { class: "btn", onclick: () => window.print() }, "🖨 Imprimer"))), holder);

  function details(slot) {
    modal({ title: `Emplacement ${slot.label}`, narrow: true, color: "red",
      body: [h("p", null, h("b", null, slot.nom)), h("p", { class: "hint" }, `Entrée n° ${slot.numero} le ${fmtDt(slot.date_entree)}`)],
      footer: [] });
  }

  async function load() {
    try {
      const data = await api("/api/plan");
      clear(holder);
      data.alerts.forEach((a) => holder.append(h("div", { class: "alert" }, "⚠ " + a)));
      if (!data.shelves.length) holder.append(h("div", { class: "card" }, "Aucun box paramétré. Le responsable de la morgue doit créer les box dans le menu Paramétrage."));
      for (const s of data.shelves) {
        const card = h("div", { class: "card accent-blue" }, h("div", { class: "shelf-title" }, h("h3", null, "Box " + s.name),
          s.saturated ? h("span", { class: "badge b-red" }, "Saturé") : h("span", { class: "badge b-green" }, "Places disponibles")));
        for (const d of s.divisions) {
          const pct = d.capacity ? Math.round((d.occupied / d.capacity) * 100) : 0;
          card.append(h("div", { class: "div-row" + (d.is_floor ? " floor" : "") },
            h("div", { class: "div-label" }, d.label, h("span", { class: "sub" }, d.is_floor ? "Sol (débordement)" : "Division"),
              h("span", { class: "sub" }, `${d.occupied}/${d.capacity} occupés`),
              h("div", { class: "progress" + (d.free === 0 ? " full" : "") }, h("i", { style: null, "data-pct": pct }))),
            h("div", { class: "slots" }, d.slots.map((x) => x.occupied
              ? h("button", { class: "slot busy", title: x.nom ? `${x.nom} (n° ${x.numero})` : "Occupé", onclick: () => x.nom && details(x) }, x.label)
              : h("span", { class: "slot free", title: "Libre" }, x.label)))));
        }
        holder.append(card);
      }
      // largeur des barres de progression (CSSOM : compatible avec la politique de sécurité)
      holder.querySelectorAll("i[data-pct]").forEach((i) => { i.style.width = i.dataset.pct + "%"; });
    } catch (e) { toast(e.message, true); }
  }
  await load();
}
