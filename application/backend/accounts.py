"""Connexion, comptes, droits (thanatopracteur / admin / super_admin), récupération de mot de passe."""
import hashlib
import os
import re
import secrets
import sqlite3
import tempfile
import unicodedata
from datetime import datetime

from flask import Blueprint, after_this_request, g, jsonify, request, send_file
from werkzeug.security import check_password_hash, generate_password_hash

from core import (ADMIN, ALL, ApiError, audit, body, can_manage, choice, get_db, integer, login_blocked,
                  login_failed, login_ok, login_required, make_token, name_exists, text)
from db import DB_PATH

bp = Blueprint("accounts", __name__)

ROLES = ("thanatopracteur", "admin", "super_admin")
MOTIFS_SUPPRESSION = {"revocation": "Révocation", "deces": "Décès", "demission": "Démission"}
MIN_PASSWORD = 10
HASH_METHOD = "scrypt" if hasattr(hashlib, "scrypt") else "pbkdf2:sha256:600000"
# Hachage factice pour que la durée de réponse ne révèle pas l'existence d'un compte
_DUMMY_HASH = generate_password_hash("x" * 12, method=HASH_METHOD)
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sans 0/O/1/I/L : lisible et dicté sans erreur


def hash_password(pw):
    return generate_password_hash(pw, method=HASH_METHOD)


def check_new_password(pw):
    if not isinstance(pw, str) or len(pw) < MIN_PASSWORD:
        raise ApiError(f"Le mot de passe doit contenir au moins {MIN_PASSWORD} caractères.")
    if len(pw) > 128:
        raise ApiError("Le mot de passe est trop long (128 caractères maximum).")
    if pw.isdigit() or pw.isalpha():
        raise ApiError("Le mot de passe doit mélanger lettres et chiffres (ou symboles).")
    return pw


def normalize_username(value):
    """Identifiant = nom de la personne, normalisé : casse et espaces multiples ignorés (« Dr  Ngo » = « dr ngo »)."""
    v = unicodedata.normalize("NFC", str(value or ""))
    v = re.sub(r"\s+", " ", v).strip().casefold()
    if not re.fullmatch(r"[\w][\w .'’-]{2,59}", v):
        raise ApiError("Identifiant (nom) : 3 à 60 caractères, lettres, chiffres, espace, point, tiret ou apostrophe.")
    return v


def new_recovery_code():
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(16))
    return "-".join(raw[i:i + 4] for i in range(0, 16, 4))


def _clean_code(code):
    return re.sub(r"[^A-Z0-9]", "", str(code or "").upper())


def issue_recovery_code(db, uid):
    code = new_recovery_code()
    db.execute("UPDATE users SET recovery_hash = ?, recovery_le = datetime('now') WHERE id = ?",
               (hash_password(_clean_code(code)), uid))
    return code


def public_user(u, db=None):
    from mfa import required_for
    db = db or get_db()
    return {"mfa_active": bool(u["totp_active"]), "mfa_requise": required_for(db, u["role"]) and not u["totp_active"],
            **_public_base(u)}


def _public_base(u):
    return {"id": u["id"], "username": u["username"], "full_name": u["full_name"],
            "role": u["role"], "visa": u["visa"], "contact": u["contact"],
            "doit_changer_mdp": bool(u["doit_changer_mdp"]), "a_code_recuperation": bool(u["recovery_hash"])}


# ---------- connexion ----------
@bp.post("/api/login")
def login():
    data = body()
    username = re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(data.get("username", "")))).strip().casefold()
    password = str(data.get("password", ""))[:200]
    key = (request.remote_addr, username)
    wait = login_blocked(key)
    if wait:
        raise ApiError(f"Trop de tentatives. Réessayez dans {wait // 60 + 1} minute(s).", 429)
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    ok = check_password_hash(user["password_hash"] if user else _DUMMY_HASH, password)
    if user and ok and user["statut"] == "en_attente":
        raise ApiError("Votre compte attend la validation de l'administration.", 403)
    if not (user and ok and user["active"] and user["statut"] == "actif"):
        login_failed(key)
        audit("login_echec", "user", user["id"] if user else None, {"username": username[:50]},
              user={"id": None, "username": username[:50]})
        raise ApiError("Identifiant ou mot de passe incorrect.", 401)
    login_ok(key)
    if user["totp_active"]:  # seconde étape : le code de l'application d'authentification
        from mfa import make_ticket
        audit("login_etape1", "user", user["id"], user=user)
        return jsonify({"etape": "2fa", "ticket": make_ticket(user["id"])})
    audit("login", "user", user["id"], user=user)
    return jsonify({"token": make_token(user["id"]), "user": public_user(user)})


@bp.get("/api/me")
@login_required()
def me():
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    return jsonify(public_user(row))


