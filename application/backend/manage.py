"""Outils d'administration en ligne de commande.

  python manage.py createuser <identifiant> <role>   # crée un compte (mot de passe demandé, jamais affiché)
  python manage.py resetpw <identifiant>             # change le mot de passe d'un compte
  python manage.py reset2fa <identifiant>            # désactive la double authentification d'un compte
  python manage.py mfa <aucun|admin|tous>            # règle de double authentification de la morgue
  python manage.py backup                            # sauvegarde la base (garde les 30 dernières)
"""
import getpass
import os
import sqlite3
import sys
from datetime import datetime

from accounts import ROLES, check_new_password, hash_password, normalize_username
from core import ApiError
from db import DATA_DIR, DB_PATH, connect, init_db


def ask_password():
    while True:
        pw = getpass.getpass("Mot de passe (10 caractères minimum, lettres + chiffres) : ")
        try:
            check_new_password(pw)
        except ApiError as e:
            print(" ", e.message)
            continue
        if pw != getpass.getpass("Confirmez le mot de passe : "):
            print("  Les mots de passe ne correspondent pas.")
            continue
        return pw


def createuser(username, role):
    if role not in ROLES:
        sys.exit(f"Rôle invalide. Choisissez parmi : {', '.join(ROLES)}")
    init_db()
    conn = connect()
    try:
        username = normalize_username(username)
    except ApiError as e:
        sys.exit(e.message)
    if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        sys.exit("Cet identifiant existe déjà.")
    full_name = input("Nom complet : ").strip() or username
    visa = input("Visa (facultatif) : ").strip()
    conn.execute("INSERT INTO users (username, password_hash, full_name, role, visa) VALUES (?,?,?,?,?)",
                 (username, hash_password(ask_password()), full_name, role, visa))
    conn.execute("INSERT INTO audit_log (username, action, entity, detail) VALUES (?,?,?,?)",
                 ("manage.py", "compte_cree", "user", f'{{"username": "{username}", "role": "{role}"}}'))
    print(f"Compte « {username} » ({role}) créé.")


def resetpw(username):
    init_db()
    conn = connect()
    username = " ".join(username.split()).casefold()
    if not conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        sys.exit("Compte introuvable.")
    conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hash_password(ask_password()), username))
    conn.execute("INSERT INTO audit_log (username, action, entity) VALUES (?,?,?)",
                 ("manage.py", "mot_de_passe_reinitialise", "user"))
    print("Mot de passe modifié.")


def reset2fa(username):
    """Téléphone perdu et plus aucun code de secours : désactive la double authentification du compte."""
    init_db()
    conn = connect()
    username = " ".join(username.split()).casefold()
    if not conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        sys.exit("Compte introuvable.")
    conn.execute("UPDATE users SET totp_secret = NULL, totp_pending = NULL, totp_active = 0, totp_last_step = 0, "
                 "totp_backup = NULL WHERE username = ?", (username,))
    conn.execute("INSERT INTO audit_log (username, action, entity) VALUES (?,?,?)",
                 ("manage.py", "2fa_reinitialisee", "user"))
    print("Double authentification désactivée pour ce compte (à réactiver à la prochaine connexion si la politique l'exige).")


def mfa(valeur):
    if valeur not in ("aucun", "admin", "tous"):
        sys.exit("Valeur possible : aucun, admin ou tous.")
    conn = connect()
    conn.execute("INSERT INTO settings (key, value) VALUES ('mfa_exigee', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (valeur,))
    conn.execute("INSERT INTO audit_log (username, action, entity, detail) VALUES ('manage.py','politique_2fa_modifiee','settings', ?)",
                 ('{"politique": "%s"}' % valeur,))
    conn.commit(); conn.close()
    print("Double authentification exigée de :", {"aucun": "personne", "admin": "les administrateurs", "tous": "tous les comptes"}[valeur])
    print("Chaque compte concerné devra l'activer à sa prochaine connexion.")


def backup():
    folder = os.path.join(DATA_DIR, "backups")
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, f"morgue-{datetime.now():%Y%m%d-%H%M%S}.db")
    src, dst = sqlite3.connect(DB_PATH), sqlite3.connect(dest)
    with dst:
        src.backup(dst)  # copie cohérente même pendant l'utilisation
    src.close(); dst.close()
    os.chmod(dest, 0o600)
    old = sorted(f for f in os.listdir(folder) if f.startswith("morgue-") and f.endswith(".db"))[:-30]
    for f in old:
        os.remove(os.path.join(folder, f))
    print(f"Sauvegarde créée : {dest}")
    print("Pensez aussi à copier le dossier data/uploads (plans de localisation) hors du téléphone.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 3 and args[0] == "createuser":
        createuser(args[1], args[2])
    elif len(args) == 2 and args[0] == "resetpw":
        resetpw(args[1])
    elif len(args) == 2 and args[0] == "reset2fa":
        reset2fa(args[1])
    elif len(args) == 2 and args[0] == "mfa":
        mfa(args[1])
    elif args == ["backup"]:
        backup()
    else:
        print(__doc__)
