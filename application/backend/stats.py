"""Statistiques calculées sur le trafic enregistré (jamais sur la capacité de la chambre froide)."""
from datetime import datetime

from flask import Blueprint, jsonify, request

from core import ApiError, get_db, login_required, parse_date

bp = Blueprint("stats", __name__)


def _filters(date_col):
    """Construit la clause WHERE commune (période, cas, service). Les annulés sont exclus."""
    where, params = ["x.annule = 0"], []
    d_from = request.args.get("from")
    d_to = request.args.get("to")
    if d_from:
        where.append(f"substr(x.{date_col}, 1, 10) >= ?")
        params.append(parse_date(d_from, "Début de période"))
    if d_to:
        where.append(f"substr(x.{date_col}, 1, 10) <= ?")
        params.append(parse_date(d_to, "Fin de période"))
    cas = request.args.get("cas")
    if cas:
        if cas not in ("externe", "interne"):
            raise ApiError("Valeur de « cas » invalide.")
        where.append("d.cas = ?")
        params.append(cas)
    service = request.args.get("service_id", type=int)
    if service:
        where.append("d.service_id = ?")
        params.append(service)
    return " AND ".join(where), params


def _months(rows):
    return {r["mois"]: r["n"] for r in rows}


def _fill(series_list):
    """Aligne toutes les séries sur la même liste continue de mois."""
    keys = sorted({k for s in series_list for k in s})
    if not keys:
        return [], [{} for _ in series_list]
    y, m = map(int, keys[0].split("-"))
    ye, me = map(int, keys[-1].split("-"))
    months = []
    while (y, m) <= (ye, me):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return months, [[s.get(mo, 0) for mo in months] for s in series_list]


def _last_12_months():
    now = datetime.now()
    y, m = now.year, now.month
    out = []
    for _ in range(12):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def _ca_by_month(db, months):
    """Chiffre d'affaires facturé par mois : levées (conservation + majoration + chapelle) + frais de transfert."""
    first = months[0] + "-01"
    lev = {r["mois"]: r for r in db.execute(
        "SELECT substr(date_levee,1,7) AS mois, COALESCE(SUM(montant_conservation),0) AS conservations, "
        "COALESCE(SUM(montant_majoration),0) AS majorations, COALESCE(SUM(prix_chapelle),0) AS chapelles, "
        "COALESCE(SUM(montant_verse),0) AS encaisse FROM levees WHERE annule = 0 AND substr(date_levee,1,10) >= ? "
        "GROUP BY mois", (first,))}
    trf = {r["mois"]: r["t"] for r in db.execute(
        "SELECT substr(date_transfert,1,7) AS mois, COALESCE(SUM(montant_transfert),0) AS t FROM transferts "
        "WHERE annule = 0 AND substr(date_transfert,1,10) >= ? GROUP BY mois", (first,))}
    rows = []
    for mo in months:
        l = lev.get(mo)
        c, mj, ch = (l["conservations"], l["majorations"], l["chapelles"]) if l else (0, 0, 0)
        t = trf.get(mo, 0)
        rows.append({"mois": mo, "total": c + mj + ch + t, "conservations": c, "majorations": mj, "chapelles": ch,
                     "transferts": t, "encaisse": l["encaisse"] if l else 0})
    return rows


@bp.get("/api/stats/finances")
@login_required()
def stats_finances():
    mois = request.args.get("mois") or datetime.now().strftime("%Y-%m")
    try:
        datetime.strptime(mois + "-01", "%Y-%m-%d")
    except ValueError:
        raise ApiError("Mois invalide (format AAAA-MM).")
    db = get_db()
    l = db.execute(
        "SELECT COALESCE(SUM(montant_conservation),0) AS cons, COALESCE(SUM(montant_majoration),0) AS maj, "
        "COALESCE(SUM(prix_chapelle),0) AS chap, COALESCE(SUM(montant_verse),0) AS verse, "
        "COALESCE(SUM(reste_a_payer),0) AS reste, COALESCE(SUM(est_solde),0) AS soldees, COUNT(*) AS n "
        "FROM levees WHERE annule = 0 AND substr(date_levee,1,7) = ?", (mois,)).fetchone()
    chapelles = {r["type_chapelle"]: dict(nombre=r["n"], montant=r["m"]) for r in db.execute(
        "SELECT type_chapelle, COUNT(*) AS n, COALESCE(SUM(prix_chapelle),0) AS m FROM levees WHERE annule = 0 "
        "AND chapelle_louee = 1 AND substr(date_levee,1,7) = ? GROUP BY type_chapelle", (mois,))}
    trf = db.execute("SELECT COALESCE(SUM(montant_transfert),0) AS t, COUNT(*) AS n FROM transferts WHERE annule = 0 "
                     "AND substr(date_transfert,1,7) = ?", (mois,)).fetchone()
    total = l["cons"] + l["maj"] + l["chap"] + trf["t"]
    return jsonify({
        "mois": mois, "total_mois": total, "total_majorations": l["maj"], "total_conservations": l["cons"],
        "total_transferts": trf["t"], "total_chapelles": l["chap"],
        "chapelles": {"petite": chapelles.get("petite", {"nombre": 0, "montant": 0}),
                      "grande": chapelles.get("grande", {"nombre": 0, "montant": 0})},
        "nombre_levees": l["n"], "nombre_soldees": l["soldees"], "nombre_non_soldees": l["n"] - l["soldees"],
        "nombre_transferts": trf["n"], "total_encaisse_levees": l["verse"], "reste_a_encaisser": l["reste"],
    })


