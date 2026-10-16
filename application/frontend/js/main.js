// Point d'entrée : connexion, menu, navigation, barre de sécurité.
import { api, setToken, state, getToken, ApiError } from "./api.js";
import { clear, field, h, makeForm, toast } from "./ui.js";
import { entrees, levees, sorties, transferts } from "./pages/registres.js";
import { tarifs } from "./pages/tarifs.js";
import { annonces, refreshUnread } from "./pages/annonces.js";
import { recherche } from "./pages/recherche.js";
import { stats } from "./pages/stats.js";
import { rh } from "./pages/rh.js";
import { plan } from "./pages/plan.js";
import { config } from "./pages/config.js";
import { mfaPanel, setupFlow } from "./pages/mfa.js";
import { comptes, journal, newCodeForm, passwordForm, ROLE_LABELS, showRecoveryCode } from "./pages/comptes.js";

const $ = (id) => document.getElementById(id);
const ALL = ["thanatopracteur", "admin", "super_admin"];
const ADMIN = ["admin", "super_admin"];
const PAGES = [
  { id: "entrees", n: "1 - DÉPÔT", color: "blue", roles: ALL, render: entrees },
  { id: "transferts", n: "2 - TRANSFERT", color: "orange", roles: ALL, render: transferts },
  { id: "levees", n: "3 - LEVÉE", color: "orange", roles: ALL, render: levees },
  { id: "sorties", n: "4 - SORTIE DÉFINITIVE", color: "red", roles: ALL, render: sorties },
  { id: "recherche", n: "5 - RECHERCHE RAPIDE", roles: ALL, render: recherche },
  { id: "stats", n: "6 - STATISTIQUES", roles: ALL, render: stats },
  { id: "rh", n: "7 - GARDES", roles: ALL, render: rh },
  { id: "annonces", n: "✉ ANNONCES", roles: ALL, render: annonces },
  { sep: true },
  { id: "plan", n: "Plan des box", roles: ALL, render: plan },
  { id: "config", n: "Paramétrage", roles: ADMIN, render: config },
  { id: "tarifs", n: "Paramètres et tarifs", roles: ADMIN, render: tarifs },
  { id: "comptes", n: "Comptes", roles: ADMIN, render: comptes },
  { id: "journal", n: "Journal", roles: ADMIN, render: journal },
];
let current = null;

function showLogin(message = "") {
  setToken(null); state.user = null;
  $("app").classList.add("hidden");
  const root = $("login"); root.classList.remove("hidden"); clear(root);
  const fm = makeForm();
  const err = h("div", { class: "form-error" + (message ? "" : " hidden"), role: "alert" }, message);
  const btn = h("button", { class: "btn primary", type: "submit" }, "Se connecter");
  const form = h("form", { class: "login-card", novalidate: true },
    h("h1", null, "Morgue PEGINTI"), h("p", null, "Registres et statistiques du service de thanatopraxie"), err,
    h("div", { class: "grid" }, field("Identifiant", fm.input("username", { autocomplete: "username", autocapitalize: "none", required: true })),
      field("Mot de passe", fm.input("password", { type: "password", autocomplete: "current-password", required: true })), btn));
  form.addEventListener("submit", async (e) => {
    e.preventDefault(); err.classList.add("hidden"); btn.disabled = true;
    try {
      const r = await api("/api/login", { method: "POST", body: { username: fm.get("username"), password: fm.f.password.value }, noAuthEvent: true });
      if (r.etape === "2fa") return show2fa(r.ticket);
      setToken(r.token); await start();
    } catch (ex) { err.textContent = ex.message; err.classList.remove("hidden"); }
    finally { btn.disabled = false; }
  });
  root.append(form);
  form.append(h("button", { class: "linkbtn", type: "button", onclick: () => showRecovery() }, "Mot de passe oublié ?"),
    h("button", { class: "linkbtn", type: "button", onclick: () => showSignup() }, "Première visite ? Créer mon compte"));
  fm.f.username.focus();
}

