// Annonces : fenêtre de rédaction pour l'administration, boîte de réception pour tous (admins inclus).
import { api, state } from "../api.js";
import { clear, field, fmtDt, h, makeForm, openForm, toast } from "../ui.js";

const isAdmin = () => ["admin", "super_admin"].includes(state.user.role);

export async function refreshUnread() {
  const btn = document.querySelector('#nav button[data-page="annonces"]');
  if (!btn) return;
  try {
    const { non_lues } = await api("/api/annonces/non-lues");
    btn.querySelector(".pill")?.remove();
    if (non_lues) btn.append(h("span", { class: "pill", "aria-label": `${non_lues} non lu(s)` }, String(non_lues)));
  } catch { /* non bloquant */ }
}

export async function annonces(main) {
  const holder = h("div");
  const title = isAdmin() ? "Annonces" : "Boîte de réception";
  const readAll = h("button", { class: "btn small", onclick: async () => { try { await api("/api/annonces/lues", { method: "POST", body: {} }); await load(); } catch (e) { toast(e.message, true); } } }, "Tout marquer comme lu");
  main.append(h("div", { class: "page-head" }, h("h2", null, title), h("div", { class: "actions" }, readAll)));

  if (isAdmin()) {
    const fm = makeForm();
    const important = h("input", { type: "checkbox", name: "important" });
    const err = h("div", { class: "form-error hidden", role: "alert" });
    const send = h("button", { class: "btn primary", type: "submit" }, "Publier à tous les comptes");
    const area = h("textarea", { name: "corps", rows: 4, maxlength: 2000, placeholder: "Votre message : il sera reçu par tous les comptes (thanatopracteurs et administrateurs)." });
    const form = h("form", { class: "card", novalidate: true }, h("h3", null, "Nouvelle annonce"), err,
      h("div", { class: "grid" }, field("Titre *", fm.input("titre", { maxlength: 120 })), field("Message *", area),
        h("label", { class: "check" }, important, h("span", null, "Marquer comme important"))), h("div", { class: "actions" }, send));
    form.addEventListener("submit", async (e) => {
      e.preventDefault(); err.classList.add("hidden"); send.disabled = true;
      try {
        await api("/api/annonces", { method: "POST", body: { titre: fm.get("titre"), corps: area.value, important: important.checked } });
        fm.f.titre.value = ""; area.value = ""; important.checked = false; toast("Annonce publiée."); await load();
      } catch (ex) { err.textContent = ex.message; err.classList.remove("hidden"); }
      finally { send.disabled = false; }
    });
    main.append(form);
  }
  main.append(holder);

  function editAnnonce(a) {
    const fm = makeForm(), imp = h("input", { type: "checkbox", checked: !!a.important });
    const area = h("textarea", { rows: 5, maxlength: 2000 }, a.corps); area.value = a.corps;
    openForm({ title: "Modifier l'annonce", content: h("div", { class: "grid" }, field("Titre *", fm.input("titre", { maxlength: 120, value: a.titre })), field("Message *", area), h("label", { class: "check" }, imp, h("span", null, "Marquer comme important"))),
      onSubmit: async () => { await api(`/api/annonces/${a.id}`, { method: "PATCH", body: { titre: fm.get("titre"), corps: area.value, important: imp.checked } }); toast("Annonce modifiée."); await load(); } });
  }

  async function load() {
    const rows = await api("/api/annonces");
    clear(holder);
    if (!rows.length) holder.append(h("p", { class: "hint" }, "Aucune annonce pour le moment."));
    for (const a of rows) {
      const card = h("article", { class: "card annonce" + (a.lu ? "" : " nonlue") + (a.important ? " important" : "") },
        h("div", { class: "annonce-head" }, h("b", null, (a.important ? "❗ " : "") + a.titre), a.lu ? null : h("span", { class: "badge b-orange" }, "Nouveau")),
        h("p", { class: "annonce-corps" }, a.corps),
        h("div", { class: "sub" }, `${a.auteur_nom} · ${fmtDt(a.created_at.replace(" ", "T") + "Z")}`),
        h("div", { class: "actions" },
          a.lu ? null : h("button", { class: "btn small", onclick: async () => { try { await api(`/api/annonces/${a.id}/lu`, { method: "POST", body: {} }); await load(); } catch (e) { toast(e.message, true); } } }, "Marquer comme lu"),
          isAdmin() && (a.auteur_id === state.user.id || state.user.role === "super_admin")
            ? h("button", { class: "btn small", onclick: () => editAnnonce(a) }, "✎ Modifier") : null,
          isAdmin() && (a.auteur_id === state.user.id || state.user.role === "super_admin")
            ? h("button", { class: "btn small red", onclick: async () => { if (!confirm("Supprimer cette annonce pour tous ?")) return; try { await api(`/api/annonces/${a.id}`, { method: "DELETE" }); await load(); } catch (e) { toast(e.message, true); } } }, "Supprimer") : null));
      holder.append(card);
    }
    refreshUnread();
  }
  await load();
}
