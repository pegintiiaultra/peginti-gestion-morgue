#!/bin/sh
# DÉMARRAGE. Trois modes d'usage :
#   sh demarrer.sh            POSTE SEUL : accessible uniquement depuis cet appareil (http://localhost:3001)
#   sh demarrer.sh reseau     RÉSEAU D'ENTREPRISE (Wi-Fi/câble commun) : les autres PC/téléphones ouvrent http://ADRESSE-IP:3001
#   sh demarrer.sh enligne    EN LIGNE derrière un tunnel/proxy HTTPS (voir GUIDE-INSTALLATION.md, domaine pegintichat.online)
cd "$(dirname "$0")/backend"
PY=$(command -v python3 || command -v python)
case "$1" in
  reseau)
    export MORGUE_HOST=0.0.0.0
    IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    [ -z "$IP" ] && IP=$(ifconfig 2>/dev/null | awk '/inet /{print $2}' | grep -v '^127' | head -1)
    echo "Réseau local : les autres appareils ouvrent  http://${IP:-ADRESSE-IP-DE-CET-APPAREIL}:3001" ;;
  enligne) export MORGUE_HOST=127.0.0.1 MORGUE_BEHIND_PROXY=1 ;;
  *) export MORGUE_HOST=127.0.0.1 ;;
esac
export MORGUE_PORT="${MORGUE_PORT:-3001}"
exec $PY app.py
