const express = require('express');
const cors = require('cors');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');

const app = express();
const PORT = 3001;

app.use(cors());
app.use(express.json());

// Base SQLite
const dbPath = path.join(__dirname, '..', 'morgue.db');
const db = new sqlite3.Database(dbPath);

// Création de la table principale
db.serialize(() => {
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
});

// Récupérer tous les corps
app.get('/api/corps', (req, res) => {
  db.all("SELECT * FROM corps ORDER BY date_entree DESC", (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows);
  });
});

// Ajouter un corps
app.post('/api/corps', (req, res) => {
  const { nom, prenom, age, sexe, date_deces, cause_deces, casier, contact_famille } = req.body;
  db.run(
    `INSERT INTO corps (nom, prenom, age, sexe, date_deces, cause_deces, casier, contact_famille) VALUES (?,?,?,?,?,?,?,?)`,
    [nom, prenom, age, sexe, date_deces, cause_deces, casier, contact_famille],
    function (err) {
      if (err) return res.status(500).json({ error: err.message });
      res.json({ id: this.lastID });
    }
  );
});

// Supprimer un corps
app.delete('/api/corps/:id', (req, res) => {
  db.run("DELETE FROM corps WHERE id=?", [req.params.id], (err) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ ok: true });
  });
});

// Sortie d’un corps
app.put('/api/corps/:id/sortie', (req, res) => {
  db.run("UPDATE corps SET statut='sorti' WHERE id=?", [req.params.id], (err) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ ok: true });
  });
});

// Démarrage du serveur
app.listen(PORT, function () {
  console.log("API morgue sur http://localhost:" + PORT);
});
