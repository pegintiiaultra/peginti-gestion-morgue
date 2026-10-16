"""Registres : dépôt (entrée), transfert, levée (chambre froide -> funérarium), sortie définitive ; annulations motivées ; plan de localisation."""
import os
import uuid
from datetime import datetime

from flask import Blueprint, g, jsonify, request, send_from_directory

from config_routes import occupied_letters, shelf_label, shelf_numbered_saturated
from core import (ALL, CANCEL, LETTERS, WRITE_REG, ApiError, audit, body, choice, get_db, integer,
                  login_required, next_numero, parse_date, parse_dt, text, thanato_snapshot)
from db import RAISON_DIRECT, UPLOAD_DIR, tx
from tarifs import MAX_PRIX, calcul_levee, get_params

bp = Blueprint("registres", __name__)

AGE_UNITS = ("ans", "mois", "jours")
GENRES = ("naturelle", "accidentelle", "criminelle", "indeterminee")
MAX_UPLOAD = 5 * 1024 * 1024
MIN_MOTIF = 5
MODES_PAIEMENT = ("especes", "momo", "om", "virement")
TYPES_CHAMBRE = ("commune", "individuelle")


def resp_fields(data):
    return (text(data, "resp_nom", "Nom du responsable du corps", 100),
            text(data, "resp_contact", "Contact du responsable", 50),
            text(data, "resp_adresse", "Adresse du responsable", 150),
            text(data, "resp_visa", "Visa du responsable", 50, False))


def motif(data, key="derogation_motif", label="Motif de la dérogation"):
    val = text(data, key, label, 300, False)
    if val and len(val) < MIN_MOTIF:
        raise ApiError(f"« {label} » est trop court.")
    return val


def emplacement_of(db, dossier):
    if dossier["division_id"] is None:
        return ""
    r = db.execute("SELECT s.name, v.number FROM divisions v JOIN shelves s ON s.id = v.shelf_id WHERE v.id = ?",
                   (dossier["division_id"],)).fetchone()
    return shelf_label(r["name"], r["number"], dossier["slot_letter"])


def get_dossier_en_conservation(db, dossier_id):
    d = db.execute("SELECT * FROM dossiers WHERE id = ?", (dossier_id,)).fetchone()
    if not d:
        raise ApiError("Dossier introuvable.", 404)
    if d["statut"] != "EN_CONSERVATION":
        raise ApiError("Ce corps n'est plus en conservation (déjà transféré, sorti ou annulé).", 409)
    return d


