// Démarrage permanent avec PM2 :  pm2 start ecosystem.config.js && pm2 save
// Port réservé : 3001 — nom de domaine : pegintichat.online (via tunnel/proxy HTTPS, voir deploy/)
const path = require("path");
module.exports = {
  apps: [{
    name: "morgue",
    cwd: path.join(__dirname, "backend"),   // chemin absolu : fonctionne quel que soit le dossier d'où PM2 est lancé
    script: "python3",
    args: "-u app.py",
    interpreter: "none",
    env: {
      MORGUE_PORT: "3001",
      MORGUE_HOST: "127.0.0.1",        // écoute locale : seul le tunnel/proxy HTTPS est exposé
      MORGUE_BEHIND_PROXY: "1",        // fait confiance à UN proxy (IP réelle, https)
    },
  }],
};
