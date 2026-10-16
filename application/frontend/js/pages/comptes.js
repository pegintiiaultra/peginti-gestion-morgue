// Comptes utilisateurs (administrateur technique) et changement de mot de passe personnel.
import { api, apiBlob, state } from "../api.js";
import { badge, clear, field, h, makeForm, openForm, table, toast } from "../ui.js";

export const ROLE_LABELS = { thanatopracteur: "Thanatopracteur", admin: "Administrateur", super_admin: "Super administrateur (DG)" };
// Rôles que le compte connecté peut créer : l'admin crée des thanatopracteurs (et le super admin unique) ; le super admin crée tout.
const creatable = () => state.user.role === "super_admin" ? ["thanatopracteur", "admin"] : ["thanatopracteur", "super_admin"];
const roleOptions = (list) => list.map((r) => [r, ROLE_LABELS[r]]);

// Le code de récupération n'est montré qu'une fois : il permet de refaire son mot de passe sans l'administration.
export function showRecoveryCode(code, then) {
  openForm({ title: "Votre code de récupération", narrow: true, submitLabel: "J'ai noté mon code",
    content: h("div", { class: "grid" },
      h("p", null, "Notez ce code et gardez-le en lieu sûr. Il vous permet de retrouver votre compte si vous oubliez votre mot de passe (« Mot de passe oublié ? » sur l'écran de connexion). Il ne sera plus affiché."),
      h("div", { class: "recovery" }, code),
      h("button", { class: "btn small", type: "button", onclick: () => { try { navigator.clipboard.writeText(code); toast("Code copié."); } catch { /* copie indisponible */ } } }, "Copier")),
    onSubmit: async () => { if (then) then(); } });
}

export function newCodeForm() {
  const fm = makeForm();
  openForm({ title: "Nouveau code de récupération", narrow: true, submitLabel: "Générer un nouveau code",
    content: h("div", { class: "grid" }, h("p", null, "L'ancien code ne fonctionnera plus."),
      field("Votre mot de passe", fm.input("password", { type: "password", autocomplete: "current-password" }))),
    onSubmit: async () => { const r = await api("/api/recuperation/code", { method: "POST", body: { password: fm.f.password.value } }); setTimeout(() => showRecoveryCode(r.code_recuperation), 50); } });
}

export function passwordForm() {
  const fm = makeForm();
  openForm({ title: "Changer mon mot de passe", narrow: true,
    content: h("div", { class: "grid" }, field("Mot de passe actuel", fm.input("ancien", { type: "password", autocomplete: "current-password" })),
      field("Nouveau mot de passe", fm.input("nouveau", { type: "password", autocomplete: "new-password" }), "10 caractères minimum, avec lettres et chiffres.")),
    onSubmit: async () => {
      const r = await api("/api/password", { method: "POST", body: { ancien: fm.f.ancien.value, nouveau: fm.f.nouveau.value } });
      toast("Mot de passe modifié.");
      if (r.code_recuperation) setTimeout(() => showRecoveryCode(r.code_recuperation), 50);
    } });
}

function userForm(reload) {
  const fm = makeForm();
  openForm({ title: "Nouveau compte",
    content: h("div", { class: "grid" }, field("Nom complet (= identifiant) *", fm.input("full_name", { maxlength: 100 })),
      field("Rôle *", fm.select("role", roleOptions(creatable()))), field("Visa", fm.input("visa", { maxlength: 50 })), field("Contact", fm.input("contact", { maxlength: 50 })),
      field("Mot de passe provisoire *", fm.input("password", { type: "password", autocomplete: "new-password" }), "10 caractères minimum, avec lettres et chiffres.")),
    onSubmit: async () => { await api("/api/users", { method: "POST", body: { full_name: fm.get("full_name"), role: fm.get("role"), visa: fm.get("visa"), contact: fm.get("contact"), password: fm.f.password.value } }); toast("Compte créé."); reload(); } });
}

function editUserForm(u, reload) {
  const fm = makeForm();
  const roleField = state.user.role === "super_admin" && u.role !== "super_admin" && u.id !== state.user.id
    ? field("Rôle", fm.select("role", roleOptions(["thanatopracteur", "admin"]), u.role)) : null;
  openForm({ title: "Modifier le compte — " + u.full_name,
    content: h("div", { class: "grid" }, field("Nom complet *", fm.input("full_name", { maxlength: 100, value: u.full_name || "" })),
      roleField, field("Visa", fm.input("visa", { maxlength: 50, value: u.visa || "" })), field("Contact", fm.input("contact", { maxlength: 50, value: u.contact || "" }))),
    onSubmit: async () => {
      const b = { full_name: fm.get("full_name"), visa: fm.get("visa"), contact: fm.get("contact") };
      if (roleField && fm.get("role") !== u.role) b.role = fm.get("role");
      await api(`/api/users/${u.id}`, { method: "PATCH", body: b }); toast("Compte modifié."); reload();
    } });
}

