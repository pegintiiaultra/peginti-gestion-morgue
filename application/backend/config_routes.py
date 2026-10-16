"""Paramétrage : étagères (box), divisions, sol (X0), services, raisons de transfert. Plan d'occupation."""
import re

from flask import Blueprint, g, jsonify, request

from core import (ALL, CONFIG, LETTERS, ApiError, audit, body, get_db, integer, login_required,
                  name_exists, text)
from db import tx

bp = Blueprint("config", __name__)

DEFAULT_CAPACITY = 24  # lettres a à x


def shelf_label(shelf_name, number, letter=None):
    return f"{shelf_name}{number}{letter or ''}"


def occupied_letters(db, division_id):
    return {r["slot_letter"] for r in db.execute(
        "SELECT slot_letter FROM dossiers WHERE division_id = ?", (division_id,))}


def shelf_numbered_saturated(db, shelf_id):
    """Vrai quand toutes les divisions numérotées actives de l'étagère sont pleines."""
    divs = db.execute("SELECT id, capacity FROM divisions WHERE shelf_id = ? AND number > 0 AND active = 1",
                      (shelf_id,)).fetchall()
    if not divs:
        return False
    return all(len(occupied_letters(db, d["id"])) >= d["capacity"] for d in divs)


def bodies_in_shelf(db, shelf_id):
    return db.execute(
        "SELECT COUNT(*) FROM dossiers d JOIN divisions v ON v.id = d.division_id WHERE v.shelf_id = ?",
        (shelf_id,)).fetchone()[0]


def division_refs(db, did):
    """Nombre de traces (dossiers, registres) qui renvoient à une division : elle ne peut alors plus être supprimée."""
    n = db.execute("SELECT COUNT(*) FROM dossiers WHERE division_id = ?", (did,)).fetchone()[0]
    for table in ("transferts", "levees", "sorties"):
        n += db.execute(f"SELECT COUNT(*) FROM {table} WHERE origine_division_id = ?", (did,)).fetchone()[0]
    return n


# ---------- configuration des étagères ----------
def shelves_tree(db):
    out = []
    for s in db.execute("SELECT id, name, active FROM shelves ORDER BY name"):
        divs = []
        for d in db.execute("SELECT id, number, capacity, active FROM divisions WHERE shelf_id = ? "
                            "ORDER BY CASE WHEN number = 0 THEN 999 ELSE number END", (s["id"],)):
            occ = len(occupied_letters(db, d["id"]))
            divs.append({**dict(d), "label": shelf_label(s["name"], d["number"]), "occupied": occ,
                         "free": max(d["capacity"] - occ, 0), "is_floor": d["number"] == 0})
        out.append({**dict(s), "divisions": divs})
    return out


@bp.get("/api/shelves")
@login_required()
def list_shelves():
    return jsonify(shelves_tree(get_db()))


@bp.post("/api/shelves")
@login_required(*CONFIG)
def create_shelf():
    data = body()
    db = get_db()
    name = text(data, "name", "Nom du box", 3).upper()
    if not re.fullmatch(r"[A-Z]{1,3}", name):
        raise ApiError("Le nom du box doit être composé de 1 à 3 lettres (ex. A, B, C).")
    nb = integer(data, "nb_divisions", "Nombre de divisions", 1, 12)
    cap = integer(data, "capacity", "Capacité par division", 1, 26, required=False) or DEFAULT_CAPACITY
    floor = bool(data.get("include_floor"))
    floor_cap = integer(data, "floor_capacity", "Capacité du sol", 1, 26, required=False) or cap
    with tx(db):
        if db.execute("SELECT 1 FROM shelves WHERE name = ?", (name,)).fetchone():
            raise ApiError(f"Le box {name} existe déjà.", 409)
        sid = db.execute("INSERT INTO shelves (name) VALUES (?)", (name,)).lastrowid
        for n in range(1, nb + 1):
            db.execute("INSERT INTO divisions (shelf_id, number, capacity) VALUES (?,?,?)", (sid, n, cap))
        if floor:
            db.execute("INSERT INTO divisions (shelf_id, number, capacity) VALUES (?,?,?)", (sid, 0, floor_cap))
        audit("box_cree", "shelf", sid, {"name": name, "divisions": nb, "sol": floor, "capacite": cap})
    return jsonify({"id": sid}), 201