# ---------- ENTRÉES (dépôt) ----------
@bp.post("/api/entrees")
@login_required(*WRITE_REG)
def create_entree():
    data = body()
    db = get_db()
    type_entree = choice(data, "type_entree", "Type d'entrée", ("conservation", "transfert_direct"), False) or "conservation"
    direct = type_entree == "transfert_direct"
    nom = text(data, "nom", "Nom du défunt", 100)
    prenoms = text(data, "prenoms", "Prénoms", 100, False)
    age_value = integer(data, "age_value", "Âge", 0, 150)
    age_unit = choice(data, "age_unit", "Unité d'âge", AGE_UNITS)
    sexe = choice(data, "sexe", "Sexe", ("M", "F"), False)
    cas = "interne" if direct else choice(data, "cas", "Cas", ("externe", "interne"))
    date_entree = parse_dt(data.get("date_entree"), "Date et heure d'entrée")
    annee = int(date_entree[:4])
    resp = resp_fields(data)
    thanato = thanato_snapshot(db, data)
    service_id = None
    service_nom = None
    if cas == "interne":
        if data.get("service_id") in (None, ""):
            if not direct:
                raise ApiError("Le champ « Service du décès » est obligatoire.")
        else:
            service_id = integer(data, "service_id", "Service du décès")
            sv = db.execute("SELECT nom FROM services WHERE id = ? AND active = 1", (service_id,)).fetchone()
            if not sv:
                raise ApiError("Service du décès introuvable.")
            service_nom = sv["nom"]
    if direct:
        service_nom = service_nom or text(data, "service_origine", "Service d'origine", 100)
        destination = text(data, "destination_transfert", "Destination du transfert", 150)
        params = get_params(db)
        # Raison du transfert : choisie par le thanatopracteur (demande de la famille, obédience religieuse…) ;
        # à défaut, la raison générique « transfert direct depuis un service interne ».
        if data.get("raison_id") in (None, ""):
            raison = db.execute("SELECT id FROM raisons_transfert WHERE libelle = ?", (RAISON_DIRECT,)).fetchone()
            raison_precision = None
        else:
            raison = db.execute("SELECT id, est_autre FROM raisons_transfert WHERE id = ? AND active = 1",
                                (integer(data, "raison_id", "Raison du transfert"),)).fetchone()
            if not raison:
                raise ApiError("Raison du transfert introuvable.")
            raison_precision = text(data, "raison_precision", "Précision de la raison", 200, False) or None
            if raison["est_autre"] and not raison_precision:
                raise ApiError("Précisez la raison du transfert (« Autre »).")
        with tx(db):
            did = db.execute(
                "INSERT INTO dossiers (nom, prenoms, age_value, age_unit, sexe, cas, service_id, statut) "
                "VALUES (?,?,?,?,?,?,?,'TRANSFERE')", (nom, prenoms, age_value, age_unit, sexe, cas, service_id)).lastrowid
            numero = next_numero(db, "entrees", annee)
            eid = db.execute(
                "INSERT INTO entrees (annee, numero_ordre, dossier_id, date_entree, resp_nom, resp_contact, resp_adresse, "
                "resp_visa, emplacement, thanato_nom, thanato_visa, created_by, type_entree, origine, service_origine, "
                "destination_transfert, montant_transfert) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'transfert_direct',"
                "'service_interne',?,?,?)",
                (annee, numero, did, date_entree, *resp, "Transfert direct", *thanato, g.user["id"], service_nom,
                 destination, params["prix_transfert"])).lastrowid
            tnum = next_numero(db, "transferts", annee)
            tid = db.execute(
                "INSERT INTO transferts (annee, numero_ordre, dossier_id, date_transfert, resp_nom, resp_contact, "
                "resp_adresse, resp_visa, emplacement, raison_id, raison_precision, lieu, thanato_nom, thanato_visa, "
                "created_by, montant_transfert, entree_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (annee, tnum, did, date_entree, *resp, "Transfert direct", raison["id"], raison_precision, destination,
                 *thanato, g.user["id"], params["prix_transfert"], eid)).lastrowid
            audit("entree_directe_creee", "entree", eid, {"numero": f"{numero}/{annee}", "transfert": f"{tnum}/{annee}",
                                                          "service": service_nom, "destination": destination})
        return jsonify({"id": eid, "dossier_id": did, "numero": f"{numero}/{annee}", "emplacement": "Transfert direct",
                        "transfert_id": tid, "transfert_numero": f"{tnum}/{annee}",
                        "frais_transfert": params["prix_transfert"]}), 201

    type_chambre = choice(data, "type_chambre", "Type de chambre froide", TYPES_CHAMBRE)
    division_id = integer(data, "division_id", "Division")
    wanted = text(data, "slot", "Emplacement", 1, False).lower()
    derog = motif(data)
    with tx(db):
        div = db.execute(
            "SELECT v.*, s.name AS shelf_name, s.active AS shelf_active FROM divisions v "
            "JOIN shelves s ON s.id = v.shelf_id WHERE v.id = ?", (division_id,)).fetchone()
        if not div or not div["active"] or not div["shelf_active"]:
            raise ApiError("Division introuvable ou désactivée.")
        label = shelf_label(div["shelf_name"], div["number"])
        if div["number"] == 0 and not shelf_numbered_saturated(db, div["shelf_id"]) and not derog:
            raise ApiError(f"Le sol ({label}) n'est utilisable que lorsque toutes les divisions du box "
                           f"{div['shelf_name']} sont saturées. Indiquez un motif de dérogation.", 409,
                           "DEROGATION_REQUISE")
        allowed = LETTERS[:div["capacity"]]
        taken = occupied_letters(db, division_id)
        if wanted:
            if wanted not in allowed:
                raise ApiError(f"L'emplacement « {wanted} » n'existe pas dans {label}.")
            if wanted in taken:
                raise ApiError(f"L'emplacement {label}{wanted} est déjà occupé.", 409)
            letter = wanted
        else:
            letter = next((l for l in allowed if l not in taken), None)
            if letter is None:
                raise ApiError(f"La division {label} est saturée.", 409)
        did = db.execute(
            "INSERT INTO dossiers (nom, prenoms, age_value, age_unit, sexe, cas, service_id, division_id, slot_letter) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (nom, prenoms, age_value, age_unit, sexe, cas, service_id, division_id, letter)).lastrowid
        numero = next_numero(db, "entrees", annee)
        emplacement = shelf_label(div["shelf_name"], div["number"], letter)
        eid = db.execute(
            "INSERT INTO entrees (annee, numero_ordre, dossier_id, date_entree, resp_nom, resp_contact, resp_adresse, "
            "resp_visa, emplacement, derogation_motif, thanato_nom, thanato_visa, created_by, type_entree, type_chambre, "
            "origine) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'conservation',?,?)",
            (annee, numero, did, date_entree, *resp, emplacement, derog or None, *thanato, g.user["id"], type_chambre,
             "service_interne" if cas == "interne" else "externe")).lastrowid
        audit("entree_creee", "entree", eid, {"numero": f"{numero}/{annee}", "emplacement": emplacement,
                                              "chambre": type_chambre, "derogation": derog or None})
    return jsonify({"id": eid, "dossier_id": did, "numero": f"{numero}/{annee}", "emplacement": emplacement}), 201


# ---------- TRANSFERTS ----------
@bp.post("/api/transferts")
@login_required(*WRITE_REG)
def create_transfert():
    data = body()
    db = get_db()
    dossier_id = integer(data, "dossier_id", "Défunt")
    date_t = parse_dt(data.get("date_transfert"), "Date et heure du transfert")
    annee = int(date_t[:4])
    resp = resp_fields(data)
    raison_id = integer(data, "raison_id", "Raison du transfert")
    precision = text(data, "raison_precision", "Précision de la raison", 200, False)
    lieu = text(data, "lieu", "Lieu du transfert", 150)
    thanato = thanato_snapshot(db, data)
    frais = get_params(db)["prix_transfert"]
    raison = db.execute("SELECT * FROM raisons_transfert WHERE id = ? AND active = 1", (raison_id,)).fetchone()
    if not raison:
        raise ApiError("Raison du transfert introuvable.")
    if raison["est_autre"] and not precision:
        raise ApiError("Précisez la raison du transfert (« Autre »).")
    with tx(db):
        d = get_dossier_en_conservation(db, dossier_id)
        entree = db.execute("SELECT date_entree FROM entrees WHERE dossier_id = ? AND annule = 0", (dossier_id,)).fetchone()
        if entree and date_t < entree["date_entree"]:
            raise ApiError("La date du transfert est antérieure à la date d'entrée du corps.")
        emplacement = emplacement_of(db, d)
        numero = next_numero(db, "transferts", annee)
        tid = db.execute(
            "INSERT INTO transferts (annee, numero_ordre, dossier_id, date_transfert, resp_nom, resp_contact, "
            "resp_adresse, resp_visa, emplacement, origine_division_id, origine_slot, raison_id, raison_precision, "
            "lieu, thanato_nom, thanato_visa, created_by, montant_transfert) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (annee, numero, dossier_id, date_t, *resp, emplacement, d["division_id"], d["slot_letter"], raison_id,
             precision or None, lieu, *thanato, g.user["id"], frais)).lastrowid
        db.execute("UPDATE dossiers SET statut = 'TRANSFERE', division_id = NULL, slot_letter = NULL WHERE id = ?",
                   (dossier_id,))
        audit("transfert_cree", "transfert", tid, {"numero": f"{numero}/{annee}", "libere": emplacement, "lieu": lieu})
    return jsonify({"id": tid, "numero": f"{numero}/{annee}", "libere": emplacement, "frais_transfert": frais}), 201


