# Peginti Gestion Morgue

Application **offline** de gestion de morgue, développée en Node.js/Express avec PM2 et SQLite.

## 📦 Installation

Clonez le dépôt :
git clone https://github.com/pegintiiaultra/peginti-gestion-morgue.git
cd peginti-gestion-morgue
npm install

## 🚀 Lancement

Démarrer en local :
node server.js

Ou avec PM2 pour la supervision :
pm2 start server.js --name peginti-gestion-morgue
pm2 save

## 🔑 Sécurité

- Authentification via **JWT** (/api/login → token)  
- Accès sécurisé via **clé API** (x-api-key: PEGINTI_SECRET_2025)  
- Validation stricte des données avec **Zod**

## 📂 Structure

- src/ → routes et logique métier  
- db/ → base SQLite locale (non versionnée)  
- .env → variables sensibles (non versionnées)

## 🛠️ Tests rapides

- Login :
curl -X POST http://localhost:3001/api/login -H "Content-Type: application/json" -d '{"username":"peginti"}'

- Liste des corps :
curl http://localhost:3001/api/corps -H "x-api-key: PEGINTI_SECRET_2025"
