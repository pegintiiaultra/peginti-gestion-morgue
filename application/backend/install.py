"""Installation : crée une base VIDE avec un seul administrateur initial.

    python install.py            # demande confirmation si une base existe déjà
    python install.py --force    # sans confirmation (scripts) — refusé si la base contient des données réelles
    python install.py --force --effacer-donnees   # efface aussi une base contenant des données (copie conservée)

Si une base existe, elle est d'abord COPIÉE dans data/backups/avant-installation-<date>/ (avec les plans de
localisation), puis remplacée. L'administrateur initial devra choisir son mot de passe à la première connexion.
"""
import os
import shutil
import sys
from datetime import datetime

from accounts import hash_password
from db import DATA_DIR, DB_PATH, UPLOAD_DIR, connect, init_db

ADMIN = dict(username="admin", password="Admin123!", visa="ADMIN", full_name="Administrateur Système", role="admin")


def archive_existing():
    """Met l'ancienne base (et ses fichiers) en sécurité avant de la remplacer. Renvoie le dossier d'archive."""
    sidecars = [DB_PATH + s for s in ("", "-wal", "-shm")]
    if not any(os.path.exists(p) for p in sidecars):
        return None
    dest = os.path.join(DATA_DIR, "backups", f"avant-installation-{datetime.now():%Y%m%d-%H%M%S}")
    os.makedirs(dest, exist_ok=True)
    os.chmod(dest, 0o700)
    for p in sidecars:
        if os.path.exists(p):
            shutil.move(p, os.path.join(dest, os.path.basename(p)))
    if os.path.isdir(UPLOAD_DIR) and os.listdir(UPLOAD_DIR):
        shutil.move(UPLOAD_DIR, os.path.join(dest, "uploads"))
    return dest


def contenu_existant():
    """Décrit ce que la base actuelle contient (corps enregistrés, comptes, box) ; None si elle est vide ou illisible."""
    import sqlite3
    if not os.path.exists(DB_PATH):
        return None
    try:
        c = sqlite3.connect(DB_PATH)
        n = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("dossiers", "users", "shelves")}
        c.close()
    except sqlite3.Error:
        return None
    if n["dossiers"] == 0 and n["users"] <= 1 and n["shelves"] == 0:
        return None
    return f"{n['dossiers']} dossier(s) de défunts, {n['users']} compte(s), {n['shelves']} box"


def install():
    os.makedirs(DATA_DIR, exist_ok=True)
    saved = archive_existing()
    # Nouvelle clé de signature : les anciennes sessions ne peuvent pas ouvrir la nouvelle base
    key = os.path.join(DATA_DIR, "secret.key")
    if os.path.exists(key):
        os.remove(key)
    init_db()
    conn = connect()
    conn.execute(
        "INSERT INTO users (username, password_hash, full_name, role, visa, active, statut, origine, doit_changer_mdp) "
        "VALUES (?,?,?,?,?,1,'actif','install',1)",
        (ADMIN["username"], hash_password(ADMIN["password"]), ADMIN["full_name"], ADMIN["role"], ADMIN["visa"]))
    # Nouvelle installation : la double authentification est exigée de TOUS les comptes (modifiable dans « Paramètres »)
    conn.execute("UPDATE settings SET value = 'tous' WHERE key = 'mfa_exigee'")
    conn.execute("INSERT INTO audit_log (username, action, entity, detail) VALUES ('install.py','installation','systeme', NULL)")
    conn.close()
    return saved


def main():
    force = "--force" in sys.argv[1:]
    effacer = "--effacer-donnees" in sys.argv[1:]
    contenu = contenu_existant()
    if os.path.exists(DB_PATH) and contenu and not effacer:
        print("STOP : cette base contient déjà des données réelles :", contenu)
        print("  -> Pour METTRE À JOUR sans rien perdre :  sh installer.sh --maj")
        print("  -> Pour tout effacer (une copie est gardée dans data/backups/) :")
        if force or not sys.stdin.isatty():
            sys.exit("     relancez avec  --force --effacer-donnees   (volontairement explicite)")
        if input("     tapez exactement  EFFACER MES DONNEES  : ").strip() != "EFFACER MES DONNEES":
            sys.exit("Installation annulée, rien n'a été modifié.")
    elif os.path.exists(DB_PATH) and not force:
        if not sys.stdin.isatty():
            sys.exit("Une base existe déjà : %s\nRelancez avec --force pour la remplacer (elle sera sauvegardée)." % DB_PATH)
        print("Une base vide existe déjà et va être remplacée :", DB_PATH)
        if input("Tapez OUI pour continuer : ").strip() != "OUI":
            sys.exit("Installation annulée, rien n'a été modifié.")
    saved = install()
    if saved:
        print("Ancienne base sauvegardée dans :", saved)
    print("Base de données :", DB_PATH)
    print("Administrateur initial : identifiant « admin » / mot de passe « Admin123! »")
    print("  (le changement du mot de passe sera exigé à la première connexion)")
    print("  Double authentification : exigée de TOUS les comptes (installez une application d'authentification : Google/Microsoft Authenticator, Aegis, FreeOTP)")
    print("Installation OK")


if __name__ == "__main__":
    main()
