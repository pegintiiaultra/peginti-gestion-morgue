import express from "express";
const router = express.Router();

// Empêcher les doublons sur numero_depot
router.post("/depots", async (req, res) => {
  const { numero_depot, nom, lieu, famille, casier } = req.body;

  try {
    const existing = await req.db.get(
      "SELECT * FROM depot WHERE numero_depot = ?",
      [numero_depot]
    );

    if (existing) {
      return res.status(400).json({ error: "Ce numéro de dépôt existe déjà" });
    }

    await req.db.run(
      "INSERT INTO depot (numero_depot, nom, lieu, famille, casier, date_entree, statut) VALUES (?, ?, ?, ?, ?, datetime('now'), 'OK')",
      [numero_depot, nom, lieu, famille, casier]
    );

    res.json({ message: "Dépôt enregistré" });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Corriger le calcul des statistiques
router.get("/statistiques", async (req, res) => {
  try {
    const totalEntrees = (await req.db.get("SELECT COUNT(*) as c FROM depot")).c;
    const totalTransferts = (await req.db.get("SELECT COUNT(*) as c FROM transfert")).c;
    const totalSorties = (await req.db.get("SELECT COUNT(*) as c FROM sortie")).c;

    const corpsRestants = Math.max(totalEntrees - totalSorties, 0);

    res.json({
      total_entrees: totalEntrees,
      total_transferts: totalTransferts,
      total_sorties: totalSorties,
      corps_restants: corpsRestants
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

export default router;
