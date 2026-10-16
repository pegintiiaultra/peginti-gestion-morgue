"""Double authentification (TOTP, RFC 6238) : application d'authentification (Google Authenticator, Aegis,
FreeOTP, Microsoft Authenticator…) + codes de secours à usage unique. Aucune dépendance externe.

Connexion : identifiant + mot de passe -> « ticket » valable 5 minutes -> code à 6 chiffres -> session.
Politique de la morgue (settings.mfa_exigee) : aucun | admin (administrateurs) | tous.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import jwt
from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash

from core import (ADMIN, ALL, CONFIG, ApiError, audit, body, can_manage, choice, get_db, login_blocked,
                  login_failed, login_ok, login_required, make_token, secret_key)
import accounts

bp = Blueprint("mfa", __name__)

PERIOD = 30
DIGITS = 6
WINDOW = 1            # tolérance : un pas avant / après (décalage d'horloge du téléphone)
TICKET_MINUTES = 5
NB_CODES_SECOURS = 8
POLITIQUES = ("aucun", "admin", "tous")
ISSUER = "PEGINTI Morgue"


# ---------- TOTP ----------
def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(secret, counter):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    off = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** DIGITS)
    return str(value).zfill(DIGITS)


def totp_now(secret, at=None):
    return _hotp(secret, int((time.time() if at is None else at) // PERIOD))


def verify_totp(secret, code, after_step=0, at=None):
    """Renvoie le pas de temps accepté (entier) ou None. Un pas déjà utilisé (<= after_step) est refusé : un code
    espionné ne peut pas être rejoué."""
    code = re.sub(r"\D", "", str(code or ""))
    if len(code) != DIGITS:
        return None
    now = int((time.time() if at is None else at) // PERIOD)
    for step in range(now - WINDOW, now + WINDOW + 1):
        if step > after_step and hmac.compare_digest(_hotp(secret, step), code):
            return step
    return None


def otpauth_uri(username, secret):
    return (f"otpauth://totp/{quote(ISSUER)}:{quote(username)}?secret={secret}&issuer={quote(ISSUER)}"
            f"&algorithm=SHA1&digits={DIGITS}&period={PERIOD}")


# ---------- codes de secours ----------
_ALPHA = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _clean(code):
    return re.sub(r"[^A-Z0-9]", "", str(code or "").upper())


def new_backup_codes():
    codes = []
    for _ in range(NB_CODES_SECOURS):
        raw = "".join(secrets.choice(_ALPHA) for _ in range(10))
        codes.append(raw[:5] + "-" + raw[5:])
    return codes


def _store_backup(db, uid, codes):
    hashes = [accounts.hash_password(_clean(c)) for c in codes]
    db.execute("UPDATE users SET totp_backup = ? WHERE id = ?", (json.dumps(hashes), uid))


def _use_backup(db, user, code):
    code = _clean(code)
    if len(code) != 10:
        return False
    hashes = json.loads(user["totp_backup"] or "[]")
    for i, h in enumerate(hashes):
        if check_password_hash(h, code):
            del hashes[i]
            db.execute("UPDATE users SET totp_backup = ? WHERE id = ?", (json.dumps(hashes), user["id"]))
            return True
    return False


# ---------- politique ----------
def get_policy(db):
    row = db.execute("SELECT value FROM settings WHERE key = 'mfa_exigee'").fetchone()
    return row["value"] if row and row["value"] in POLITIQUES else "aucun"


def required_for(db, role):
    p = get_policy(db)
    return p == "tous" or (p == "admin" and role in ("admin", "super_admin"))


# ---------- tickets de connexion (étape intermédiaire) ----------
def make_ticket(uid):
    now = datetime.now(timezone.utc)
    return jwt.encode({"tkt": str(uid), "typ": "mfa", "iat": now, "exp": now + timedelta(minutes=TICKET_MINUTES)},
                      secret_key(), algorithm="HS256")


def read_ticket(token):
    try:
        p = jwt.decode(str(token or ""), secret_key(), algorithms=["HS256"])
        if p.get("typ") != "mfa":
            raise ValueError
        return int(p["tkt"])
    except Exception:
        raise ApiError("La vérification a expiré. Reconnectez-vous.", 401)


def _check_second_factor(db, user, code):
    """Vérifie un code TOTP ou un code de secours. Renvoie 'totp', 'secours' ou None."""
    if user["totp_active"] and user["totp_secret"]:
        step = verify_totp(user["totp_secret"], code, user["totp_last_step"] or 0)
        if step:
            db.execute("UPDATE users SET totp_last_step = ? WHERE id = ?", (step, user["id"]))
            return "totp"
    if _use_backup(db, user, code):
        return "secours"
    return None


@bp.post("/api/login/2fa")
def login_second_step():
    data = body()
    uid = read_ticket(data.get("ticket"))
    keys = [(request.remote_addr, "2fa", uid), ("2fa-compte", uid)]
    for k in keys:
        wait = login_blocked(k)
        if wait:
            raise ApiError(f"Trop de tentatives. Réessayez dans {wait // 60 + 1} minute(s).", 429)
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    if not user or not user["active"] or user["statut"] != "actif" or not user["totp_active"]:
        raise ApiError("La vérification a expiré. Reconnectez-vous.", 401)
    how = _check_second_factor(db, user, data.get("code"))
    if not how:
        for k in keys:
            login_failed(k)
        audit("login_2fa_echec", "user", uid, user=user)
        raise ApiError("Code incorrect ou expiré. Vérifiez l'heure de votre téléphone.", 401)
    for k in keys:
        login_ok(k)
    login_ok((request.remote_addr, user["username"]))
    audit("login", "user", uid, {"2fa": how}, user=user)
    out = {"token": make_token(uid), "user": accounts.public_user(user, db)}
    if how == "secours":
        out["codes_restants"] = len(json.loads(user["totp_backup"] or "[]")) - 1
    return jsonify(out)


# ---------- gestion par l'utilisateur ----------
def _me(db):
    from flask import g
    return db.execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()


def _need_password(user, data):
    if not check_password_hash(user["password_hash"], str(data.get("password", ""))):
        raise ApiError("Mot de passe incorrect.", 403)


@bp.get("/api/2fa")
@login_required()
def status():
    db = get_db()
    u = _me(db)
    return jsonify({"active": bool(u["totp_active"]), "exigee": required_for(db, u["role"]),
                    "codes_restants": len(json.loads(u["totp_backup"] or "[]")) if u["totp_active"] else 0,
                    "politique": get_policy(db)})


@bp.post("/api/2fa/preparer")
@login_required()
def prepare():
    db = get_db()
    u = _me(db)
    _need_password(u, body())
    if u["totp_active"]:
        raise ApiError("La double authentification est déjà active.", 409)
    secret = new_secret()
    db.execute("UPDATE users SET totp_pending = ? WHERE id = ?", (secret, u["id"]))
    return jsonify({"secret": secret, "groupes": " ".join(secret[i:i + 4] for i in range(0, len(secret), 4)),
                    "uri": otpauth_uri(u["username"], secret)})


@bp.post("/api/2fa/activer")
@login_required()
def activate():
    db = get_db()
    u = _me(db)
    if u["totp_active"]:
        raise ApiError("La double authentification est déjà active.", 409)
    if not u["totp_pending"]:
        raise ApiError("Commencez par générer la clé.", 409)
    key = (request.remote_addr, "2fa-act", u["id"])
    if login_blocked(key):
        raise ApiError("Trop de tentatives. Réessayez plus tard.", 429)
    step = verify_totp(u["totp_pending"], body().get("code"))
    if not step:
        login_failed(key)
        raise ApiError("Code incorrect. Vérifiez l'heure de votre téléphone et réessayez.", 400)
    login_ok(key)
    codes = new_backup_codes()
    db.execute("UPDATE users SET totp_secret = ?, totp_pending = NULL, totp_active = 1, totp_last_step = ? WHERE id = ?",
               (u["totp_pending"], step, u["id"]))
    _store_backup(db, u["id"], codes)
    audit("2fa_activee", "user", u["id"])
    return jsonify({"ok": True, "codes_secours": codes})


@bp.post("/api/2fa/desactiver")
@login_required()
def deactivate():
    db = get_db()
    u = _me(db)
    data = body()
    _need_password(u, data)
    if not u["totp_active"]:
        raise ApiError("La double authentification n'est pas active.", 409)
    if required_for(db, u["role"]):
        raise ApiError("La politique de la morgue exige la double authentification pour votre rôle.", 403)
    if not _check_second_factor(db, u, data.get("code")):
        raise ApiError("Code incorrect.", 403)
    _clear(db, u["id"])
    audit("2fa_desactivee", "user", u["id"])
    return jsonify({"ok": True})


@bp.post("/api/2fa/codes")
@login_required()
def regenerate_codes():
    db = get_db()
    u = _me(db)
    data = body()
    _need_password(u, data)
    if not u["totp_active"]:
        raise ApiError("La double authentification n'est pas active.", 409)
    step = verify_totp(u["totp_secret"], data.get("code"), u["totp_last_step"] or 0)
    if not step:
        raise ApiError("Code incorrect.", 403)
    db.execute("UPDATE users SET totp_last_step = ? WHERE id = ?", (step, u["id"]))
    codes = new_backup_codes()
    _store_backup(db, u["id"], codes)
    audit("2fa_codes_secours_renouveles", "user", u["id"])
    return jsonify({"codes_secours": codes})


def _clear(db, uid):
    db.execute("UPDATE users SET totp_secret = NULL, totp_pending = NULL, totp_active = 0, totp_last_step = 0, "
               "totp_backup = NULL WHERE id = ?", (uid,))


# ---------- administration ----------
@bp.post("/api/users/<int:uid>/reset-2fa")
@login_required(*ADMIN)
def reset_for_user(uid):
    """Téléphone perdu : l'administration désactive la 2FA du compte (qui devra la réactiver si elle est exigée)."""
    from flask import g
    db = get_db()
    target = db.execute("SELECT id, username, role, statut FROM users WHERE id = ?", (uid,)).fetchone()
    if not target or target["statut"] == "supprime":
        raise ApiError("Compte introuvable.", 404)
    if uid == g.user["id"]:
        raise ApiError("Utilisez « Désactiver » depuis votre propre compte, ou demandez à un autre administrateur.", 409)
    if not can_manage(g.user["role"], target["role"]):
        raise ApiError("Vous n'avez pas le droit sur ce compte.", 403)
    _clear(db, uid)
    audit("2fa_reinitialisee", "user", uid, {"username": target["username"]})
    return jsonify({"ok": True})


@bp.get("/api/2fa/politique")
@login_required(*CONFIG)
def get_policy_route():
    return jsonify({"politique": get_policy(get_db())})


@bp.put("/api/2fa/politique")
@login_required(*CONFIG)
def set_policy():
    value = choice(body(), "politique", "Politique", POLITIQUES)
    db = get_db()
    db.execute("INSERT INTO settings (key, value) VALUES ('mfa_exigee', ?) "
               "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (value,))
    audit("politique_2fa_modifiee", "settings", None, {"politique": value})
    return jsonify({"politique": value})