// Seconde étape : code de l'application d'authentification (ou code de secours).
function show2fa(ticket) {
  const root = $("login"); clear(root);
  const fm = makeForm();
  const err = h("div", { class: "form-error hidden", role: "alert" });
  const btn = h("button", { class: "btn primary", type: "submit" }, "Vérifier");
  const form = h("form", { class: "login-card", novalidate: true },
    h("h1", null, "Vérification en deux étapes"), h("p", null, "Entrez le code à 6 chiffres affiché par votre application d'authentification. Téléphone perdu : utilisez un code de secours."), err,
    h("div", { class: "grid" }, field("Code", fm.input("code", { inputmode: "text", autocomplete: "one-time-code", autocapitalize: "characters", required: true })), btn),
    h("button", { class: "linkbtn", type: "button", onclick: () => showLogin() }, "← Retour à la connexion"));
  form.addEventListener("submit", async (e) => {
    e.preventDefault(); err.classList.add("hidden"); btn.disabled = true;
    try {
      const r = await api("/api/login/2fa", { method: "POST", body: { ticket, code: fm.get("code") }, noAuthEvent: true });
      setToken(r.token); await start();
      if (r.codes_restants !== undefined) toast(`Code de secours utilisé. Il vous en reste ${r.codes_restants}.`, r.codes_restants <= 2);
    } catch (ex) {
      err.textContent = ex.message; err.classList.remove("hidden");
      if (ex.status === 401 && /expiré/i.test(ex.message)) setTimeout(() => showLogin(ex.message), 1200);
    } finally { btn.disabled = false; }
  });
  root.append(form); fm.f.code.focus();
}

// Double authentification exigée par la politique de la morgue : activation avant d'entrer.
function showForced2fa(me) {
  $("app").classList.add("hidden");
  const root = $("login"); root.classList.remove("hidden"); clear(root);
  const holder = h("div");
  root.append(h("div", { class: "login-card" }, h("h1", null, "Activez la double authentification"),
    h("p", null, `Bonjour ${me.full_name}. La politique de la morgue exige un second facteur pour votre compte.`), holder,
    h("button", { class: "linkbtn", type: "button", onclick: () => showLogin() }, "Se déconnecter")));
  setupFlow(holder, () => start());
}

// Inscription : identifiant = nom du thanatopracteur ; mot de passe saisi puis confirmé ; validation par l'administration.
function showSignup() {
  const root = $("login"); clear(root);
  const fm = makeForm();
  const err = h("div", { class: "form-error hidden", role: "alert" });
  const btn = h("button", { class: "btn primary", type: "submit" }, "Envoyer ma demande");
  const form = h("form", { class: "login-card", novalidate: true },
    h("h1", null, "Créer mon compte"), h("p", null, "Votre nom sera votre identifiant. Un administrateur validera votre demande."), err,
    h("div", { class: "grid" }, field("Nom du thanatopracteur (identifiant) *", fm.input("nom", { maxlength: 100, autocomplete: "name" })),
      field("Visa", fm.input("visa", { maxlength: 50 })), field("Contact", fm.input("contact", { maxlength: 50, autocomplete: "tel" })),
      field("Mot de passe *", fm.input("password", { type: "password", autocomplete: "new-password" }), "10 caractères minimum, avec lettres et chiffres."),
      field("Confirmer le mot de passe *", fm.input("confirmation", { type: "password", autocomplete: "new-password" })), btn),
    h("button", { class: "linkbtn", type: "button", onclick: () => showLogin() }, "← Retour à la connexion"));
  form.addEventListener("submit", async (e) => {
    e.preventDefault(); err.classList.add("hidden"); btn.disabled = true;
    try {
      const r = await api("/api/inscription", { method: "POST", noAuthEvent: true, body: { nom: fm.get("nom"), visa: fm.get("visa"), contact: fm.get("contact"), password: fm.f.password.value, confirmation: fm.f.confirmation.value } });
      showLogin(r.message);
      $("login").querySelector(".form-error").classList.add("ok");
    } catch (ex) { err.textContent = ex.message; err.classList.remove("hidden"); }
    finally { btn.disabled = false; }
  });
  root.append(form); fm.f.nom.focus();
}