# ---------- LEVÉES (chambre froide -> funérarium) ----------
def _levee_inputs(db, data):
    """Lit et contrôle le formulaire d'une levée ; renvoie les valeurs prêtes à calculer."""
    dossier_id = integer(data, "dossier_id", "Défunt")
    date_l = parse_dt(data.get("date_levee"), "Date et heure de la levée")
    chapelle = bool(data.get("chapelle_louee"))
    type_chapelle = choice(data, "type_chapelle", "Type de chapelle", ("petite", "grande")) if chapelle else None
    return dossier_id, date_l, chapelle, type_chapelle


def _entree_of(db, dossier_id):
    e = db.execute("SELECT * FROM entrees WHERE dossier_id = ? AND annule = 0", (dossier_id,)).fetchone()
    if not e:
        raise ApiError("Entrée du corps introuvable.", 404)
    return e


@bp.get("/api/levees/apercu")
@login_required(*ALL)
def levee_apercu():
    """Calcul en direct (nuitées, majoration, chapelle, total) affiché dans le formulaire de levée."""
    db = get_db()
    dossier_id = integer(request.args, "dossier_id", "Défunt")
    date_l = parse_dt(request.args.get("date_levee"), "Date et heure de la levée")
    chap = request.args.get("chapelle") or None
    if chap not in (None, "petite", "grande"):
        raise ApiError("Type de chapelle invalide.")
    e = _entree_of(db, dossier_id)
    calc = calcul_levee(get_params(db), e["type_chambre"] or "commune", e["date_entree"], date_l, chap)
    return jsonify({**calc, "type_chambre": e["type_chambre"] or "commune", "date_entree": e["date_entree"]})


@bp.post("/api/levees")
@login_required(*WRITE_REG)
def create_levee():
    data = body()
    db = get_db()
    dossier_id, date_l, chapelle, type_chapelle = _levee_inputs(db, data)
    annee = int(date_l[:4])
    resp = resp_fields(data)
    verse = integer(data, "montant_verse", "Montant versé", 0, MAX_PRIX)
    mode = choice(data, "mode_paiement", "Mode de paiement", MODES_PAIEMENT, required=verse > 0) if verse > 0 else None
    date_p = parse_date(data.get("date_paiement") or date_l[:10], "Date du paiement") if verse > 0 else None
    thanato = thanato_snapshot(db, data)
    params = get_params(db)
    with tx(db):
        d = get_dossier_en_conservation(db, dossier_id)
        e = _entree_of(db, dossier_id)
        if date_l < e["date_entree"]:
            raise ApiError("La date de la levée est antérieure à la date d'entrée du corps.")
        c = calcul_levee(params, e["type_chambre"] or "commune", e["date_entree"], date_l, type_chapelle)
        if verse > c["montant_total"]:
            raise ApiError(f"Le montant versé ({verse}) dépasse le total à payer ({c['montant_total']}).")
        reste = c["montant_total"] - verse
        if data.get("est_solde") and reste > 0:
            raise ApiError(f"La levée ne peut pas être marquée « soldée » : il reste {reste} {params['devise']} à payer.")
        emplacement = emplacement_of(db, d)
        numero = next_numero(db, "levees", annee)
        lid = db.execute(
            "INSERT INTO levees (annee, numero_ordre, dossier_id, date_levee, resp_nom, resp_contact, resp_adresse, "
            "resp_visa, emplacement, origine_division_id, origine_slot, type_chambre, nuitees, prix_nuitee, "
            "montant_conservation, est_majore, motif_majoration, montant_majoration, chapelle_louee, type_chapelle, "
            "prix_chapelle, montant_total, montant_verse, reste_a_payer, est_solde, date_paiement, mode_paiement, "
            "thanato_nom, thanato_visa, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (annee, numero, dossier_id, date_l, *resp, emplacement, d["division_id"], d["slot_letter"],
             e["type_chambre"] or "commune", c["nuitees"], c["prix_nuitee"], c["montant_conservation"],
             int(c["est_majore"]), c["motif_majoration"], c["montant_majoration"], int(chapelle), type_chapelle,
             c["prix_chapelle"], c["montant_total"], verse, reste, int(reste == 0), date_p, mode,
             *thanato, g.user["id"])).lastrowid
        if verse > 0:
            db.execute("INSERT INTO levee_paiements (levee_id, date_paiement, montant, mode_paiement, created_by) "
                       "VALUES (?,?,?,?,?)", (lid, date_p, verse, mode, g.user["id"]))
        db.execute("UPDATE dossiers SET statut = 'LEVE', division_id = NULL, slot_letter = NULL WHERE id = ?", (dossier_id,))
        audit("levee_creee", "levee", lid, {"numero": f"{numero}/{annee}", "libere": emplacement,
                                            "total": c["montant_total"], "verse": verse, "majoration": c["est_majore"]})
    return jsonify({"id": lid, "numero": f"{numero}/{annee}", "libere": emplacement, "montant_total": c["montant_total"],
                    "montant_verse": verse, "reste_a_payer": reste, "est_solde": reste == 0,
                    "est_majore": c["est_majore"], "motif_majoration": c["motif_majoration"]}), 201


