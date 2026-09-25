import express from "express";

const router = express.Router();

export default function statsRoutes(db) {
  // 📊 Statistiques globales
  router.get("/", (req, res) => {
    try {
      const total_entrees = db.exec("SELECT COUNT(*) FROM depot")[0]?.values[0][0] || 0;
      const total_transferts = db.exec("SELECT COUNT(*) FROM transfert")[0]?.values[0][0] || 0;
      const total_sorties = db.exec("SELECT COUNT(*) FROM sortie")[0]?.values[0][0] || 0;
      const corps_restants = total_entrees - total_sorties;
      res.json({ total_entrees, total_transferts, total_sorties, corps_restants });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  return router;
}