function resetForm(u, reload) {
  const fm = makeForm();
  openForm({ title: "Nouveau mot de passe — " + u.full_name, narrow: true,
    content: h("div", { class: "grid" }, field("Nouveau mot de passe", fm.input("password", { type: "password", autocomplete: "new-password" }))),
    onSubmit: async () => { await api(`/api/users/${u.id}`, { method: "PATCH", body: { password: fm.f.password.value } }); toast("Mot de passe réinitialisé."); reload(); } });
}

async function validateForm(u, reload) {
  const fm = makeForm();
  openForm({ title: "Valider la demande — " + u.full_name, narrow: true, submitLabel: "Valider le compte",
    content: h("div", { class: "grid" }, field("Rôle attribué", fm.select("role", roleOptions(state.user.role === "super_admin" ? ["thanatopracteur", "admin"] : ["thanatopracteur"]), "thanatopracteur")),
      h("p", { class: "hint" }, "Visa déclaré : " + (u.visa || "—") + " · Contact : " + (u.contact || "—"))),
    onSubmit: async () => { await api(`/api/users/${u.id}/valider`, { method: "POST", body: { role: fm.get("role") } }); toast("Compte validé."); reload(); } });
}

async function refuse(u, reload) {
  if (!confirm(`Refuser la demande de « ${u.full_name} » ?`)) return;
  try { await api(`/api/users/${u.id}/refuser`, { method: "POST", body: {} }); toast("Demande refusée."); reload(); } catch (e) { toast(e.message, true); }
}

// Suppression : l'administration choisit le motif, confirme avec son mot de passe ; le compte n'a plus aucun accès.
function deleteForm(u, reload) {
  const fm = makeForm();
  openForm({ title: "Supprimer le compte — " + u.full_name, color: "red", submitLabel: "Supprimer définitivement l'accès", submitClass: "red",
    content: h("div", { class: "grid" },
      h("p", null, "Le compte n'aura plus aucun accès à l'application. L'historique des registres et du journal est conservé."),
      field("Motif *", fm.select("motif", [["", "— Choisir le motif —"], ["revocation", "Révocation"], ["deces", "Décès"], ["demission", "Démission"]])),
      field("Votre mot de passe *", fm.input("password", { type: "password", autocomplete: "current-password" }))),
    onSubmit: async () => {
      if (!fm.get("motif")) throw new Error("Choisissez le motif de suppression.");
      await api(`/api/users/${u.id}`, { method: "DELETE", body: { motif: fm.get("motif"), password: fm.f.password.value } });
      toast("Compte supprimé."); reload();
    } });
}

const MOTIF = { revocation: "Révocation", deces: "Décès", demission: "Démission" };

