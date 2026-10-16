"""Tests du backend. Lancer :  python -m unittest discover -s tests -v   (depuis le dossier backend)"""
import io
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp()
os.environ["MORGUE_DATA"] = _tmp
os.environ["MORGUE_SECRET"] = "secret-de-test-" + "x" * 32
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from accounts import hash_password  # noqa: E402
from app import app  # noqa: E402
from db import connect  # noqa: E402

PW = "MotDePasse2026!"
ENTREE_BASE = dict(nom="MBARGA", prenoms="Jean", age_value=54, age_unit="ans", sexe="M", cas="externe",
                   date_entree="2025-09-15T08:30", resp_nom="MBARGA Paul", resp_contact="699000000",
                   resp_adresse="Yaoundé, Mvog-Ada", resp_visa="V123", type_chambre="commune")
WEDNESDAY = "2025-10-01T10:00"
MONDAY = "2025-10-06T10:00"


def sortie_payload(dossier_id, date=WEDNESDAY, **kw):
    p = dict(dossier_id=dossier_id, date_sortie=date, resp_nom="MBARGA Paul", resp_contact="699000000",
             resp_adresse="Yaoundé", genre_mort="naturelle", region="Centre", departement="Mfoundi",
             arrondissement="Yaoundé 6e", village="Ebang", date_inhumation="2025-10-02")
    p.update(kw)
    return p


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = connect()
        for u, role in (("admin1", "admin"), ("resp1", "admin"), ("thana1", "thanatopracteur"),
                        ("thana2", "thanatopracteur"), ("dir1", "admin"), ("dg1", "super_admin"), ("verrou1", "admin")):
            conn.execute("INSERT OR IGNORE INTO users (username, password_hash, full_name, role, visa) VALUES (?,?,?,?,?)",
                         (u, hash_password(PW), u.upper(), role, "VISA-" + u))
        conn.close()
        cls.client = app.test_client()
        cls.tokens = {}
        for u in ("admin1", "resp1", "thana1", "thana2", "dir1", "dg1"):
            r = cls.client.post("/api/login", json={"username": u, "password": PW})
            assert r.status_code == 200, r.get_json()
            cls.tokens[u] = r.get_json()["token"]

    def call(self, who, method, url, **kw):
        headers = {"Authorization": "Bearer " + self.tokens[who]} if who else {}
        return getattr(self.client, method)(url, headers=headers, **kw)


class T01_Auth(Base):
    def test_sans_jeton(self):
        self.assertEqual(self.call(None, "get", "/api/plan").status_code, 401)

    def test_jeton_invalide(self):
        r = self.client.get("/api/plan", headers={"Authorization": "Bearer abc.def.ghi"})
        self.assertEqual(r.status_code, 401)

    def test_mauvais_mot_de_passe_puis_blocage(self):
        c = app.test_client()
        for _ in range(5):
            self.assertEqual(c.post("/api/login", json={"username": "verrou1", "password": "faux"}).status_code, 401)
        self.assertEqual(c.post("/api/login", json={"username": "verrou1", "password": PW}).status_code, 429)

    def test_roles(self):
        self.assertEqual(self.call("dir1", "post", "/api/entrees", json=ENTREE_BASE).status_code, 403)
        self.assertEqual(self.call("thana1", "post", "/api/shelves", json={"name": "Z", "nb_divisions": 1}).status_code, 403)
        self.assertEqual(self.call("thana1", "get", "/api/users").status_code, 403)
        self.assertEqual(self.call("admin1", "get", "/api/users").status_code, 200)

    def test_mot_de_passe_faible_refuse(self):
        r = self.call("admin1", "post", "/api/users", json={"username": "nouveau", "password": "court1",
                                                            "full_name": "N", "role": "direction"})
        self.assertEqual(r.status_code, 400)

    def test_headers_securite(self):
        r = self.client.get("/")
        self.assertIn("Content-Security-Policy", r.headers)
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")


