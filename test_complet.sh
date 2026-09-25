#!/bin/bash

echo "=== 🚀 Test Complet Peginti Gestion Morgue ==="

# 1. Redémarrer le serveur avec PM2
echo ">> Démarrage du serveur..."
pm2 stop peginti-morgue 2>/dev/null
pm2 start backend/server.js --name peginti-morgue

# 2. Réinitialiser la base
echo ">> Réinitialisation de la base..."
sqlite3 morgue.db "DELETE FROM depot; DELETE FROM transfert; DELETE FROM sortie;"

# 3. Lancer les tests API classiques (corrigés avec numéro unique)
echo ">> Test API classique"
sh test_api.sh

# 4. Lancer les tests sécurisés (JWT)
echo ">> Test API sécurisée"
sh test_secure.sh

# 5. Vérifier les statistiques finales
echo ">> Vérification des statistiques"
curl -s http://localhost:3000/api/statistiques | jq .

# 6. Arrêter le serveur pour un cycle propre
echo ">> Arrêt du serveur..."
pm2 stop peginti-morgue

echo "=== ✅ Test complet terminé ==="
