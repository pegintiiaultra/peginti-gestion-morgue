"""Base de données SQLite : schéma, connexion, transactions, migrations."""
import os
import sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("MORGUE_DATA", os.path.join(BASE_DIR, "data"))
DB_PATH = os.environ.get("MORGUE_DB", os.path.join(DATA_DIR, "morgue.db"))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

ROLES = ("thanatopracteur", "admin", "super_admin")
SCHEMA_VERSION = 2

USERS_DDL = """CREATE TABLE {name} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('thanatopracteur','admin','super_admin')),
    visa TEXT NOT NULL DEFAULT '',
    contact TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    statut TEXT NOT NULL DEFAULT 'actif',
    origine TEXT NOT NULL DEFAULT 'admin',
    motif_suppression TEXT,
    supprime_le TEXT,
    supprime_par TEXT,
    doit_changer_mdp INTEGER NOT NULL DEFAULT 0,
    recovery_hash TEXT,
    recovery_le TEXT
)"""

# Dossier unique par défunt : Entrée -> (Transfert)* | Levée -> Sortie définitive
DOSSIERS_DDL = """CREATE TABLE {name} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    prenoms TEXT NOT NULL DEFAULT '',
    age_value INTEGER NOT NULL CHECK (age_value >= 0),
    age_unit TEXT NOT NULL CHECK (age_unit IN ('ans','mois','jours')),
    sexe TEXT NOT NULL DEFAULT '' CHECK (sexe IN ('','M','F')),
    cas TEXT NOT NULL CHECK (cas IN ('externe','interne')),
    service_id INTEGER REFERENCES services(id),
    statut TEXT NOT NULL DEFAULT 'EN_CONSERVATION'
        CHECK (statut IN ('EN_CONSERVATION','LEVE','TRANSFERE','SORTI','ANNULE')),
    division_id INTEGER REFERENCES divisions(id),
    slot_letter TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)"""

