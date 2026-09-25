import express from "express";
import fs from "fs";

const router = express.Router();

export default function transfertRoutes(db, dbPath) {
  // ➡️ Ajouter un transfert
  router.post("/", (req, res) => {
    const { depot_id, date_transfert, destination, raison, nom_retirant, decharge_transfert, agent } = req.body;
    try {
      db.run(`INSERT INTO transfert (depot_id, date_transfert, destination, raison, nom_retirant, decharge_transfert, agent)
              VALUES (?, ?, ?, ?, ?, ?, ?)`, [depot_id, date_transfert, destination, raison, nom_retirant, decharge_transfert, agent]);
      fs.writeFileSync(dbPath, Buffer.from(db.export()));
      res.json({ message: "Transfert enregistré" });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // 📋 Lister les transferts
  router.get("/", (req, res) => {
    const rows = db.exec("SELECT * FROM transfert ORDER BY date_transfert DESC");
    res.json(rows[0]?.values || []);
  });

  return router;
}
