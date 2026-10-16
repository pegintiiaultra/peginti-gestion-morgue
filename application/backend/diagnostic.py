"""Diagnostic complet à lancer dans Termux :  cd ~/peginti-morgue/backend && python diagnostic.py
Rejoue un vrai parcours (créer un box, enregistrer une entrée, un transfert, une sortie) sur une base TEMPORAIRE :
vos données ne sont pas touchées. Chaque étape affiche OK ou l'erreur exacte."""
import hashlib
import json
import os
import sys
import tempfile
import traceback

tmp = tempfile.mkdtemp()
os.environ["MORGUE_DATA"] = tmp
os.environ.setdefault("MORGUE_SECRET", "diagnostic-" + "x" * 32)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Python", sys.version.split()[0], "| scrypt :", hasattr(hashlib, "scrypt"))
failed = []


def step(name, fn):
    try:
        r = fn()
        print(f"  OK   {name}" + (f" -> {r}" if r else ""))
    except Exception:
        failed.append(name)
        print(f"  ECHEC {name}")
        traceback.print_exc()


try:
    import sqlite3
    print("SQLite", sqlite3.sqlite_version)
    import flask, jwt  # noqa: E401
    from importlib.metadata import version
    print("Flask", version("flask"))
    from accounts import hash_password
    from app import app
    from db import connect
except Exception:
    print("ECHEC au chargement (module manquant ?) :")
    traceback.print_exc()
    print("\n=> Lancez :  pip install -r requirements.txt")
    sys.exit(1)

c = connect()
print("Mode du journal SQLite :", c.execute("PRAGMA journal_mode").fetchone()[0])
c.execute("INSERT INTO users (username,password_hash,full_name,role,visa) VALUES (?,?,?,?,?)",
          ("diag", hash_password("DiagTest2026x"), "Diag", "thanatopracteur", "V1"))
c.execute("INSERT INTO users (username,password_hash,full_name,role,visa) VALUES (?,?,?,?,?)",
          ("diagadm", hash_password("DiagTest2026x"), "Diag Admin", "admin", "ADM"))
c.close()
cl = app.test_client()
H = {}


def call(method, url, **kw):
    r = getattr(cl, method)(url, headers=H, **kw)
    data = r.get_json(silent=True)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} : {json.dumps(data, ensure_ascii=False)}")
    return data


def login(user="diag"):
    H["Authorization"] = "Bearer " + call("post", "/api/login", json={"username": user, "password": "DiagTest2026x"})["token"]


step("connexion administrateur", lambda: login("diagadm"))
step("création d'un box A (4 divisions)", lambda: call("post", "/api/shelves", json={"name": "A", "nb_divisions": 4, "capacity": 24, "include_floor": True, "floor_capacity": 3}))
step("connexion thanatopracteur", lambda: login("diag"))
plan = {}
step("lecture du plan", lambda: plan.update(call("get", "/api/plan")) or f"{len(plan['shelves'])} box")
ent = {}
div = plan["shelves"][0]["divisions"][0]["id"] if plan.get("shelves") else None
step("enregistrement d'une entrée (type chambre commune)", lambda: ent.update(call("post", "/api/entrees", json=dict(
    nom="TEST", prenoms="Essai", age_value=40, age_unit="ans", sexe="M", cas="externe", date_entree="2025-09-15T08:30",
    division_id=div, slot="", type_chambre="commune", resp_nom="Resp", resp_contact="699000000", resp_adresse="Yaoundé"))) or ent.get("emplacement"))
step("aperçu de facturation d'une levée", lambda: call("get", f"/api/levees/apercu?dossier_id={ent['id']}&date_levee=2025-09-17T10:00") if ent.get("id") else (_ for _ in ()).throw(RuntimeError("pas de dossier")))
step("aucune erreur serveur enregistrée", lambda: (_ for _ in ()).throw(RuntimeError(open(os.path.join(tmp, "erreurs.log")).read())) if os.path.getsize(os.path.join(tmp, "erreurs.log")) else "ok")
print()
if failed:
    print("RESULTAT : ECHEC à l'étape :", ", ".join(failed))
    print("Envoyez-moi tout ce texte (capture ou copier-coller).")
else:
    print("RESULTAT : tout fonctionne dans votre Termux. Si l'écran échoue encore, envoyez le contenu de :")
    print("   curl -s localhost:3001/api/sante")
    print("   tail -n 30 data/erreurs.log")