SCHEMA = (USERS_DDL.format(name="IF NOT EXISTS users") + ";\n" + """
CREATE TABLE IF NOT EXISTS shelves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1
);

-- number = 0 : le sol, devant l'étagère (zone de débordement)
CREATE TABLE IF NOT EXISTS divisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shelf_id INTEGER NOT NULL REFERENCES shelves(id),
    number INTEGER NOT NULL CHECK (number >= 0),
    capacity INTEGER NOT NULL CHECK (capacity BETWEEN 1 AND 26),
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE (shelf_id, number)
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS raisons_transfert (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    libelle TEXT NOT NULL UNIQUE,
    est_autre INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);

""" + DOSSIERS_DDL.format(name="IF NOT EXISTS dossiers") + """;

CREATE TABLE IF NOT EXISTS entrees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    annee INTEGER NOT NULL,
    numero_ordre INTEGER NOT NULL,
    dossier_id INTEGER NOT NULL REFERENCES dossiers(id),
    date_entree TEXT NOT NULL,
    resp_nom TEXT NOT NULL,
    resp_contact TEXT NOT NULL,
    resp_adresse TEXT NOT NULL,
    resp_visa TEXT NOT NULL DEFAULT '',
    emplacement TEXT NOT NULL,
    derogation_motif TEXT,
    thanato_nom TEXT NOT NULL,
    thanato_visa TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    annule INTEGER NOT NULL DEFAULT 0,
    annule_motif TEXT,
    annule_par INTEGER REFERENCES users(id),
    annule_le TEXT,
    modifie_le TEXT,
    modifie_par TEXT,
    type_entree TEXT NOT NULL DEFAULT 'conservation' CHECK (type_entree IN ('conservation','transfert_direct')),
    type_chambre TEXT CHECK (type_chambre IS NULL OR type_chambre IN ('commune','individuelle')),
    origine TEXT NOT NULL DEFAULT '',
    service_origine TEXT,
    destination_transfert TEXT,
    montant_transfert INTEGER NOT NULL DEFAULT 0,
    UNIQUE (annee, numero_ordre)
);

CREATE TABLE IF NOT EXISTS transferts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    annee INTEGER NOT NULL,
    numero_ordre INTEGER NOT NULL,
    dossier_id INTEGER NOT NULL REFERENCES dossiers(id),
    date_transfert TEXT NOT NULL,
    resp_nom TEXT NOT NULL,
    resp_contact TEXT NOT NULL,
    resp_adresse TEXT NOT NULL,
    resp_visa TEXT NOT NULL DEFAULT '',
    emplacement TEXT NOT NULL,
    origine_division_id INTEGER REFERENCES divisions(id),
    origine_slot TEXT,
    raison_id INTEGER NOT NULL REFERENCES raisons_transfert(id),
    raison_precision TEXT,
    lieu TEXT NOT NULL,
    thanato_nom TEXT NOT NULL,
    thanato_visa TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    annule INTEGER NOT NULL DEFAULT 0,
    annule_motif TEXT,
    annule_par INTEGER REFERENCES users(id),
    annule_le TEXT,
    modifie_le TEXT,
    modifie_par TEXT,
    montant_transfert INTEGER NOT NULL DEFAULT 0,
    entree_id INTEGER REFERENCES entrees(id),
    UNIQUE (annee, numero_ordre)
);

-- Levée : le corps quitte la chambre froide pour le funérarium (levée systématique le mercredi)
CREATE TABLE IF NOT EXISTS levees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    annee INTEGER NOT NULL,
    numero_ordre INTEGER NOT NULL,
    dossier_id INTEGER NOT NULL REFERENCES dossiers(id),
    date_levee TEXT NOT NULL,
    resp_nom TEXT NOT NULL,
    resp_contact TEXT NOT NULL,
    resp_adresse TEXT NOT NULL,
    resp_visa TEXT NOT NULL DEFAULT '',
    emplacement TEXT NOT NULL,
    origine_division_id INTEGER REFERENCES divisions(id),
    origine_slot TEXT,
    type_chambre TEXT NOT NULL CHECK (type_chambre IN ('commune','individuelle')),
    nuitees INTEGER NOT NULL DEFAULT 0,
    prix_nuitee INTEGER NOT NULL DEFAULT 0,
    montant_conservation INTEGER NOT NULL DEFAULT 0,
    est_majore INTEGER NOT NULL DEFAULT 0,
    motif_majoration TEXT,
    montant_majoration INTEGER NOT NULL DEFAULT 0,
    chapelle_louee INTEGER NOT NULL DEFAULT 0,
    type_chapelle TEXT CHECK (type_chapelle IS NULL OR type_chapelle IN ('petite','grande')),
    prix_chapelle INTEGER NOT NULL DEFAULT 0,
    montant_total INTEGER NOT NULL DEFAULT 0,
    montant_verse INTEGER NOT NULL DEFAULT 0 CHECK (montant_verse >= 0),
    reste_a_payer INTEGER NOT NULL DEFAULT 0,
    est_solde INTEGER NOT NULL DEFAULT 0,
    date_paiement TEXT,
    mode_paiement TEXT CHECK (mode_paiement IS NULL OR mode_paiement IN ('especes','momo','om','virement')),
    thanato_nom TEXT NOT NULL,
    thanato_visa TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    annule INTEGER NOT NULL DEFAULT 0,
    annule_motif TEXT,
    annule_par INTEGER REFERENCES users(id),
    annule_le TEXT,
    modifie_le TEXT,
    modifie_par TEXT,
    UNIQUE (annee, numero_ordre)
);

CREATE TABLE IF NOT EXISTS levee_paiements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    levee_id INTEGER NOT NULL REFERENCES levees(id),
    date_paiement TEXT NOT NULL,
    montant INTEGER NOT NULL CHECK (montant > 0),
    mode_paiement TEXT NOT NULL CHECK (mode_paiement IN ('especes','momo','om','virement')),
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Tarifs (une seule ligne) ; montants en FCFA
CREATE TABLE IF NOT EXISTS parametres_tarifs (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    prix_nuitee_commune INTEGER NOT NULL DEFAULT 0,
    prix_nuitee_individuelle INTEGER NOT NULL DEFAULT 0,
    prix_chapelle_petite INTEGER NOT NULL DEFAULT 0,
    prix_chapelle_grande INTEGER NOT NULL DEFAULT 0,
    prix_majoration INTEGER NOT NULL DEFAULT 0,
    prix_transfert INTEGER NOT NULL DEFAULT 0,
    heure_debut_levee INTEGER NOT NULL DEFAULT 7 CHECK (heure_debut_levee BETWEEN 0 AND 23),
    heure_fin_levee INTEGER NOT NULL DEFAULT 18 CHECK (heure_fin_levee BETWEEN 1 AND 24),
    devise TEXT NOT NULL DEFAULT 'FCFA',
    tarifs_configures INTEGER NOT NULL DEFAULT 0
);

-- Sortie définitive / remise à la famille (inhumation) : après la levée
CREATE TABLE IF NOT EXISTS sorties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    annee INTEGER NOT NULL,
    numero_ordre INTEGER NOT NULL,
    dossier_id INTEGER NOT NULL REFERENCES dossiers(id),
    date_sortie TEXT NOT NULL,
    resp_nom TEXT NOT NULL,
    resp_contact TEXT NOT NULL,
    resp_adresse TEXT NOT NULL,
    resp_visa TEXT NOT NULL DEFAULT '',
    emplacement TEXT NOT NULL,
    origine_division_id INTEGER REFERENCES divisions(id),
    origine_slot TEXT,
    genre_mort TEXT NOT NULL CHECK (genre_mort IN ('naturelle','accidentelle','criminelle','indeterminee')),
    region TEXT NOT NULL,
    departement TEXT NOT NULL,
    arrondissement TEXT NOT NULL,
    village TEXT NOT NULL,
    date_inhumation TEXT NOT NULL,
    plan_fichier TEXT,
    derogation_motif TEXT,
    thanato_nom TEXT NOT NULL,
    thanato_visa TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    annule INTEGER NOT NULL DEFAULT 0,
    annule_motif TEXT,
    annule_par INTEGER REFERENCES users(id),
    annule_le TEXT,
    modifie_le TEXT,
    modifie_par TEXT,
    UNIQUE (annee, numero_ordre)
);

-- Ressources humaines : équipes, agents, planning des gardes
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS equipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    fonction TEXT NOT NULL DEFAULT '',
    visa TEXT NOT NULL DEFAULT '',
    contact TEXT NOT NULL DEFAULT '',
    equipe_id INTEGER REFERENCES equipes(id),
    user_id INTEGER UNIQUE REFERENCES users(id),
    active INTEGER NOT NULL DEFAULT 1
);

-- type : permanence (7h30-17h00) et garde (17h00-7h30) en système 12 h ; 24h (7h30 -> 7h30) en système 24 h
CREATE TABLE IF NOT EXISTS gardes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('permanence','garde','24h')),
    equipe_id INTEGER NOT NULL REFERENCES equipes(id),
    UNIQUE (date, type)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (datetime('now')),
    user_id INTEGER,
    username TEXT,
    action TEXT NOT NULL,
    entity TEXT,
    entity_id INTEGER,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS annonces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    auteur_id INTEGER NOT NULL REFERENCES users(id),
    auteur_nom TEXT NOT NULL,
    titre TEXT NOT NULL,
    corps TEXT NOT NULL,
    important INTEGER NOT NULL DEFAULT 0,
    supprime INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS annonces_lues (
    annonce_id INTEGER NOT NULL REFERENCES annonces(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    lu_le TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (annonce_id, user_id)
);
""")