@bp.post("/api/levees/<int:lid>/paiement")
@login_required(*WRITE_REG)
def add_paiement(lid):
    """Versement complémentaire sur une levée non soldée."""
    data = body()
    db = get_db()
    montant = integer(data, "montant", "Montant versé", 1, MAX_PRIX)
    mode = choice(data, "mode_paiement", "Mode de paiement", MODES_PAIEMENT)
    date_p = parse_date(data.get("date_paiement") or datetime.now().strftime("%Y-%m-%d"), "Date du paiement")
    with tx(db):
        l = db.execute("SELECT * FROM levees WHERE id = ?", (lid,)).fetchone()
        if not l or l["annule"]:
            raise ApiError("Levée introuvable.", 404)
        if l["reste_a_payer"] <= 0:
            raise ApiError("Cette levée est déjà soldée.", 409)
        if montant > l["reste_a_payer"]:
            raise ApiError(f"Le versement dépasse le reste à payer ({l['reste_a_payer']}).")
        verse = l["montant_verse"] + montant
        reste = l["montant_total"] - verse
        db.execute("UPDATE levees SET montant_verse = ?, reste_a_payer = ?, est_solde = ?, date_paiement = ?, "
                   "mode_paiement = ? WHERE id = ?", (verse, reste, int(reste == 0), date_p, mode, lid))
        db.execute("INSERT INTO levee_paiements (levee_id, date_paiement, montant, mode_paiement, created_by) "
                   "VALUES (?,?,?,?,?)", (lid, date_p, montant, mode, g.user["id"]))
        audit("paiement_ajoute", "levee", lid, {"montant": montant, "reste": reste})
    return jsonify({"montant_verse": verse, "reste_a_payer": reste, "est_solde": reste == 0})


@bp.get("/api/levees/<int:lid>/paiements")
@login_required(*ALL)
def list_paiements(lid):
    rows = get_db().execute("SELECT p.id, p.date_paiement, p.montant, p.mode_paiement, u.full_name AS par "
                            "FROM levee_paiements p JOIN users u ON u.id = p.created_by WHERE p.levee_id = ? "
                            "ORDER BY p.id", (lid,)).fetchall()
    return jsonify([dict(r) for r in rows])


# ---------- SORTIES DÉFINITIVES (remise à la famille / inhumation) ----------
@bp.post("/api/sorties")
@login_required(*WRITE_REG)
def create_sortie():
    data = body()
    db = get_db()
    dossier_id = integer(data, "dossier_id", "Défunt")
    date_s = parse_dt(data.get("date_sortie"), "Date et heure de sortie")
    annee = int(date_s[:4])
    resp = resp_fields(data)
    genre = choice(data, "genre_mort", "Genre de mort", GENRES)
    region = text(data, "region", "Région", 80)
    departement = text(data, "departement", "Département", 80)
    arrondissement = text(data, "arrondissement", "Arrondissement", 80)
    village = text(data, "village", "Village", 80)
    date_inh = parse_date(data.get("date_inhumation"), "Date d'inhumation")
    thanato = thanato_snapshot(db, data)
    with tx(db):
        d = db.execute("SELECT * FROM dossiers WHERE id = ?", (dossier_id,)).fetchone()
        if not d:
            raise ApiError("Dossier introuvable.", 404)
        if d["statut"] != "LEVE":
            raise ApiError("La sortie définitive suppose que la levée de la chambre froide a déjà été enregistrée "
                           "(registre « Levée »).", 409)
        levee = db.execute("SELECT date_levee, reste_a_payer FROM levees WHERE dossier_id = ? AND annule = 0",
                           (dossier_id,)).fetchone()
        if levee and date_s < levee["date_levee"]:
            raise ApiError("La date de sortie est antérieure à la date de la levée.")
        numero = next_numero(db, "sorties", annee)
        sid = db.execute(
            "INSERT INTO sorties (annee, numero_ordre, dossier_id, date_sortie, resp_nom, resp_contact, resp_adresse, "
            "resp_visa, emplacement, genre_mort, region, departement, arrondissement, village, date_inhumation, "
            "thanato_nom, thanato_visa, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (annee, numero, dossier_id, date_s, *resp, "Après levée (funérarium)", genre, region, departement,
             arrondissement, village, date_inh, *thanato, g.user["id"])).lastrowid
        db.execute("UPDATE dossiers SET statut = 'SORTI' WHERE id = ?", (dossier_id,))
        audit("sortie_creee", "sortie", sid, {"numero": f"{numero}/{annee}", "lieu": f"{village}, {arrondissement}"})
    emplacement = ""
    return jsonify({"id": sid, "numero": f"{numero}/{annee}", "solde_a_regler": (levee["reste_a_payer"] if levee else 0)}), 201