class T02_Registres(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        c = cls.client
        r = c.post("/api/shelves", headers={"Authorization": "Bearer " + cls.tokens["resp1"]},
                   json={"name": "a", "nb_divisions": 4, "include_floor": True, "capacity": 2, "floor_capacity": 3})
        assert r.status_code == 201, r.get_json()
        cls.shelves = c.get("/api/shelves", headers={"Authorization": "Bearer " + cls.tokens["resp1"]}).get_json()
        cls.div = {d["label"]: d["id"] for d in cls.shelves[0]["divisions"]}

    def entree(self, label, who="thana1", **kw):
        p = dict(ENTREE_BASE, division_id=self.div[label]); p.update(kw)
        return self.call(who, "post", "/api/entrees", json=p)

    def test_01_structure_generee(self):
        self.assertEqual(list(self.div), ["A1", "A2", "A3", "A4", "A0"])

    def test_02_attribution_premier_emplacement_libre(self):
        r1 = self.entree("A1"); r2 = self.entree("A1", nom="NGONO")
        self.assertEqual((r1.status_code, r1.get_json()["emplacement"]), (201, "A1a"))
        self.assertEqual(r2.get_json()["emplacement"], "A1b")
        self.assertEqual(r1.get_json()["numero"], "1/2025")
        self.assertEqual(r2.get_json()["numero"], "2/2025")

    def test_03_division_saturee_et_doublon(self):
        r = self.entree("A1", nom="TROP")
        self.assertEqual(r.status_code, 409)
        r = self.entree("A2", slot="a"); self.assertEqual(r.status_code, 201)
        r = self.entree("A2", slot="a", nom="DOUBLON"); self.assertEqual(r.status_code, 409)
        r = self.entree("A2", slot="z", nom="HORS"); self.assertEqual(r.status_code, 400)

    def test_04_sol_reserve_a_la_saturation(self):
        r = self.entree("A0", nom="SOL1")
        self.assertEqual(r.status_code, 409); self.assertEqual(r.get_json()["code"], "DEROGATION_REQUISE")
        r = self.entree("A0", nom="SOL2", derogation_motif="Travaux dans la chambre froide")
        self.assertEqual((r.status_code, r.get_json()["emplacement"]), (201, "A0a"))
        # on sature A2, A3, A4 (A1 déjà pleine) -> le sol devient libre sans dérogation
        self.entree("A2", nom="S2"); self.entree("A3", nom="S3a"); self.entree("A3", nom="S3b")
        self.entree("A4", nom="S4a"); self.entree("A4", nom="S4b")
        plan = self.call("dir1", "get", "/api/plan").get_json()
        self.assertTrue(plan["shelves"][0]["saturated"]); self.assertTrue(plan["alerts"])
        r = self.entree("A0", nom="SOL3")
        self.assertEqual((r.status_code, r.get_json()["emplacement"]), (201, "A0b"))

    def test_05_validation(self):
        r = self.call("thana1", "post", "/api/entrees", json={"nom": "X"}); self.assertEqual(r.status_code, 400)
        r = self.entree("A2", date_entree="2999-01-01T10:00", nom="FUTUR"); self.assertEqual(r.status_code, 400)
        r = self.entree("A2", cas="interne", nom="SANS_SERVICE"); self.assertEqual(r.status_code, 400)

    def test_06_reduction_capacite_bloquee(self):
        tok = "resp1"
        r = self.call(tok, "patch", f"/api/divisions/{self.div['A1']}", json={"capacity": 1})
        self.assertEqual(r.status_code, 409)
        r = self.call(tok, "patch", f"/api/divisions/{self.div['A1']}", json={"active": False})
        self.assertEqual(r.status_code, 409)

    def test_07_cycle_complet(self):
        # nouvelle étagère pour isoler le scénario
        self.call("resp1", "post", "/api/shelves", json={"name": "B", "nb_divisions": 1, "capacity": 4})
        tree = self.call("resp1", "get", "/api/shelves").get_json()
        b1 = next(d["id"] for s in tree if s["name"] == "B" for d in s["divisions"])
        svc = self.call("resp1", "get", "/api/services").get_json()[0]["id"]
        r = self.call("thana1", "post", "/api/entrees", json=dict(ENTREE_BASE, nom="CYCLE", division_id=b1,
                                                                   cas="interne", service_id=svc))
        self.assertEqual(r.status_code, 201); did = r.get_json()["dossier_id"]; eid = r.get_json()["id"]
        self.assertEqual(r.get_json()["emplacement"], "B1a")
        # transfert : libère B1a
        raison = self.call("thana1", "get", "/api/raisons").get_json()
        autopsie = next(x["id"] for x in raison if x["libelle"] == "Autopsie")
        autre = next(x["id"] for x in raison if x["est_autre"])
        base = dict(dossier_id=did, date_transfert="2025-09-20T09:00", resp_nom="R", resp_contact="6", resp_adresse="A",
                    lieu="Hôpital Central")
        self.assertEqual(self.call("thana1", "post", "/api/transferts", json=dict(base, raison_id=autre)).status_code, 400)
        r = self.call("thana1", "post", "/api/transferts", json=dict(base, raison_id=autopsie))
        self.assertEqual((r.status_code, r.get_json()["libere"]), (201, "B1a")); tid = r.get_json()["id"]
        self.assertEqual(self.call("thana1", "post", "/api/transferts", json=dict(base, raison_id=autopsie)).status_code, 409)
        # le slot est libre : un autre corps le prend
        r2 = self.call("thana1", "post", "/api/entrees", json=dict(ENTREE_BASE, nom="AUTRE", division_id=b1))
        self.assertEqual(r2.get_json()["emplacement"], "B1a")
        # annuler le transfert est maintenant impossible (emplacement repris)
        r = self.call("thana1", "post", f"/api/transferts/{tid}/annuler", json={"motif": "Erreur de saisie"})
        self.assertEqual(r.status_code, 409)
        # l'administration est en lecture seule : ni saisie, ni annulation, ni modification
        r = self.call("admin1", "post", f"/api/entrees/{eid}/annuler", json={"motif": "Erreur de saisie"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.call("dg1", "patch", f"/api/entrees/{eid}", json={"nom": "X"}).status_code, 403)

    def test_08_levee_puis_sortie_et_plan(self):
        self.call("resp1", "post", "/api/shelves", json={"name": "C", "nb_divisions": 1, "capacity": 4})
        tree = self.call("resp1", "get", "/api/shelves").get_json()
        c1 = next(d["id"] for s in tree if s["name"] == "C" for d in s["divisions"])
        r = self.call("thana1", "post", "/api/entrees", json=dict(ENTREE_BASE, nom="SORTI", division_id=c1))
        did = r.get_json()["dossier_id"]
        # sortie définitive impossible avant la levée
        r = self.call("thana1", "post", "/api/sorties", json=sortie_payload(did, WEDNESDAY))
        self.assertEqual(r.status_code, 409)
        lev = dict(dossier_id=did, date_levee=WEDNESDAY, resp_nom="MBARGA Paul", resp_contact="699000000",
                   resp_adresse="Yaoundé", montant_verse=0)
        r = self.call("thana1", "post", "/api/levees", json=lev)
        self.assertEqual((r.status_code, r.get_json()["libere"]), (201, "C1a"))
        r = self.call("thana1", "post", "/api/sorties", json=sortie_payload(did, WEDNESDAY, genre_mort="inconnue"))
        self.assertEqual(r.status_code, 400)
        r = self.call("thana1", "post", "/api/sorties", json=sortie_payload(did, WEDNESDAY))
        self.assertEqual(r.status_code, 201); sid = r.get_json()["id"]
        bad = self.call("thana1", "post", f"/api/sorties/{sid}/plan",
                        data={"plan": (io.BytesIO(b"pas un pdf"), "x.pdf")}, content_type="multipart/form-data")
        self.assertEqual(bad.status_code, 400)
        ok = self.call("thana1", "post", f"/api/sorties/{sid}/plan",
                       data={"plan": (io.BytesIO(b"%PDF-1.4 test"), "plan.pdf")}, content_type="multipart/form-data")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.call(None, "get", f"/api/sorties/{sid}/plan").status_code, 401)
        self.assertEqual(self.call("dir1", "get", f"/api/sorties/{sid}/plan").data, b"%PDF-1.4 test")
        # annulation de la sortie puis de la levée : le corps revient à C1a
        self.assertEqual(self.call("thana1", "post", f"/api/sorties/{sid}/annuler", json={"motif": "Sortie saisie par erreur"}).status_code, 200)
        lid = self.call("thana1", "get", "/api/levees?q=SORTI").get_json()[0]["id"]
        self.assertEqual(self.call("thana1", "post", f"/api/levees/{lid}/annuler", json={"motif": "Levée saisie par erreur"}).status_code, 200)
        en_cons = self.call("thana1", "get", "/api/dossiers/en-conservation?q=SORTI").get_json()
        self.assertEqual(en_cons[0]["emplacement"], "C1a")

    def test_09_registres_et_audit(self):
        lst = self.call("dir1", "get", "/api/entrees").get_json()
        self.assertGreater(len(lst), 5)
        self.assertEqual(self.call("dir1", "get", "/api/entrees?q=MBARGA").status_code, 200)
        n = connect().execute("SELECT COUNT(*) FROM audit_log WHERE action = 'entree_creee'").fetchone()[0]
        self.assertGreater(n, 5)

    def test_10_statistiques(self):
        s = self.call("dir1", "get", "/api/stats").get_json()
        self.assertEqual(s["mois"], ["2025-09"])  # levée et sortie d'octobre annulées : exclues des statistiques
        self.assertEqual(sum(s["sorties_par_mois"]), 0)
        self.assertEqual(sum(s["entrees_par_mois"]), s["flux"]["entrees"])
        self.assertEqual(s["raison_dominante"]["nom"], "Autopsie")
        self.assertEqual(s["service_dominant"]["n"], 1)
        s2 = self.call("dir1", "get", "/api/stats?cas=interne&from=2025-09-01&to=2025-09-30").get_json()
        self.assertEqual(s2["cas"], {"interne": 1})
        self.assertEqual(self.call("dir1", "get", "/api/stats?from=pas-une-date").status_code, 400)


class T03_RH(Base):
    """Gardes : systèmes 12 h / 24 h, présence obligatoire jeudi-vendredi, thanatopracteur de service."""

    def put(self, who, date, type_, equipe_id):
        return self.call(who, "put", "/api/rh/planning", json={"date": date, "type": type_, "equipe_id": equipe_id})

    def test_01_equipes_agents_et_roles(self):
        cls = type(self)
        for nom in ("Équipe A", "Équipe B", "Équipe C"):
            self.assertEqual(self.call("resp1", "post", "/api/rh/equipes", json={"nom": nom}).status_code, 201)
        self.assertEqual(self.call("resp1", "post", "/api/rh/equipes", json={"nom": "équipe a"}).status_code, 409)
        self.assertEqual(self.call("thana1", "post", "/api/rh/equipes", json={"nom": "X"}).status_code, 403)
        eq = self.call("thana1", "get", "/api/rh/equipes").get_json()["equipes"]
        cls.A, cls.B, cls.C = [e["id"] for e in eq]
        uid = connect().execute("SELECT id FROM users WHERE username = 'thana1'").fetchone()[0]
        r = self.call("resp1", "post", "/api/rh/agents", json={"nom": "Agent A1", "fonction": "Thanatopracteur", "visa": "V1", "equipe_id": cls.A, "user_id": uid})
        self.assertEqual(r.status_code, 201)
        dup = self.call("resp1", "post", "/api/rh/agents", json={"nom": "Doublon", "equipe_id": cls.A, "user_id": uid})
        self.assertEqual(dup.status_code, 409)
        self.assertEqual(self.call("resp1", "post", "/api/rh/agents", json={"nom": "Agent A2", "equipe_id": cls.A}).status_code, 201)
        self.assertEqual(self.call("resp1", "post", "/api/rh/agents", json={"nom": "Agent B1", "equipe_id": cls.B}).status_code, 201)
        self.assertEqual(self.call("resp1", "post", "/api/rh/agents", json={"nom": "Agent C1", "equipe_id": cls.C}).status_code, 201)
        self.assertEqual(self.call("resp1", "post", "/api/rh/agents", json={"fonction": "sans nom"}).status_code, 400)

    def test_02_calendrier_regles(self):
        p = self.call("dir1", "get", "/api/rh/planning?mois=2025-10").get_json()
        self.assertEqual(p["systeme"], "12h")
        self.assertEqual([t["id"] for t in p["types"]], ["permanence", "garde"])
        by = {j["date"]: j for j in p["jours"]}
        self.assertTrue(by["2025-10-01"]["sortie_corps"])            # mercredi
        self.assertTrue(by["2025-10-02"]["presence_obligatoire"])    # jeudi
        self.assertTrue(by["2025-10-03"]["presence_obligatoire"])    # vendredi
        self.assertFalse(by["2025-10-06"]["presence_obligatoire"])   # lundi
        self.assertEqual(self.call("dir1", "get", "/api/rh/planning?mois=2025-13").status_code, 400)

    def test_03_equipe_sortante_exclue_jeudi(self):
        cls = type(self)
        self.assertEqual(self.put("resp1", "2025-10-01", "garde", cls.A).status_code, 200)   # garde de nuit mer. -> jeu. 7h30
        by = {j["date"]: j for j in self.call("dir1", "get", "/api/rh/planning?mois=2025-10").get_json()["jours"]}
        jeudi = by["2025-10-02"]
        self.assertEqual(jeudi["equipe_sortante"]["equipe_id"], cls.A)
        self.assertEqual(len(jeudi["agents_attendus"]), 2)            # B1 et C1 ; l'équipe A (sortante) est exclue
        self.assertFalse(any("Agent A" in n for n in jeudi["agents_attendus"]))
        self.assertEqual(self.put("thana1", "2025-10-01", "garde", cls.B).status_code, 403)
        self.assertEqual(self.put("resp1", "2025-10-01", "24h", cls.A).status_code, 400)      # type étranger au système actif

    def test_04_generation_rotation(self):
        r = self.call("resp1", "post", "/api/rh/planning/generer", json={"mois": "2025-11"})
        self.assertEqual((r.status_code, r.get_json()["cases_remplies"]), (200, 60))          # 30 jours x 2 gardes
        by = {j["date"]: j for j in self.call("dir1", "get", "/api/rh/planning?mois=2025-11").get_json()["jours"]}
        self.assertTrue(all(j["gardes"]["permanence"] and j["gardes"]["garde"] for j in by.values()))
        self.assertTrue(all(j["gardes"]["permanence"]["equipe_id"] != j["gardes"]["garde"]["equipe_id"] for j in by.values()))
        r = self.call("resp1", "post", "/api/rh/planning/generer", json={"mois": "2025-11"})
        self.assertEqual(r.get_json()["cases_remplies"], 0)                                   # ne remplace rien par défaut
        r = self.call("resp1", "post", "/api/rh/planning/generer", json={"mois": "2025-11", "ecraser": True})
        self.assertEqual(r.get_json()["cases_remplies"], 60)

    def test_05_thanatopracteur_de_service_12h(self):
        cls = type(self)
        self.put("resp1", "2025-10-02", "permanence", cls.A)
        self.put("resp1", "2025-10-02", "garde", cls.B)
        g = lambda at: self.call("thana1", "get", "/api/rh/service?at=" + at).get_json()
        self.assertEqual(g("2025-10-02T06:00")["garde"], {"date": "2025-10-01", "type": "garde", "label": "Garde (17h00-7h30)"})
        self.assertEqual(g("2025-10-02T06:00")["equipe"]["equipe_id"], cls.A)   # garde de la veille = équipe A
        j = g("2025-10-02T09:00"); self.assertEqual((j["garde"]["type"], j["equipe"]["equipe_id"]), ("permanence", cls.A))
        self.assertEqual([a["nom"] for a in j["agents"]], ["Agent A1", "Agent A2"])
        self.assertIsNotNone(j["agents"][0]["user_id"])
        n = g("2025-10-02T18:00"); self.assertEqual((n["garde"]["type"], n["equipe"]["equipe_id"]), ("garde", cls.B))
        self.assertEqual(g("2025-10-02T07:29")["garde"]["type"], "garde")
        self.assertEqual(g("2025-10-02T07:30")["garde"]["type"], "permanence")
        self.assertEqual(g("2025-10-02T17:00")["garde"]["type"], "garde")

    def test_06_systeme_24h(self):
        cls = type(self)
        self.assertEqual(self.call("thana1", "put", "/api/rh/systeme", json={"systeme": "24h"}).status_code, 403)
        self.assertEqual(self.call("resp1", "put", "/api/rh/systeme", json={"systeme": "36h"}).status_code, 400)
        self.assertEqual(self.call("resp1", "put", "/api/rh/systeme", json={"systeme": "24h"}).status_code, 200)
        self.assertEqual(self.put("resp1", "2025-10-01", "24h", cls.C).status_code, 200)
        self.assertEqual(self.put("resp1", "2025-10-01", "garde", cls.C).status_code, 400)
        s = self.call("thana1", "get", "/api/rh/service?at=2025-10-02T06:00").get_json()
        self.assertEqual((s["garde"]["date"], s["garde"]["type"], s["equipe"]["equipe_id"]), ("2025-10-01", "24h", cls.C))
        s = self.call("thana1", "get", "/api/rh/service?at=2025-10-01T07:30").get_json()
        self.assertEqual(s["garde"]["date"], "2025-10-01")
        by = {j["date"]: j for j in self.call("dir1", "get", "/api/rh/planning?mois=2025-10").get_json()["jours"]}
        self.assertEqual(by["2025-10-02"]["equipe_sortante"]["equipe_id"], cls.C)             # sortante = garde 24 h de la veille
        self.assertFalse(any("Agent C" in n for n in by["2025-10-02"]["agents_attendus"]))
        r = self.call("resp1", "post", "/api/rh/planning/generer", json={"mois": "2025-12"})
        self.assertEqual(r.get_json()["cases_remplies"], 31)
        self.put("resp1", "2025-10-01", "24h", None)                                          # retrait d'une case
        self.assertIsNone(self.call("dir1", "get", "/api/rh/planning?mois=2025-10").get_json()["jours"][0]["gardes"]["24h"])


class T04_Comptes(Base):
    def signup(self, nom, pw=PW, conf=None, **kw):
        import core
        core._failures.clear()
        return self.client.post("/api/inscription", json=dict(nom=nom, password=pw,
                                confirmation=pw if conf is None else conf, **kw))

    def login(self, username, pw=PW):
        return self.client.post("/api/login", json={"username": username, "password": pw})

    def test_inscription_attente_validation_connexion(self):
        self.assertEqual(self.signup("Dr  Ngo Bilong", visa="TH-12").status_code, 201)
        r = self.login("dr ngo bilong")
        self.assertEqual(r.status_code, 403)                       # en attente : aucun accès
        self.assertIn("validation", r.get_json()["error"])
        uid = next(u["id"] for u in self.call("admin1", "get", "/api/users").get_json() if u["statut"] == "en_attente")
        self.assertEqual(self.call("thana1", "post", f"/api/users/{uid}/valider", json={}).status_code, 403)
        self.assertEqual(self.call("admin1", "post", f"/api/users/{uid}/valider", json={}).status_code, 200)
        r = self.login("DR NGO  bilong")                            # insensible à la casse et aux espaces
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["user"]["role"], "thanatopracteur")
        self.assertEqual(r.get_json()["user"]["full_name"], "Dr Ngo Bilong")

    def test_inscription_controles(self):
        self.assertEqual(self.signup("Abc Def", pw="court1").status_code, 400)
        self.assertEqual(self.signup("Abc Def", conf="Autre2026!x").status_code, 400)
        self.assertEqual(self.signup("a").status_code, 400)
        self.assertEqual(self.signup("Éric Mballa").status_code, 201)
        self.assertEqual(self.signup("éric  MBALLA").status_code, 409)   # doublon accents/casse
        self.assertEqual(self.signup("ADMIN1").status_code, 409)

    def test_refus_supprime_la_demande(self):
        self.signup("Refuse Moi")
        uid = next(u["id"] for u in self.call("admin1", "get", "/api/users").get_json() if u["username"] == "refuse moi")
        self.assertEqual(self.call("admin1", "post", f"/api/users/{uid}/refuser").status_code, 200)
        self.assertEqual(self.login("refuse moi").status_code, 401)

    def test_suppression_avec_motif(self):
        conn = connect()
        cur = conn.execute("INSERT INTO users (username, password_hash, full_name, role) VALUES (?,?,?,?)",
                           ("a supprimer", hash_password(PW), "A Supprimer", "thanatopracteur"))
        uid = cur.lastrowid
        conn.close()
        tok = self.login("a supprimer").get_json()["token"]
        url = f"/api/users/{uid}"
        self.assertEqual(self.call("thana2", "delete", url, json={"motif": "deces", "password": PW}).status_code, 403)
        self.assertEqual(self.call("admin1", "delete", url, json={"password": PW}).status_code, 400)           # motif obligatoire
        self.assertEqual(self.call("admin1", "delete", url, json={"motif": "congé", "password": PW}).status_code, 400)
        self.assertEqual(self.call("admin1", "delete", url, json={"motif": "demission", "password": "faux"}).status_code, 403)
        self.assertEqual(self.call("admin1", "delete", url, json={"motif": "demission", "password": PW}).status_code, 200)
        self.assertEqual(self.login("a supprimer").status_code, 401)                                          # plus d'accès
        self.assertEqual(self.client.get("/api/plan", headers={"Authorization": "Bearer " + tok}).status_code, 401)
        row = next(u for u in self.call("admin1", "get", "/api/users").get_json() if u["id"] == uid)
        self.assertEqual((row["statut"], row["motif_suppression"], row["supprime_par"]), ("supprime", "demission", "admin1"))
        self.assertEqual(self.call("admin1", "delete", url, json={"motif": "deces", "password": PW}).status_code, 409)
        self.assertEqual(self.signup("A Supprimer").status_code, 409)       # le nom archivé n'est pas réutilisable
        self.assertNotIn("a supprimer", [p["full_name"].lower() for p in self.call("thana1", "get", "/api/personnel").get_json()])

    def test_dernier_admin_et_soi_meme(self):
        me = next(u["id"] for u in self.call("admin1", "get", "/api/users").get_json() if u["username"] == "admin1")
        self.assertEqual(self.call("admin1", "delete", f"/api/users/{me}", json={"motif": "deces", "password": PW}).status_code, 400)
        self.assertEqual(self.call("admin1", "patch", f"/api/users/{me}", json={"role": "responsable"}).status_code, 400)

    def test_journal_et_sauvegarde(self):
        self.assertEqual(self.call("thana1", "get", "/api/audit").status_code, 403)
        acts = {a["action"] for a in self.call("admin1", "get", "/api/audit?limit=500").get_json()}
        self.assertIn("login", acts)
        r = self.call("admin1", "get", "/api/sauvegarde")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.startswith(b"SQLite format 3"))
        self.assertEqual(self.call("thana1", "get", "/api/sauvegarde").status_code, 403)