@bp.get("/api/stats")
@bp.get("/api/stats/global")
@login_required()
def stats():
    db = get_db()
    base = "FROM {t} x JOIN dossiers d ON d.id = x.dossier_id WHERE {w}"

    w, p = _filters("date_entree")
    ent_mois = _months(db.execute(
        f"SELECT substr(x.date_entree,1,7) AS mois, COUNT(*) AS n {base.format(t='entrees', w=w)} GROUP BY mois", p))
    cas_rows = db.execute(f"SELECT d.cas AS k, COUNT(*) AS n {base.format(t='entrees', w=w)} GROUP BY d.cas", p).fetchall()
    services = db.execute(
        f"SELECT sv.nom AS nom, COUNT(*) AS n FROM entrees x JOIN dossiers d ON d.id = x.dossier_id "
        f"JOIN services sv ON sv.id = d.service_id WHERE {w} AND d.cas = 'interne' "
        "GROUP BY sv.id ORDER BY n DESC, sv.nom", p).fetchall()
    flux_rows = db.execute(f"SELECT d.statut AS k, COUNT(*) AS n {base.format(t='entrees', w=w)} GROUP BY d.statut", p).fetchall()
    total_entrees = sum(r["n"] for r in cas_rows)

    w, p = _filters("date_transfert")
    tr_mois = _months(db.execute(
        f"SELECT substr(x.date_transfert,1,7) AS mois, COUNT(*) AS n {base.format(t='transferts', w=w)} GROUP BY mois", p))
    raisons = db.execute(
        f"SELECT CASE WHEN rt.est_autre = 1 AND x.raison_precision IS NOT NULL THEN rt.libelle || ' : ' || x.raison_precision "
        f"ELSE rt.libelle END AS nom, COUNT(*) AS n FROM transferts x JOIN dossiers d ON d.id = x.dossier_id "
        f"JOIN raisons_transfert rt ON rt.id = x.raison_id WHERE {w} GROUP BY rt.id ORDER BY n DESC, rt.libelle", p).fetchall()
    total_transferts = sum(tr_mois.values())

    w, p = _filters("date_levee")
    le_mois = _months(db.execute(
        f"SELECT substr(x.date_levee,1,7) AS mois, COUNT(*) AS n {base.format(t='levees', w=w)} GROUP BY mois", p))
    majorees = db.execute(f"SELECT COUNT(*) FROM levees x JOIN dossiers d ON d.id = x.dossier_id WHERE {w} AND x.est_majore = 1", p).fetchone()[0]
    total_levees = sum(le_mois.values())

    w, p = _filters("date_sortie")
    so_mois = _months(db.execute(
        f"SELECT substr(x.date_sortie,1,7) AS mois, COUNT(*) AS n {base.format(t='sorties', w=w)} GROUP BY mois", p))
    genres = db.execute(
        f"SELECT x.genre_mort AS k, COUNT(*) AS n {base.format(t='sorties', w=w)} GROUP BY x.genre_mort ORDER BY n DESC", p).fetchall()
    total_sorties = sum(so_mois.values())

    months, (m_ent, m_tr, m_le, m_so) = _fill([ent_mois, tr_mois, le_mois, so_mois])
    flux = {r["k"]: r["n"] for r in flux_rows}
    present = db.execute("SELECT COUNT(*) FROM dossiers WHERE statut = 'EN_CONSERVATION'").fetchone()[0]
    return jsonify({
        "mois": months,
        "entrees_par_mois": m_ent,
        "transferts_par_mois": m_tr,
        "levees_par_mois": m_le,
        "sorties_par_mois": m_so,
        "levees_majorees": majorees,
        "chiffre_affaire_mensuel": _ca_by_month(db, _last_12_months()),
        "cas": {r["k"]: r["n"] for r in cas_rows},
        "services": [dict(r) for r in services],
        "service_dominant": dict(services[0]) if services else None,
        "raisons": [dict(r) for r in raisons],
        "raison_dominante": dict(raisons[0]) if raisons else None,
        "genres_mort": {r["k"]: r["n"] for r in genres},
        "flux": {"entrees": total_entrees, "transferts": total_transferts, "levees": total_levees, "sorties": total_sorties,
                 "devenir_des_entrees": {"transferes": flux.get("TRANSFERE", 0), "leves": flux.get("LEVE", 0),
                                         "sortis": flux.get("SORTI", 0),
                                         "en_conservation": flux.get("EN_CONSERVATION", 0)}},
        "corps_presents_actuellement": present,
    })