// Mot de passe oublié : identifiant + code de récupération personnel (remis au premier changement de mot de passe).
function showRecovery() {
  const root = $("login"); clear(root);
  const fm = makeForm();
  const err = h("div", { class: "form-error hidden", role: "alert" });
  const btn = h("button", { class: "btn primary", type: "submit" }, "Changer mon mot de passe");
  const form = h("form", { class: "login-card", novalidate: true },
    h("h1", null, "Mot de passe oublié"), h("p", null, "Saisissez votre identifiant et le code de récupération qui vous a été remis. Sans code, demandez une réinitialisation à l'administration."), err,
    h("div", { class: "grid" }, field("Identifiant", fm.input("username", { autocapitalize: "none", autocomplete: "username" })),
      field("Code de récupération", fm.input("code", { autocapitalize: "characters", autocomplete: "off", placeholder: "XXXX-XXXX-XXXX-XXXX" })),
      field("Nouveau mot de passe", fm.input("nouveau", { type: "password", autocomplete: "new-password" }), "10 caractères minimum, avec lettres et chiffres."),
      field("Confirmer le mot de passe", fm.input("confirmation", { type: "password", autocomplete: "new-password" })), btn),
    h("button", { class: "linkbtn", type: "button", onclick: () => showLogin() }, "← Retour à la connexion"));
  form.addEventListener("submit", async (e) => {
    e.preventDefault(); err.classList.add("hidden"); btn.disabled = true;
    try {
      const r = await api("/api/recuperation", { method: "POST", noAuthEvent: true, body: { username: fm.get("username"), code: fm.get("code"), nouveau: fm.f.nouveau.value, confirmation: fm.f.confirmation.value } });
      showLogin("Mot de passe modifié. Connectez-vous. Votre NOUVEAU code de récupération : " + r.code_recuperation + " (notez-le, il ne sera plus affiché).");
      $("login").querySelector(".form-error").classList.add("ok");
    } catch (ex) { err.textContent = ex.message; err.classList.remove("hidden"); }
    finally { btn.disabled = false; }
  });
  root.append(form); fm.f.username.focus();
}

function buildNav() {
  const nav = $("nav"); clear(nav);
  for (const p of PAGES) {
    if (p.sep) { nav.append(h("div", { class: "sep" })); continue; }
    if (!p.roles.includes(state.user.role)) continue;
    nav.append(h("button", { type: "button", "data-page": p.id, "data-c": p.color || "", onclick: () => go(p.id) }, p.n));
  }
  const foot = $("side-foot"); clear(foot);
  foot.append(h("div", { class: "who" }, state.user.full_name), h("div", null, ROLE_LABELS[state.user.role]),
    h("button", { class: "linkbtn", onclick: passwordForm }, "Changer mon mot de passe"),
    h("button", { class: "linkbtn", onclick: newCodeForm }, "Code de récupération"),
    h("button", { class: "linkbtn", onclick: () => mfaPanel().catch((e) => toast(e.message, true)) }, "Double authentification"),
    h("button", { class: "linkbtn", onclick: logout }, "Se déconnecter"));
}

async function refreshSecbar() {
  const bar = $("secbar");
  let libres = "";
  try { const p = await api("/api/plan"); libres = `${p.totaux.capacite_etageres - p.totaux.occupes_etageres} emplacements libres`; } catch { /* non bloquant */ }
  const d = new Date();
  clear(bar);
  bar.append(h("span", null, "🔒 ", h("b", null, "SÉCURITÉ"), " · accès par compte nominatif · saisies tracées"),
    h("span", null, "Utilisateur : ", h("b", null, state.user.username), ` (${ROLE_LABELS[state.user.role]})`),
    libres ? h("span", null, libres) : null, h("span", null, d.toLocaleDateString("fr-FR") + " " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })));
}

