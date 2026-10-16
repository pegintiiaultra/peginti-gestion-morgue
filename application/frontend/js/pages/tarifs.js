// Paramètres : tarifs (nuitées, chapelles, majoration, transfert) et horaires des levées.
import { api, state } from "../api.js";
import { policyCard } from "./mfa.js";
import { field, fcfa, h, makeForm, toast } from "../ui.js";

const PRIX = [
  ["prix_nuitee_commune", "Nuitée — chambre commune"], ["prix_nuitee_individuelle", "Nuitée — chambre individuelle"],
  ["prix_chapelle_petite", "Petite chapelle"], ["prix_chapelle_grande", "Grande chapelle"],
  ["prix_majoration", "Majoration (levée hors horaires / dimanche)"], ["prix_transfert", "Frais de transfert"],
];

export async function tarifs(main) {
  const p = await api("/api/parametres");
  const fm = makeForm();
  const canEdit = ["admin", "super_admin"].includes(state.user.role);
  const err = h("div", { class: "form-error hidden", role: "alert" });
  const btn = h("button", { class: "btn primary", type: "submit" }, "Enregistrer les paramètres");
  const grid = h("div", { class: "grid" },
    ...PRIX.map(([k, label]) => field(label, fm.input(k, { type: "number", min: 0, step: 1, inputmode: "numeric", value: p[k], disabled: !canEdit }))),
    field("Début des levées (heure)", fm.input("heure_debut_levee", { type: "number", min: 0, max: 23, value: p.heure_debut_levee, disabled: !canEdit })),
    field("Fin des levées (heure)", fm.input("heure_fin_levee", { type: "number", min: 1, max: 24, value: p.heure_fin_levee, disabled: !canEdit })),
    field("Devise", fm.input("devise", { maxlength: 10, value: p.devise, disabled: !canEdit })));
  const form = h("form", { class: "card", novalidate: true }, err, grid, canEdit ? h("div", { class: "actions" }, btn) : h("p", { class: "hint" }, "Lecture seule : seuls l'administrateur et le super administrateur modifient les tarifs."));
  form.addEventListener("submit", async (e) => {
    e.preventDefault(); err.classList.add("hidden"); btn.disabled = true;
    try {
      const body = { devise: fm.get("devise") };
      for (const k of [...PRIX.map((x) => x[0]), "heure_debut_levee", "heure_fin_levee"]) body[k] = Number(fm.get(k));
      await api("/api/parametres", { method: "PUT", body });
      state.tarifs = await api("/api/parametres");
      toast("Paramètres enregistrés.");
    } catch (ex) { err.textContent = ex.message; err.classList.remove("hidden"); }
    finally { btn.disabled = false; }
  });
  main.append(h("div", { class: "page-head" }, h("h2", null, "Paramètres et tarifs")),
    p.tarifs_configures ? null : h("div", { class: "alert warn" }, "Les tarifs n'ont pas encore été configurés : vérifiez-les avant la première levée."),
    form,
    canEdit ? await policyCard(true) : null,
    h("div", { class: "card" }, h("h3", null, "Règles de majoration appliquées automatiquement"),
      h("ul", null, h("li", null, "Lundi, mardi, samedi : normal entre les heures de levée, majoré en dehors."),
        h("li", null, "Jeudi et vendredi : normal dans les heures de levée, majoré après la fin."),
        h("li", null, "Mercredi (levée / vidange systématique) : majoré après la fin des levées."),
        h("li", null, "Dimanche : toute la journée majorée."))),
    h("p", { class: "hint" }, `Exemple : une nuitée en chambre commune = ${fcfa(p.prix_nuitee_commune, p.devise)}.`));
}