# Créés APRÈS la migration (ils référencent des colonnes que d'anciennes bases n'ont pas encore)
INDEXES = """
-- Un emplacement ne peut contenir qu'un corps à la fois (garantie au niveau base)
CREATE UNIQUE INDEX IF NOT EXISTS ux_dossier_slot ON dossiers(division_id, slot_letter) WHERE division_id IS NOT NULL;
-- Un seul super administrateur (DG) en base
CREATE UNIQUE INDEX IF NOT EXISTS ux_un_seul_super_admin ON users(role)
    WHERE role = 'super_admin' AND statut IN ('actif','en_attente');
CREATE INDEX IF NOT EXISTS ix_dossiers_statut ON dossiers(statut);
CREATE INDEX IF NOT EXISTS ix_dossiers_nom ON dossiers(nom);
CREATE INDEX IF NOT EXISTS ix_entrees_dossier ON entrees(dossier_id);
CREATE INDEX IF NOT EXISTS ix_entrees_date ON entrees(date_entree);
CREATE INDEX IF NOT EXISTS ix_transferts_dossier ON transferts(dossier_id);
CREATE INDEX IF NOT EXISTS ix_transferts_date ON transferts(date_transfert);
CREATE INDEX IF NOT EXISTS ix_levees_dossier ON levees(dossier_id);
CREATE INDEX IF NOT EXISTS ix_levees_date ON levees(date_levee);
CREATE INDEX IF NOT EXISTS ix_levees_solde ON levees(est_solde, annule);
CREATE INDEX IF NOT EXISTS ix_sorties_dossier ON sorties(dossier_id);
CREATE INDEX IF NOT EXISTS ix_sorties_date ON sorties(date_sortie);
CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit_log(ts);
CREATE INDEX IF NOT EXISTS ix_paiements_levee ON levee_paiements(levee_id);
"""

