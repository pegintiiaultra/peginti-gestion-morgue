#!/bin/bash

# Création de la base morgue.db avec les tables principales
sqlite3 morgue.db <<'SQL'
CREATE TABLE IF NOT EXISTS depot (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  numero_depot TEXT UNIQUE NOT NULL,
  nom_defunt TEXT NOT NULL,
  provenance TEXT,
  deposant TEXT,
  casier TEXT NOT NULL,
  date_entree TEXT NOT NULL,
  decharge_entree TEXT
);

CREATE TABLE IF NOT EXISTS transfert (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  depot_id INTEGER NOT NULL,
  date_transfert TEXT NOT NULL,
  destination TEXT,
  raison TEXT,
  nom_retirant TEXT,
  decharge_transfert TEXT,
  agent TEXT,
  FOREIGN KEY(depot_id) REFERENCES depot(id)
);

CREATE TABLE IF NOT EXISTS sortie (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  depot_id INTEGER NOT NULL,
  date_sortie TEXT NOT NULL,
  heure TEXT,
  destination_finale TEXT,
  type_sortie TEXT,
  nom_retirant TEXT,
  decharge_sortie TEXT,
  casier_libere INTEGER DEFAULT 0,
  frais_solde REAL DEFAULT 0,
  FOREIGN KEY(depot_id) REFERENCES depot(id)
);

CREATE TABLE IF NOT EXISTS statistiques (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  total_entrees INTEGER DEFAULT 0,
  total_transferts INTEGER DEFAULT 0,
  total_sorties INTEGER DEFAULT 0,
  corps_restants INTEGER DEFAULT 0,
  raison_top TEXT,
  service_top TEXT,
  recette_mois REAL DEFAULT 0,
  duree_moyenne REAL DEFAULT 0
);
SQL
