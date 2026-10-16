#!/bin/sh
# Écrit automatiquement ~/.cloudflared/config.yml SANS erreur de syntaxe (tunnel déjà créé et connecté à votre compte).
# Usage : sh deploy/configurer-tunnel.sh [nom-de-domaine] [port]
HOST="${1:-pegintichat.online}"; PORT="${2:-3001}"
DIR="${CLOUDFLARED_DIR:-$HOME/.cloudflared}"
CRED=$(ls "$DIR"/*.json 2>/dev/null | head -1)
if [ -z "$CRED" ]; then
  echo "Aucun fichier d'identifiants (*.json) dans $DIR."
  echo "Créez d'abord le tunnel :  cloudflared tunnel login  puis  cloudflared tunnel create peginti"; exit 1
fi
ID=$(basename "$CRED" .json)
[ -f "$DIR/config.yml" ] && cp "$DIR/config.yml" "$DIR/config.yml.ancien"
cat > "$DIR/config.yml" <<EOF
tunnel: $ID
credentials-file: $CRED
ingress:
  - hostname: $HOST
    service: http://localhost:$PORT
  - service: http_status:404
EOF
echo "Écrit : $DIR/config.yml"; cat "$DIR/config.yml"
echo; echo "Liez le domaine (une seule fois) :  cloudflared tunnel route dns $ID $HOST"
echo "Puis relancez :  pm2 restart cloudflared   (ou)   cloudflared tunnel run $ID"
