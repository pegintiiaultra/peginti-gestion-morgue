"""Ressources humaines : équipes, agents, systèmes de garde (12 h / 24 h), planning mensuel.

Règles métier :
  - système 12 h : permanence 7h30-17h00 (jour) et garde 17h00-7h30 (nuit)
  - système 24 h : garde de 7h30 (jour 1) à 7h30 (jour 2)
  - un seul système actif par morgue
  - présence obligatoire de tous le jeudi et le vendredi, sauf l'équipe sortante
    (= l'équipe dont la garde se termine à 7h30 ce jour-là)
  - levée / vidange systématique de la chambre froide : le mercredi
"""
import calendar
from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify, request

from core import CONFIG, ApiError, audit, body, choice, get_db, integer, login_required, name_exists, parse_date, text

bp = Blueprint("rh", __name__)

TYPES = {"12h": ("permanence", "garde"), "24h": ("24h",)}
LABELS = {"permanence": "Permanence (7h30-17h00)", "garde": "Garde (17h00-7h30)", "24h": "Garde de 24 h (7h30-7h30)"}
WEDNESDAY, THURSDAY, FRIDAY = 2, 3, 4
DEBUT_JOUR = 7 * 60 + 30
FIN_JOUR = 17 * 60


def get_systeme(db):
    row = db.execute("SELECT value FROM settings WHERE key = 'garde_systeme'").fetchone()
    return row["value"] if row else "12h"


def shift_for(dt, systeme):
    """Garde en cours à un instant donné : (date de début de la garde, type)."""
    minutes = dt.hour * 60 + dt.minute
    d = dt.date()
    if systeme == "24h":
        return (d if minutes >= DEBUT_JOUR else d - timedelta(days=1)), "24h"
    if DEBUT_JOUR <= minutes < FIN_JOUR:
        return d, "permanence"
    if minutes >= FIN_JOUR:
        return d, "garde"
    return d - timedelta(days=1), "garde"  # petit matin : encore la garde de la veille


def _guard_map(db, start, end):
    rows = db.execute(
        "SELECT g.date, g.type, e.id AS equipe_id, e.nom FROM gardes g JOIN equipes e ON e.id = g.equipe_id "
        "WHERE g.date BETWEEN ? AND ?", (start.isoformat(), end.isoformat())).fetchall()
    return {(r["date"], r["type"]): {"equipe_id": r["equipe_id"], "nom": r["nom"]} for r in rows}


def _agents_of(db, equipe_id):
    return db.execute(
        "SELECT a.id, a.nom, a.fonction, a.visa, a.user_id FROM agents a WHERE a.active = 1 AND a.equipe_id = ? ORDER BY a.nom",
        (equipe_id,)).fetchall()


