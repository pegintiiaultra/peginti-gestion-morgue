#!/bin/bash

echo "=== 🔒 Test API Sécurisée ==="

# 1. Obtenir un token JWT
echo ">> Récupération du token"
TOKEN=$(curl -s -X POST http://localhost:3000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"peginti","password":"secret"}' | jq -r '.token')

echo "Token reçu: $TOKEN"

# 2. Vérifier l'accès aux données sensibles
echo ">> Vérification accès sécurisé"
RESPONSE=$(curl -s -X GET http://localhost:3000/api/secure-data \
  -H "Authorization: Bearer $TOKEN")

echo "$RESPONSE"

# 3. Vérifier automatiquement que la réponse contient "SUCCÈS"
echo ">> Validation du résultat"
echo "$RESPONSE" | grep -q '"status":"SUCCÈS"'
if [ $? -eq 0 ]; then
  echo "✅ Accès sécurisé validé"
else
  echo "❌ Erreur : accès sécurisé non validé"
fi

echo "=== ✅ Test sécurisé terminé ==="