def _sniff(head):
    if head.startswith(b"%PDF"):
        return ".pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    return None


@bp.post("/api/sorties/<int:sid>/plan")
@login_required(*WRITE_REG)
def upload_plan(sid):
    db = get_db()
    row = db.execute("SELECT id, plan_fichier, annule FROM sorties WHERE id = ?", (sid,)).fetchone()
    if not row or row["annule"]:
        raise ApiError("Sortie introuvable.", 404)
    if row["plan_fichier"]:
        raise ApiError("Un plan de localisation est déjà archivé pour cette sortie.", 409)
    f = request.files.get("plan")
    if not f:
        raise ApiError("Aucun fichier reçu.")
    content = f.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise ApiError("Fichier trop volumineux (maximum 5 Mo).", 413)
    ext = _sniff(content[:8])
    if not ext:
        raise ApiError("Format non accepté : PDF, PNG ou JPEG uniquement.")
    name = uuid.uuid4().hex + ext
    with open(os.path.join(UPLOAD_DIR, name), "wb") as out:
        out.write(content)
    db.execute("UPDATE sorties SET plan_fichier = ? WHERE id = ?", (name, sid))
    audit("plan_archive", "sortie", sid, {"fichier": name})
    return jsonify({"ok": True})


@bp.get("/api/sorties/<int:sid>/plan")
@login_required()
def get_plan(sid):
    row = get_db().execute("SELECT plan_fichier FROM sorties WHERE id = ?", (sid,)).fetchone()
    if not row or not row["plan_fichier"]:
        raise ApiError("Aucun plan archivé.", 404)
    return send_from_directory(UPLOAD_DIR, row["plan_fichier"])


# ---------- ANNULATION MOTIVÉE (jamais de suppression) ----------
def _restore_slot(db, rec, d):
    """Remet le corps à son emplacement d'origine (annulation d'un transfert ou d'une levée)."""
    div = db.execute("SELECT v.*, s.active AS shelf_active FROM divisions v JOIN shelves s ON s.id = v.shelf_id "
                     "WHERE v.id = ?", (rec["origine_division_id"],)).fetchone()
    if not div or not div["active"] or not div["shelf_active"]:
        raise ApiError("L'emplacement d'origine n'existe plus : annulation impossible.", 409)
    if rec["origine_slot"] in occupied_letters(db, div["id"]):
        raise ApiError(f"L'emplacement d'origine ({rec['emplacement']}) est maintenant occupé : "
                       "annulation impossible.", 409)
    db.execute("UPDATE dossiers SET statut = 'EN_CONSERVATION', division_id = ?, slot_letter = ? WHERE id = ?",
               (div["id"], rec["origine_slot"], d["id"]))


@bp.post("/api/<kind>/<int:rid>/annuler")
@login_required(*CANCEL)
def annuler(kind, rid):
    if kind not in ("entrees", "transferts", "levees", "sorties"):
        raise ApiError("Registre inconnu.", 404)
    data = body()
    m = text(data, "motif", "Motif de l'annulation", 300)
    if len(m) < MIN_MOTIF:
        raise ApiError("Le motif de l'annulation est trop court.")
    db = get_db()
    stamp = "annule = 1, annule_motif = ?, annule_par = ?, annule_le = datetime('now') WHERE id = ?"
    with tx(db):
        rec = db.execute(f"SELECT * FROM {kind} WHERE id = ?", (rid,)).fetchone()
        if not rec:
            raise ApiError("Enregistrement introuvable.", 404)
        if rec["annule"]:
            raise ApiError("Cet enregistrement est déjà annulé.", 409)
        d = db.execute("SELECT * FROM dossiers WHERE id = ?", (rec["dossier_id"],)).fetchone()
        if kind == "entrees":
            if rec["type_entree"] == "transfert_direct":
                # l'entrée directe et son transfert automatique ne se séparent pas : on annule les deux
                if d["statut"] != "TRANSFERE":
                    raise ApiError("Le statut du corps ne permet plus cette annulation.", 409)
                db.execute(f"UPDATE transferts SET {stamp.replace('WHERE id = ?', 'WHERE entree_id = ?')}",
                           (m, g.user["id"], rid))
                db.execute("UPDATE dossiers SET statut = 'ANNULE' WHERE id = ?", (d["id"],))
            else:
                if d["statut"] != "EN_CONSERVATION":
                    raise ApiError("Ce corps a déjà été transféré, levé ou sorti : annulez d'abord l'opération "
                                   "suivante.", 409)
                db.execute("UPDATE dossiers SET statut = 'ANNULE', division_id = NULL, slot_letter = NULL WHERE id = ?",
                           (d["id"],))
        elif kind == "transferts":
            if rec["entree_id"]:
                raise ApiError("Ce transfert découle d'une entrée directe : annulez l'entrée correspondante.", 409)
            if d["statut"] != "TRANSFERE":
                raise ApiError("Le statut du corps ne permet plus cette annulation.", 409)
            _restore_slot(db, rec, d)
        elif kind == "levees":
            if d["statut"] != "LEVE":
                raise ApiError("Ce corps a déjà quitté le funérarium (sortie définitive) : annulez d'abord la sortie.", 409)
            _restore_slot(db, rec, d)
        else:  # sorties
            if d["statut"] != "SORTI":
                raise ApiError("Le statut du corps ne permet plus cette annulation.", 409)
            if rec["origine_division_id"]:  # ancienne sortie directe depuis la chambre froide
                _restore_slot(db, rec, d)
            else:
                db.execute("UPDATE dossiers SET statut = 'LEVE' WHERE id = ?", (d["id"],))
        db.execute(f"UPDATE {kind} SET {stamp}", (m, g.user["id"], rid))
        audit("annulation", {"entrees": "entree", "transferts": "transfert", "levees": "levee", "sorties": "sortie"}[kind],
              rid, {"motif": m})
    return jsonify({"ok": True})


