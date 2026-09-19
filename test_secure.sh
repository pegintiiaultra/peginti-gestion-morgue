#!/bin/bash
BASE_URL="http://localhost:3001"
API_KEY="PEGINTI_SECRET_2025"

# 1. Login et extraction du token
TOKEN=$(curl -s -X POST $BASE_URL/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"peginti"}' | jq -r '.token')

echo "Token reçu: $TOKEN"

# 2. Test accès sécurisé avec le token
curl -s $BASE_URL/api/secure-data -H "Authorization: Bearer $TOKEN"
