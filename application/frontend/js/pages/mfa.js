// Double authentification (TOTP) : activation guidée, codes de secours, désactivation, politique de la morgue.
import { api } from "../api.js";
import { clear, field, h, makeForm, modal, openForm, toast } from "../ui.js";

function copy(text, msg) { try { navigator.clipboard.writeText(text); toast(msg); } catch { /* copie indisponible */ } }

// Les codes de secours ne sont montrés qu'une fois : chacun ouvre une session si le téléphone est perdu.
export function backupCodesView(codes, onDone, label = "J'ai noté mes codes") {
  const box = h("div", { class: "recovery codes" }, codes.join("\n"));
  const ok = h("button", { class: "btn primary", type: "button" }, label);
  ok.addEventListener("click", () => onDone());
  return h("div", { class: "grid" },
    h("p", null, h("b", null, "Codes de secours."), " Si vous perdez votre téléphone, chacun de ces codes ouvre votre session une seule fois à la place du code à 6 chiffres. Notez-les sur papier et gardez-les à part. Ils ne seront plus affichés."),
    box,
    h("div", { class: "actions" }, h("button", { class: "btn small", type: "button", onclick: () => copy(codes.join("\n"), "Codes copiés.") }, "Copier"), ok));
}

// Assistant en trois temps : mot de passe -> clé à saisir dans l'application -> code de contrôle -> codes de secours.
export function setupFlow(holder, onDone) {
  const err = h("div", { class: "form-error hidden", role: "alert" });
  const show = (msg) => { err.textContent = msg; err.classList.toggle("hidden", !msg); };
  const step1 = () => {
    const fm = makeForm();
    const btn = h("button", { class: "btn primary", type: "submit" }, "Continuer");
    const form = h("form", { class: "grid", novalidate: true },
      h("p", null, "1. Installez sur votre téléphone une application d'authentification (Google Authenticator, Microsoft Authenticator, Aegis, FreeOTP…). 2. Confirmez votre mot de passe pour générer votre clé."),
      field("Votre mot de passe", fm.input("password", { type: "password", autocomplete: "current-password" })), btn);
    form.addEventListener("submit", async (e) => {
      e.preventDefault(); show(""); btn.disabled = true;
      try { step2(await api("/api/2fa/preparer", { method: "POST", body: { password: fm.f.password.value } })); }
      catch (ex) { show(ex.message); } finally { btn.disabled = false; }
    });
    clear(holder); holder.append(err, form); fm.f.password.focus();
  };
  const step2 = (k) => {
    const fm = makeForm();
    const btn = h("button", { class: "btn primary", type: "submit" }, "Activer");
    const form = h("form", { class: "grid", novalidate: true },
      h("p", null, "Dans l'application, ajoutez un compte en choisissant « Saisir une clé de configuration » (type : basé sur l'heure), puis entrez cette clé :"),
      h("div", { class: "recovery" }, k.groupes),
      h("div", { class: "actions" },
        h("button", { class: "btn small", type: "button", onclick: () => copy(k.secret, "Clé copiée.") }, "Copier la clé"),
        h("a", { class: "btn small", href: k.uri }, "Ouvrir dans l'application (ce téléphone)")),
      field("Code à 6 chiffres affiché par l'application", fm.input("code", { inputmode: "numeric", autocomplete: "one-time-code", maxlength: 7, placeholder: "123456" }), "Vérifie que l'heure de votre téléphone est automatique."), btn);
    form.addEventListener("submit", async (e) => {
      e.preventDefault(); show(""); btn.disabled = true;
      try { const r = await api("/api/2fa/activer", { method: "POST", body: { code: fm.get("code") } }); clear(holder); holder.append(backupCodesView(r.codes_secours, onDone)); }
      catch (ex) { show(ex.message); } finally { btn.disabled = false; }
    });
    clear(holder); holder.append(err, form); fm.f.code.focus();
  };
  step1();
}

// Fenêtre « Double authentification » du menu.
export async function mfaPanel(onChange) {
  const st = await api("/api/2fa");
  const holder = h("div");
  const m = modal({ title: "Double authentification", narrow: true, body: holder, footer: [h("button", { class: "btn", type: "button", onclick: () => m.close() }, "Fermer")] });
  const done = () => { m.close(); toast("Double authentification activée."); if (onChange) onChange(); };
  if (!st.active) {
    holder.append(h("p", { class: "hint" }, st.exigee ? "La politique de la morgue l'exige pour votre rôle." : "Elle protège votre compte même si votre mot de passe est découvert : à chaque connexion, un code à 6 chiffres change toutes les 30 secondes."));
    const flow = h("div"); holder.append(flow); setupFlow(flow, done);
    return;
  }
  const err = h("div", { class: "form-error hidden", role: "alert" });
  holder.append(h("p", null, "✅ Active. Codes de secours restants : ", h("b", null, String(st.codes_restants)), st.codes_restants <= 2 ? " — pensez à en générer de nouveaux." : ""), err);
  const ask = (title, label, go) => {
    const fm = makeForm();
    openForm({ title, narrow: true, submitLabel: label,
      content: h("div", { class: "grid" }, field("Votre mot de passe", fm.input("password", { type: "password", autocomplete: "current-password" })),
        field("Code à 6 chiffres (ou code de secours)", fm.input("code", { autocomplete: "one-time-code" }))),
      onSubmit: () => go(fm.f.password.value, fm.get("code")) });
  };
  holder.append(h("div", { class: "actions" },
    h("button", { class: "btn", onclick: () => ask("Nouveaux codes de secours", "Générer", async (password, code) => {
      const r = await api("/api/2fa/codes", { method: "POST", body: { password, code } });
      m.close(); const mm = modal({ title: "Nouveaux codes de secours", narrow: true, body: backupCodesView(r.codes_secours, () => mm.close(), "J'ai noté mes codes"), footer: [] });
    }) }, "Nouveaux codes de secours"),
    st.exigee ? null : h("button", { class: "btn red", onclick: () => ask("Désactiver la double authentification", "Désactiver", async (password, code) => {
      await api("/api/2fa/desactiver", { method: "POST", body: { password, code } }); toast("Double authentification désactivée."); m.close(); if (onChange) onChange();
    }) }, "Désactiver")));
  if (st.exigee) holder.append(h("p", { class: "hint" }, "Exigée par la politique de la morgue : elle ne peut pas être désactivée depuis votre compte."));
}

// Politique (administrateur) : qui doit utiliser la double authentification.
export async function policyCard(canEdit) {
  const { politique } = await api("/api/2fa/politique");
  const sel = h("select", { disabled: !canEdit }, ...[["aucun", "Facultative pour tous"], ["admin", "Obligatoire pour les administrateurs"], ["tous", "Obligatoire pour tous les comptes"]].map(([v, l]) => h("option", { value: v }, l)));
  sel.value = politique;
  sel.addEventListener("change", async () => {
    try { await api("/api/2fa/politique", { method: "PUT", body: { politique: sel.value } }); toast("Politique enregistrée."); }
    catch (e) { toast(e.message, true); }
  });
  return h("div", { class: "card" }, h("h3", null, "Double authentification"),
    field("Politique de la morgue", sel, "Un compte concerné doit l'activer à sa prochaine connexion. Recommandé : obligatoire pour tous les comptes."));
}