# ---------- CONSULTATION ----------
def _list(kind, order_col, extra_select="", extra_join="", extra_where="", extra_params=()):
    db = get_db()
    q = request.args.get("q", "").strip()[:60]
    annee = request.args.get("annee", type=int)
    limit = max(1, min(request.args.get("limit", 200, type=int), 500))
    offset = max(0, request.args.get("offset", 0, type=int))
    sql = (f"SELECT r.*, d.nom, d.prenoms, d.age_value, d.age_unit, d.sexe, d.cas, d.statut, sv.nom AS service"
           f"{extra_select} FROM {kind} r JOIN dossiers d ON d.id = r.dossier_id "
           f"LEFT JOIN services sv ON sv.id = d.service_id {extra_join} WHERE 1=1 {extra_where}")
    params = list(extra_params)
    if q:
        sql += (" AND (d.nom LIKE ? OR d.prenoms LIKE ? OR r.resp_nom LIKE ? OR r.resp_contact LIKE ? "
                "OR (r.numero_ordre || '/' || r.annee) LIKE ?)")
        params += [f"%{q}%"] * 5
    if annee:
        sql += " AND r.annee = ?"
        params.append(annee)
    sql += f" ORDER BY r.{order_col} DESC, r.id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    return jsonify([dict(r) for r in db.execute(sql, params)])


@bp.get("/api/entrees")
@login_required()
def list_entrees():
    return _list("entrees", "date_entree")


@bp.get("/api/transferts")
@login_required()
def list_transferts():
    return _list("transferts", "date_transfert", ", rt.libelle AS raison",
                 "JOIN raisons_transfert rt ON rt.id = r.raison_id")


@bp.get("/api/levees")
@login_required()
def list_levees():
    if request.args.get("non_soldees") == "1":
        return _list("levees", "date_levee", extra_where="AND r.annule = 0 AND r.reste_a_payer > 0")
    return _list("levees", "date_levee")


@bp.get("/api/sorties")
@login_required()
def list_sorties():
    return _list("sorties", "date_sortie")


@bp.get("/api/dossiers/en-conservation")
@login_required()
def en_conservation():
    """Corps présents en chambre froide (pour choisir le défunt d'un transfert ou d'une levée)."""
    db = get_db()
    q = request.args.get("q", "").strip()[:60]
    sql = ("SELECT d.id, d.nom, d.prenoms, d.age_value, d.age_unit, d.cas, d.division_id, d.slot_letter, "
           "e.numero_ordre, e.annee, e.date_entree, e.emplacement, e.type_chambre, e.resp_nom, e.resp_contact, "
           "e.resp_adresse, e.resp_visa, sv.nom AS service FROM dossiers d "
           "JOIN entrees e ON e.dossier_id = d.id AND e.annule = 0 LEFT JOIN services sv ON sv.id = d.service_id "
           "WHERE d.statut = 'EN_CONSERVATION'")
    params = []
    if q:
        sql += " AND (d.nom LIKE ? OR d.prenoms LIKE ?)"
        params += [f"%{q}%"] * 2
    sql += " ORDER BY d.nom LIMIT 300"
    return jsonify([dict(r) for r in db.execute(sql, params)])


@bp.get("/api/dossiers/leves")
@login_required()
def leves():
    """Corps levés, au funérarium, en attente de sortie définitive (préremplissage de la sortie)."""
    db = get_db()
    q = request.args.get("q", "").strip()[:60]
    sql = ("SELECT d.id, d.nom, d.prenoms, d.age_value, d.age_unit, d.cas, l.numero_ordre, l.annee, l.date_levee, "
           "l.resp_nom, l.resp_contact, l.resp_adresse, l.resp_visa, l.reste_a_payer, sv.nom AS service "
           "FROM dossiers d JOIN levees l ON l.dossier_id = d.id AND l.annule = 0 "
           "LEFT JOIN services sv ON sv.id = d.service_id WHERE d.statut = 'LEVE'")
    params = []
    if q:
        sql += " AND (d.nom LIKE ? OR d.prenoms LIKE ?)"
        params += [f"%{q}%"] * 2
    sql += " ORDER BY d.nom LIMIT 300"
    return jsonify([dict(r) for r in db.execute(sql, params)])


