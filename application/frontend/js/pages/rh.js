// 6 - Gardes et planning : systèmes 12 h / 24 h, équipes, agents, présence obligatoire jeudi-vendredi.
import { api, state } from "../api.js";
import { badge, clear, field, h, makeForm, openForm, toast } from "../ui.js";

const JOURS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."];
const MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
const canEdit = () => ["admin", "super_admin"].includes(state.user.role);
const monthKey = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
const shiftMonth = (key, n) => { const [y, m] = key.split("-").map(Number); return monthKey(new Date(y, m - 1 + n, 1)); };
const monthTitle = (key) => { const [y, m] = key.split("-").map(Number); return `${MOIS[m - 1]} ${y}`; };
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };

export async function rh(main) {
  let mois = monthKey(new Date()), equipes = [];
  const planHolder = h("div"), teamHolder = h("div");
  const title = h("h3", { class: "month-title" });
  const sysBadge = h("span");
  const actions = h("div", { class: "actions" });
  const phTitle = h("div", { class: "ph-title" }), phMeta = h("div", { class: "ph-meta" });
  const printHead = h("div", { class: "print-head" },
    h("div", { class: "ph-etab" }, (state.etab && state.etab.nom) || "Morgue", state.etab && state.etab.ville ? " — " + state.etab.ville : ""),
    phTitle, phMeta);
  const printFoot = h("div", { class: "print-foot" },
    h("div", null, "Le responsable de la morgue", h("br"), h("br"), "Visa et signature"),
    h("div", null, "L'administration de l'établissement", h("br"), h("br"), "Visa et signature"));
  teamHolder.classList.add("no-print");
  main.append(printHead, h("div", { class: "page-head" }, h("h2", null, "6 - Gardes et planning"), actions),
    h("div", { class: "card accent-blue" },
      h("div", { class: "page-head" }, h("div", { class: "actions" },
        h("button", { class: "btn small", onclick: () => { mois = shiftMonth(mois, -1); loadPlan(); } }, "‹ Mois précédent"), title,
        h("button", { class: "btn small", onclick: () => { mois = shiftMonth(mois, 1); loadPlan(); } }, "Mois suivant ›")), sysBadge),
      h("p", { class: "hint" }, "Règle : présence obligatoire de tous le jeudi et le vendredi, sauf l'équipe sortante (dont la garde se termine à 7h30 ce jour-là). Mercredi : levée / vidange systématique de la chambre froide."),
      planHolder), teamHolder, printFoot);

  // ----- planning -----
  async function setGarde(date, type, equipeId) {
    try { await api("/api/rh/planning", { method: "PUT", body: { date, type, equipe_id: equipeId ? Number(equipeId) : null } }); await loadPlan(); }
    catch (e) { toast(e.message, true); await loadPlan(); }
  }
  function drawPlan(p) {
    title.textContent = monthTitle(p.mois);
    phTitle.textContent = "PLANNING DES GARDES — " + monthTitle(p.mois).toUpperCase();
    phMeta.textContent = (p.systeme === "12h" ? "Système de 12 h : permanence 7h30-17h00, garde 17h00-7h30" : "Système de 24 h : garde de 7h30 à 7h30") + " · Imprimé le " + new Date().toLocaleString("fr-FR") + " par " + state.user.full_name;
    clear(sysBadge);
    sysBadge.append(badge(p.systeme === "12h" ? "Système 12 h : permanence 7h30-17h00, garde 17h00-7h30" : "Système 24 h : garde de 7h30 à 7h30", "blue"));
    const active = equipes.filter((e) => e.active);
    const head = ["Date", "Repères", ...p.types.map((t) => t.label)];
    const rows = p.jours.map((j) => {
      const d = new Date(j.date + "T00:00:00");
      const cells = p.types.map((t) => {
        const cur = j.gardes[t.id];
        if (!canEdit()) return cur ? cur.nom : h("span", { class: "hint" }, "—");
        const sel = h("select", { "aria-label": `${t.label} du ${j.date}` }, h("option", { value: "" }, "— non défini —"),
          ...active.map((e) => h("option", { value: e.id }, e.nom)));
        if (cur && !active.some((e) => e.id === cur.equipe_id)) sel.append(h("option", { value: cur.equipe_id }, cur.nom + " (désactivée)"));
        sel.value = cur ? String(cur.equipe_id) : "";
        sel.addEventListener("change", () => setGarde(j.date, t.id, sel.value));
        return h("div", null, sel, h("span", { class: "print-only" }, cur ? cur.nom : "—"));
      });
      const marks = [
        j.sortie_corps ? badge("Levée / vidange systématique", "orange") : null,
        j.presence_obligatoire ? badge("Présence obligatoire", "orange") : null,
        j.presence_obligatoire && j.equipe_sortante ? h("span", { class: "sub" }, "Équipe sortante : " + j.equipe_sortante.nom) : null,
        j.presence_obligatoire && j.agents_attendus ? h("details", null, h("summary", { class: "sub" }, `${j.agents_attendus.length} agent(s) attendu(s)`), h("small", null, j.agents_attendus.join(", ") || "—")) : null,
      ];
      return { cls: j.date === today() ? "today" : "", cells: [h("b", null, `${JOURS[j.jour_semaine]} ${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`), h("div", { class: "marks" }, marks), ...cells] };
    });
    const body = rows.map((r) => h("tr", { class: r.cls }, r.cells.map((c) => h("td", null, c))));
    clear(planHolder);
    planHolder.append(h("div", { class: "table-wrap" }, h("table", { class: "th-blue keep-last" }, h("thead", null, h("tr", null, head.map((t) => h("th", null, t)))), h("tbody", null, body))));
  }
  async function loadPlan() {
    try { const [p, e] = await Promise.all([api("/api/rh/planning?mois=" + mois), api("/api/rh/equipes")]); equipes = e.equipes; drawPlan(p); drawTeams(e); }
    catch (e) { toast(e.message, true); }
  }

  // ----- système, génération -----
  function generateForm() {
    const fm = makeForm(), check = h("input", { type: "checkbox", name: "ecraser" });
    openForm({ title: "Générer une rotation pour " + monthTitle(mois), narrow: true, submitLabel: "Générer",
      content: h("div", { class: "grid" },
        h("p", { class: "hint" }, "Propose une rotation des équipes actives. Vous pourrez ensuite modifier chaque case."),
        field("Décalage de départ (0 = première équipe le 1er du mois)", fm.input("decalage", { type: "number", min: 0, max: 50, value: 0 })),
        h("label", { class: "check" }, check, "Remplacer aussi les cases déjà remplies")),
      onSubmit: async () => { const r = await api("/api/rh/planning/generer", { method: "POST", body: { mois, decalage: fm.num("decalage") || 0, ecraser: check.checked } }); toast(`${r.cases_remplies} case(s) remplie(s).`); loadPlan(); } });
  }

  // ----- équipes et agents -----
  async function agentForm(agent, defaultTeam) {
    const people = await api("/api/personnel").catch(() => []);
    const fm = makeForm(), a = agent || {};
    openForm({ title: agent ? "Modifier l'agent" : "Nouvel agent",
      content: h("div", { class: "grid" }, field("Nom *", fm.input("nom", { maxlength: 100, value: a.nom || "" })), field("Fonction", fm.input("fonction", { maxlength: 80, value: a.fonction || "", placeholder: "Thanatopracteur, aide…" })),
        field("Visa", fm.input("visa", { maxlength: 50, value: a.visa || "" })), field("Contact", fm.input("contact", { maxlength: 50, value: a.contact || "" })),
        field("Équipe", fm.select("equipe_id", [["", "— sans équipe —"], ...equipes.filter((e) => e.active).map((e) => [e.id, e.nom])], a.equipe_id ?? defaultTeam ?? "")),
        field("Compte de connexion lié", fm.select("user_id", [["", "— aucun —"], ...people.map((u) => [u.id, `${u.full_name}`])], a.user_id ?? ""), "Permet de proposer cet agent comme thanatopracteur de service à la saisie.")),
      onSubmit: async () => {
        const body = { nom: fm.get("nom"), fonction: fm.get("fonction"), visa: fm.get("visa"), contact: fm.get("contact"), equipe_id: fm.num("equipe_id") ?? null, user_id: fm.num("user_id") ?? null };
        await api(agent ? `/api/rh/agents/${agent.id}` : "/api/rh/agents", { method: agent ? "PATCH" : "POST", body });
        toast(agent ? "Agent modifié." : "Agent ajouté."); loadPlan();
      } });
  }
  function teamForm() {
    const fm = makeForm();
    openForm({ title: "Nouvelle équipe", narrow: true, content: h("div", { class: "grid" }, field("Nom de l'équipe *", fm.input("nom", { maxlength: 60, placeholder: "Équipe A" }))),
      onSubmit: async () => { await api("/api/rh/equipes", { method: "POST", body: { nom: fm.get("nom") } }); toast("Équipe créée."); loadPlan(); } });
  }
  function renameTeam(e) {
    const fm = makeForm();
    openForm({ title: "Modifier l'équipe", narrow: true, content: h("div", { class: "grid" }, field("Nom de l'équipe *", fm.input("nom", { maxlength: 60, value: e.nom }))),
      onSubmit: async () => { await api(`/api/rh/equipes/${e.id}`, { method: "PATCH", body: { nom: fm.get("nom") } }); toast("Équipe modifiée."); loadPlan(); } });
  }
  async function patch(url, body, ok) { try { await api(url, { method: "PATCH", body }); if (ok) toast(ok); loadPlan(); } catch (e) { toast(e.message, true); } }

  function agentRow(a) {
    return h("div", { class: "div-row" },
      h("div", { class: "div-label" }, a.nom, h("span", { class: "sub" }, [a.fonction, a.visa ? "visa " + a.visa : "", a.contact].filter(Boolean).join(" · ")), a.compte ? h("span", { class: "sub" }, "Compte : " + a.compte) : null),
      canEdit() ? h("div", { class: "actions" }, h("button", { class: "btn small", onclick: () => agentForm(a) }, "Modifier"),
        h("button", { class: "btn small red", onclick: async () => { if (!confirm(`Supprimer définitivement l'agent « ${a.nom} » ?`)) return; try { await api(`/api/rh/agents/${a.id}`, { method: "DELETE" }); toast("Agent supprimé."); loadPlan(); } catch (e) { toast(e.message, true); } } }, "Supprimer")) : null);
  }
  function drawTeams(data) {
    clear(teamHolder);
    teamHolder.append(h("div", { class: "page-head" }, h("h3", null, "Équipes et agents"),
      canEdit() ? h("div", { class: "actions" }, h("button", { class: "btn small", onclick: teamForm }, "+ Équipe"), h("button", { class: "btn small", onclick: () => agentForm(null) }, "+ Agent")) : null));
    if (!data.equipes.length) teamHolder.append(h("div", { class: "card" }, "Aucune équipe. " + (canEdit() ? "Créez les équipes, puis ajoutez les agents." : "Le responsable de morgue doit créer les équipes.")));
    for (const e of data.equipes) {
      const agents = e.agents.filter((a) => a.active);
      teamHolder.append(h("div", { class: "card accent-blue" },
        h("div", { class: "page-head" }, h("div", { class: "shelf-title" }, h("h3", null, e.nom), e.active ? badge("Active", "green") : badge("Désactivée", "grey"), h("span", { class: "hint" }, `${agents.length} agent(s)`)),
          canEdit() ? h("div", { class: "actions" }, h("button", { class: "btn small", onclick: () => agentForm(null, e.id) }, "+ Agent"),
            h("button", { class: "btn small", onclick: () => renameTeam(e) }, "✎ Modifier"),
            h("button", { class: "btn small", onclick: () => patch(`/api/rh/equipes/${e.id}`, { active: !e.active }) }, e.active ? "Désactiver" : "Réactiver"),
            h("button", { class: "btn small red", onclick: async () => { if (!confirm(`Supprimer définitivement l'équipe « ${e.nom} » ? (ses agents resteront sans équipe)`)) return; try { await api(`/api/rh/equipes/${e.id}`, { method: "DELETE" }); toast("Équipe supprimée."); loadPlan(); } catch (x) { toast(x.message, true); } } }, "Supprimer")) : null),
        agents.length ? agents.map(agentRow) : h("p", { class: "hint" }, "Aucun agent dans cette équipe.")));
    }
    const loose = data.sans_equipe.filter((a) => a.active);
    if (loose.length) teamHolder.append(h("div", { class: "card" }, h("h3", null, "Agents sans équipe"), loose.map(agentRow)));
  }

  if (canEdit()) {
    async function choisir(v) {
      try { await api("/api/rh/systeme", { method: "PUT", body: { systeme: v } }); toast(v === "12h" ? "Système de garde de 12 h activé." : "Système de garde de 24 h activé."); drawToggle(v); loadPlan(); }
      catch (e) { toast(e.message, true); }
    }
    const b12 = h("button", { class: "btn", onclick: () => choisir("12h"), title: "Permanence 7h30-17h00 et garde 17h00-7h30" }, "Garde de 12 h");
    const b24 = h("button", { class: "btn", onclick: () => choisir("24h"), title: "De 7h30 (jour 1) à 7h30 (jour 2)" }, "Garde de 24 h");
    function drawToggle(v) { b12.classList.toggle("blue", v === "12h"); b24.classList.toggle("blue", v === "24h"); }
    api("/api/rh/planning?mois=" + mois).then((p) => drawToggle(p.systeme)).catch(() => {});
    actions.append(h("span", { class: "sub" }, "Système :"), b12, b24, h("button", { class: "btn", onclick: generateForm }, "Générer le mois"));
  }
  actions.append(h("button", { class: "btn", onclick: () => window.print() }, "🖨 Imprimer"));
  await loadPlan();
}
