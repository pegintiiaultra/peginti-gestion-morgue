import express from "express";
import cors from "cors";
import helmet from "helmet";
import path from "path";
import { fileURLToPath } from "url";
import fs from "fs";
import initSqlJs from "sql.js";
import { authenticateToken, generateToken } from "./auth.js";

import depotRoutes from "./routes/depot.js";
import transfertRoutes from "./routes/transfert.js";
import sortieRoutes from "./routes/sortie.js";
import statsRoutes from "./routes/stats.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3001;

app.use(helmet({ contentSecurityPolicy: false, crossOriginEmbedderPolicy: false }));
app.use(cors());
app.use(express.json({ limit: "10kb" }));

// Authentification JWT
app.post("/api/login", (req, res) => {
  const { username } = req.body;
  if (!username) return res.status(400).json({ error: "Nom d'utilisateur requis" });
  const token = generateToken({ username });
  res.json({ token });
});

app.get("/api/secure-data", authenticateToken, (req, res) => {
  res.json({
    status: "SUCCÈS",
    message: "Accès autorisé aux données sensibles",
    user: req.user
  });
});

let db;
let dbPath = path.join(__dirname, "../morgue.db");

(async () => {
  const SQL = await initSqlJs();

  if (fs.existsSync(dbPath)) {
    const filebuffer = fs.readFileSync(dbPath);
    db = new SQL.Database(filebuffer);
  } else {
    db = new SQL.Database();
  }

  // Tables
  db.run(`CREATE TABLE IF NOT EXISTS depot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_depot TEXT UNIQUE NOT NULL,
    nom_defunt TEXT NOT NULL,
    provenance TEXT,
    deposant TEXT,
    casier TEXT NOT NULL,
    date_entree TEXT DEFAULT CURRENT_TIMESTAMP,
    decharge_entree TEXT
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS transfert (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    depot_id INTEGER NOT NULL,
    date_transfert TEXT NOT NULL,
    destination TEXT,
    raison TEXT,
    nom_retirant TEXT,
    decharge_transfert TEXT,
    agent TEXT
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS sortie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    depot_id INTEGER NOT NULL,
    date_sortie TEXT NOT NULL,
    heure TEXT,
    destination_finale TEXT,
    type_sortie TEXT,
    nom_retirant TEXT,
    decharge_sortie TEXT,
    casier_libere INTEGER DEFAULT 0,
    frais_solde REAL DEFAULT 0
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS statistiques (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total_entrees INTEGER DEFAULT 0,
    total_transferts INTEGER DEFAULT 0,
    total_sorties INTEGER DEFAULT 0,
    corps_restants INTEGER DEFAULT 0,
    raison_top TEXT,
    service_top TEXT,
    recette_mois REAL DEFAULT 0,
    duree_moyenne REAL DEFAULT 0
  )`);

  // Routes
  app.use("/api/depot", depotRoutes(db, dbPath));
  app.use("/api/transfert", transfertRoutes(db, dbPath));
  app.use("/api/sortie", sortieRoutes(db, dbPath));
  app.use("/api/stats", statsRoutes(db));

  app.listen(PORT, () => {
    console.log("🚀 API morgue opérationnelle sur http://localhost:" + PORT);
  });
})();