# ---------- MODIFICATION (correction d'erreurs de saisie, tracée avant/après) ----------
RESP_KEYS = (("resp_nom", "Nom du responsable du corps", 100), ("resp_contact", "Contact du responsable", 50),
             ("resp_adresse", "Adresse du responsable", 150), ("resp_visa", "Visa du responsable", 50))
KIND_TO_ENTITY = {"entrees": "entree", "transferts": "transfert", "levees": "levee", "sorties": "sortie"}


def _same_year(new_dt, rec, label):
    if int(new_dt[:4]) != rec["annee"]:
        raise ApiError(f"« {label} » doit rester dans l'année {rec['annee']} (numéro d'ordre {rec['numero_ordre']}/{rec['annee']}). "
                       "Pour une autre année, annulez l'enregistrement et saisissez-le de nouveau.")


@bp.patch("/api/<kind>/<int:rid>")
@login_required(*WRITE_REG)
def modifier(kind, rid):
    """Corrige un enregistrement. Seuls les champs envoyés changent. Les déplacements de corps passent par un
    transfert ou une levée ; les versements se corrigent par annulation. Tout est journalisé (avant/après)."""
    if kind not in KIND_TO_ENTITY:
        raise ApiError("Registre inconnu.", 404)
    data = body()
    db = get_db()
    with tx(db):
        rec = db.execute(f"SELECT * FROM {kind} WHERE id = ?", (rid,)).fetchone()
        if not rec:
            raise ApiError("Enregistrement introuvable.", 404)
        if rec["annule"]:
            raise ApiError("Un enregistrement annulé ne peut plus être modifié.", 409)
        d = db.execute("SELECT * FROM dossiers WHERE id = ?", (rec["dossier_id"],)).fetchone()
        dos, new = {}, {}   # modifications du dossier du défunt / de l'enregistrement
        extra = []          # requêtes complémentaires (enregistrements liés)

        # -- identité du défunt (commune aux quatre registres)
        if "nom" in data: dos["nom"] = text(data, "nom", "Nom du défunt", 100)
        if "prenoms" in data: dos["prenoms"] = text(data, "prenoms", "Prénoms", 100, False)
        if "age_value" in data or "age_unit" in data:
            dos["age_value"] = integer(data, "age_value", "Âge", 0, 150)
            dos["age_unit"] = choice(data, "age_unit", "Unité d'âge", AGE_UNITS)
        if "sexe" in data: dos["sexe"] = choice(data, "sexe", "Sexe", ("M", "F"), False)
        for key, label, mx in RESP_KEYS:
            if key in data:
                new[key] = text(data, key, label, mx, key != "resp_visa")

        def other_dates(*tables):
            out = []
            for t, col in tables:
                r = db.execute(f"SELECT {col} AS dt FROM {t} WHERE dossier_id = ? AND annule = 0", (rec["dossier_id"],)).fetchone()
                if r:
                    out.append(r["dt"])
            return out

        if kind == "entrees":
            direct = rec["type_entree"] == "transfert_direct"
            if "date_entree" in data:
                v = parse_dt(data.get("date_entree"), "Date et heure d'entrée")
                _same_year(v, rec, "Date d'entrée")
                if any(v > x for x in other_dates(("transferts", "date_transfert"), ("levees", "date_levee"), ("sorties", "date_sortie")) if not direct):
                    raise ApiError("La date d'entrée ne peut pas être postérieure à une opération déjà enregistrée sur ce corps.")
                new["date_entree"] = v
                if direct:
                    extra.append(("UPDATE transferts SET date_transfert = ? WHERE entree_id = ?", (v, rid)))
            if "cas" in data or "service_id" in data:
                if direct:
                    raise ApiError("Pour une entrée directe, corrigez le « service d'origine ».")
                cas = choice(data, "cas", "Cas", ("externe", "interne"))
                sid = None
                if cas == "interne":
                    sid = integer(data, "service_id", "Service du décès")
                    if not db.execute("SELECT 1 FROM services WHERE id = ?", (sid,)).fetchone():
                        raise ApiError("Service du décès introuvable.")
                dos["cas"], dos["service_id"] = cas, sid
                new["origine"] = "service_interne" if cas == "interne" else "externe"
            if "type_chambre" in data:
                if direct:
                    raise ApiError("Une entrée directe n'a pas de chambre froide.")
                if db.execute("SELECT 1 FROM levees WHERE dossier_id = ? AND annule = 0", (rec["dossier_id"],)).fetchone():
                    raise ApiError("La levée est déjà facturée : corrigez le type de chambre depuis la levée.", 409)
                new["type_chambre"] = choice(data, "type_chambre", "Type de chambre froide", TYPES_CHAMBRE)
            if direct:
                if "service_origine" in data: new["service_origine"] = text(data, "service_origine", "Service d'origine", 100)
                if "destination_transfert" in data:
                    new["destination_transfert"] = text(data, "destination_transfert", "Destination du transfert", 150)
                    extra.append(("UPDATE transferts SET lieu = ? WHERE entree_id = ?", (new["destination_transfert"], rid)))
        elif kind == "transferts":
            if "date_transfert" in data:
                v = parse_dt(data.get("date_transfert"), "Date et heure du transfert")
                _same_year(v, rec, "Date du transfert")
                e = db.execute("SELECT date_entree FROM entrees WHERE dossier_id = ? AND annule = 0", (rec["dossier_id"],)).fetchone()
                if e and v < e["date_entree"]:
                    raise ApiError("La date du transfert est antérieure à la date d'entrée du corps.")
                new["date_transfert"] = v
            if "lieu" in data: new["lieu"] = text(data, "lieu", "Lieu du transfert", 150)
            if "raison_id" in data or "raison_precision" in data:
                rid_ = integer(data, "raison_id", "Raison du transfert")
                raison = db.execute("SELECT * FROM raisons_transfert WHERE id = ? AND active = 1", (rid_,)).fetchone()
                if not raison:
                    raise ApiError("Raison du transfert introuvable.")
                prec = text(data, "raison_precision", "Précision de la raison", 200, False)
                if raison["est_autre"] and not prec:
                    raise ApiError("Précisez la raison du transfert (« Autre »).")
                new["raison_id"], new["raison_precision"] = rid_, prec or None
        elif kind == "levees":
            e = _entree_of(db, rec["dossier_id"])
            params = get_params(db)
            date_l = rec["date_levee"]
            chambre = rec["type_chambre"]
            chapelle, type_chap = bool(rec["chapelle_louee"]), rec["type_chapelle"]
            recalc = False
            if "date_levee" in data:
                date_l = parse_dt(data.get("date_levee"), "Date et heure de la levée")
                _same_year(date_l, rec, "Date de la levée")
                if date_l < e["date_entree"]:
                    raise ApiError("La date de la levée est antérieure à la date d'entrée du corps.")
                if any(date_l > x for x in other_dates(("sorties", "date_sortie"))):
                    raise ApiError("La date de la levée ne peut pas être postérieure à la sortie définitive déjà enregistrée.")
                recalc = True
            if "type_chambre" in data:
                chambre = choice(data, "type_chambre", "Type de chambre froide", TYPES_CHAMBRE); recalc = True
            if "chapelle_louee" in data or "type_chapelle" in data:
                chapelle = bool(data.get("chapelle_louee"))
                type_chap = choice(data, "type_chapelle", "Type de chapelle", ("petite", "grande")) if chapelle else None
                recalc = True
            if recalc:
                c = calcul_levee(params, chambre, e["date_entree"], date_l, type_chap)
                if rec["montant_verse"] > c["montant_total"]:
                    raise ApiError(f"Après correction le total ({c['montant_total']}) serait inférieur au montant déjà versé "
                                   f"({rec['montant_verse']}). Annulez la levée et saisissez-la de nouveau.", 409)
                reste = c["montant_total"] - rec["montant_verse"]
                new.update(date_levee=date_l, type_chambre=chambre, nuitees=c["nuitees"], prix_nuitee=c["prix_nuitee"],
                           montant_conservation=c["montant_conservation"], est_majore=int(c["est_majore"]),
                           motif_majoration=c["motif_majoration"], montant_majoration=c["montant_majoration"],
                           chapelle_louee=int(chapelle), type_chapelle=type_chap, prix_chapelle=c["prix_chapelle"],
                           montant_total=c["montant_total"], reste_a_payer=reste, est_solde=int(reste == 0))
                if "type_chambre" in data:
                    extra.append(("UPDATE entrees SET type_chambre = ? WHERE id = ?", (chambre, e["id"])))
        else:  # sorties
            if "date_sortie" in data:
                v = parse_dt(data.get("date_sortie"), "Date et heure de sortie")
                _same_year(v, rec, "Date de sortie")
                lv = db.execute("SELECT date_levee FROM levees WHERE dossier_id = ? AND annule = 0", (rec["dossier_id"],)).fetchone()
                if lv and v < lv["date_levee"]:
                    raise ApiError("La date de sortie est antérieure à la date de la levée.")
                new["date_sortie"] = v
            if "genre_mort" in data: new["genre_mort"] = choice(data, "genre_mort", "Genre de mort", GENRES)
            for key, label in (("region", "Région"), ("departement", "Département"), ("arrondissement", "Arrondissement"), ("village", "Village")):
                if key in data: new[key] = text(data, key, label, 80)
            if "date_inhumation" in data: new["date_inhumation"] = parse_date(data.get("date_inhumation"), "Date d'inhumation")

        # -- on ne retient que ce qui change réellement
        dos = {k: v for k, v in dos.items() if d[k] != v}
        new = {k: v for k, v in new.items() if rec[k] != v}
        if not dos and not new:
            raise ApiError("Aucune modification : les valeurs sont identiques.")
        avant = {**{k: d[k] for k in dos}, **{k: rec[k] for k in new}}
        if dos:
            db.execute(f"UPDATE dossiers SET {', '.join(k + ' = ?' for k in dos)} WHERE id = ?", (*dos.values(), d["id"]))
        new_all = {**new, "modifie_le": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "modifie_par": g.user["full_name"]}
        db.execute(f"UPDATE {kind} SET {', '.join(k + ' = ?' for k in new_all)} WHERE id = ?", (*new_all.values(), rid))
        for sql, args in extra:
            db.execute(sql, args)
        audit("modification", KIND_TO_ENTITY[kind], rid, {"numero": f"{rec['numero_ordre']}/{rec['annee']}",
                                                         "avant": avant, "apres": {**dos, **new}})
    return jsonify({"ok": True, "modifie": sorted({**dos, **new})})