SEED_SERVICES = ["Urgences", "Médecine interne", "Chirurgie", "Maternité",
                 "Pédiatrie", "Réanimation", "Autre service"]
SEED_RAISONS = [("Autopsie", 0), ("Rapatriement", 0), ("Transfert vers une autre morgue", 0),
                ("Demande de la famille", 0), ("Obédience religieuse", 0), ("Autre", 1)]
RAISON_DIRECT = "Transfert direct depuis un service interne"


def connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA synchronous = NORMAL")
    mode = os.environ.get("MORGUE_JOURNAL", "WAL").upper()
    try:
        conn.execute(f"PRAGMA journal_mode = {mode if mode in ('WAL', 'DELETE', 'TRUNCATE') else 'WAL'}")
    except sqlite3.OperationalError:
        # Certains systèmes de fichiers (Android, partages réseau) refusent le mode WAL : repli sur le mode classique
        conn.execute("PRAGMA journal_mode = DELETE")
    return conn


# ---------- migrations ----------
ADDED_COLUMNS = {
    "users": {
        "statut": "TEXT NOT NULL DEFAULT 'actif'",
        "origine": "TEXT NOT NULL DEFAULT 'admin'",
        "motif_suppression": "TEXT",
        "supprime_le": "TEXT",
        "supprime_par": "TEXT",
        "doit_changer_mdp": "INTEGER NOT NULL DEFAULT 0",
        "recovery_hash": "TEXT",
        "recovery_le": "TEXT",
        "totp_secret": "TEXT",
        "totp_pending": "TEXT",
        "totp_active": "INTEGER NOT NULL DEFAULT 0",
        "totp_last_step": "INTEGER NOT NULL DEFAULT 0",
        "totp_backup": "TEXT",
    },
    "levees": {"modifie_le": "TEXT", "modifie_par": "TEXT"},
    "sorties": {"modifie_le": "TEXT", "modifie_par": "TEXT"},
    "entrees": {
        "modifie_le": "TEXT",
        "modifie_par": "TEXT",
        "type_entree": "TEXT NOT NULL DEFAULT 'conservation'",
        "type_chambre": "TEXT",
        "origine": "TEXT NOT NULL DEFAULT ''",
        "service_origine": "TEXT",
        "destination_transfert": "TEXT",
        "montant_transfert": "INTEGER NOT NULL DEFAULT 0",
    },
    "transferts": {
        "modifie_le": "TEXT",
        "modifie_par": "TEXT",
        "montant_transfert": "INTEGER NOT NULL DEFAULT 0",
        "entree_id": "INTEGER REFERENCES entrees(id)",
    },
}


