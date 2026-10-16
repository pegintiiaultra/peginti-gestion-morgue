"""Outils communs : connexion, authentification JWT, rôles, validation, audit."""
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import g, jsonify, request

from db import DATA_DIR, connect

TOKEN_HOURS = 8
LETTERS = "abcdefghijklmnopqrstuvwxyz"

# Groupes de rôles
# Rôles : le thanatopracteur est seul à saisir les registres ; admin = supervision en lecture seule + gestion des
# comptes thanatopracteurs ; super_admin = directeur général (unique), peut tout administrer.
ALL = ("thanatopracteur", "admin", "super_admin")
WRITE_REG = ("thanatopracteur",)
CANCEL = ("thanatopracteur",)
CONFIG = ("admin", "super_admin")   # paramétrage : box, services, tarifs, planning des gardes
ADMIN = ("admin", "super_admin")    # gestion des comptes (limitée par can_manage)
SUPER = ("super_admin",)


def can_manage(requester_role, target_role):
    """Droits sur un compte : le super_admin gère tout le monde ; l'admin ne gère que les thanatopracteurs."""
    if requester_role == "super_admin":
        return True
    return requester_role == "admin" and target_role == "thanatopracteur"


class ApiError(Exception):
    def __init__(self, message, status=400, code=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code  # ex. DEROGATION_REQUISE : le frontend demande alors un motif


# ---------- base ----------
def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ---------- clé secrète ----------
_secret_cache = None


def secret_key():
    """Clé de signature des jetons : variable MORGUE_SECRET, sinon fichier data/secret.key (droits 600)."""
    global _secret_cache
    if _secret_cache:
        return _secret_cache
    env = os.environ.get("MORGUE_SECRET")
    if env:
        _secret_cache = env
        return env
    path = os.path.join(DATA_DIR, "secret.key")
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(path):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(32))
    with open(path) as f:
        _secret_cache = f.read().strip()
    return _secret_cache


def make_token(user_id):
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=TOKEN_HOURS)}
    return jwt.encode(payload, secret_key(), algorithm="HS256")


# ---------- authentification / rôles ----------
# routes accessibles tant que la double authentification exigée n'est pas encore activée
MFA_OK = ("accounts.me", "accounts.change_password", "mfa.status", "mfa.prepare", "mfa.activate")


def login_required(*roles):
    allowed = roles or ALL

    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                raise ApiError("Authentification requise.", 401)
            try:
                payload = jwt.decode(header[7:], secret_key(), algorithms=["HS256"])
                uid = int(payload["sub"])
            except Exception:
                raise ApiError("Session expirée ou invalide. Reconnectez-vous.", 401)
            user = get_db().execute(
                "SELECT id, username, full_name, role, visa, contact, active, statut, doit_changer_mdp, totp_active FROM users WHERE id = ?",
                (uid,)).fetchone()
            if not user or not user["active"] or user["statut"] != "actif":
                raise ApiError("Compte désactivé ou inconnu.", 401)
            if user["doit_changer_mdp"] and request.endpoint not in ("accounts.change_password", "accounts.me"):
                raise ApiError("Vous devez d'abord choisir votre mot de passe personnel.", 403, "MDP_A_CHANGER")
            if not user["totp_active"] and request.endpoint not in MFA_OK:
                from mfa import required_for
                if required_for(get_db(), user["role"]):
                    raise ApiError("La double authentification est obligatoire : activez-la pour continuer.", 403, "MFA_A_ACTIVER")
            if user["role"] not in allowed:
                raise ApiError("Vous n'avez pas le droit d'effectuer cette action.", 403)
            g.user = user
            return fn(*args, **kwargs)
        return wrapper
    return deco


# ---------- limitation des tentatives de connexion ----------
_failures = {}
MAX_FAILS = 5
LOCK_SECONDS = 15 * 60


def _prune():
    if len(_failures) > 5000:  # évite une croissance sans fin de la mémoire
        now = time.time()
        for k in [k for k, (_, first) in _failures.items() if now - first > LOCK_SECONDS]:
            _failures.pop(k, None)


def login_blocked(key):
    _prune()
    entry = _failures.get(key)
    if not entry:
        return 0
    count, first = entry
    if time.time() - first > LOCK_SECONDS:
        _failures.pop(key, None)
        return 0
    return int(LOCK_SECONDS - (time.time() - first)) if count >= MAX_FAILS else 0


