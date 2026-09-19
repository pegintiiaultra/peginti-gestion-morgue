#!/bin/bash
BASE_URL="http://localhost:3001"
API_KEY="PEGINTI_SECRET_2025"

echo "=== Test API Morgue ==="

TOKEN=$(curl -s -X POST $BASE_URL/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"peginti"}' | jq -r '.token')

echo "Token reçu: $TOKEN"

echo "=== Secure Data ==="
curl -s $BASE_URL/api/secure-data -H "Authorization: Bearer $TOKEN"

echo "=== Liste des corps (vide au départ) ==="
curl -s $BASE_URL/api/corps -H "x-api-key: $API_KEY"

echo "=== Ajout d’un corps VALIDE ==="
curl -s -X POST $BASE_URL/api/corps \
  -H "Content-Type: application/json" -H "x-api-key: $API_KEY" \
  -d '{"nom":"Doe","prenom":"John","age":45,"sexe":"M","date_deces":"2026-09-19","cause_deces":"Accident"}'

echo "=== Liste mise à jour ==="
curl -s $BASE_URL/api/corps -H "x-api-key: $API_KEY"

echo "=== Ajout d’un corps INVALIDE (age string) ==="
curl -s -X POST $BASE_URL/api/corps \
  -H "Content-Type: application/json" -H "x-api-key: $API_KEY" \
  -d '{"nom":"Smith","age":"quarante"}'

echo "=== Ajout d’un corps INVALIDE (nom manquant) ==="
curl -s -X POST $BASE_URL/api/corps \
  -H "Content-Type: application/json" -H "x-api-key: $API_KEY" \
  -d '{"prenom":"Alice","age":30}'

echo "=== Test avec clé API INVALIDE ==="
curl -s $BASE_URL/api/corps -H "x-api-key: FAUSSE_CLE"

echo "=== Sortie du corps id=1 ==="
curl -s -X PUT $BASE_URL/api/corps/1/sortie -H "x-api-key: $API_KEY"

echo "=== Suppression du corps id=1 ==="
curl -s -X DELETE $BASE_URL/api/corps/1 -H "x-api-key: $API_KEY"
