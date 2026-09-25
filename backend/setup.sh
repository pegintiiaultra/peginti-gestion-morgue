#!/bin/bash

echo "🚀 Initialisation de l'arborescence PEGINTI-GESTION-MORGUE..."

# Création des dossiers principaux et internes
mkdir -p backend/routes
mkdir -p backend/controllers
mkdir -p backend/models

mkdir -p database/migrations
mkdir -p database/seeds

mkdir -p public/css
mkdir -p public/js
mkdir -p public/images

mkdir -p src/components
mkdir -p src/pages
mkdir -p src/utils

echo "✅ Arborescence créée avec succès !"