export async function comptes(main) {
  const holder = h("div");
  const bk = h("button", { class: "btn", onclick: async () => {
    try { const blob = await apiBlob("/api/sauvegarde"); const a = h("a", { href: URL.createObjectURL(blob), download: `morgue-${new Date().toISOString().slice(0, 10)}.db` }); document.body.append(a); a.click(); a.remove(); toast("Sauvegarde téléchargée."); }
    catch (e) { toast(e.message, true); } } }, "Sauvegarde de la base");
  main.append(h("div", { class: "page-head" }, h("h2", null, "Comptes utilisateurs"), h("div", { class: "actions" }, bk, h("button", { class: "btn blue", onclick: () => userForm(load) }, state.user.role === "admin" ? "+ Nouveau compte" : "+ Nouveau compte"))), holder);
  async function load() {
    try {
      const users = await api("/api/users");
      clear(holder);
      const pending = users.filter((u) => u.statut === "en_attente");
      const actifs = users.filter((u) => u.statut === "actif");
      const archives = users.filter((u) => u.statut === "supprime");
      if (pending.length) {
        holder.append(h("h3", null, `Demandes en attente (${pending.length})`), table({ color: "orange", head: ["Nom (identifiant)", "Visa", "Contact", "Demande du", "Actions"],
          rows: pending.map((u) => ({ cells: [u.full_name, u.visa, u.contact, u.created_at.slice(0, 16),
            h("div", { class: "actions" }, h("button", { class: "btn small primary", onclick: () => validateForm(u, load) }, "Valider"), h("button", { class: "btn small red", onclick: () => refuse(u, load) }, "Refuser"))] })) }));
      }
      holder.append(h("h3", null, "Comptes actifs"), table({ color: "grey", head: ["Identifiant", "Nom", "Rôle", "Visa", "Statut", "2FA", "Actions"],
        rows: actifs.map((u) => ({ cls: u.active ? "" : "annule", cells: [u.username, u.full_name, ROLE_LABELS[u.role], u.visa, u.active ? badge("Actif", "green") : badge("Suspendu", "grey"),
          u.mfa_active ? badge("Activée", "green") : badge("Non", "grey"),
          h("div", { class: "actions" }, u.gerable && u.mfa_active ? h("button", { class: "btn small", title: "Téléphone perdu : désactive la double authentification de ce compte", onclick: async () => { if (!confirm(`Réinitialiser la double authentification de « ${u.full_name} » ?`)) return; try { await api(`/api/users/${u.id}/reset-2fa`, { method: "POST", body: {} }); toast("Double authentification réinitialisée."); load(); } catch (e) { toast(e.message, true); } } }, "Réinit. 2FA") : null, u.gerable || u.id === state.user.id ? h("button", { class: "btn small", onclick: () => editUserForm(u, load) }, "✎ Modifier") : null, u.gerable || u.id === state.user.id ? h("button", { class: "btn small", onclick: () => resetForm(u, load) }, "Mot de passe") : null,
            u.id === state.user.id || !u.gerable ? null : h("button", { class: "btn small", onclick: async () => { try { await api(`/api/users/${u.id}`, { method: "PATCH", body: { active: !u.active } }); load(); } catch (e) { toast(e.message, true); } } }, u.active ? "Suspendre" : "Réactiver"),
            u.id === state.user.id ? null : u.gerable ? h("button", { class: "btn small red", onclick: () => deleteForm(u, load) }, "Supprimer") : null)] })) }));
      if (archives.length) {
        holder.append(h("h3", null, "Comptes supprimés (archives)"), table({ color: "grey", head: ["Nom", "Rôle", "Motif", "Supprimé le", "Par"],
          rows: archives.map((u) => ({ cls: "annule", cells: [u.full_name, ROLE_LABELS[u.role], MOTIF[u.motif_suppression] || "", (u.supprime_le || "").slice(0, 16), u.supprime_par] })) }));
      }
    } catch (e) { toast(e.message, true); }
  }
  await load();
}


