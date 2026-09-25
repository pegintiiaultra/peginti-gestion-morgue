import express from 'express';
import cors from 'cors';
import rateLimit from 'express-rate-limit';
import { globalKeyPool } from './src/core/multiKeyPool.js';

const app = express();

// Rate Limiter (Protection Anti-Brute Force)
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100,
  message: { error: "Trop de requêtes, veuillez réessayer plus tard." }
});

app.use(cors());
app.use(express.json());
app.use(limiter);

// Endpoint de santé
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ONLINE',
    engine: "bo'oivinichat & PEGINTI DSK PRO",
    multiKeyPool: globalKeyPool.getHealthReport(),
    concepteur: 'TOMTECH.INC'
  });
});

// Middleware de gestion d'erreurs global
app.use((err, req, res, next) => {
  console.error("[PEGINTI-ERROR]:", err.stack);
  res.status(500).json({
    status: 'ERROR',
    message: 'Une erreur critique est survenue dans le moteur PEGINTI.',
    details: process.env.NODE_ENV === 'development' ? err.message : undefined
  });
});

export default app;