async function go(id, arg) {
  const page = PAGES.find((p) => p.id === id && p.roles && p.roles.includes(state.user.role)) || PAGES[0];
  current = page.id;
  document.querySelectorAll("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.page === page.id));
  const main = $("main"); clear(main);
  try { await page.render(main, arg); } catch (e) { main.append(h("div", { class: "form-error" }, e.message)); }
  refreshSecbar(); refreshUnread();
  window.scrollTo(0, 0);
}

// Premier accès avec un mot de passe provisoire (installation, compte créé par l'administration) : changement obligatoire.
function showForcedPassword(me) {
  $("app").classList.add("hidden");
  const root = $("login"); root.classList.remove("hidden"); clear(root);
  const fm = makeForm();
  const err = h("div", { class: "form-error hidden", role: "alert" });
  const btn = h("button", { class: "btn primary", type: "submit" }, "Enregistrer mon mot de passe");
  const form = h("form", { class: "login-card", novalidate: true },
    h("h1", null, "Choisissez votre mot de passe"), h("p", null, `Bonjour ${me.full_name}. Le mot de passe actuel est provisoire : choisissez-en un personnel pour continuer.`), err,
    h("div", { class: "grid" }, field("Mot de passe actuel (provisoire)", fm.input("ancien", { type: "password", autocomplete: "current-password" })),
      field("Nouveau mot de passe", fm.input("nouveau", { type: "password", autocomplete: "new-password" }), "10 caractères minimum, avec lettres et chiffres."),
      field("Confirmer le nouveau mot de passe", fm.input("confirmation", { type: "password", autocomplete: "new-password" })), btn),
    h("button", { class: "linkbtn", type: "button", onclick: () => showLogin() }, "Se déconnecter"));
  form.addEventListener("submit", async (e) => {
    e.preventDefault(); err.classList.add("hidden");
    if (fm.f.nouveau.value !== fm.f.confirmation.value) { err.textContent = "Le nouveau mot de passe et sa confirmation ne correspondent pas."; err.classList.remove("hidden"); return; }
    btn.disabled = true;
    try {
      const r = await api("/api/password", { method: "POST", body: { ancien: fm.f.ancien.value, nouveau: fm.f.nouveau.value } });
      await start();
      if (r.code_recuperation) showRecoveryCode(r.code_recuperation);
    }
    catch (ex) { err.textContent = ex.message; err.classList.remove("hidden"); }
    finally { btn.disabled = false; }
  });
  root.append(form); fm.f.ancien.focus();
}

async function start() {
  const me = await api("/api/me");
  if (me.doit_changer_mdp) return showForcedPassword(me);
  if (me.mfa_requise) return showForced2fa(me);
  state.user = me;
  try { state.etab = await api("/api/etablissement"); } catch { state.etab = null; }
  try { state.tarifs = await api("/api/parametres"); } catch { state.tarifs = null; }
  $("login").classList.add("hidden"); $("app").classList.remove("hidden");
  buildNav();
  await go("entrees");
}

function logout() { showLogin(); }

$("quick").addEventListener("submit", (e) => { e.preventDefault(); const q = $("quick-input").value.trim(); if (q && state.user) go("recherche", q); });
window.addEventListener("goto-page", (e) => { if (state.user) go(e.detail); });
window.addEventListener("mfa-required", () => { if (state.user) start().catch(() => {}); });
window.addEventListener("auth-expired", () => { if (state.user) showLogin("Session expirée. Veuillez vous reconnecter."); });

(async () => {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  if (!getToken()) return showLogin();
  try { await start(); } catch (e) { showLogin(e instanceof ApiError && e.status === 401 ? "" : e.message); }
})();
