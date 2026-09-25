import express from "express";
import fs from "fs";

const router = express.Router();

export default function sortieRoutes(db, dbPath) {
  // ⚰️ Ajouter une sortie
  router.post("/", (req, res) => {
    const { depot_id, date_sortie, heure, destination_finale, type_sortie, nom_retirant, decharge_sortie, frais_solde } = req.body;
    if (!decharge_sortie) return res.status(400).json({ error: "Décharge obligatoire pour sortie" });
    try {
      db.run(`INSERT INTO sortie (depot_id, date_sortie, heure, destination_finale, type_sortie, nom_retirant, decharge_sortie, casier_libere, frais_solde)
              VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)`, [depot_id, date_sortie, heure, destination_finale, type_sortie, nom_retirant, decharge_sortie, frais_solde]);
      fs.writeFileSync(dbPath, Buffer.from(db.export()));
      res.json({ message: "Sortie enregistrée et casier libéré" });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // 📋 Lister les sorties
  router.get("/", (req, res) => {
    const rows = db.exec("SELECT * FROM sortie ORDER BY date_sortie DESC");
    res.json(rows[0]?.values || []);
  });

  return router;
}