// Journal : libellés lisibles (le détail brut JSON reste consultable côté serveur)
const ACTIONS = {
  installation: "Installation", login: "Connexion", login_etape1: "Connexion (mot de passe validé)", login_echec: "Échec de connexion",
  login_2fa_echec: "Échec du code à 6 chiffres", "2fa_activee": "Double authentification activée", "2fa_desactivee": "Double authentification désactivée",
  "2fa_reinitialisee": "Double authentification réinitialisée", "2fa_codes_secours_renouveles": "Codes de secours renouvelés", politique_2fa_modifiee: "Règle de double authentification modifiée",
  mot_de_passe_modifie: "Mot de passe modifié", mot_de_passe_recupere: "Mot de passe récupéré", code_recuperation_cree: "Code de récupération créé", recuperation_echec: "Échec de récupération",
  inscription_demandee: "Demande d'inscription", inscription_refusee: "Inscription refusée", compte_valide: "Compte validé", compte_cree: "Compte créé", compte_modifie: "Compte modifié", compte_supprime: "Compte supprimé",
  etablissement_modifie: "Établissement modifié", tarifs_modifies: "Tarifs modifiés", systeme_garde_modifie: "Système de garde modifié",
  box_cree: "Box créé", box_renomme: "Box renommé", box_desactive: "Box désactivé", box_reactive: "Box réactivé", box_supprime: "Box supprimé",
  division_ajoutee: "Division ajoutée", division_modifiee: "Division modifiée", division_supprimee: "Division supprimée",
  service_ajoute: "Service ajouté", service_renomme: "Service renommé", service_modifie: "Service modifié", service_supprime: "Service supprimé",
  raison_ajoutee: "Raison ajoutée", raison_renommee: "Raison renommée", raison_modifiee: "Raison modifiée", raison_supprimee: "Raison supprimée",
  equipe_creee: "Équipe créée", equipe_modifiee: "Équipe modifiée", equipe_supprimee: "Équipe supprimée", agent_cree: "Agent créé", agent_modifie: "Agent modifié", agent_supprime: "Agent supprimé",
  garde_definie: "Garde définie", garde_retiree: "Garde retirée", planning_genere: "Planning généré",
  entree_creee: "Dépôt enregistré", entree_directe_creee: "Entrée directe enregistrée", transfert_cree: "Transfert enregistré", levee_creee: "Levée enregistrée", sortie_creee: "Sortie enregistrée",
  paiement_ajoute: "Versement ajouté", modification: "Enregistrement corrigé", annulation: "Enregistrement supprimé (annulé)", plan_archive: "Plan de localisation archivé",
  annonce_publiee: "Annonce publiée", annonce_modifiee: "Annonce modifiée", annonce_retiree: "Annonce supprimée", export_excel: "Export Excel", sauvegarde_telechargee: "Sauvegarde téléchargée",
};
const CLES = {
  name: "Nom", nom: "Nom", libelle: "Libellé", username: "Identifiant", role: "Rôle", divisions: "Divisions", sol: "Sol", capacite: "Capacité", prix_nuitee_commune: "Nuitée commune",
  prix_nuitee_individuelle: "Nuitée individuelle", prix_chapelle_petite: "Petite chapelle", prix_chapelle_grande: "Grande chapelle", prix_majoration: "Majoration", prix_transfert: "Transfert",
  heure_debut_levee: "Début des levées (h)", heure_fin_levee: "Fin des levées (h)", devise: "Devise", titre: "Titre", motif: "Motif", systeme: "Système", mois: "Mois", cases: "Cases", date: "Date", type: "Type",
  numero: "N°", division: "Division", box: "Box", numero_ordre: "N°", full_name: "Nom complet", active: "Actif", cases_remplies: "Cases remplies",
};
const money = (k, v) => (/^prix_/.test(k) ? Number(v).toLocaleString("fr-FR") + " FCFA" : v === true ? "oui" : v === false ? "non" : String(v));
function detailLisible(raw) {
  if (!raw) return "";
  let o; try { o = JSON.parse(raw); } catch { return raw; }
  if (o === null || typeof o !== "object") return String(o);
  return Object.entries(o).map(([k, v]) => {
    const lab = CLES[k] || k.replace(/_/g, " ");
    if (v && typeof v === "object" && ("avant" in v || "apres" in v)) return `${CLES[k] || lab.replace(/^prix /, "")} : ${money(k, v.avant ?? "—")} → ${money(k, v.apres ?? "—")}`;
    if (v && typeof v === "object") return `${lab} : ${JSON.stringify(v)}`;
    return `${lab} : ${money(k, v)}`;
  }).join(" · ");
}

export async function journal(main) {
  const q = makeForm();
  const holder = h("div", { class: "keep-last-wrap" });
  const form = h("form", { class: "actions", onsubmit: (e) => { e.preventDefault(); load(); } }, q.input("q", { placeholder: "Rechercher (utilisateur, action…)" }), h("button", { class: "btn", type: "submit" }, "Filtrer"));
  const phMeta = h("div", { class: "ph-meta" });
  const printHead = h("div", { class: "print-head" },
    h("div", { class: "ph-etab" }, (state.etab && state.etab.nom) || "Morgue", state.etab && state.etab.ville ? " — " + state.etab.ville : ""),
    h("div", { class: "ph-title" }, "JOURNAL DE SÉCURITÉ"), phMeta);
  const printFoot = h("div", { class: "print-foot" },
    h("div", null, "Le responsable de la morgue", h("br"), h("br"), "Visa et signature"),
    h("div", null, "L'administration de l'établissement", h("br"), h("br"), "Visa et signature"));
  main.append(printHead, h("div", { class: "page-head" }, h("h2", null, "Journal de sécurité"), h("div", { class: "actions" }, form, h("button", { class: "btn", onclick: () => window.print() }, "🖨 Imprimer / PDF"))), holder, printFoot);
  async function load() {
    try {
      const rows = await api("/api/audit?limit=300&q=" + encodeURIComponent(q.get("q")));
      clear(holder);
      const filtre = q.get("q");
      phMeta.textContent = `${rows.length} ligne(s)` + (filtre ? ` · filtre « ${filtre} »` : " · les plus récentes") + " · Imprimé le " + new Date().toLocaleString("fr-FR") + " par " + state.user.full_name;
      holder.append(table({ color: "grey", head: ["Date", "Utilisateur", "Action", "Détail"],
        rows: rows.map((r) => ({ cells: [r.ts, r.username || "", ACTIONS[r.action] || r.action, detailLisible(r.detail)] })) }));
    } catch (e) { toast(e.message, true); }
  }
  await load();
}