@bp.patch("/api/shelves/<int:sid>")
@login_required(*CONFIG)
def update_shelf(sid):
    data = body()
    db = get_db()
    with tx(db):
        shelf = db.execute("SELECT * FROM shelves WHERE id = ?", (sid,)).fetchone()
        if not shelf:
            raise ApiError("Box introuvable.", 404)
        if "name" in data:
            name = text(data, "name", "Nom du box", 3).upper()
            if not re.fullmatch(r"[A-Z]{1,3}", name):
                raise ApiError("Le nom du box doit être composé de 1 à 3 lettres (ex. A, B, C).")
            if db.execute("SELECT 1 FROM shelves WHERE name = ? AND id <> ?", (name, sid)).fetchone():
                raise ApiError(f"Le box {name} existe déjà.", 409)
            db.execute("UPDATE shelves SET name = ? WHERE id = ?", (name, sid))
            audit("box_renomme", "shelf", sid, {"avant": shelf["name"], "apres": name})
            return jsonify({"ok": True})
        if "active" in data and not data["active"]:
            if bodies_in_shelf(db, sid):
                raise ApiError("Impossible de désactiver ce box : il contient encore des corps.", 409)
            db.execute("UPDATE shelves SET active = 0 WHERE id = ?", (sid,))
            audit("box_desactive", "shelf", sid, {"name": shelf["name"]})
        elif "active" in data:
            db.execute("UPDATE shelves SET active = 1 WHERE id = ?", (sid,))
            audit("box_reactive", "shelf", sid, {"name": shelf["name"]})
    return jsonify({"ok": True})


@bp.delete("/api/shelves/<int:sid>")
@login_required(*CONFIG)
def delete_shelf(sid):
    db = get_db()
    with tx(db):
        shelf = db.execute("SELECT * FROM shelves WHERE id = ?", (sid,)).fetchone()
        if not shelf:
            raise ApiError("Box introuvable.", 404)
        divs = [r["id"] for r in db.execute("SELECT id FROM divisions WHERE shelf_id = ?", (sid,))]
        if any(division_refs(db, d) for d in divs):
            raise ApiError(f"Impossible de supprimer le box {shelf['name']} : il a déjà servi (corps ou registres "
                           "y renvoient). Utilisez « Désactiver » pour le retirer des choix.", 409)
        db.execute("DELETE FROM divisions WHERE shelf_id = ?", (sid,))
        db.execute("DELETE FROM shelves WHERE id = ?", (sid,))
        audit("box_supprime", "shelf", sid, {"name": shelf["name"], "divisions": len(divs)})
    return jsonify({"ok": True})


@bp.post("/api/shelves/<int:sid>/divisions")
@login_required(*CONFIG)
def add_division(sid):
    data = body()
    db = get_db()
    cap = integer(data, "capacity", "Capacité", 1, 26, required=False) or DEFAULT_CAPACITY
    floor = bool(data.get("is_floor"))
    with tx(db):
        shelf = db.execute("SELECT * FROM shelves WHERE id = ?", (sid,)).fetchone()
        if not shelf:
            raise ApiError("Box introuvable.", 404)
        if floor:
            number = 0
            if db.execute("SELECT 1 FROM divisions WHERE shelf_id = ? AND number = 0", (sid,)).fetchone():
                raise ApiError("Ce box a déjà une division 0 (sol).", 409)
        else:
            number = db.execute("SELECT COALESCE(MAX(number), 0) + 1 FROM divisions WHERE shelf_id = ?",
                                (sid,)).fetchone()[0]
            if number > 12:
                raise ApiError("Maximum 12 divisions par box.")
        did = db.execute("INSERT INTO divisions (shelf_id, number, capacity) VALUES (?,?,?)",
                         (sid, number, cap)).lastrowid
        audit("division_ajoutee", "division", did, {"box": shelf["name"], "numero": number, "capacite": cap})
    return jsonify({"id": did}), 201


@bp.patch("/api/divisions/<int:did>")
@login_required(*CONFIG)
def update_division(did):
    data = body()
    db = get_db()
    with tx(db):
        div = db.execute("SELECT v.*, s.name AS shelf_name FROM divisions v JOIN shelves s ON s.id = v.shelf_id "
                         "WHERE v.id = ?", (did,)).fetchone()
        if not div:
            raise ApiError("Division introuvable.", 404)
        label = shelf_label(div["shelf_name"], div["number"])
        occ = occupied_letters(db, did)
        changes = {}
        if "capacity" in data:
            cap = integer(data, "capacity", "Capacité", 1, 26)
            if any(l not in LETTERS[:cap] for l in occ):
                raise ApiError(f"Impossible de réduire {label} à {cap} emplacements : "
                               "des corps occupent des emplacements au-delà.", 409)
            db.execute("UPDATE divisions SET capacity = ? WHERE id = ?", (cap, did))
            changes["capacite"] = {"avant": div["capacity"], "apres": cap}
        if "active" in data:
            if not data["active"] and occ:
                raise ApiError(f"Impossible de désactiver {label} : elle contient des corps.", 409)
            db.execute("UPDATE divisions SET active = ? WHERE id = ?", (1 if data["active"] else 0, did))
            changes["active"] = bool(data["active"])
        if not changes:
            raise ApiError("Aucune modification demandée.")
        audit("division_modifiee", "division", did, {"division": label, **changes})
    return jsonify({"ok": True})


