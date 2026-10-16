// Paramétrage par les responsables : box (étagères), divisions, sol, services, raisons de transfert.
import { api, state } from "../api.js";
import { askMotif, badge, clear, field, h, makeForm, openForm, toast } from "../ui.js";

// Confirmation de suppression définitive (le serveur refuse si l'élément a déjà servi et propose « Désactiver »).
async function supprimer(url, nom, ok) {
  if (!confirm(`Supprimer définitivement « ${nom} » ?\n\nSi cet élément a déjà servi dans les registres, la suppression sera refusée : utilisez alors « Désactiver ».`)) return false;
  return act(() => api(url, { method: "DELETE" }), ok || "Supprimé.");
}

function renameForm(title, label, current, url, key, reload) {
  const fm = makeForm();
  openForm({ title, narrow: true, content: h("div", { class: "grid" }, field(label, fm.input(key, { maxlength: 80, value: current }))),
    onSubmit: async () => { await api(url, { method: "PATCH", body: { [key]: fm.get(key) } }); toast("Modifié."); reload(); } });
}

async function act(fn, ok) {
  try { await fn(); if (ok) toast(ok); return true; } catch (e) { toast(e.message, true); return false; }
}

function shelfForm(reload) {
  const fm = makeForm();
  const floorCap = field("Capacité du sol (emplacements)", fm.input("floor_capacity", { type: "number", min: 1, max: 26, value: 24 }));
  const floor = h("input", { type: "checkbox", name: "include_floor", checked: true });
  floor.addEventListener("change", () => floorCap.classList.toggle("hidden", !floor.checked));
  const content = h("div", { class: "grid" },
    field("Nom du box (1 à 3 lettres) *", fm.input("name", { maxlength: 3, placeholder: "A" })),
    field("Nombre de divisions *", fm.input("nb_divisions", { type: "number", min: 1, max: 12, value: 4 })),
    field("Capacité par division (24 = lettres a à x)", fm.input("capacity", { type: "number", min: 1, max: 26, value: 24 })),
    h("label", { class: "check" }, floor, "Inclure la division 0 (le sol, utilisée quand toutes les divisions sont pleines)"), floorCap);
  openForm({ title: "Ajouter un box (étagère)", content,
    onSubmit: async () => {
      const r = await api("/api/shelves", { method: "POST", body: { name: fm.get("name"), nb_divisions: fm.num("nb_divisions"), capacity: fm.num("capacity"), include_floor: floor.checked, floor_capacity: fm.num("floor_capacity") } });
      toast("Box créé : divisions et emplacements générés automatiquement."); reload(r);
    } });
}

function shelfCard(s, reload) {
  const card = h("div", { class: "card accent-blue" });
  const total = s.divisions.reduce((n, d) => n + d.occupied, 0);
  card.append(h("div", { class: "page-head" }, h("div", { class: "shelf-title" }, h("h3", null, "Box " + s.name), s.active ? badge("Actif", "green") : badge("Désactivé", "grey"), h("span", { class: "hint" }, `${total} corps présents`)),
    h("div", { class: "actions" },
      s.active ? h("button", { class: "btn small", onclick: async () => { const hasSol = s.divisions.some((d) => d.is_floor); await act(() => api(`/api/shelves/${s.id}/divisions`, { method: "POST", body: { is_floor: false } }), "Division ajoutée."); reload(); void hasSol; } }, "+ Division") : null,
      s.active && !s.divisions.some((d) => d.is_floor) ? h("button", { class: "btn small", onclick: async () => { await act(() => api(`/api/shelves/${s.id}/divisions`, { method: "POST", body: { is_floor: true } }), "Sol ajouté."); reload(); } }, "+ Sol (division 0)") : null,
      h("button", { class: "btn small", onclick: () => renameForm("Modifier le box " + s.name, "Nom du box (1 à 3 lettres)", s.name, `/api/shelves/${s.id}`, "name", reload) }, "✎ Modifier"),
      h("button", { class: "btn small", onclick: async () => { await act(() => api(`/api/shelves/${s.id}`, { method: "PATCH", body: { active: !s.active } }), s.active ? "Box désactivé." : "Box réactivé."); reload(); } }, s.active ? "Désactiver" : "Réactiver"),
      h("button", { class: "btn small red", onclick: async () => { if (await supprimer(`/api/shelves/${s.id}`, "Box " + s.name, "Box supprimé.")) reload(); } }, "Supprimer"))));
  for (const d of s.divisions) {
    const cap = h("input", { type: "number", min: 1, max: 26, value: d.capacity, "aria-label": "Capacité " + d.label });
    card.append(h("div", { class: "div-row" + (d.is_floor ? " floor" : "") },
      h("div", { class: "div-label" }, d.label, h("span", { class: "sub" }, d.is_floor ? "Sol" : "Division")),
      h("div", { class: "actions" }, h("span", { class: "hint" }, `${d.occupied} occupé(s) ·`), cap, h("span", { class: "hint" }, "emplacements"),
        h("button", { class: "btn small", onclick: async () => { await act(() => api(`/api/divisions/${d.id}`, { method: "PATCH", body: { capacity: Number(cap.value) } }), "Capacité modifiée."); reload(); } }, "✎ Modifier"),
        h("button", { class: "btn small", onclick: async () => { await act(() => api(`/api/divisions/${d.id}`, { method: "PATCH", body: { active: !d.active } }), d.active ? "Division désactivée." : "Division réactivée."); reload(); } }, d.active ? "Désactiver" : "Réactiver"),
        h("button", { class: "btn small red", onclick: async () => { if (await supprimer(`/api/divisions/${d.id}`, d.label, "Division supprimée.")) reload(); } }, "Supprimer"),
        d.active ? null : badge("Désactivée", "grey"))));
  }
  return card;
}

