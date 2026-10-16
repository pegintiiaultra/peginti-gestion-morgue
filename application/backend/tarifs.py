"""Tarifs, majoration des levées, nuitées et calcul des montants (FCFA, entiers)."""
from datetime import datetime

from flask import Blueprint, jsonify

from core import ALL, CONFIG, ApiError, audit, body, get_db, integer, login_required, text

bp = Blueprint("tarifs", __name__)

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
PRIX_FIELDS = (("prix_nuitee_commune", "Nuitée — chambre commune"),
               ("prix_nuitee_individuelle", "Nuitée — chambre individuelle"),
               ("prix_chapelle_petite", "Petite chapelle"),
               ("prix_chapelle_grande", "Grande chapelle"),
               ("prix_majoration", "Majoration (levée hors horaires / dimanche)"),
               ("prix_transfert", "Frais de transfert"))
MAX_PRIX = 100_000_000


def get_params(db):
    row = db.execute("SELECT * FROM parametres_tarifs WHERE id = 1").fetchone()
    if not row:
        db.execute("INSERT OR IGNORE INTO parametres_tarifs (id) VALUES (1)")
        row = db.execute("SELECT * FROM parametres_tarifs WHERE id = 1").fetchone()
    return dict(row)


def calcul_majoration(datetime_levee, params):
    """Majoration automatique d'une levée -> {is_majore, motif, montant}.

    Horaires de levée : 7h00 à 18h00 (modifiables). Majorée : tout le dimanche ; tout autre jour, avant l'heure
    d'ouverture ou après 18h00 (jeudi/vendredi après 18h, mercredi après 18h, etc.). Lundi, mardi, mercredi,
    jeudi, vendredi et samedi entre 7h et 18h : tarif normal."""
    dt = datetime_levee if isinstance(datetime_levee, datetime) else datetime.strptime(str(datetime_levee)[:16], "%Y-%m-%dT%H:%M")
    debut, fin = params["heure_debut_levee"], params["heure_fin_levee"]
    minutes = dt.hour * 60 + dt.minute
    jour = JOURS[dt.weekday()]
    motif = None
    if dt.weekday() == 6:
        motif = "Levée un dimanche (toute la journée)"
    elif minutes > fin * 60:
        motif = f"Levée le {jour} après {fin:02d}h00"
    elif minutes < debut * 60:
        motif = f"Levée le {jour} avant {debut:02d}h00"
    return {"is_majore": motif is not None, "motif": motif, "montant": params["prix_majoration"] if motif else 0}


def nuitees_between(date_entree, date_levee):
    """Nuitées facturées : nombre de nuits calendaires entre l'entrée et la levée, 1 au minimum."""
    d1 = datetime.strptime(date_entree[:10], "%Y-%m-%d").date()
    d2 = datetime.strptime(date_levee[:10], "%Y-%m-%d").date()
    return max((d2 - d1).days, 1)


def calcul_levee(params, type_chambre, date_entree, date_levee, chapelle_type=None):
    """Détail complet d'une levée (utilisé pour l'aperçu à l'écran ET pour l'enregistrement)."""
    nuitees = nuitees_between(date_entree, date_levee)
    prix_nuitee = params["prix_nuitee_commune" if type_chambre == "commune" else "prix_nuitee_individuelle"]
    maj = calcul_majoration(date_levee, params)
    prix_chapelle = params["prix_chapelle_" + chapelle_type] if chapelle_type else 0
    conservation = nuitees * prix_nuitee
    total = conservation + maj["montant"] + prix_chapelle
    return {"nuitees": nuitees, "prix_nuitee": prix_nuitee, "montant_conservation": conservation,
            "est_majore": maj["is_majore"], "motif_majoration": maj["motif"], "montant_majoration": maj["montant"],
            "prix_chapelle": prix_chapelle, "montant_total": total}


@bp.get("/api/parametres")
@login_required(*ALL)
def get_parametres():
    return jsonify(get_params(get_db()))


@bp.put("/api/parametres")
@login_required(*CONFIG)
def put_parametres():
    data = body()
    db = get_db()
    vals = {k: integer(data, k, label, 0, MAX_PRIX) for k, label in PRIX_FIELDS}
    debut = integer(data, "heure_debut_levee", "Heure de début des levées", 0, 23)
    fin = integer(data, "heure_fin_levee", "Heure de fin des levées", 1, 24)
    if fin <= debut:
        raise ApiError("L'heure de fin des levées doit être après l'heure de début.")
    devise = text(data, "devise", "Devise", 10, False) or "FCFA"
    avant = get_params(db)
    sets = ", ".join(f"{k} = ?" for k in vals) + ", heure_debut_levee = ?, heure_fin_levee = ?, devise = ?, tarifs_configures = 1"
    db.execute(f"UPDATE parametres_tarifs SET {sets} WHERE id = 1", (*vals.values(), debut, fin, devise))
    changes = {k: {"avant": avant.get(k), "apres": v} for k, v in {**vals, "heure_debut_levee": debut, "heure_fin_levee": fin, "devise": devise}.items()
               if avant.get(k) != v}
    if changes or not avant.get("tarifs_configures"):  # aucune ligne de journal quand on enregistre sans rien changer
        audit("tarifs_modifies", "parametres_tarifs", 1, changes or {"tarifs": "première configuration"})
    return jsonify({"ok": True})