def login_failed(key):
    count, first = _failures.get(key, (0, time.time()))
    _failures[key] = (count + 1, first)


def login_ok(key):
    _failures.pop(key, None)


# ---------- audit ----------
def audit(action, entity=None, entity_id=None, detail=None, user=None):
    u = user or getattr(g, "user", None)
    get_db().execute(
        "INSERT INTO audit_log (user_id, username, action, entity, entity_id, detail) VALUES (?,?,?,?,?,?)",
        (u["id"] if u else None, u["username"] if u else None, action, entity, entity_id,
         json.dumps(detail, ensure_ascii=False) if detail is not None else None))


# ---------- validation ----------
def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Requête invalide (JSON attendu).")
    return data


def text(data, key, label, max_len=200, required=True):
    val = data.get(key)
    if val is None or (isinstance(val, str) and not val.strip()):
        if required:
            raise ApiError(f"Le champ « {label} » est obligatoire.")
        return ""
    if not isinstance(val, (str, int)):
        raise ApiError(f"Le champ « {label} » est invalide.")
    val = str(val).strip()
    if len(val) > max_len:
        raise ApiError(f"Le champ « {label} » est trop long (maximum {max_len} caractères).")
    return val


def integer(data, key, label, minimum=None, maximum=None, required=True):
    val = data.get(key)
    if val in (None, ""):
        if required:
            raise ApiError(f"Le champ « {label} » est obligatoire.")
        return None
    try:
        if isinstance(val, bool):
            raise ValueError
        val = int(val)
    except (TypeError, ValueError):
        raise ApiError(f"Le champ « {label} » doit être un nombre entier.")
    if minimum is not None and val < minimum:
        raise ApiError(f"Le champ « {label} » doit être au moins {minimum}.")
    if maximum is not None and val > maximum:
        raise ApiError(f"Le champ « {label} » doit être au plus {maximum}.")
    return val


def choice(data, key, label, options, required=True):
    val = text(data, key, label, 50, required)
    if val and val not in options:
        raise ApiError(f"Valeur invalide pour « {label} ».")
    return val


def parse_dt(value, label):
    """Accepte AAAA-MM-JJTHH:MM ; renvoie la même forme normalisée."""
    if not isinstance(value, str):
        raise ApiError(f"Le champ « {label} » est obligatoire.")
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(value.strip(), fmt)
            break
        except ValueError:
            dt = None
    if dt is None:
        raise ApiError(f"Date/heure invalide pour « {label} ».")
    if dt > datetime.now() + timedelta(days=1):
        raise ApiError(f"« {label} » ne peut pas être dans le futur.")
    if dt.year < 2000:
        raise ApiError(f"Date/heure invalide pour « {label} ».")
    return dt.strftime("%Y-%m-%dT%H:%M")


def parse_date(value, label, allow_future=True):
    if not isinstance(value, str):
        raise ApiError(f"Le champ « {label} » est obligatoire.")
    try:
        d = datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ApiError(f"Date invalide pour « {label} ».")
    if d.year < 2000:
        raise ApiError(f"Date invalide pour « {label} ».")
    if not allow_future and d > datetime.now().date():
        raise ApiError(f"« {label} » ne peut pas être dans le futur.")
    return d.isoformat()


def next_numero(db, table, annee):
    """Numéro d'ordre séquentiel par année (à appeler dans une transaction)."""
    row = db.execute(f"SELECT COALESCE(MAX(numero_ordre), 0) FROM {table} WHERE annee = ?",
                     (annee,)).fetchone()
    return row[0] + 1


def thanato_snapshot(db, data):
    """Thanatopracteur de service : par défaut l'utilisateur connecté, sinon un compte choisi."""
    uid = data.get("thanato_user_id")
    if uid in (None, ""):
        u = g.user
    else:
        u = db.execute("SELECT full_name, visa, role, active, statut FROM users WHERE id = ?", (uid,)).fetchone()
        if not u or not u["active"] or u["statut"] != "actif" or u["role"] != "thanatopracteur":
            raise ApiError("Thanatopracteur de service introuvable.")
    return u["full_name"], u["visa"]


def name_exists(db, table, column, value, exclude_id=None):
    """Doublon insensible à la casse ET aux accents de casse (É/é) : SQLite lower() ne gère que l'ASCII."""
    wanted = value.casefold()
    for row in db.execute(f"SELECT id, {column} AS v FROM {table}"):
        if row["id"] != exclude_id and row["v"].casefold() == wanted:
            return True
    return False
