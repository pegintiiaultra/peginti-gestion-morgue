-- ============================================================================
-- migration_v2_final.sql — passage d'une base PEGINTI Morgue v1.x à la version 2.0.0
-- ============================================================================
-- MÉTHODE RECOMMANDÉE : ne rien faire. Au démarrage, l'application (python app.py) exécute la
-- même migration automatiquement, après avoir copié la base dans data/backups/avant-migration-*.db.
-- Ce fichier sert uniquement à une migration MANUELLE :
--     1) ARRÊTER l'application (pm2 stop morgue) et COPIER data/morgue.db en lieu sûr ;
--     2) sqlite3 data/morgue.db < migration_v2_final.sql   (Termux : pkg install sqlite)
--     3) Relancer l'application.
-- Si une instruction ALTER répond « duplicate column name », la colonne existe déjà : la sauter.
-- Rôles : responsable et direction deviennent « admin » ; le compte super_admin (DG) se crée ensuite
-- depuis l'application (un administrateur → Comptes → Nouveau compte).
-- ============================================================================

PRAGMA foreign_keys = OFF;
BEGIN IMMEDIATE;

-- 1) Nouvelles colonnes
ALTER TABLE users ADD COLUMN statut TEXT NOT NULL DEFAULT 'actif';
ALTER TABLE users ADD COLUMN origine TEXT NOT NULL DEFAULT 'admin';
ALTER TABLE users ADD COLUMN motif_suppression TEXT;
ALTER TABLE users ADD COLUMN supprime_le TEXT;
ALTER TABLE users ADD COLUMN supprime_par TEXT;
ALTER TABLE users ADD COLUMN doit_changer_mdp INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN recovery_hash TEXT;
ALTER TABLE users ADD COLUMN recovery_le TEXT;
ALTER TABLE sorties ADD COLUMN modifie_le TEXT;
ALTER TABLE sorties ADD COLUMN modifie_par TEXT;
ALTER TABLE entrees ADD COLUMN modifie_le TEXT;
ALTER TABLE entrees ADD COLUMN modifie_par TEXT;
ALTER TABLE entrees ADD COLUMN type_entree TEXT NOT NULL DEFAULT 'conservation';
ALTER TABLE entrees ADD COLUMN type_chambre TEXT;
ALTER TABLE entrees ADD COLUMN origine TEXT NOT NULL DEFAULT '';
ALTER TABLE entrees ADD COLUMN service_origine TEXT;
ALTER TABLE entrees ADD COLUMN destination_transfert TEXT;
ALTER TABLE entrees ADD COLUMN montant_transfert INTEGER NOT NULL DEFAULT 0;
ALTER TABLE transferts ADD COLUMN modifie_le TEXT;
ALTER TABLE transferts ADD COLUMN modifie_par TEXT;
ALTER TABLE transferts ADD COLUMN montant_transfert INTEGER NOT NULL DEFAULT 0;
ALTER TABLE transferts ADD COLUMN entree_id INTEGER REFERENCES entrees(id);

-- 2) Nouvelles tables (tarifs, levées, versements, annonces)
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

INSERT OR IGNORE INTO parametres_tarifs (id) VALUES (1);
INSERT OR IGNORE INTO raisons_transfert (libelle, est_autre) VALUES ('Transfert direct depuis un service interne', 0);

-- 3) Reconstruction de users (3 rôles) et dossiers (statut LEVE) : les données sont conservées
DROP TABLE IF EXISTS users_v2;
CREATE TABLE users_v2 (
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
);
INSERT INTO users_v2 (id, username, password_hash, full_name, role, visa, contact, active, created_at, statut, origine, motif_suppression, supprime_le, supprime_par, doit_changer_mdp, recovery_hash, recovery_le) SELECT id, username, password_hash, full_name, CASE role WHEN 'responsable' THEN 'admin' WHEN 'direction' THEN 'admin' ELSE role END, visa, contact, active, created_at, statut, origine, motif_suppression, supprime_le, supprime_par, doit_changer_mdp, recovery_hash, recovery_le FROM users;
DROP TABLE users;
ALTER TABLE users_v2 RENAME TO users;

DROP TABLE IF EXISTS dossiers_v2;
CREATE TABLE dossiers_v2 (
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
);
INSERT INTO dossiers_v2 (id, nom, prenoms, age_value, age_unit, sexe, cas, service_id, statut, division_id, slot_letter, created_at) SELECT id, nom, prenoms, age_value, age_unit, sexe, cas, service_id, statut, division_id, slot_letter, created_at FROM dossiers;
DROP TABLE dossiers;
ALTER TABLE dossiers_v2 RENAME TO dossiers;

INSERT INTO settings (key, value) VALUES ('schema_version', '2') ON CONFLICT(key) DO UPDATE SET value = excluded.value;
PRAGMA foreign_key_check;
COMMIT;
PRAGMA foreign_keys = ON;

-- 4) Index
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
