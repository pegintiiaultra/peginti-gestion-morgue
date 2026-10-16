"""Application PEGINTI Morgue : API + service des fichiers du frontend."""
import logging
import os
import sqlite3
import sys
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request, send_from_directory

import accounts
import annonces
import config_routes
import exports
import mfa
import registres
import rh
import stats
import tarifs
from core import ApiError, close_db, secret_key
from db import DATA_DIR, DB_PATH, connect, init_db

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
       "object-src 'none'; worker-src 'self'; manifest-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


def create_app():
    init_db()
    secret_key()  # crée la clé de signature au premier lancement
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024
    if os.environ.get("MORGUE_BEHIND_PROXY") == "1":
        # Derrière Cloudflare Tunnel / Caddy : on fait confiance à UN niveau de proxy pour l'IP et le schéma
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.teardown_appcontext(close_db)
    for module in (accounts, annonces, config_routes, exports, mfa, registres, rh, stats, tarifs):
        app.register_blueprint(module.bp)

    @app.errorhandler(ApiError)
    def api_error(e):
        payload = {"error": e.message}
        if e.code:
            payload["code"] = e.code
        return jsonify(payload), e.status

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "Introuvable."}), 404

    @app.errorhandler(405)
    def not_allowed(_e):
        return jsonify({"error": "Méthode non autorisée."}), 405

    @app.errorhandler(413)
    def too_big(_e):
        return jsonify({"error": "Fichier trop volumineux (maximum 5 Mo)."}), 413

    os.makedirs(DATA_DIR, exist_ok=True)
    handler = RotatingFileHandler(os.path.join(DATA_DIR, "erreurs.log"), maxBytes=500_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    app.logger.addHandler(handler)

    @app.errorhandler(Exception)
    def unexpected(e):
        app.logger.exception("Erreur interne sur %s %s", request.method, request.path)
        return jsonify({"error": f"Erreur interne du serveur ({type(e).__name__}). "
                                 "Détail dans backend/data/erreurs.log"}), 500

    @app.get("/api/sante")
    def sante():
        """Vérification publique sans donnée sensible : base accessible, écriture possible, version."""
        info = {"python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version, "base": DB_PATH}
        try:
            db = connect()
            info["journal"] = db.execute("PRAGMA journal_mode").fetchone()[0]
            info["box"] = db.execute("SELECT COUNT(*) FROM shelves WHERE active=1").fetchone()[0]
            info["comptes_actifs"] = db.execute("SELECT COUNT(*) FROM users WHERE statut='actif'").fetchone()[0]
            db.execute("BEGIN IMMEDIATE"); db.execute("ROLLBACK")  # test du verrou d'écriture
            info["ecriture"] = "ok"
            db.close()
        except Exception as ex:  # noqa: BLE001
            info["ecriture"] = f"ERREUR {type(ex).__name__}: {ex}"
        return jsonify(info)

    @app.after_request
    def secure_headers(resp):
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        if request.is_secure:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000"
        # no-store partout : Cloudflare (et le navigateur) ne gardent jamais une ancienne version de l'interface après une mise à jour
        resp.headers["Cache-Control"] = "no-store" if request.path.startswith("/api/") else "no-cache, no-store, must-revalidate"
        resp.headers["CDN-Cache-Control"] = "no-store"
        return resp

    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/<path:path>")
    def static_files(path):
        if path.startswith("api/"):
            raise ApiError("Introuvable.", 404)
        return send_from_directory(FRONTEND_DIR, path)

    return app


app = create_app()


def sauvegarde_auto():
    """Sauvegarde quotidienne automatique (data/backups, 30 dernières gardées) : aucune action de l'utilisateur."""
    import threading, time
    from datetime import datetime

    def boucle():
        while True:
            try:
                folder = os.path.join(DATA_DIR, "backups")
                os.makedirs(folder, exist_ok=True)
                jour = f"{datetime.now():%Y%m%d}"
                if not any(f.startswith(f"auto-{jour}") for f in os.listdir(folder)) and os.path.exists(DB_PATH):
                    dest = os.path.join(folder, f"auto-{jour}-{datetime.now():%H%M%S}.db")
                    src, dst = sqlite3.connect(DB_PATH), sqlite3.connect(dest)
                    with dst:
                        src.backup(dst)
                    src.close(); dst.close(); os.chmod(dest, 0o600)
                    for f in sorted(x for x in os.listdir(folder) if x.startswith("auto-"))[:-30]:
                        os.remove(os.path.join(folder, f))
            except Exception:
                pass  # ne jamais gêner le service
            time.sleep(3600)
    threading.Thread(target=boucle, daemon=True).start()


if __name__ == "__main__":
    host = os.environ.get("MORGUE_HOST", "0.0.0.0")
    port = int(os.environ.get("MORGUE_PORT", "3001"))
    sauvegarde_auto()
    try:
        from waitress import serve
        print(f"PEGINTI Morgue : http://{host}:{port} (waitress)")
        serve(app, host=host, port=port, threads=6)
    except ImportError:
        print(f"PEGINTI Morgue : http://{host}:{port} (serveur Flask)")
        app.run(host=host, port=port, threaded=True)