# ---------- système actif ----------
@bp.put("/api/rh/systeme")
@login_required(*CONFIG)
def set_systeme():
    value = choice(body(), "systeme", "Système de garde", ("12h", "24h"))
    db = get_db()
    db.execute("INSERT INTO settings (key, value) VALUES ('garde_systeme', ?) "
               "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (value,))
    audit("systeme_garde_modifie", "settings", None, {"systeme": value})
    return jsonify({"systeme": value})


# ---------- équipes et agents ----------
@bp.get("/api/rh/equipes")
@login_required()
def list_equipes():
    db = get_db()
    users = {u["id"]: u["username"] for u in db.execute("SELECT id, username FROM users")}
    agents = db.execute("SELECT * FROM agents ORDER BY nom").fetchall()

    def view(a):
        return {"id": a["id"], "nom": a["nom"], "fonction": a["fonction"], "visa": a["visa"], "contact": a["contact"],
                "equipe_id": a["equipe_id"], "user_id": a["user_id"], "compte": users.get(a["user_id"]), "active": a["active"]}

    out = []
    for e in db.execute("SELECT id, nom, active FROM equipes ORDER BY id"):
        out.append({**dict(e), "agents": [view(a) for a in agents if a["equipe_id"] == e["id"]]})
    return jsonify({"equipes": out, "sans_equipe": [view(a) for a in agents if a["equipe_id"] is None]})


@bp.post("/api/rh/equipes")
@login_required(*CONFIG)
def add_equipe():
    nom = text(body(), "nom", "Nom de l'équipe", 60)
    db = get_db()
    if name_exists(db, "equipes", "nom", nom):
        raise ApiError("Cette équipe existe déjà.", 409)
    eid = db.execute("INSERT INTO equipes (nom) VALUES (?)", (nom,)).lastrowid
    audit("equipe_creee", "equipe", eid, {"nom": nom})
    return jsonify({"id": eid}), 201


@bp.patch("/api/rh/equipes/<int:eid>")
@login_required(*CONFIG)
def update_equipe(eid):
    data = body()
    db = get_db()
    if not db.execute("SELECT 1 FROM equipes WHERE id = ?", (eid,)).fetchone():
        raise ApiError("Équipe introuvable.", 404)
    changes = {}
    if "nom" in data:
        nom = text(data, "nom", "Nom de l'équipe", 60)
        if name_exists(db, "equipes", "nom", nom, eid):
            raise ApiError("Ce nom est déjà utilisé.", 409)
        db.execute("UPDATE equipes SET nom = ? WHERE id = ?", (nom, eid)); changes["nom"] = nom
    if "active" in data:
        db.execute("UPDATE equipes SET active = ? WHERE id = ?", (1 if data["active"] else 0, eid)); changes["active"] = bool(data["active"])
    if not changes:
        raise ApiError("Aucune modification demandée.")
    audit("equipe_modifiee", "equipe", eid, changes)
    return jsonify({"ok": True})


@bp.delete("/api/rh/equipes/<int:eid>")
@login_required(*CONFIG)
def delete_equipe(eid):
    db = get_db()
    row = db.execute("SELECT nom FROM equipes WHERE id = ?", (eid,)).fetchone()
    if not row:
        raise ApiError("Équipe introuvable.", 404)
    if db.execute("SELECT 1 FROM gardes WHERE equipe_id = ? LIMIT 1", (eid,)).fetchone():
        raise ApiError("Impossible de supprimer cette équipe : elle figure au planning des gardes. "
                       "Utilisez « Désactiver » ou retirez-la du planning.", 409)
    db.execute("UPDATE agents SET equipe_id = NULL WHERE equipe_id = ?", (eid,))
    db.execute("DELETE FROM equipes WHERE id = ?", (eid,))
    audit("equipe_supprimee", "equipe", eid, {"nom": row["nom"]})
    return jsonify({"ok": True})


def _check_links(db, data, agent_id=None):
    equipe_id = integer(data, "equipe_id", "Équipe", required=False)
    if equipe_id is not None and not db.execute("SELECT 1 FROM equipes WHERE id = ?", (equipe_id,)).fetchone():
        raise ApiError("Équipe introuvable.")
    user_id = integer(data, "user_id", "Compte", required=False)
    if user_id is not None:
        if not db.execute("SELECT 1 FROM users WHERE id = ? AND active = 1", (user_id,)).fetchone():
            raise ApiError("Compte utilisateur introuvable.")
        used = db.execute("SELECT id FROM agents WHERE user_id = ? AND id <> ?", (user_id, agent_id or 0)).fetchone()
        if used:
            raise ApiError("Ce compte est déjà lié à un autre agent.", 409)
    return equipe_id, user_id


@bp.post("/api/rh/agents")
@login_required(*CONFIG)
def add_agent():
    data = body()
    db = get_db()
    nom = text(data, "nom", "Nom de l'agent", 100)
    equipe_id, user_id = _check_links(db, data)
    aid = db.execute("INSERT INTO agents (nom, fonction, visa, contact, equipe_id, user_id) VALUES (?,?,?,?,?,?)",
                     (nom, text(data, "fonction", "Fonction", 80, False), text(data, "visa", "Visa", 50, False),
                      text(data, "contact", "Contact", 50, False), equipe_id, user_id)).lastrowid
    audit("agent_cree", "agent", aid, {"nom": nom, "equipe_id": equipe_id})
    return jsonify({"id": aid}), 201


@bp.patch("/api/rh/agents/<int:aid>")
@login_required(*CONFIG)
def update_agent(aid):
    data = body()
    db = get_db()
    if not db.execute("SELECT 1 FROM agents WHERE id = ?", (aid,)).fetchone():
        raise ApiError("Agent introuvable.", 404)
    fields, params, changes = [], [], {}
    for key, label, size in (("nom", "Nom de l'agent", 100), ("fonction", "Fonction", 80), ("visa", "Visa", 50), ("contact", "Contact", 50)):
        if key in data:
            fields.append(f"{key} = ?"); params.append(text(data, key, label, size, key == "nom")); changes[key] = params[-1]
    if "equipe_id" in data or "user_id" in data:
        equipe_id, user_id = _check_links(db, data, aid)
        if "equipe_id" in data:
            fields.append("equipe_id = ?"); params.append(equipe_id); changes["equipe_id"] = equipe_id
        if "user_id" in data:
            fields.append("user_id = ?"); params.append(user_id); changes["user_id"] = user_id
    if "active" in data:
        fields.append("active = ?"); params.append(1 if data["active"] else 0); changes["active"] = bool(data["active"])
    if not fields:
        raise ApiError("Aucune modification demandée.")
    db.execute(f"UPDATE agents SET {', '.join(fields)} WHERE id = ?", (*params, aid))
    audit("agent_modifie", "agent", aid, changes)
    return jsonify({"ok": True})


@bp.delete("/api/rh/agents/<int:aid>")
@login_required(*CONFIG)
def delete_agent(aid):
    db = get_db()
    row = db.execute("SELECT nom FROM agents WHERE id = ?", (aid,)).fetchone()
    if not row:
        raise ApiError("Agent introuvable.", 404)
    db.execute("DELETE FROM agents WHERE id = ?", (aid,))
    audit("agent_supprime", "agent", aid, {"nom": row["nom"]})
    return jsonify({"ok": True})


# ---------- planning mensuel ----------
@bp.get("/api/rh/planning")
@login_required()
def planning():
    mois = request.args.get("mois") or datetime.now().strftime("%Y-%m")
    try:
        first = datetime.strptime(mois + "-01", "%Y-%m-%d").date()
    except ValueError:
        raise ApiError("Mois invalide (format AAAA-MM).")
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    db = get_db()
    systeme = get_systeme(db)
    gmap = _guard_map(db, first - timedelta(days=1), last)
    agents = db.execute("SELECT a.nom, a.equipe_id, e.nom AS equipe FROM agents a LEFT JOIN equipes e ON e.id = a.equipe_id "
                        "WHERE a.active = 1 ORDER BY a.nom").fetchall()
    sortante_type = "garde" if systeme == "12h" else "24h"
    jours, d = [], first
    while d <= last:
        wd = d.weekday()
        prev = (d - timedelta(days=1)).isoformat()
        sortante = gmap.get((prev, sortante_type))
        obligatoire = wd in (THURSDAY, FRIDAY)
        attendus = None
        if obligatoire:
            attendus = [a["nom"] + (f" ({a['equipe']})" if a["equipe"] else "") for a in agents
                        if not (sortante and a["equipe_id"] == sortante["equipe_id"])]
        jours.append({"date": d.isoformat(), "jour_semaine": wd, "sortie_corps": wd == WEDNESDAY,
                      "presence_obligatoire": obligatoire, "equipe_sortante": sortante,
                      "gardes": {t: gmap.get((d.isoformat(), t)) for t in TYPES[systeme]}, "agents_attendus": attendus})
        d += timedelta(days=1)
    return jsonify({"systeme": systeme, "mois": mois, "types": [{"id": t, "label": LABELS[t]} for t in TYPES[systeme]], "jours": jours})


@bp.put("/api/rh/planning")
@login_required(*CONFIG)
def set_garde():
    data = body()
    db = get_db()
    date = parse_date(data.get("date"), "Date")
    systeme = get_systeme(db)
    type_ = choice(data, "type", "Type de garde", TYPES[systeme])
    equipe_id = integer(data, "equipe_id", "Équipe", required=False)
    if equipe_id is None:
        db.execute("DELETE FROM gardes WHERE date = ? AND type = ?", (date, type_))
        audit("garde_retiree", "garde", None, {"date": date, "type": type_})
        return jsonify({"ok": True})
    if not db.execute("SELECT 1 FROM equipes WHERE id = ? AND active = 1", (equipe_id,)).fetchone():
        raise ApiError("Équipe introuvable ou désactivée.")
    db.execute("INSERT INTO gardes (date, type, equipe_id) VALUES (?,?,?) "
               "ON CONFLICT(date, type) DO UPDATE SET equipe_id = excluded.equipe_id", (date, type_, equipe_id))
    audit("garde_definie", "garde", None, {"date": date, "type": type_, "equipe_id": equipe_id})
    return jsonify({"ok": True})


@bp.post("/api/rh/planning/generer")
@login_required(*CONFIG)
def generer():
    """Propose une rotation des équipes sur un mois (modifiable ensuite case par case)."""
    data = body()
    db = get_db()
    mois = text(data, "mois", "Mois", 7)
    try:
        first = datetime.strptime(mois + "-01", "%Y-%m-%d").date()
    except ValueError:
        raise ApiError("Mois invalide (format AAAA-MM).")
    decalage = integer(data, "decalage", "Décalage", 0, 50, required=False) or 0
    ecraser = bool(data.get("ecraser"))
    equipes = [r["id"] for r in db.execute("SELECT id FROM equipes WHERE active = 1 ORDER BY id")]
    if not equipes:
        raise ApiError("Créez d'abord au moins une équipe.")
    systeme, n, count = get_systeme(db), len(equipes), 0
    for i in range(calendar.monthrange(first.year, first.month)[1]):
        date = first.replace(day=i + 1).isoformat()
        wanted = {"24h": equipes[(i + decalage) % n]} if systeme == "24h" else {
            "permanence": equipes[(i + decalage) % n], "garde": equipes[(i + decalage - 1) % n]}
        for type_, equipe_id in wanted.items():
            exists = db.execute("SELECT 1 FROM gardes WHERE date = ? AND type = ?", (date, type_)).fetchone()
            if exists and not ecraser:
                continue
            db.execute("INSERT INTO gardes (date, type, equipe_id) VALUES (?,?,?) "
                       "ON CONFLICT(date, type) DO UPDATE SET equipe_id = excluded.equipe_id", (date, type_, equipe_id))
            count += 1
    audit("planning_genere", "garde", None, {"mois": mois, "cases": count, "ecraser": ecraser})
    return jsonify({"cases_remplies": count})


@bp.get("/api/rh/service")
@login_required()
def service_at():
    """Équipe et agents de service à un instant donné (sert à proposer le thanatopracteur à la saisie)."""
    at = request.args.get("at", "")
    try:
        dt = datetime.strptime(at, "%Y-%m-%dT%H:%M")
    except ValueError:
        raise ApiError("Date et heure invalides.")
    db = get_db()
    systeme = get_systeme(db)
    date, type_ = shift_for(dt, systeme)
    row = _guard_map(db, date, date).get((date.isoformat(), type_))
    agents = [dict(a) for a in _agents_of(db, row["equipe_id"])] if row else []
    return jsonify({"systeme": systeme, "garde": {"date": date.isoformat(), "type": type_, "label": LABELS[type_]},
                    "equipe": row, "agents": agents})