@bp.delete("/api/divisions/<int:did>")
@login_required(*CONFIG)
def delete_division(did):
    db = get_db()
    with tx(db):
        div = db.execute("SELECT v.*, s.name AS shelf_name FROM divisions v JOIN shelves s ON s.id = v.shelf_id "
                         "WHERE v.id = ?", (did,)).fetchone()
        if not div:
            raise ApiError("Division introuvable.", 404)
        label = shelf_label(div["shelf_name"], div["number"])
        if division_refs(db, did):
            raise ApiError(f"Impossible de supprimer {label} : elle a déjà servi. Utilisez « Désactiver ».", 409)
        db.execute("DELETE FROM divisions WHERE id = ?", (did,))
        audit("division_supprimee", "division", did, {"division": label})
    return jsonify({"ok": True})


# ---------- plan d'occupation ----------
@bp.get("/api/plan")
@login_required()
def plan():
    db = get_db()
    rows = db.execute(
        "SELECT d.division_id, d.slot_letter, d.id AS dossier_id, d.nom, d.prenoms, e.date_entree, e.numero_ordre, e.annee "
        "FROM dossiers d JOIN entrees e ON e.dossier_id = d.id AND e.annule = 0 "
        "WHERE d.division_id IS NOT NULL").fetchall()
    by_div = {}
    for r in rows:
        by_div.setdefault(r["division_id"], {})[r["slot_letter"]] = r
    shelves, total_cap, total_occ, alerts = [], 0, 0, []
    for s in db.execute("SELECT id, name FROM shelves WHERE active = 1 ORDER BY name"):
        divs = []
        for d in db.execute("SELECT id, number, capacity FROM divisions WHERE shelf_id = ? AND active = 1 "
                            "ORDER BY CASE WHEN number = 0 THEN 999 ELSE number END", (s["id"],)):
            occ = by_div.get(d["id"], {})
            slots = []
            for letter in LETTERS[:d["capacity"]]:
                r = occ.get(letter)
                slot = {"letter": letter, "label": shelf_label(s["name"], d["number"], letter), "occupied": bool(r)}
                if r:
                    slot.update({"dossier_id": r["dossier_id"], "nom": f"{r['nom']} {r['prenoms']}".strip(),
                                 "date_entree": r["date_entree"], "numero": f"{r['numero_ordre']}/{r['annee']}"})
                slots.append(slot)
            divs.append({"id": d["id"], "number": d["number"], "label": shelf_label(s["name"], d["number"]),
                         "is_floor": d["number"] == 0, "capacity": d["capacity"], "occupied": len(occ),
                         "free": d["capacity"] - len(occ), "slots": slots})
            if d["number"] > 0:
                total_cap += d["capacity"]
                total_occ += len(occ)
        saturated = shelf_numbered_saturated(db, s["id"])
        floor = next((x for x in divs if x["is_floor"]), None)
        if saturated:
            alerts.append(f"Box {s['name']} saturé : seul le sol ({s['name']}0) reste disponible."
                          if floor and floor["free"] > 0 else f"Box {s['name']} et son sol sont saturés.")
        shelves.append({"id": s["id"], "name": s["name"], "saturated": saturated, "divisions": divs})
    return jsonify({"shelves": shelves, "alerts": alerts,
                    "totaux": {"capacite_etageres": total_cap, "occupes_etageres": total_occ}})


# ---------- listes paramétrables ----------
@bp.get("/api/services")
@login_required()
def list_services():
    allflag = request.args.get("all") == "1" and g.user["role"] in CONFIG
    rows = get_db().execute(f"SELECT id, nom, active FROM services {'' if allflag else 'WHERE active = 1'} "
                            "ORDER BY nom").fetchall()
    return jsonify([dict(r) for r in rows])


@bp.post("/api/services")
@login_required(*CONFIG)
def add_service():
    nom = text(body(), "nom", "Service", 80)
    db = get_db()
    if name_exists(db, "services", "nom", nom):
        raise ApiError("Ce service existe déjà.", 409)
    sid = db.execute("INSERT INTO services (nom) VALUES (?)", (nom,)).lastrowid
    audit("service_ajoute", "service", sid, {"nom": nom})
    return jsonify({"id": sid}), 201