@bp.post("/api/password")
@login_required()
def change_password():
    data = body()
    db = get_db()
    row = db.execute("SELECT password_hash, recovery_hash FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    if not check_password_hash(row["password_hash"], str(data.get("ancien", ""))):
        raise ApiError("Ancien mot de passe incorrect.", 403)
    nouveau = check_new_password(data.get("nouveau"))
    if nouveau == str(data.get("ancien", "")):
        raise ApiError("Le nouveau mot de passe doit être différent de l'ancien.")
    db.execute("UPDATE users SET password_hash = ?, doit_changer_mdp = 0 WHERE id = ?",
               (hash_password(nouveau), g.user["id"]))
    audit("mot_de_passe_modifie", "user", g.user["id"])
    out = {"ok": True}
    if not row["recovery_hash"]:  # premier mot de passe personnel : on remet aussi le code de récupération
        out["code_recuperation"] = issue_recovery_code(db, g.user["id"])
        audit("code_recuperation_cree", "user", g.user["id"])
    return jsonify(out)


# ---------- récupération du compte ----------
@bp.post("/api/recuperation/code")
@login_required()
def regenerate_code():
    """Génère (ou remplace) le code de récupération personnel ; il n'est affiché qu'une seule fois."""
    data = body()
    db = get_db()
    row = db.execute("SELECT password_hash FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    if not check_password_hash(row["password_hash"], str(data.get("password", ""))):
        raise ApiError("Mot de passe incorrect.", 403)
    code = issue_recovery_code(db, g.user["id"])
    audit("code_recuperation_cree", "user", g.user["id"])
    return jsonify({"code_recuperation": code})


@bp.post("/api/recuperation")
def recover_account():
    """Mot de passe oublié : identifiant + code de récupération personnel -> nouveau mot de passe."""
    data = body()
    username = re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(data.get("username", "")))).strip().casefold()
    keys = [(request.remote_addr, "rec", username), ("rec-compte", username)]  # par adresse ET par compte
    for k in keys:
        wait = login_blocked(k)
        if wait:
            raise ApiError(f"Trop de tentatives. Réessayez dans {wait // 60 + 1} minute(s).", 429)
    nouveau = check_new_password(data.get("nouveau"))
    if nouveau != data.get("confirmation"):
        raise ApiError("Le nouveau mot de passe et sa confirmation ne correspondent pas.")
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    code = _clean_code(data.get("code"))
    stored = user["recovery_hash"] if user and user["recovery_hash"] else _DUMMY_HASH
    ok = len(code) == 16 and check_password_hash(stored, code)
    if not (user and ok and user["active"] and user["statut"] == "actif"):
        for k in keys:
            login_failed(k)
        audit("recuperation_echec", "user", user["id"] if user else None, {"username": username[:50]},
              user={"id": None, "username": username[:50]})
        raise ApiError("Identifiant ou code de récupération incorrect. Sinon, demandez une réinitialisation "
                       "à l'administration.", 401)
    for k in keys:
        login_ok(k)
    db.execute("UPDATE users SET password_hash = ?, doit_changer_mdp = 0 WHERE id = ?", (hash_password(nouveau), user["id"]))
    new_code = issue_recovery_code(db, user["id"])  # le code utilisé est périmé : on en remet un nouveau
    audit("mot_de_passe_recupere", "user", user["id"], user=user)
    return jsonify({"ok": True, "code_recuperation": new_code})


@bp.get("/api/personnel")
@login_required()
def personnel():
    """Thanatopracteurs actifs (liste de choix pour « thanatopracteur de service »)."""
    rows = get_db().execute(
        "SELECT id, full_name, visa FROM users WHERE active = 1 AND statut = 'actif' AND role = 'thanatopracteur' "
        "ORDER BY full_name").fetchall()
    return jsonify([dict(r) for r in rows])


# ---------- inscription (auto-demande, validée par l'administration) ----------
@bp.post("/api/inscription")
def inscription():
    """Le thanatopracteur crée sa demande de compte : identifiant = son nom, mot de passe saisi puis confirmé.
    Le compte reste en attente (aucun accès) tant que l'administration ne l'a pas validé."""
    data = body()
    key = (request.remote_addr, "inscription")
    if login_blocked(key):
        raise ApiError("Trop de demandes. Réessayez plus tard.", 429)
    db = get_db()
    full_name = re.sub(r"\s+", " ", text(data, "nom", "Nom du thanatopracteur", 100))
    username = normalize_username(full_name)
    pw = check_new_password(data.get("password"))
    if pw != data.get("confirmation"):
        raise ApiError("Le mot de passe et sa confirmation ne correspondent pas.")
    if name_exists(db, "users", "username", username):
        login_failed(key)
        raise ApiError("Ce nom est déjà utilisé (compte existant, en attente ou archivé). "
                       "Adressez-vous à l'administration.", 409)
    cur = db.execute(
        "INSERT INTO users (username, password_hash, full_name, role, visa, contact, active, statut, origine) "
        "VALUES (?,?,?,?,?,?,0,'en_attente','inscription')",
        (username, hash_password(pw), full_name, "thanatopracteur",
         text(data, "visa", "Visa", 50, False), text(data, "contact", "Contact", 50, False)))
    login_failed(key)  # chaque demande compte : 5 demandes par quart d'heure et par adresse au maximum
    audit("inscription_demandee", "user", cur.lastrowid, {"username": username},
          user={"id": None, "username": username})
    return jsonify({"ok": True, "message": "Demande enregistrée. Vous pourrez vous connecter dès que "
                                           "l'administration l'aura validée."}), 201


