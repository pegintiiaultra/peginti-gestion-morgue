import express from "express";
import cors from "cors";
import path from "path";
import { fileURLToPath } from "url";
import Database from "better-sqlite3";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

// Base SQLite
const dbPath = path.join(__dirname, "morgue.db");
const db = new Database(dbPath);

// Création des tables principales
db.prepare(`CREATE TABLE IF NOT EXISTS depot (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  numero_depot TEXT UNIQUE NOT NULL,
  nom_defunt TEXT NOT NULL,
  provenance TEXT,
  deposant TEXT,
  casier TEXT NOT NULL,
  date_entree TEXT DEFAULT CURRENT_TIMESTAMP,
  decharge_entree TEXT
)`).run();

db.prepare(`CREATE TABLE IF NOT EXISTS transfert (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  depot_id INTEGER NOT NULL,
  date_transfert TEXT NOT NULL,
  destination TEXT,
  raison TEXT,
  nom_retirant TEXT,
  decharge_transfert TEXT,
  agent TEXT,
  FOREIGN KEY(depot_id) REFERENCES depot(id)
)`).run();

db.prepare(`CREATE TABLE IF NOT EXISTS sortie (
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
)`).run();

db.prepare(`CREATE TABLE IF NOT EXISTS statistiques (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  total_entrees INTEGER DEFAULT 0,
  total_transferts INTEGER DEFAULT 0,
  total_sorties INTEGER DEFAULT 0,
  corps_restants INTEGER DEFAULT 0,
  raison_top TEXT,
  service_top TEXT,
  recette_mois REAL DEFAULT 0,
  duree_moyenne REAL DEFAULT 0
)`).run();

// Routes DEPOT
app.post("/api/depot", (req, res) => {
  const { numero_depot, nom_defunt, provenance, deposant, casier, decharge_entree } = req.body;
  try {
    const stmt = db.prepare(`INSERT INTO depot (numero_depot, nom_defunt, provenance, deposant, casier, decharge_entree)
                             VALUES (?, ?, ?, ?, ?, ?)`);
    const result = stmt.run(numero_depot, nom_defunt, provenance, deposant, casier, decharge_entree);
    res.json({ id: result.lastInsertRowid });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get("/api/depot", (req, res) => {
  const rows = db.prepare("SELECT * FROM depot ORDER BY date_entree DESC").all();
  res.json(rows);
});

// Routes TRANSFERT
app.post("/api/transfert", (req, res) => {
  const { depot_id, date_transfert, destination, raison, nom_retirant, decharge_transfert, agent } = req.body;
  try {
    const stmt = db.prepare(`INSERT INTO transfert (depot_id, date_transfert, destination, raison, nom_retirant, decharge_transfert, agent)
                             VALUES (?, ?, ?, ?, ?, ?, ?)`);
    const result = stmt.run(depot_id, date_transfert, destination, raison, nom_retirant, decharge_transfert, agent);
    res.json({ id: result.lastInsertRowid });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get("/api/transfert", (req, res) => {
  const rows = db.prepare("SELECT * FROM transfert ORDER BY date_transfert DESC").all();
  res.json(rows);
});

// Routes SORTIE
app.post("/api/sortie", (req, res) => {
  const { depot_id, date_sortie, heure, destination_finale, type_sortie, nom_retirant, decharge_sortie, frais_solde } = req.body;
  if (!decharge_sortie) return res.status(400).json({ error: "Décharge obligatoire pour sortie" });
  try {
    const stmt = db.prepare(`INSERT INTO sortie (depot_id, date_sortie, heure, destination_finale, type_sortie, nom_retirant, decharge_sortie, casier_libere, frais_solde)
                             VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)`);
    const result = stmt.run(depot_id, date_sortie, heure, destination_finale, type_sortie, nom_retirant, decharge_sortie, frais_solde);
    res.json({ id: result.lastInsertRowid });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get("/api/sortie", (req, res) => {
  const rows = db.prepare("SELECT * FROM sortie ORDER BY date_sortie DESC").all();
  res.json(rows);
});

// Routes STATISTIQUES
app.get("/api/stats", (req, res) => {
  const total_entrees = db.prepare("SELECT COUNT(*) as c FROM depot").get().c;
  const total_transferts = db.prepare("SELECT COUNT(*) as c FROM transfert").get().c;
  const total_sorties = db.prepare("SELECT COUNT(*) as c FROM sortie").get().c;
  const corps_restants = total_entrees - total_sorties;
  res.json({ total_entrees, total_transferts, total_sorties, corps_restants });
});

// Démarrage du serveur
app.listen(PORT, () => {
  console.log("🚀 API morgue opérationnelle sur http://localhost:" + PORT);
});