@bp.patch("/api/services/<int:sid>")
@login_required(*CONFIG)
def update_service(sid):
    data = body()
    db = get_db()
    if not db.execute("SELECT 1 FROM services WHERE id = ?", (sid,)).fetchone():
        raise ApiError("Service introuvable.", 404)
    if "nom" in data:
        nom = text(data, "nom", "Service", 80)
        if name_exists(db, "services", "nom", nom, sid):
            raise ApiError("Ce service existe déjà.", 409)
        db.execute("UPDATE services SET nom = ? WHERE id = ?", (nom, sid))
        audit("service_renomme", "service", sid, {"nom": nom})
    if "active" in data:
        db.execute("UPDATE services SET active = ? WHERE id = ?", (1 if data["active"] else 0, sid))
        audit("service_modifie", "service", sid, {"active": bool(data["active"])})
    return jsonify({"ok": True})


@bp.delete("/api/services/<int:sid>")
@login_required(*CONFIG)
def delete_service(sid):
    db = get_db()
    row = db.execute("SELECT nom FROM services WHERE id = ?", (sid,)).fetchone()
    if not row:
        raise ApiError("Service introuvable.", 404)
    if db.execute("SELECT 1 FROM dossiers WHERE service_id = ? LIMIT 1", (sid,)).fetchone():
        raise ApiError("Impossible de supprimer ce service : des décès internes y sont rattachés. "
                       "Utilisez « Désactiver ».", 409)
    db.execute("DELETE FROM services WHERE id = ?", (sid,))
    audit("service_supprime", "service", sid, {"nom": row["nom"]})
    return jsonify({"ok": True})


@bp.get("/api/raisons")
@login_required()
def list_raisons():
    allflag = request.args.get("all") == "1" and g.user["role"] in CONFIG
    rows = get_db().execute("SELECT id, libelle, est_autre, active FROM raisons_transfert "
                            f"{'' if allflag else 'WHERE active = 1'} ORDER BY est_autre, libelle").fetchall()
    from db import RAISON_DIRECT
    out = [dict(r) for r in rows]
    for r in out:  # raison réservée au transfert direct : non sélectionnable à la main
        r["reserve"] = r["libelle"] == RAISON_DIRECT
    return jsonify(out)


@bp.post("/api/raisons")
@login_required(*CONFIG)
def add_raison():
    libelle = text(body(), "libelle", "Raison", 80)
    db = get_db()
    if name_exists(db, "raisons_transfert", "libelle", libelle):
        raise ApiError("Cette raison existe déjà.", 409)
    rid = db.execute("INSERT INTO raisons_transfert (libelle) VALUES (?)", (libelle,)).lastrowid
    audit("raison_ajoutee", "raison", rid, {"libelle": libelle})
    return jsonify({"id": rid}), 201


@bp.patch("/api/raisons/<int:rid>")
@login_required(*CONFIG)
def update_raison(rid):
    data = body()
    db = get_db()
    row = db.execute("SELECT * FROM raisons_transfert WHERE id = ?", (rid,)).fetchone()
    if not row:
        raise ApiError("Raison introuvable.", 404)
    from db import RAISON_DIRECT
    if "libelle" in data:
        if row["est_autre"] or row["libelle"] == RAISON_DIRECT:
            raise ApiError("Cette raison système ne peut pas être renommée.")
        libelle = text(data, "libelle", "Raison", 80)
        if name_exists(db, "raisons_transfert", "libelle", libelle, rid):
            raise ApiError("Cette raison existe déjà.", 409)
        db.execute("UPDATE raisons_transfert SET libelle = ? WHERE id = ?", (libelle, rid))
        audit("raison_renommee", "raison", rid, {"avant": row["libelle"], "apres": libelle})
    if "active" in data:
        if row["est_autre"] and not data["active"]:
            raise ApiError("La raison « Autre » ne peut pas être désactivée.")
        db.execute("UPDATE raisons_transfert SET active = ? WHERE id = ?", (1 if data["active"] else 0, rid))
        audit("raison_modifiee", "raison", rid, {"active": bool(data["active"])})
    return jsonify({"ok": True})


@bp.delete("/api/raisons/<int:rid>")
@login_required(*CONFIG)
def delete_raison(rid):
    from db import RAISON_DIRECT
    db = get_db()
    row = db.execute("SELECT * FROM raisons_transfert WHERE id = ?", (rid,)).fetchone()
    if not row:
        raise ApiError("Raison introuvable.", 404)
    if row["est_autre"] or row["libelle"] == RAISON_DIRECT:
        raise ApiError("Cette raison système ne peut pas être supprimée.")
    if db.execute("SELECT 1 FROM transferts WHERE raison_id = ? LIMIT 1", (rid,)).fetchone():
        raise ApiError("Impossible de supprimer cette raison : des transferts l'utilisent. Utilisez « Désactiver ».", 409)
    db.execute("DELETE FROM raisons_transfert WHERE id = ?", (rid,))
    audit("raison_supprimee", "raison", rid, {"libelle": row["libelle"]})
    return jsonify({"ok": True})