# ---------- gestion des comptes ----------
def _target(db, uid):
    t = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    if not t:
        raise ApiError("Compte introuvable.", 404)
    return t


def _need_right(target):
    if not can_manage(g.user["role"], target["role"]):
        raise ApiError("Vous n'avez pas le droit de gérer ce compte"
                       + (" (réservé au super administrateur)." if target["role"] != "thanatopracteur" else "."), 403)


def _other_supervisors(db, excluding):
    return db.execute("SELECT COUNT(*) FROM users WHERE role IN ('admin','super_admin') AND active=1 "
                      "AND statut='actif' AND id != ?", (excluding,)).fetchone()[0]


@bp.get("/api/users")
@login_required(*ADMIN)
def list_users():
    rows = get_db().execute(
        "SELECT id, username, full_name, role, visa, contact, active, statut, origine, created_at, "
        "motif_suppression, supprime_le, supprime_par, totp_active FROM users ORDER BY statut, role DESC, username").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["mfa_active"] = bool(d.pop("totp_active"))
        d["gerable"] = can_manage(g.user["role"], r["role"]) and r["id"] != g.user["id"]
        out.append(d)
    return jsonify(out)


@bp.post("/api/users")
@login_required(*ADMIN)
def create_user():
    data = body()
    db = get_db()
    full_name = re.sub(r"\s+", " ", text(data, "full_name", "Nom complet", 100))
    username = normalize_username(data.get("username") or full_name)
    role = choice(data, "role", "Rôle", ROLES)
    me_role = g.user["role"]
    if role == "super_admin":
        if me_role != "admin":
            raise ApiError("Le compte super administrateur est créé par un administrateur.", 403)
        if db.execute("SELECT 1 FROM users WHERE role = 'super_admin' AND statut IN ('actif','en_attente')").fetchone():
            raise ApiError("Un super administrateur existe déjà : il est unique.", 409)
    elif role == "admin" and me_role != "super_admin":
        raise ApiError("Seul le super administrateur peut créer un administrateur.", 403)
    pw = check_new_password(data.get("password"))
    if name_exists(db, "users", "username", username):
        raise ApiError("Cet identifiant existe déjà (compte actif, en attente ou archivé).", 409)
    try:
        cur = db.execute(
            "INSERT INTO users (username, password_hash, full_name, role, visa, contact, doit_changer_mdp) "
            "VALUES (?,?,?,?,?,?,1)",
            (username, hash_password(pw), full_name, role, text(data, "visa", "Visa", 50, False),
             text(data, "contact", "Contact", 50, False)))
    except sqlite3.IntegrityError:
        raise ApiError("Un super administrateur existe déjà : il est unique.", 409)
    audit("compte_cree", "user", cur.lastrowid, {"username": username, "role": role})
    return jsonify({"id": cur.lastrowid}), 201


@bp.patch("/api/users/<int:uid>")
@login_required(*ADMIN)
def update_user(uid):
    data = body()
    db = get_db()
    target = _target(db, uid)
    if uid != g.user["id"]:
        _need_right(target)
    elif "role" in data or "active" in data:
        raise ApiError("Vous ne pouvez pas modifier votre propre rôle ni suspendre votre propre compte.")
    if target["statut"] != "actif":
        raise ApiError("Seuls les comptes actifs peuvent être modifiés.", 409)
    fields, params, changes = [], [], {}
    if "full_name" in data:
        fields.append("full_name = ?"); params.append(text(data, "full_name", "Nom complet", 100))
        changes["full_name"] = params[-1]
    if "role" in data:
        if g.user["role"] != "super_admin":
            raise ApiError("Seul le super administrateur peut changer un rôle.", 403)
        role = choice(data, "role", "Rôle", ("thanatopracteur", "admin"))
        if target["role"] == "super_admin":
            raise ApiError("Le rôle du super administrateur ne peut pas être modifié ici.", 409)
        fields.append("role = ?"); params.append(role); changes["role"] = role
    for key, label in (("visa", "Visa"), ("contact", "Contact")):
        if key in data:
            fields.append(f"{key} = ?"); params.append(text(data, key, label, 50, False))
            changes[key] = params[-1]
    if "active" in data:
        active = 1 if data["active"] else 0
        if not active and target["role"] in ("admin", "super_admin") and _other_supervisors(db, uid) == 0:
            raise ApiError("Il doit rester au moins un administrateur actif.")
        fields.append("active = ?"); params.append(active); changes["active"] = active
    if data.get("password"):
        fields.append("password_hash = ?"); params.append(hash_password(check_new_password(data["password"])))
        fields.append("doit_changer_mdp = 1")  # mot de passe fixé par l'administration : provisoire
        changes["password"] = "réinitialisé"
    if not fields:
        raise ApiError("Aucune modification demandée.")
    db.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", (*params, uid))
    audit("compte_modifie", "user", uid, changes)
    return jsonify({"ok": True})


