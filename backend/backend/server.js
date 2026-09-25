import express from "express";
import cors from "cors";
import helmet from "helmet";
import initSqlJs from "sql.js";
import fs from "fs";
import path from "path";
import morgan from "morgan";
import { z } from "zod";
import { authenticateToken, generateToken } from "../auth.js";

const app = express();
const PORT = process.env.PORT || 3001;
const DB_PATH = path.resolve("morgue.sqlite");

app.use(helmet({ contentSecurityPolicy: false, crossOriginEmbedderPolicy: false }));
app.use(cors());
app.use(express.json({ limit: "10kb" }));

// Logs vers access.log
const accessLogStream = fs.createWriteStream(path.join(process.cwd(), "access.log"), { flags: "a" });
app.use(morgan("combined", { stream: accessLogStream }));

let db;
const SQL = await initSqlJs();

// Initialisation DB
if (fs.existsSync(DB_PATH)) {
  const filebuffer = fs.readFileSync(DB_PATH);
  db = new SQL.Database(filebuffer);
} else {
  db = new SQL.Database();
  db.run(`CREATE TABLE IF NOT EXISTS corps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    prenom TEXT,
    age INTEGER,
    sexe TEXT,
    date_deces TEXT,
    cause_deces TEXT,
    date_entree TEXT DEFAULT CURRENT_TIMESTAMP,
    casier TEXT,
    statut TEXT DEFAULT 'conservé',
    contact_famille TEXT
  )`);
  fs.writeFileSync(DB_PATH, Buffer.from(db.export()));
}

// Sauvegarde utilitaire
const saveToDisk = () => {
  const data = db.export();
  fs.writeFileSync(DB_PATH, Buffer.from(data));
};

// Middleware clé API
const API_KEY = "PEGINTI_SECRET_2025";
const authenticateApiKey = (req, res, next) => {
  const userKey = req.headers["x-api-key"];
  if (!userKey || userKey !== API_KEY) {
    return res.status(403).json({ status: "ERREUR", message: "Accès refusé : Clé API invalide" });
  }
  next();
};

// Schéma de validation Zod
const corpsSchema = z.object({
  nom: z.string().min(1),
  prenom: z.string().optional(),
  age: z.number().int().nonnegative().optional(),
  sexe: z.enum(["M", "F"]).optional(),
  date_deces: z.string().optional(),
  cause_deces: z.string().optional(),
  casier: z.string().optional(),
  contact_famille: z.string().optional()
});

// CRUD corps
app.get("/api/corps", authenticateApiKey, (req, res) => {
  const stmt = db.prepare("SELECT * FROM corps ORDER BY date_entree DESC");
  const rows = [];
  while (stmt.step()) rows.push(stmt.getAsObject());
  res.json(rows);
});

app.post("/api/corps", authenticateApiKey, (req, res) => {
  const parseResult = corpsSchema.safeParse(req.body);
  if (!parseResult.success) {
    return res.status(400).json({ error: parseResult.error.errors });
  }
  const { nom, prenom, age, sexe, date_deces, cause_deces, casier, contact_famille } = parseResult.data;
  db.run("INSERT INTO corps (nom, prenom, age, sexe, date_deces, cause_deces, casier, contact_famille) VALUES (?,?,?,?,?,?,?,?)",
    [nom, prenom, age, sexe, date_deces, cause_deces, casier, contact_famille]);
  saveToDisk();
  res.json({ status: "SUCCÈS", message: "Corps enregistré" });
});

app.delete("/api/corps/:id", authenticateApiKey, (req, res) => {
  db.run("DELETE FROM corps WHERE id=?", [req.params.id]);
  saveToDisk();
  res.json({ status: "SUCCÈS", message: "Corps supprimé" });
});

app.put("/api/corps/:id/sortie", authenticateApiKey, (req, res) => {
  db.run("UPDATE corps SET statut='sorti' WHERE id=?", [req.params.id]);
  saveToDisk();
  res.json({ status: "SUCCÈS", message: "Corps marqué comme sorti" });
});

// Auth JWT
app.post("/api/login", (req, res) => {
  const { username } = req.body;
  if (!username) return res.status(400).json({ error: "Nom d'utilisateur requis" });
  const token = generateToken({ username });
  res.json({ token });
});

app.get("/api/secure-data", authenticateToken, (req, res) => {
  res.json({ status: "SUCCÈS", message: "Accès autorisé aux données sensibles", user: req.user });
});

// Démarrage
app.listen(PORT, () => console.log("🚀 API morgue opérationnelle sur http://localhost:" + PORT));
