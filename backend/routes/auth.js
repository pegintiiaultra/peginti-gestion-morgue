import express from "express";
import jwt from "jsonwebtoken";

const router = express.Router();
const SECRET = "PEGINTI_SECRET_2026"; // clé secrète à garder privée

// Endpoint login
router.post("/login", (req, res) => {
  const { username, password } = req.body;

  // Exemple simple : à adapter avec ta vraie logique utilisateur
  if (username === "peginti" && password === "secret") {
    const token = jwt.sign({ username }, SECRET, { expiresIn: "1h" });
    return res.json({ token });
  }

  res.status(401).json({ error: "Identifiants invalides" });
});

// Middleware de vérification du token
function verifyToken(req, res, next) {
  const authHeader = req.headers["authorization"];
  const token = authHeader && authHeader.split(" ")[1];
  if (!token) return res.status(403).json({ error: "Token manquant" });

  jwt.verify(token, SECRET, (err, user) => {
    if (err) return res.status(403).json({ error: "Token invalide" });
    req.user = user;
    next();
  });
}

// Route sécurisée
router.get("/secure-data", verifyToken, (req, res) => {
  res.json({
    status: "SUCCÈS",
    message: "Accès autorisé aux données sensibles",
    user: req.user
  });
});

export default router;