@bp.post("/api/users/<int:uid>/valider")
@login_required(*ADMIN)
def validate_user(uid):
    db = get_db()
    target = _target(db, uid)
    _need_right(target)
    if target["statut"] != "en_attente":
        raise ApiError("Ce compte n'est pas en attente de validation.", 409)
    db.execute("UPDATE users SET statut='actif', active=1 WHERE id=?", (uid,))
    audit("compte_valide", "user", uid, {"username": target["username"], "role": target["role"]})
    return jsonify({"ok": True})


@bp.post("/api/users/<int:uid>/refuser")
@login_required(*ADMIN)
def refuse_user(uid):
    db = get_db()
    target = _target(db, uid)
    _need_right(target)
    if target["statut"] != "en_attente":
        raise ApiError("Ce compte n'est pas en attente de validation.", 409)
    db.execute("DELETE FROM users WHERE id = ?", (uid,))  # aucune donnée liée : la demande disparaît
    audit("inscription_refusee", "user", uid, {"username": target["username"]})
    return jsonify({"ok": True})


@bp.delete("/api/users/<int:uid>")
@login_required(*ADMIN)
def delete_user(uid):
    """Suppression d'un compte avec motif obligatoire (révocation, décès, démission) et confirmation du mot de passe.
    Admin : thanatopracteurs uniquement. Super administrateur : tous les comptes sauf le sien.
    Le compte perd définitivement tout accès ; l'historique (registres, journal) est conservé."""
    data = body()
    db = get_db()
    motif = choice(data, "motif", "Motif de suppression", tuple(MOTIFS_SUPPRESSION))
    admin = db.execute("SELECT password_hash FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    if not check_password_hash(admin["password_hash"], str(data.get("password", ""))):
        raise ApiError("Mot de passe de l'administrateur incorrect.", 403)
    target = _target(db, uid)
    if uid == g.user["id"]:
        raise ApiError("Vous ne pouvez pas supprimer votre propre compte.")
    _need_right(target)
    if target["statut"] == "supprime":
        raise ApiError("Ce compte est déjà supprimé.", 409)
    if target["role"] in ("admin", "super_admin") and target["statut"] == "actif" and _other_supervisors(db, uid) == 0:
        raise ApiError("Il doit rester au moins un administrateur actif.")
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute("UPDATE users SET statut='supprime', active=0, motif_suppression=?, supprime_le=datetime('now'), "
                   "supprime_par=?, recovery_hash=NULL WHERE id=?", (motif, g.user["username"], uid))
        db.execute("UPDATE agents SET active=0, user_id=NULL WHERE user_id=?", (uid,))
        audit("compte_supprime", "user", uid, {"username": target["username"], "role": target["role"], "motif": motif})
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    return jsonify({"ok": True})


# ---------- journal et sauvegarde ----------
@bp.get("/api/audit")
@login_required(*ADMIN)
def audit_list():
    limit = integer(request.args, "limit", "Limite", 1, 1000, required=False) or 200
    q = (request.args.get("q") or "").strip()
    sql, params = "SELECT id, ts, username, action, entity, entity_id, detail FROM audit_log", []
    if q:
        sql += " WHERE username LIKE ? OR action LIKE ? OR detail LIKE ?"
        params = [f"%{q}%"] * 3
    rows = get_db().execute(sql + " ORDER BY id DESC LIMIT ?", (*params, limit)).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.get("/api/sauvegarde")
@login_required(*ADMIN)
def sauvegarde():
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    src, dst = sqlite3.connect(DB_PATH), sqlite3.connect(tmp)
    with dst:
        src.backup(dst)
    src.close(); dst.close()
    audit("sauvegarde_telechargee", "systeme")

    @after_this_request
    def cleanup(resp):
        try:
            os.remove(tmp)
        except OSError:
            pass
        return resp
    return send_file(tmp, as_attachment=True, download_name=f"morgue-{datetime.now():%Y%m%d-%H%M}.db",
                     mimetype="application/octet-stream")
