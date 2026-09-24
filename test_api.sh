#!/bin/bash

BASE_URL="http://localhost:3001/api"

# Couleurs
GREEN="\033[0;32m"
CYAN="\033[0;36m"
RESET="\033[0m"

echo -e "${CYAN}=== 🚀 Test API Morgue ===${RESET}"

# ➕ Ajouter un dépôt
echo -e "${GREEN}>> Ajout dépôt${RESET}"
curl -s -X POST $BASE_URL/depot \
  -H "Content-Type: application/json" \
  -d '{"numero_depot":"D001","nom_defunt":"Jean","provenance":"Yaoundé","deposant":"Famille","casier":"C1","decharge_entree":"OK"}'
echo -e "\n"

# 📋 Lister les dépôts
echo -e "${GREEN}>> Liste dépôts${RESET}"
curl -s $BASE_URL/depot
echo -e "\n"

# ➡️ Ajouter un transfert
echo -e "${GREEN}>> Ajout transfert${RESET}"
curl -s -X POST $BASE_URL/transfert \
  -H "Content-Type: application/json" \
  -d '{"depot_id":1,"date_transfert":"2026-09-24","destination":"Douala","raison":"Autopsie","nom_retirant":"Docteur","decharge_transfert":"OK","agent":"AgentX"}'
echo -e "\n"

# 📋 Lister les transferts
echo -e "${GREEN}>> Liste transferts${RESET}"
curl -s $BASE_URL/transfert
echo -e "\n"

# ⚰️ Ajouter une sortie
echo -e "${GREEN}>> Ajout sortie${RESET}"
curl -s -X POST $BASE_URL/sortie \
  -H "Content-Type: application/json" \
  -d '{"depot_id":1,"date_sortie":"2026-09-24","heure":"10:00","destination_finale":"Village","type_sortie":"Inhumation","nom_retirant":"Famille","decharge_sortie":"OK","frais_solde":50000}'
echo -e "\n"

# 📋 Lister les sorties
echo -e "${GREEN}>> Liste sorties${RESET}"
curl -s $BASE_URL/sortie
echo -e "\n"

# 📊 Statistiques
echo -e "${GREEN}>> Statistiques${RESET}"
curl -s $BASE_URL/stats
echo -e "\n"

echo -e "${CYAN}=== ✅ Tests terminés ===${RESET}"
