#!/bin/sh
# INSTALLATION AUTOMATIQUE — Android (Termux), Linux, macOS : détecte l'appareil, installe ce qui manque, installe ou met à jour, démarre.
#   sh installer.sh            installation neuve ; si une installation existe déjà ici, MISE À JOUR automatique sans perte de données
#   sh installer.sh --maj      mise à jour explicite (jamais de perte)
#   sh installer.sh --force    base neuve (refusé si la base contient des données ; voir GUIDE-INSTALLATION.md)
set -e
cd "$(dirname "$0")"

# 1. Quel appareil ?
TERMUX=0
if [ -n "$TERMUX_VERSION" ] || [ -d /data/data/com.termux/files ]; then TERMUX=1; fi
if [ "$TERMUX" = 1 ]; then echo "==> Appareil détecté : Android (Termux)"; else echo "==> Appareil détecté : $(uname -s)"; fi

# 2. Python (installé automatiquement si possible)
PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo "==> Installation de Python"
  if [ "$TERMUX" = 1 ]; then pkg install -y python
  elif command -v apt-get >/dev/null 2>&1; then sudo apt-get update -y && sudo apt-get install -y python3 python3-pip
  elif command -v brew >/dev/null 2>&1; then brew install python
  fi
  PY=$(command -v python3 || command -v python || true)
fi
if [ -z "$PY" ]; then echo "Python est introuvable et n'a pas pu être installé : installez Python 3 puis relancez."; exit 1; fi

# 3. Démarrage permanent : PM2 (facultatif, installé s'il est possible)
if ! command -v pm2 >/dev/null 2>&1; then
  if [ "$TERMUX" = 1 ] && ! command -v npm >/dev/null 2>&1; then pkg install -y nodejs >/dev/null 2>&1 || true; fi
  if command -v npm >/dev/null 2>&1; then echo "==> Installation de PM2 (démarrage permanent)"; npm i -g pm2 >/dev/null 2>&1 || true; fi
fi
if [ "$TERMUX" = 1 ] && command -v termux-wake-lock >/dev/null 2>&1; then termux-wake-lock || true; fi

# 4. Dépendances
echo "==> Installation des dépendances"
if [ -z "$PEGINTI_SANS_PIP" ]; then   # PEGINTI_SANS_PIP=1 : dépendances déjà présentes (installation hors ligne)
  $PY -m pip install -q -r backend/requirements.txt --break-system-packages 2>/dev/null || $PY -m pip install -q -r backend/requirements.txt || $PY -m pip install -q flask PyJWT waitress --break-system-packages
fi
if ! $PY -c "import flask, jwt" 2>/dev/null; then
  echo "ERREUR : modules Python manquants (flask, PyJWT). Verifiez la connexion Internet puis relancez : sh INSTALLER.sh"; exit 1
fi

# 5. Installation neuve ou mise à jour (une installation existante n'est JAMAIS effacée par erreur)
MODE="$1"
if [ -z "$MODE" ] && [ -f backend/data/morgue.db ]; then
  MODE="--maj"
  echo "==> Installation existante détectée : mise à jour sans perte de données"
fi
cd backend
if [ "$MODE" = "--maj" ]; then
  $PY -c "import db; db.init_db(); print('Base migrée / à jour.')"
else
  $PY install.py "$@"
fi
cd ..

# 6. Démarrage
if command -v pm2 >/dev/null 2>&1; then
  pm2 delete morgue >/dev/null 2>&1 || true   # repart toujours du dossier courant (évite de relancer une ancienne copie)
  pm2 start ecosystem.config.js
  pm2 save >/dev/null 2>&1 || true
  echo "Application démarrée en permanence par PM2 (pm2 restart morgue pour la relancer)."
else
  nohup sh demarrer.sh > backend/data/serveur.log 2>&1 &
  echo "Application démarrée en arrière-plan (journal : backend/data/serveur.log). Pour la relancer plus tard : sh demarrer.sh"
fi
# Attente du démarrage (jusqu'à 60 s) et contrôle
i=0; while [ $i -lt 30 ]; do
  if $PY -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:3001/api/sante',timeout=2)" 2>/dev/null; then echo "==> Application en ligne sur le port 3001 : OK"; break; fi
  i=$((i+1)); sleep 2
done
[ $i -ge 30 ] && echo "ATTENTION : l'application ne répond pas encore. Patientez 1 minute puis ouvrez http://localhost:3001 ; sinon : sh demarrer.sh"
echo
echo "Ouvrez  http://localhost:3001"
if [ "$MODE" != "--maj" ]; then
  echo "Première connexion : identifiant  admin   mot de passe provisoire  Admin123!  (changement obligatoire)"
  echo "Double authentification exigée : installez Google/Microsoft Authenticator, Aegis ou FreeOTP sur le téléphone avant de vous connecter."
fi
if [ "$TERMUX" = 1 ]; then echo "Sur Android : dans Chrome, menu ⋮ puis « Installer l'application » pour l'icône sur l'écran d'accueil."; fi
