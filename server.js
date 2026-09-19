import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import { authenticateToken, generateToken } from './auth.js';

const app = express();
const PORT = process.env.PORT || 3001;

app.use(helmet({ contentSecurityPolicy: false, crossOriginEmbedderPolicy: false }));
app.use(cors());
app.use(express.json({ limit: '10kb' }));

// Route publique pour obtenir un token
app.post('/api/login', (req, res) => {
  const { username } = req.body;
  if (!username) return res.status(400).json({ error: "Nom d'utilisateur requis" });

  const token = generateToken({ username });
  res.json({ token });
});

// Route protégée par JWT
app.get('/api/secure-data', authenticateToken, (req, res) => {
  res.json({
    status: "SUCCÈS",
    message: "Accès autorisé aux données sensibles",
    user: req.user
  });
});

app.listen(PORT, () => {
  console.log("🚀 API morgue sécurisée sur http://localhost:" + PORT);
});