def _columns(conn, table):
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]


def _rebuild(conn, table, ddl, select_exprs):
    """Reconstruit une table (nécessaire pour changer une contrainte CHECK) sans perdre de données."""
    new = table + "_v2"
    conn.execute(f"DROP TABLE IF EXISTS {new}")
    conn.execute(ddl.format(name=new))
    cols = [c for c in _columns(conn, new) if c in set(_columns(conn, table))]
    exprs = ", ".join(select_exprs.get(c, c) for c in cols)
    conn.execute(f"INSERT INTO {new} ({', '.join(cols)}) SELECT {exprs} FROM {table}")
    conn.execute(f"DROP TABLE {table}")
    conn.execute(f"ALTER TABLE {new} RENAME TO {table}")


def _backup_before_migration(conn):
    """Copie de sécurité de la base avant toute migration (data/backups/avant-migration-AAAAMMJJ-HHMMSS.db)."""
    import time
    if not conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        return
    folder = os.path.join(os.path.dirname(DB_PATH), "backups")
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, "avant-migration-" + time.strftime("%Y%m%d-%H%M%S") + ".db")
    try:
        target = sqlite3.connect(dest)
        conn.backup(target)
        target.close()
    except Exception:  # la sauvegarde ne doit jamais empêcher le démarrage
        pass


def migrate(conn):
    """Met à niveau une base créée par une version précédente. Ne supprime jamais de données."""
    for table, cols in ADDED_COLUMNS.items():
        have = set(_columns(conn, table))
        if not have:
            continue
        for col, ddl in cols.items():
            if col not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    row = conn.execute("SELECT value FROM settings WHERE key = 'schema_version'").fetchone()
    if row and int(row["value"]) >= SCHEMA_VERSION:
        return
    # v1 -> v2 : 3 rôles (responsable et direction deviennent admin), statut LEVE
    _backup_before_migration(conn)
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        _rebuild(conn, "users", USERS_DDL, {
            "role": "CASE role WHEN 'responsable' THEN 'admin' WHEN 'direction' THEN 'admin' ELSE role END"})
        _rebuild(conn, "dossiers", DOSSIERS_DDL, {})
        conn.execute("INSERT INTO settings (key, value) VALUES ('schema_version', ?) "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (str(SCHEMA_VERSION),))
        problems = conn.execute("PRAGMA foreign_key_check").fetchall()
        if problems:
            raise sqlite3.IntegrityError("Migration annulée : références incohérentes.")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def init_db():
    """Crée les tables manquantes et met à niveau les anciennes bases. Ne supprime JAMAIS de données."""
    conn = connect()
    existed = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
    conn.executescript(SCHEMA)
    if not existed:  # base neuve : directement au schéma courant
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
    migrate(conn)
    conn.executescript(INDEXES)
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('garde_systeme', '12h')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('mfa_exigee', 'aucun')")
    conn.execute("INSERT OR IGNORE INTO parametres_tarifs (id) VALUES (1)")
    if conn.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 0:
        conn.executemany("INSERT INTO services (nom) VALUES (?)", [(s,) for s in SEED_SERVICES])
    if conn.execute("SELECT COUNT(*) FROM raisons_transfert").fetchone()[0] == 0:
        conn.executemany("INSERT INTO raisons_transfert (libelle, est_autre) VALUES (?,?)", SEED_RAISONS)
    conn.execute("INSERT OR IGNORE INTO raisons_transfert (libelle, est_autre) VALUES (?, 0)", (RAISON_DIRECT,))
    conn.close()


@contextmanager
def tx(conn):
    """Transaction exclusive : verrouille l'écriture le temps de la vérification + insertion."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
