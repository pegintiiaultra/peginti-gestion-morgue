"""Annonces : l'administration écrit, tous les comptes actifs reçoivent (boîte de réception, lu / non lu)."""
from flask import Blueprint, g, jsonify, request

from core import ALL, CONFIG, ApiError, audit, body, get_db, login_required, text

bp = Blueprint("annonces", __name__)


@bp.get("/api/annonces")
@login_required(*ALL)
def list_annonces():
    limit = max(1, min(request.args.get("limit", 100, type=int), 300))
    rows = get_db().execute(
        "SELECT a.id, a.created_at, a.auteur_id, a.auteur_nom, a.titre, a.corps, a.important, "
        "(l.user_id IS NOT NULL) AS lu FROM annonces a "
        "LEFT JOIN annonces_lues l ON l.annonce_id = a.id AND l.user_id = ? "
        "WHERE a.supprime = 0 ORDER BY a.id DESC LIMIT ?", (g.user["id"], limit)).fetchall()
    return jsonify([dict(r, lu=bool(r["lu"])) for r in rows])


@bp.get("/api/annonces/non-lues")
@login_required(*ALL)
def unread_count():
    n = get_db().execute(
        "SELECT COUNT(*) FROM annonces a WHERE a.supprime = 0 AND NOT EXISTS "
        "(SELECT 1 FROM annonces_lues l WHERE l.annonce_id = a.id AND l.user_id = ?)", (g.user["id"],)).fetchone()[0]
    return jsonify({"non_lues": n})


@bp.post("/api/annonces")
@login_required(*CONFIG)
def post_annonce():
    data = body()
    titre = text(data, "titre", "Titre", 120, True)
    corps = text(data, "corps", "Message", 2000, True)
    db = get_db()
    aid = db.execute("INSERT INTO annonces (auteur_id, auteur_nom, titre, corps, important) VALUES (?,?,?,?,?)",
                     (g.user["id"], g.user["full_name"], titre, corps, 1 if data.get("important") else 0)).lastrowid
    db.execute("INSERT INTO annonces_lues (annonce_id, user_id) VALUES (?,?)", (aid, g.user["id"]))  # l'auteur l'a lue
    audit("annonce_publiee", "annonce", aid, {"titre": titre})
    return jsonify({"id": aid}), 201


@bp.post("/api/annonces/<int:aid>/lu")
@login_required(*ALL)
def mark_read(aid):
    db = get_db()
    if not db.execute("SELECT 1 FROM annonces WHERE id = ? AND supprime = 0", (aid,)).fetchone():
        raise ApiError("Annonce introuvable.", 404)
    db.execute("INSERT OR IGNORE INTO annonces_lues (annonce_id, user_id) VALUES (?,?)", (aid, g.user["id"]))
    return jsonify({"ok": True})


@bp.post("/api/annonces/lues")
@login_required(*ALL)
def mark_all_read():
    get_db().execute("INSERT OR IGNORE INTO annonces_lues (annonce_id, user_id) "
                     "SELECT id, ? FROM annonces WHERE supprime = 0", (g.user["id"],))
    return jsonify({"ok": True})


@bp.delete("/api/annonces/<int:aid>")
@login_required(*CONFIG)
def delete_annonce(aid):
    db = get_db()
    row = db.execute("SELECT * FROM annonces WHERE id = ? AND supprime = 0", (aid,)).fetchone()
    if not row:
        raise ApiError("Annonce introuvable.", 404)
    if row["auteur_id"] != g.user["id"] and g.user["role"] != "super_admin":
        raise ApiError("Seul l'auteur ou le super administrateur peut retirer cette annonce.", 403)
    db.execute("UPDATE annonces SET supprime = 1 WHERE id = ?", (aid,))
    audit("annonce_retiree", "annonce", aid, {"titre": row["titre"]})
    return jsonify({"ok": True})


@bp.patch("/api/annonces/<int:aid>")
@login_required(*CONFIG)
def update_annonce(aid):
    data = body()
    db = get_db()
    row = db.execute("SELECT * FROM annonces WHERE id = ? AND supprime = 0", (aid,)).fetchone()
    if not row:
        raise ApiError("Annonce introuvable.", 404)
    if row["auteur_id"] != g.user["id"] and g.user["role"] != "super_admin":
        raise ApiError("Seul l'auteur ou le super administrateur peut modifier cette annonce.", 403)
    titre = text(data, "titre", "Titre", 120, True)
    corps = text(data, "corps", "Message", 2000, True)
    db.execute("UPDATE annonces SET titre = ?, corps = ?, important = ? WHERE id = ?",
               (titre, corps, 1 if data.get("important") else 0, aid))
    audit("annonce_modifiee", "annonce", aid, {"titre": titre})
    return jsonify({"ok": True})