class T05_Admin_et_installation(Base):
    def test_droits_de_creation_des_comptes(self):
        mk = lambda who, nom, role: self.call(who, "post", "/api/users", json=dict(full_name=nom, role=role, password="Provisoire2026x"))
        # admin : crée des thanatopracteurs, pas d'admin ; super_admin existe déjà (dg1) donc unique
        self.assertEqual(mk("admin1", "Thanato Cree Par Admin", "thanatopracteur").status_code, 201)
        self.assertEqual(mk("admin1", "Admin Interdit", "admin").status_code, 403)
        self.assertEqual(mk("admin1", "Super Doublon", "super_admin").status_code, 409)
        # le super administrateur crée des admins mais pas un second super_admin
        r = mk("dg1", "Admin Cree Par DG", "admin")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(mk("dg1", "Autre Super", "super_admin").status_code, 403)
        self.assertEqual(mk("thana1", "Interdit Total", "thanatopracteur").status_code, 403)
        self.assertEqual(mk("dg1", "Role Inconnu", "superman").status_code, 400)
        login = self.client.post("/api/login", json={"username": "ADMIN CREE PAR DG", "password": "Provisoire2026x"})
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.get_json()["user"]["doit_changer_mdp"])

    def test_suppression_hierarchique(self):
        conn = connect()
        ids = {}
        for nom, role in (("cible admin", "admin"), ("cible thanato", "thanatopracteur")):
            ids[role] = conn.execute("INSERT INTO users (username, password_hash, full_name, role) VALUES (?,?,?,?)",
                                     (nom, hash_password(PW), nom, role)).lastrowid
        conn.close()
        body = {"motif": "revocation", "password": PW}
        # l'admin ne supprime pas un autre admin ni le super admin ; il supprime un thanatopracteur
        self.assertEqual(self.call("admin1", "delete", f"/api/users/{ids['admin']}", json=body).status_code, 403)
        dg_id = next(u["id"] for u in self.call("dg1", "get", "/api/users").get_json() if u["role"] == "super_admin")
        self.assertEqual(self.call("admin1", "delete", f"/api/users/{dg_id}", json=body).status_code, 403)
        self.assertEqual(self.call("admin1", "delete", f"/api/users/{ids['thanatopracteur']}", json=body).status_code, 200)
        # le super admin supprime tout, sauf lui-même
        self.assertEqual(self.call("dg1", "delete", f"/api/users/{ids['admin']}", json=dict(body, motif="demission", password=PW)).status_code, 200)
        self.assertEqual(self.call("dg1", "delete", f"/api/users/{dg_id}", json=body).status_code, 400)

    def test_changement_obligatoire_du_mot_de_passe(self):
        self.call("admin1", "post", "/api/users", json=dict(full_name="Premiere Connexion", role="thanatopracteur", password="Provisoire2026x"))
        tok = self.client.post("/api/login", json={"username": "premiere connexion", "password": "Provisoire2026x"}).get_json()["token"]
        h = {"Authorization": "Bearer " + tok}
        r = self.client.get("/api/plan", headers=h)
        self.assertEqual((r.status_code, r.get_json()["code"]), (403, "MDP_A_CHANGER"))       # tout est bloqué
        self.assertEqual(self.client.get("/api/me", headers=h).status_code, 200)
        same = self.client.post("/api/password", headers=h, json={"ancien": "Provisoire2026x", "nouveau": "Provisoire2026x"})
        self.assertEqual(same.status_code, 400)                                                  # doit être différent
        ok = self.client.post("/api/password", headers=h, json={"ancien": "Provisoire2026x", "nouveau": "MonVraiMdp2026!"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.client.get("/api/plan", headers=h).status_code, 200)

    def test_install_py_base_vide_un_seul_admin(self):
        import subprocess
        d = tempfile.mkdtemp()
        env = dict(os.environ, MORGUE_DATA=d, MORGUE_SECRET="")
        env.pop("MORGUE_SECRET")
        cwd = os.path.join(os.path.dirname(__file__), "..")
        for _ in range(2):  # deuxième passage : remplace et sauvegarde l'ancienne base
            out = subprocess.run([sys.executable, "install.py", "--force"], cwd=cwd, env=env, capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("Installation OK", out.stdout)
        import sqlite3
        c = sqlite3.connect(os.path.join(d, "morgue.db"))
        rows = c.execute("SELECT username, role, statut, visa, full_name, doit_changer_mdp FROM users").fetchall()
        self.assertEqual(rows, [("admin", "admin", "actif", "ADMIN", "Administrateur Système", 1)])
        self.assertEqual(c.execute("SELECT COUNT(*) FROM dossiers").fetchone()[0], 0)
        self.assertTrue(any(n.startswith("avant-installation") for n in os.listdir(os.path.join(d, "backups"))))
        refus = subprocess.run([sys.executable, "install.py"], cwd=cwd, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertNotEqual(refus.returncode, 0)                                                 # sans --force : refuse


class T06_Export(Base):
    def test_export_xlsx_valide_et_sans_formule(self):
        import zipfile
        r = self.call("thana1", "post", "/api/export/xlsx", json=dict(titre="Registre entrées", headers=["N°", "Nom"],
                      rows=[["1", "=cmd|' /C calc'!A0"], ["2", "Éric <b>&"]]))
        self.assertEqual(r.status_code, 200)
        z = zipfile.ZipFile(io.BytesIO(r.data))
        self.assertIsNone(z.testzip())
        sheet = z.read("xl/worksheets/sheet1.xml").decode()
        self.assertIn("&lt;b&gt;&amp;", sheet)
        self.assertNotIn("<f>", sheet)                       # aucune formule
        import xml.dom.minidom
        for n in z.namelist():
            xml.dom.minidom.parseString(z.read(n))           # XML bien formé
        self.assertEqual(self.call("thana1", "post", "/api/export/xlsx", json=dict(headers=[], rows=[])).status_code, 400)
        self.assertEqual(self.call(None, "post", "/api/export/xlsx", json={}).status_code, 401)

    def test_etablissement(self):
        self.assertEqual(self.call("thana1", "put", "/api/etablissement", json={"nom": "X"}).status_code, 403)
        self.assertEqual(self.call("resp1", "put", "/api/etablissement", json={"nom": "Hôpital Régional de Bafoussam", "ville": "Bafoussam"}).status_code, 200)
        self.assertEqual(self.call("dir1", "get", "/api/etablissement").get_json()["ville"], "Bafoussam")


class T07_Levees_Tarifs(Base):
    """Levée (chambre froide -> funérarium), majoration, nuitées, soldé, chapelle, transfert direct, corrections."""
    P = dict(prix_nuitee_commune=5000, prix_nuitee_individuelle=12000, prix_chapelle_petite=30000,
             prix_chapelle_grande=60000, prix_majoration=10000, prix_transfert=2000,
             heure_debut_levee=7, heure_fin_levee=18, devise="FCFA")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        h = lambda who: {"Authorization": "Bearer " + cls.tokens[who]}
        assert cls.client.put("/api/parametres", headers=h("admin1"), json=cls.P).status_code == 200
        r = cls.client.post("/api/shelves", headers=h("admin1"), json={"name": "L", "nb_divisions": 2, "capacity": 24})
        assert r.status_code == 201, r.get_json()
        tree = cls.client.get("/api/shelves", headers=h("admin1")).get_json()
        cls.div = next(s for s in tree if s["name"] == "L")["divisions"][0]["id"]

    def corps(self, nom, chambre="commune", date="2025-09-29T08:00"):
        r = self.call("thana1", "post", "/api/entrees", json=dict(ENTREE_BASE, nom=nom, division_id=self.div,
                      type_chambre=chambre, date_entree=date))
        self.assertEqual(r.status_code, 201, r.get_json())
        return r.get_json()

    def levee(self, did, date="2025-10-01T10:00", verse=0, **kw):
        p = dict(dossier_id=did, date_levee=date, resp_nom="R", resp_contact="6", resp_adresse="A", montant_verse=verse,
                 mode_paiement="momo" if verse else None)
        p.update(kw)
        return self.call("thana1", "post", "/api/levees", json=p)

    def test_01_regles_de_majoration(self):
        from tarifs import calcul_majoration
        p = dict(heure_debut_levee=7, heure_fin_levee=18, prix_majoration=10000)
        cas = {"2025-09-29T07:00": False, "2025-09-30T18:00": False, "2025-10-01T10:00": False,   # lundi, mardi, mercredi
               "2025-10-02T07:00": False, "2025-10-02T17:59": False, "2025-10-02T18:01": True,     # jeudi
               "2025-10-03T18:30": True, "2025-10-03T12:00": False,                                # vendredi
               "2025-10-01T19:00": True,                                                           # mercredi après 18h
               "2025-10-04T10:00": False, "2025-10-05T00:00": True, "2025-10-05T23:59": True,      # samedi / dimanche
               "2025-10-01T06:59": True}                                                           # avant 7h
        for dt, attendu in cas.items():
            r = calcul_majoration(dt, p)
            self.assertEqual(r["is_majore"], attendu, dt)
            self.assertEqual(r["montant"], 10000 if attendu else 0)
            self.assertEqual(bool(r["motif"]), attendu)

    def test_02_levee_nuitees_soldee_et_versements(self):
        c = self.corps("NUIT1")                                   # entré lundi 29/09, levé mercredi 01/10 : 2 nuitées
        ap = self.call("thana1", "get", f"/api/levees/apercu?dossier_id={c['dossier_id']}&date_levee=2025-10-01T10:00").get_json()
        self.assertEqual((ap["nuitees"], ap["montant_total"], ap["est_majore"]), (2, 10000, False))
        self.assertEqual(self.levee(c["dossier_id"], verse=20000).status_code, 400)          # dépasse le total
        self.assertEqual(self.levee(c["dossier_id"], verse=4000, est_solde=True).status_code, 400)  # pas soldée
        r = self.levee(c["dossier_id"], verse=4000)
        self.assertEqual(r.status_code, 201, r.get_json())
        j = r.get_json()
        self.assertEqual((j["montant_total"], j["reste_a_payer"], j["est_solde"]), (10000, 6000, False))
        nonsoldees = self.call("dir1", "get", "/api/levees?non_soldees=1").get_json()
        self.assertIn("NUIT1", [x["nom"] for x in nonsoldees])
        self.assertEqual(self.call("thana1", "post", f"/api/levees/{j['id']}/paiement", json={"montant": 9999, "mode_paiement": "om"}).status_code, 400)
        r = self.call("thana1", "post", f"/api/levees/{j['id']}/paiement", json={"montant": 6000, "mode_paiement": "om"})
        self.assertEqual((r.get_json()["reste_a_payer"], r.get_json()["est_solde"]), (0, True))
        self.assertEqual(len(self.call("dir1", "get", f"/api/levees/{j['id']}/paiements").get_json()), 2)
        self.assertEqual(self.call("dir1", "post", f"/api/levees/{j['id']}/paiement", json={"montant": 1, "mode_paiement": "om"}).status_code, 403)
        # le corps n'est plus en chambre froide : second enregistrement refusé
        self.assertEqual(self.levee(c["dossier_id"]).status_code, 409)

    def test_03_majoration_et_grande_chapelle(self):
        c = self.corps("DIM1", chambre="individuelle", date="2025-10-01T08:00")
        r = self.levee(c["dossier_id"], date="2025-10-05T10:00", chapelle_louee=True, type_chapelle="grande")
        self.assertEqual(r.status_code, 201, r.get_json())
        j = r.get_json()   # 4 nuitées x 12000 + 10000 (dimanche) + 60000
        self.assertEqual((j["montant_total"], j["est_majore"]), (118000, True))
        self.assertIn("dimanche", j["motif_majoration"])
        self.assertEqual(self.levee(self.corps("CHAP0")["dossier_id"], chapelle_louee=True).status_code, 400)  # type requis

    def test_04_transfert_direct_sans_conservation(self):
        svc = self.call("thana1", "get", "/api/services").get_json()[0]["id"]
        base = dict(ENTREE_BASE, nom="DIRECT1", type_entree="transfert_direct", cas="interne", service_id=svc,
                    destination_transfert="Morgue centrale")
        base.pop("type_chambre")
        self.assertEqual(self.call("thana1", "post", "/api/entrees", json={k: v for k, v in base.items() if k != "destination_transfert"}).status_code, 400)
        r = self.call("thana1", "post", "/api/entrees", json=base)
        self.assertEqual(r.status_code, 201, r.get_json())
        j = r.get_json()
        self.assertEqual((j["emplacement"], j["frais_transfert"]), ("Transfert direct", 2000))
        row = connect().execute("SELECT d.statut, d.division_id, e.montant_transfert, t.lieu FROM entrees e "
                                "JOIN dossiers d ON d.id = e.dossier_id JOIN transferts t ON t.entree_id = e.id WHERE e.id = ?", (j["id"],)).fetchone()
        self.assertEqual((row[0], row[1], row[2], row[3]), ("TRANSFERE", None, 2000, "Morgue centrale"))
        self.assertEqual(self.call("thana1", "post", f"/api/transferts/{j['transfert_id']}/annuler", json={"motif": "Erreur de saisie"}).status_code, 409)
        self.assertEqual(self.call("thana1", "post", f"/api/entrees/{j['id']}/annuler", json={"motif": "Erreur de saisie"}).status_code, 200)
        self.assertEqual(connect().execute("SELECT annule FROM transferts WHERE id = ?", (j["transfert_id"],)).fetchone()[0], 1)

    def test_05_modifier_les_registres(self):
        c = self.corps("ERREUR1")
        eid = c["id"]
        r = self.call("thana1", "patch", f"/api/entrees/{eid}", json={"nom": "CORRIGE", "prenoms": "Marie", "age_value": 41, "age_unit": "ans", "resp_contact": "677000000"})
        self.assertEqual(r.status_code, 200, r.get_json())
        e = next(x for x in self.call("dir1", "get", "/api/entrees?q=CORRIGE").get_json() if x["id"] == eid)
        self.assertEqual((e["nom"], e["prenoms"], e["resp_contact"], e["age_value"]), ("CORRIGE", "Marie", "677000000", 41))
        self.assertTrue(e["modifie_le"]); self.assertEqual(e["modifie_par"], "THANA1")
        self.assertEqual(self.call("thana1", "patch", f"/api/entrees/{eid}", json={"nom": "CORRIGE"}).status_code, 400)        # rien à changer
        self.assertEqual(self.call("thana1", "patch", f"/api/entrees/{eid}", json={"nom": ""}).status_code, 400)
        self.assertEqual(self.call("thana1", "patch", f"/api/entrees/{eid}", json={"date_entree": "2024-09-29T08:00"}).status_code, 400)  # autre année
        self.assertEqual(self.call("admin1", "patch", f"/api/entrees/{eid}", json={"nom": "X"}).status_code, 403)
        self.assertEqual(self.call("thana1", "patch", "/api/inconnus/1", json={"nom": "X"}).status_code, 404)
        log = connect().execute("SELECT detail FROM audit_log WHERE action = 'modification' AND entity_id = ? ORDER BY id DESC", (eid,)).fetchone()[0]
        self.assertIn("ERREUR1", log); self.assertIn("CORRIGE", log)
        # correction d'une levée : la chapelle change le total, jamais en dessous du montant déjà versé
        l = self.levee(c["dossier_id"], verse=3000).get_json()
        r = self.call("thana1", "patch", f"/api/levees/{l['id']}", json={"chapelle_louee": True, "type_chapelle": "petite"})
        self.assertEqual(r.status_code, 200, r.get_json())
        row = connect().execute("SELECT montant_total, reste_a_payer, prix_chapelle FROM levees WHERE id = ?", (l["id"],)).fetchone()
        self.assertEqual(tuple(row), (40000, 37000, 30000))
        self.assertEqual(self.call("thana1", "patch", f"/api/levees/{l['id']}", json={"date_levee": "2025-10-01T12:00"}).status_code, 200)
        # correction de la sortie
        self.assertEqual(self.call("thana1", "post", "/api/sorties", json=sortie_payload(c["dossier_id"], "2025-10-02T10:00")).status_code, 201)
        sid = self.call("dir1", "get", "/api/sorties?q=CORRIGE").get_json()[0]["id"]
        self.assertEqual(self.call("thana1", "patch", f"/api/sorties/{sid}", json={"village": "Ebolowa", "genre_mort": "accidentelle"}).status_code, 200)
        self.assertEqual(self.call("thana1", "patch", f"/api/sorties/{sid}", json={"date_sortie": "2025-09-01T10:00"}).status_code, 400)  # avant la levée
        # un enregistrement annulé n'est plus modifiable
        self.call("thana1", "post", f"/api/sorties/{sid}/annuler", json={"motif": "Erreur de saisie"})
        self.assertEqual(self.call("thana1", "patch", f"/api/sorties/{sid}", json={"village": "Autre"}).status_code, 409)

    def test_06_parametres_tarifs_droits(self):
        self.assertEqual(self.call("thana1", "put", "/api/parametres", json=self.P).status_code, 403)
        self.assertEqual(self.call("thana1", "get", "/api/parametres").status_code, 200)
        self.assertEqual(self.call("dg1", "put", "/api/parametres", json=dict(self.P, prix_majoration=-5)).status_code, 400)
        self.assertEqual(self.call("dg1", "put", "/api/parametres", json=dict(self.P, heure_fin_levee=6)).status_code, 400)

    def test_07_statistiques_finances(self):
        f = self.call("dir1", "get", "/api/stats/finances?mois=2025-10").get_json()
        self.assertGreater(f["total_mois"], 0)
        self.assertEqual(f["total_mois"], f["total_conservations"] + f["total_majorations"] + f["total_chapelles"] + f["total_transferts"])
        self.assertEqual(f["nombre_levees"], f["nombre_soldees"] + f["nombre_non_soldees"])
        self.assertEqual(f["chapelles"]["grande"]["nombre"], 1)
        self.assertEqual(self.call("dir1", "get", "/api/stats/finances?mois=oups").status_code, 400)
        g = self.call("dir1", "get", "/api/stats/global").get_json()
        self.assertEqual(len(g["chiffre_affaire_mensuel"]), 12)
        self.assertGreaterEqual(g["flux"]["levees"], 1)

    def test_08_recuperation_du_mot_de_passe(self):
        self.call("admin1", "post", "/api/users", json=dict(full_name="Oubli Mdp", role="thanatopracteur", password="Provisoire2026x"))
        tok = self.client.post("/api/login", json={"username": "oubli mdp", "password": "Provisoire2026x"}).get_json()["token"]
        h = {"Authorization": "Bearer " + tok}
        r = self.client.post("/api/password", headers=h, json={"ancien": "Provisoire2026x", "nouveau": "MonMdp2026!ok"})
        code = r.get_json()["code_recuperation"]
        self.assertRegex(code, r"^[A-Z0-9]{4}(-[A-Z0-9]{4}){3}$")
        rec = lambda c, pw="NouveauMdp2026!z": self.client.post("/api/recuperation", json=dict(username="Oubli  MDP", code=c, nouveau=pw, confirmation=pw))
        self.assertEqual(rec("AAAA-BBBB-CCCC-DDDD").status_code, 401)
        self.assertEqual(rec(code, "court").status_code, 400)
        ok = rec(code.lower().replace("-", " "))            # tolère minuscules et séparateurs
        self.assertEqual(ok.status_code, 200)
        self.assertNotEqual(ok.get_json()["code_recuperation"], code)
        self.assertEqual(self.client.post("/api/login", json={"username": "oubli mdp", "password": "NouveauMdp2026!z"}).status_code, 200)
        self.assertEqual(rec(code).status_code, 401)        # l'ancien code est périmé
        for _ in range(5):
            rec("ZZZZ-ZZZZ-ZZZZ-ZZZZ")
        self.assertEqual(rec(ok.get_json()["code_recuperation"]).status_code, 429)   # verrouillage anti-devinette
        import core; core._failures.clear()
        # sans code défini, la récupération est impossible
        self.assertEqual(rec("AAAA-BBBB-CCCC-DDDD").status_code, 401)

    def test_09_migration_v1_vers_v2(self):
        import sqlite3, subprocess
        d = tempfile.mkdtemp()
        c = sqlite3.connect(os.path.join(d, "morgue.db"))
        c.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
          full_name TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('thanatopracteur','responsable','direction','admin')),
          visa TEXT NOT NULL DEFAULT '', contact TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT (datetime('now')));
        INSERT INTO users (username,password_hash,full_name,role) VALUES ('a','x','A','admin'),('b','x','B','responsable'),('c','x','C','direction'),('d','x','D','thanatopracteur');
        CREATE TABLE services (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE dossiers (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL, prenoms TEXT NOT NULL DEFAULT '',
          age_value INTEGER NOT NULL, age_unit TEXT NOT NULL, sexe TEXT NOT NULL DEFAULT '', cas TEXT NOT NULL,
          service_id INTEGER REFERENCES services(id), statut TEXT NOT NULL DEFAULT 'EN_CONSERVATION'
            CHECK (statut IN ('EN_CONSERVATION','TRANSFERE','SORTI','ANNULE')),
          division_id INTEGER, slot_letter TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')));
        INSERT INTO dossiers (nom,age_value,age_unit,cas) VALUES ('ANCIEN',50,'ans','externe');
        CREATE TABLE entrees (id INTEGER PRIMARY KEY AUTOINCREMENT, annee INTEGER NOT NULL, numero_ordre INTEGER NOT NULL,
          dossier_id INTEGER NOT NULL REFERENCES dossiers(id), date_entree TEXT NOT NULL, resp_nom TEXT NOT NULL,
          resp_contact TEXT NOT NULL, resp_adresse TEXT NOT NULL, resp_visa TEXT NOT NULL DEFAULT '', emplacement TEXT NOT NULL,
          derogation_motif TEXT, thanato_nom TEXT NOT NULL, thanato_visa TEXT NOT NULL DEFAULT '', created_by INTEGER NOT NULL,
          created_at TEXT NOT NULL DEFAULT (datetime('now')), annule INTEGER NOT NULL DEFAULT 0, annule_motif TEXT,
          annule_par INTEGER, annule_le TEXT, UNIQUE (annee, numero_ordre));
        INSERT INTO entrees (annee,numero_ordre,dossier_id,date_entree,resp_nom,resp_contact,resp_adresse,emplacement,thanato_nom,created_by)
          VALUES (2025,1,1,'2025-01-01T08:00','R','6','A','A1a','D',4);
        """)
        c.commit(); c.close()
        env = dict(os.environ, MORGUE_DATA=d); env.pop("MORGUE_DB", None)
        code = "import db; db.init_db(); db.init_db()"      # deux fois : la migration est idempotente
        out = subprocess.run([sys.executable, "-c", code], cwd=os.path.join(os.path.dirname(__file__), ".."), env=env, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        c = sqlite3.connect(os.path.join(d, "morgue.db"))
        self.assertEqual([r[0] for r in c.execute("SELECT role FROM users ORDER BY username")], ["admin", "admin", "admin", "thanatopracteur"])
        self.assertEqual(c.execute("SELECT nom, statut FROM dossiers").fetchone(), ("ANCIEN", "EN_CONSERVATION"))
        self.assertEqual(c.execute("SELECT type_entree, montant_transfert FROM entrees").fetchone(), ("conservation", 0))
        c.execute("INSERT INTO dossiers (nom,age_value,age_unit,cas,statut) VALUES ('X',1,'ans','externe','LEVE')")   # nouveau statut accepté
        self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0], "ok")


class T08_Annonces(Base):
    def test_annonces_diffusion(self):
        r = self.call("thana1", "post", "/api/annonces", json={"titre": "X", "corps": "Y"})
        self.assertEqual(r.status_code, 403)                       # le thanatopracteur ne publie pas
        r = self.call("admin1", "post", "/api/annonces", json={"titre": "Réunion jeudi", "corps": "Présence de tous.\nMerci.", "important": True})
        self.assertEqual(r.status_code, 201)
        aid = r.get_json()["id"]
        r = self.call("admin1", "post", "/api/annonces", json={"titre": "", "corps": "x"})
        self.assertEqual(r.status_code, 400)
        for who, attendu in (("thana1", 1), ("thana2", 1), ("dir1", 1), ("dg1", 1), ("admin1", 0)):   # tous reçoivent, l'auteur l'a déjà lue
            self.assertEqual(self.call(who, "get", "/api/annonces/non-lues").get_json()["non_lues"], attendu, who)
        self.assertEqual(self.call("thana1", "get", "/api/annonces").get_json()[0]["lu"], False)
        self.call("thana1", "post", f"/api/annonces/{aid}/lu")
        self.assertEqual(self.call("thana1", "get", "/api/annonces/non-lues").get_json()["non_lues"], 0)
        self.assertEqual(self.call("thana1", "delete", f"/api/annonces/{aid}").status_code, 403)
        self.assertEqual(self.call("dir1", "delete", f"/api/annonces/{aid}").status_code, 403)   # autre admin : non
        self.assertEqual(self.call("dg1", "delete", f"/api/annonces/{aid}").status_code, 200)    # super admin : oui
        self.assertEqual(self.call("thana2", "get", "/api/annonces").get_json(), [])


if __name__ == "__main__":
    unittest.main()


class T09_DoubleAuthentification(Base):
    """TOTP (RFC 6238) : activation, connexion en deux étapes, rejeu refusé, codes de secours, politique, reset."""

    def test_vecteur_rfc6238(self):
        import base64
        import mfa
        secret = base64.b32encode(b"12345678901234567890").decode()
        self.assertEqual(mfa._hotp(secret, 59 // 30), "287082")   # RFC 6238, annexe B, T = 59 s (6 chiffres)
        self.assertEqual(mfa.verify_totp(secret, "287082", at=59), 1)
        self.assertIsNone(mfa.verify_totp(secret, "287082", after_step=1, at=59))   # rejeu refusé

    def _login(self, u):
        return self.client.post("/api/login", json={"username": u, "password": PW})

    def _activer(self, who):
        import mfa
        h = lambda **kw: dict(headers={"Authorization": "Bearer " + self.tokens[who]}, **kw)
        r = self.client.post("/api/2fa/preparer", json={"password": "faux"}, **h())
        self.assertEqual(r.status_code, 403)
        r = self.client.post("/api/2fa/preparer", json={"password": PW}, **h())
        self.assertEqual(r.status_code, 200)
        secret = r.get_json()["secret"]
        self.assertIn("otpauth://totp/", r.get_json()["uri"])
        self.assertEqual(self.client.post("/api/2fa/activer", json={"code": "000000"}, **h()).status_code, 400)
        r = self.client.post("/api/2fa/activer", json={"code": mfa.totp_now(secret)}, **h())
        self.assertEqual(r.status_code, 200)
        return secret, r.get_json()["codes_secours"]

    def test_flux_complet(self):
        import mfa
        secret, codes = self._activer("thana2")
        self.assertEqual(len(codes), 8)
        # étape 1 : pas de jeton de session, seulement un ticket
        r = self._login("thana2")
        d = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(d["etape"], "2fa")
        self.assertNotIn("token", d)
        # le ticket ne donne aucun accès aux données
        self.assertEqual(self.client.get("/api/plan", headers={"Authorization": "Bearer " + d["ticket"]}).status_code, 401)
        # mauvais code
        self.assertEqual(self.client.post("/api/login/2fa", json={"ticket": d["ticket"], "code": "123456"}).status_code, 401)
        # code valide d'un AUTRE pas : le code courant est déjà utilisé à l'activation -> pas de rejeu
        self.assertEqual(self.client.post("/api/login/2fa", json={"ticket": d["ticket"], "code": mfa.totp_now(secret)}).status_code, 401)
        # un code de secours ouvre la session une seule fois
        r = self.client.post("/api/login/2fa", json={"ticket": d["ticket"], "code": codes[0]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["codes_restants"], 7)
        self.assertEqual(self.client.get("/api/plan", headers={"Authorization": "Bearer " + r.get_json()["token"]}).status_code, 200)
        self.assertEqual(self.client.post("/api/login/2fa", json={"ticket": d["ticket"], "code": codes[0]}).status_code, 401)
        # désactivation (compte non soumis à la politique) : mot de passe + code
        t = self.client.post("/api/login/2fa", json={"ticket": self._login("thana2").get_json()["ticket"], "code": codes[1]}).get_json()["token"]
        h = {"Authorization": "Bearer " + t}
        self.assertEqual(self.client.post("/api/2fa/desactiver", json={"password": PW, "code": "000000"}, headers=h).status_code, 403)
        self.assertEqual(self.client.post("/api/2fa/desactiver", json={"password": PW, "code": codes[2]}, headers=h).status_code, 200)
        self.assertIn("token", self._login("thana2").get_json())

    def test_ticket_expire_ou_faux(self):
        self.assertEqual(self.client.post("/api/login/2fa", json={"ticket": "abc", "code": "123456"}).status_code, 401)
        import jwt, core
        faux = jwt.encode({"sub": "1"}, core.secret_key(), algorithm="HS256")   # un jeton de session n'est pas un ticket
        self.assertEqual(self.client.post("/api/login/2fa", json={"ticket": faux, "code": "123456"}).status_code, 401)

    def test_blocage_apres_echecs(self):
        import mfa
        c = app.test_client()
        conn = connect()
        conn.execute("INSERT OR IGNORE INTO users (username, password_hash, full_name, role, visa) VALUES (?,?,?,?,?)",
                     ("verrou2fa", hash_password(PW), "VERROU2FA", "thanatopracteur", "V"))
        uid = conn.execute("SELECT id FROM users WHERE username='verrou2fa'").fetchone()[0]
        conn.execute("UPDATE users SET totp_secret=?, totp_active=1 WHERE id=?", (mfa.new_secret(), uid))
        conn.close()
        ticket = c.post("/api/login", json={"username": "verrou2fa", "password": PW}).get_json()["ticket"]
        for _ in range(5):
            self.assertEqual(c.post("/api/login/2fa", json={"ticket": ticket, "code": "111111"}).status_code, 401)
        self.assertEqual(c.post("/api/login/2fa", json={"ticket": ticket, "code": "111111"}).status_code, 429)

    def test_politique_et_reset(self):
        import mfa
        # politique « admin » : l'administrateur doit activer avant tout autre accès
        r = self.call("dg1", "put", "/api/2fa/politique", json={"politique": "admin"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.call("thana1", "put", "/api/2fa/politique", json={"politique": "aucun"}).status_code, 403)
        try:
            r = self.call("admin1", "get", "/api/users")
            self.assertEqual(r.status_code, 403)
            self.assertEqual(r.get_json()["code"], "MFA_A_ACTIVER")
            self.assertEqual(self.call("admin1", "get", "/api/me").get_json()["mfa_requise"], True)
            self.assertEqual(self.call("thana1", "get", "/api/plan").status_code, 200)   # thanatopracteur non concerné
            secret, codes = self._activer("admin1")
            self.assertEqual(self.call("admin1", "get", "/api/users").status_code, 200)
            # un compte soumis à la politique ne peut pas désactiver
            r = self.call("admin1", "post", "/api/2fa/desactiver", json={"password": PW, "code": codes[0]})
            self.assertEqual(r.status_code, 403)
            # l'administrateur ne peut pas réinitialiser un autre administrateur ; le super admin, si
            uid = connect().execute("SELECT id FROM users WHERE username='admin1'").fetchone()[0]
            self._activer("resp1"); self._activer("dg1")   # la politique s'applique aussi à eux
            self.assertEqual(self.call("resp1", "post", f"/api/users/{uid}/reset-2fa").status_code, 403)
            self.assertEqual(self.call("dg1", "post", f"/api/users/{uid}/reset-2fa").status_code, 200)
            self.assertIn("token", self._login("admin1").get_json())   # plus de seconde étape
        finally:
            self.call("dg1", "put", "/api/2fa/politique", json={"politique": "aucun"})
            conn = connect()
            conn.execute("UPDATE users SET totp_secret=NULL, totp_active=0, totp_backup=NULL, totp_last_step=0")
            conn.close()


class T10_TransfertDirectAvecRaison(Base):
    """Un corps jamais conservé peut être transféré (famille, obédience religieuse…) avec la raison choisie."""

    def test_transfert_direct_avec_raison_et_precision(self):
        svc = self.call("thana1", "get", "/api/services").get_json()[0]["id"]
        raisons = self.call("thana1", "get", "/api/raisons").get_json()
        normale = next(r for r in raisons if not r["reserve"] and not r["est_autre"])
        autre = next(r for r in raisons if r["est_autre"])
        base = dict(nom="DIRECT", prenoms="Ali", age_value=40, age_unit="ans", sexe="M", cas="interne", service_id=svc,
                    type_entree="transfert_direct", date_entree="2025-09-15T08:30", resp_nom="Souleyman", resp_contact="698600487",
                    resp_adresse="Ngousso", destination_transfert="Mosquée Ngousso")
        # « Autre » sans précision : refusé
        r = self.call("thana1", "post", "/api/entrees", json=dict(base, raison_id=autre["id"]))
        self.assertEqual(r.status_code, 400)
        # raison inconnue : refusé
        self.assertEqual(self.call("thana1", "post", "/api/entrees", json=dict(base, raison_id=99999)).status_code, 400)
        # raison choisie
        r = self.call("thana1", "post", "/api/entrees", json=dict(base, raison_id=normale["id"]))
        self.assertEqual(r.status_code, 201, r.get_json())
        # « Autre » avec précision
        r2 = self.call("thana1", "post", "/api/entrees", json=dict(base, nom="DIRECT2", raison_id=autre["id"], raison_precision="Demande de la famille"))
        self.assertEqual(r2.status_code, 201, r2.get_json())
        # sans raison : raison générique, comme avant
        r3 = self.call("thana1", "post", "/api/entrees", json=dict(base, nom="DIRECT3"))
        self.assertEqual(r3.status_code, 201)
        lst = {t["nom"]: t for t in self.call("thana1", "get", "/api/transferts").get_json()}
        self.assertEqual(lst["DIRECT"]["raison"], normale["libelle"])
        self.assertEqual(lst["DIRECT2"]["raison_precision"], "Demande de la famille")
        self.assertIn("direct", lst["DIRECT3"]["raison"].lower())
        self.assertEqual(lst["DIRECT"]["lieu"], "Mosquée Ngousso")
        # aucun passage en chambre froide : le corps n'est jamais « en conservation »
        en_cons = [d["nom"] for d in self.call("thana1", "get", "/api/dossiers/en-conservation").get_json()]
        self.assertNotIn("DIRECT", en_cons)


class T11_ModifierSupprimer(Base):
    """Boutons Modifier / Supprimer du paramétrage, des équipes et des annonces."""

    def test_services_et_raisons(self):
        c = self.call
        sid = c("admin1", "post", "/api/services", json={"nom": "Service Test Supp"}).get_json()["id"]
        self.assertEqual(c("admin1", "patch", f"/api/services/{sid}", json={"nom": "Service Renommé"}).status_code, 200)
        self.assertEqual(c("thana1", "delete", f"/api/services/{sid}").status_code, 403)
        self.assertEqual(c("admin1", "delete", f"/api/services/{sid}").status_code, 200)
        self.assertEqual(c("admin1", "delete", f"/api/services/{sid}").status_code, 404)
        # service utilisé : suppression refusée
        used = c("thana1", "get", "/api/services").get_json()[0]["id"]
        c("admin1", "post", "/api/shelves", json={"name": "QW", "nb_divisions": 1, "capacity": 6})
        divs = {d["label"]: d["id"] for sh in c("admin1", "get", "/api/shelves").get_json() for d in sh["divisions"]}
        e = dict(ENTREE_BASE, nom="UTILISE", cas="interne", service_id=used, date_entree="2025-09-15T09:30", division_id=divs["QW1"])
        self.assertEqual(c("thana1", "post", "/api/entrees", json=e).status_code, 201)
        self.assertEqual(c("admin1", "delete", f"/api/services/{used}").status_code, 409)
        rid = c("admin1", "post", "/api/raisons", json={"libelle": "Raison jetable"}).get_json()["id"]
        self.assertEqual(c("admin1", "patch", f"/api/raisons/{rid}", json={"libelle": "Raison modifiée"}).status_code, 200)
        self.assertEqual(c("admin1", "delete", f"/api/raisons/{rid}").status_code, 200)
        autre = next(r for r in c("admin1", "get", "/api/raisons?all=1").get_json() if r["est_autre"])
        self.assertEqual(c("admin1", "delete", f"/api/raisons/{autre['id']}").status_code, 400)
        self.assertEqual(c("admin1", "patch", f"/api/raisons/{autre['id']}", json={"libelle": "X"}).status_code, 400)

    def test_box_et_divisions(self):
        c = self.call
        sid = c("admin1", "post", "/api/shelves", json={"name": "QZ", "nb_divisions": 2}).get_json()["id"]
        self.assertEqual(c("admin1", "patch", f"/api/shelves/{sid}", json={"name": "QY"}).status_code, 200)
        self.assertEqual(c("admin1", "patch", f"/api/shelves/{sid}", json={"name": "A1"}).status_code, 400)
        tree = next(s for s in c("admin1", "get", "/api/shelves").get_json() if s["id"] == sid)
        self.assertEqual(tree["name"], "QY")
        self.assertEqual(c("admin1", "delete", f"/api/divisions/{tree['divisions'][0]['id']}").status_code, 200)
        self.assertEqual(c("admin1", "delete", f"/api/shelves/{sid}").status_code, 200)
        # box ayant servi : refusé
        c("admin1", "post", "/api/shelves", json={"name": "QV", "nb_divisions": 1, "capacity": 6})
        divs = {d["label"]: d["id"] for sh in c("admin1", "get", "/api/shelves").get_json() for d in sh["divisions"]}
        r = c("thana1", "post", "/api/entrees", json=dict(ENTREE_BASE, nom="DANSBOX", date_entree="2025-09-15T10:30", division_id=divs["QV1"]))
        self.assertEqual(r.status_code, 201, r.get_json())
        used = [s for s in c("admin1", "get", "/api/shelves").get_json() if any(d["occupied"] for d in s["divisions"])][0]
        self.assertEqual(c("admin1", "delete", f"/api/shelves/{used['id']}").status_code, 409)

    def test_equipes_agents_annonces(self):
        c = self.call
        c("admin1", "put", "/api/rh/systeme", json={"systeme": "12h"})
        eid = c("admin1", "post", "/api/rh/equipes", json={"nom": "Equipe Supp"}).get_json()["id"]
        aid = c("admin1", "post", "/api/rh/agents", json={"nom": "Agent Supp", "equipe_id": eid}).get_json()["id"]
        self.assertEqual(c("admin1", "patch", f"/api/rh/equipes/{eid}", json={"nom": "Equipe Renommée"}).status_code, 200)
        self.assertEqual(c("admin1", "put", "/api/rh/planning", json={"date": "2025-10-01", "type": "permanence", "equipe_id": eid}).status_code, 200)
        self.assertEqual(c("admin1", "delete", f"/api/rh/equipes/{eid}").status_code, 409)  # figure au planning
        c("admin1", "put", "/api/rh/planning", json={"date": "2025-10-01", "type": "permanence", "equipe_id": None})
        self.assertEqual(c("admin1", "delete", f"/api/rh/equipes/{eid}").status_code, 200)
        self.assertEqual(c("admin1", "delete", f"/api/rh/agents/{aid}").status_code, 200)
        self.assertEqual(c("admin1", "delete", f"/api/rh/agents/{aid}").status_code, 404)
        an = c("admin1", "post", "/api/annonces", json={"titre": "T", "corps": "Corps"}).get_json()["id"]
        self.assertEqual(c("admin1", "patch", f"/api/annonces/{an}", json={"titre": "T2", "corps": "C2", "important": True}).status_code, 200)
        self.assertEqual(c("thana1", "patch", f"/api/annonces/{an}", json={"titre": "x", "corps": "y"}).status_code, 403)
        titres = [a["titre"] for a in c("thana1", "get", "/api/annonces").get_json()]
        self.assertIn("T2", titres)


class T12_InstallateurProtege(Base):
    """L'installateur ne doit jamais effacer une base contenant des données sans demande explicite ; le journal reste sobre."""

    def test_install_refuse_si_donnees(self):
        import subprocess, sqlite3
        d = tempfile.mkdtemp()
        env = dict(os.environ, MORGUE_DATA=d)
        env.pop("MORGUE_SECRET", None)
        cwd = os.path.join(os.path.dirname(__file__), "..")
        run = lambda *a: subprocess.run([sys.executable, "install.py", *a], cwd=cwd, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(run("--force").returncode, 0)
        c = sqlite3.connect(os.path.join(d, "morgue.db"))
        c.execute("INSERT INTO shelves (name) VALUES ('A')"); c.commit(); c.close()
        r = run("--force")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--maj", r.stdout)
        self.assertTrue(os.path.exists(os.path.join(d, "morgue.db")))
        c = sqlite3.connect(os.path.join(d, "morgue.db"))
        self.assertEqual(c.execute("SELECT COUNT(*) FROM shelves").fetchone()[0], 1)  # intacte
        c.close()
        self.assertEqual(run("--force", "--effacer-donnees").returncode, 0)

    def test_tarifs_sans_changement_pas_de_ligne(self):
        cur = self.call("admin1", "get", "/api/parametres").get_json()
        body = {k: cur[k] for k in ("prix_nuitee_commune", "prix_nuitee_individuelle", "prix_chapelle_petite", "prix_chapelle_grande",
                                    "prix_majoration", "prix_transfert", "heure_debut_levee", "heure_fin_levee", "devise")}
        self.call("admin1", "put", "/api/parametres", json=body)
        n1 = connect().execute("SELECT COUNT(*) FROM audit_log WHERE action='tarifs_modifies'").fetchone()[0]
        self.assertEqual(self.call("admin1", "put", "/api/parametres", json=body).status_code, 200)
        n2 = connect().execute("SELECT COUNT(*) FROM audit_log WHERE action='tarifs_modifies'").fetchone()[0]
        self.assertEqual(n1, n2)
        self.call("admin1", "put", "/api/parametres", json=dict(body, prix_transfert=body["prix_transfert"] + 500))
        n3 = connect().execute("SELECT COUNT(*) FROM audit_log WHERE action='tarifs_modifies'").fetchone()[0]
        self.assertEqual(n3, n2 + 1)

