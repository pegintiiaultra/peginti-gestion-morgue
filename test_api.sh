#!/bin/bash

echo "=== 🚀 Test API Morgue ==="

# Générer un numéro de dépôt unique basé sur l'heure
NUM_DEPOT="D$(date +%s)"

echo ">> Ajout dépôt"
curl -s -X POST http://localhost:3000/api/depots \
  -H "Content-Type: application/json" \
  -d '{"numero_depot":"'"$NUM_DEPOT"'","nom":"Jean","lieu":"Yaoundé","famille":"Famille","casier":"C1"}'

echo
echo ">> Liste dépôts"
curl -s http://localhost:3000/api/depots
echo

echo ">> Ajout transfert"
curl -s -X POST http://localhost:3000/api/transferts \
  -H "Content-Type: application/json" \
  -d '{"depot_id":1,"date":"2026-09-24","destination":"Douala","motif":"Autopsie","responsable":"Docteur","statut":"OK","agent":"AgentX"}'

echo
echo ">> Liste transferts"
curl -s http://localhost:3000/api/transferts
echo

echo ">> Ajout sortie"
curl -s -X POST http://localhost:3000/api/sorties \
  -H "Content-Type: application/json" \
  -d '{"depot_id":1,"date":"2026-09-24","heure":"10:00","destination":"Village","motif":"Inhumation","responsable":"Famille","statut":"OK","casier":1,"montant":50000}'

echo
echo ">> Liste sorties"
curl -s http://localhost:3000/api/sorties
echo

echo ">> Statistiques"
curl -s http://localhost:3000/api/statistiques
echo

echo "=== ✅ Tests terminés ==="