function listCard(title, color, items, label, toggleUrl, addUrl, addField, reload) {
  const input = h("input", { type: "text", maxlength: 80, placeholder: "Nouvel élément" });
  const card = h("div", { class: "card accent-" + color }, h("h3", null, title));
  card.append(h("div", { class: "actions" }, h("div", { class: "field" }, input),
    h("button", { class: "btn small", onclick: async () => { if (!input.value.trim()) return; await act(() => api(addUrl, { method: "POST", body: { [addField]: input.value.trim() } }), "Ajouté."); reload(); } }, "Ajouter")));
  items.forEach((it) => card.append(h("div", { class: "div-row" }, h("div", { class: "div-label" }, label(it), it.active ? null : h("span", { class: "sub" }, "désactivé")),
    h("div", { class: "actions" }, it.est_autre || it.reserve ? h("span", { class: "hint" }, it.est_autre ? "Choix « autre » : précision obligatoire" : "Raison système (transfert direct)") : [
      h("button", { class: "btn small", onclick: () => renameForm("Modifier", "Nouveau libellé", label(it), `${toggleUrl}/${it.id}`, addField, reload) }, "✎ Modifier"),
      h("button", { class: "btn small", onclick: async () => { await act(() => api(`${toggleUrl}/${it.id}`, { method: "PATCH", body: { active: !it.active } })); reload(); } }, it.active ? "Désactiver" : "Réactiver"),
      h("button", { class: "btn small red", onclick: async () => { if (await supprimer(`${toggleUrl}/${it.id}`, label(it))) reload(); } }, "Supprimer")]))));
  return card;
}

function etabCard() {
  const fm = makeForm();
  const e = state.etab || {};
  const card = h("div", { class: "card accent-blue" }, h("h3", null, "Établissement (en-tête des registres imprimés)"),
    h("div", { class: "inline" }, field("Nom de l'hôpital / de la morgue", fm.input("nom", { maxlength: 120, value: e.nom || "" })), field("Ville", fm.input("ville", { maxlength: 80, value: e.ville || "" }))),
    h("button", { class: "btn blue", type: "button", onclick: async () => {
      try { await api("/api/etablissement", { method: "PUT", body: { nom: fm.get("nom"), ville: fm.get("ville") } }); state.etab = { nom: fm.get("nom"), ville: fm.get("ville") }; toast("Établissement enregistré."); } catch (ex) { toast(ex.message, true); }
    } }, "Enregistrer"));
  return card;
}

export async function config(main) {
  const holder = h("div");
  main.append(h("div", { class: "page-head" }, h("h2", null, "Paramétrage"),
    h("div", { class: "actions" }, h("button", { class: "btn blue", onclick: () => shelfForm(load) }, "+ Ajouter un box"))),
    h("p", { class: "hint" }, "Renseignez les box (étagères) de vos chambres froides et leurs divisions : l'application génère automatiquement les emplacements (ex. A3c) et la logique d'enregistrement. Un box ou une division contenant des corps ne peut pas être désactivé."),
    holder);
  async function load() {
    try {
      const [shelves, services, raisons] = await Promise.all([api("/api/shelves"), api("/api/services?all=1"), api("/api/raisons?all=1")]);
      clear(holder);
      holder.append(etabCard());
      if (!shelves.length) holder.append(h("div", { class: "card" }, "Aucun box pour l'instant. Cliquez sur « Ajouter un box »."));
      shelves.forEach((s) => holder.append(shelfCard(s, load)));
      holder.append(
        listCard("Services hospitaliers (cas internes)", "blue", services, (x) => x.nom, "/api/services", "/api/services", "nom", load),
        listCard("Raisons de transfert", "orange", raisons, (x) => x.libelle, "/api/raisons", "/api/raisons", "libelle", load));
    } catch (e) { toast(e.message, true); }
  }
  await load();
}
