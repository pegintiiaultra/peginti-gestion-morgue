import express from "express";
import fs from "fs";

const router = express.Router();

export default function depotRoutes(db, dbPath) {
  // ➕ Ajouter un dépôt
  router.post("/", (req, res) => {
    const { numero_depot, nom_defunt, provenance, deposant, casier, decharge_entree } = req.body;
    try {
      db.run(`INSERT INTO depot (numero_depot, nom_defunt, provenance, deposant, casier, decharge_entree)
              VALUES (?, ?, ?, ?, ?, ?)`, [numero_depot, nom_defunt, provenance, deposant, casier, decharge_entree]);
      fs.writeFileSync(dbPath, Buffer.from(db.export()));
      res.json({ message: "Dépôt ajouté avec succès" });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // 📋 Lister les dépôts
  router.get("/", (req, res) => {
    const rows = db.exec("SELECT * FROM depot ORDER BY date_entree DESC");
    res.json(rows[0]?.values || []);
  });

  return router;
}
