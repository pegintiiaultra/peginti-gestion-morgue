# Passer de Termux (téléphone) à un serveur 24 h/24

*PEGINTI Morgue v2.1.0 — le même code tourne sur Linux sans modification ; seules la machine et le démarrage automatique changent. Les données (patients, comptes, plans) se déplacent par simple copie.*

## 1. Quelle machine choisir
| Option | Avantages | Points d'attention |
|---|---|---|
| **Mini-PC / vieux PC portable** sous Ubuntu ou Debian (4 Go de RAM suffisent) | Local, sans abonnement, accessible aussi sur le réseau de l'hôpital | Alimentation : prévoir un onduleur ; régler le BIOS sur « redémarrer après coupure de courant » |
| **Raspberry Pi 4/5** | Très économe en énergie, silencieux | Utiliser un disque SSD (la carte SD s'use) |
| **Serveur loué (VPS)**, 1 Go de RAM | Toujours allumé, indépendant des coupures de l'hôpital | Abonnement mensuel ; les données quittent l'hôpital : vérifier les règles de protection des données du service |

## 2. Préparer le serveur (Ubuntu / Debian)
```bash
sudo apt update && sudo apt install -y python3 python3-pip unzip
unzip PEGINTI-Morgue-v1.0.0.0.zip -d ~ && cd ~/PEGINTI-Morgue-v1.0.0.0
```
N'installez rien d'autre : `sh INSTALLER.sh` (étape 3) installe les dépendances. Il crée une base vide, remplacée à l'étape 3 par vos données.

## 3. Déplacer les données du téléphone
1. **Sur le téléphone**, arrêtez l'écriture et faites l'archive :
   ```bash
   pm2 stop morgue
   cd ~/peginti-morgue/backend && tar czf ~/morgue-data.tgz data
   ```
2. Envoyez `morgue-data.tgz` au serveur : câble USB (`termux-setup-storage` puis copier vers Téléchargements) ou `scp ~/morgue-data.tgz utilisateur@IP-SERVEUR:~/` (`pkg install openssh`).
3. **Sur le serveur** :
   ```bash
   tar xzf ~/morgue-data.tgz -C ~/PEGINTI-Morgue-v1.0.0.0/application/backend
   cd ~/PEGINTI-Morgue-v1.0.0.0 && sh INSTALLER.sh      # détecte la base existante : mise à jour sans perte
   cd application/backend && python3 manage.py mfa tous   # double authentification pour tous
   ```
   Le dossier `data` contient la base `morgue.db`, la clé de signature `secret.key` et les plans de localisation (`uploads/`).

## 4. Démarrage automatique (systemd)
Créez `/etc/systemd/system/morgue.service` (remplacez `UTILISATEUR`) :
```ini
[Unit]
Description=PEGINTI Morgue
After=network-online.target

[Service]
User=UTILISATEUR
WorkingDirectory=/home/UTILISATEUR/peginti-morgue/backend
Environment=MORGUE_HOST=127.0.0.1 MORGUE_PORT=3001 MORGUE_BEHIND_PROXY=1
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload && sudo systemctl enable --now morgue
curl -s localhost:3001/api/sante          # doit afficher les comptes existants
```

## 5. Reprendre le nom de domaine (même tunnel Cloudflare)
Le tunnel peut tourner sur une seule machine à la fois.
1. **Téléphone** : `pm2 delete cloudflared-morgue` (et `pm2 save`).
2. **Serveur** : installez `cloudflared` (voir developers.cloudflare.com → Downloads), puis :
   ```bash
   sudo cloudflared service install <JETON-DU-TUNNEL>
   ```
   Le jeton se prend dans Cloudflare → Tunnels → votre tunnel → Configure. La destination reste `127.0.0.1:3001` : **rien à changer** dans Public Hostname.
3. Vérifiez : `curl -s https://morgue.pegintichat.online/api/sante`, puis connectez-vous.

## 6. Sauvegardes et sécurité
- Sauvegarde quotidienne à 2 h (`crontab -e`) :
  ```
  0 2 * * * cd /home/UTILISATEUR/peginti-morgue/backend && python3 manage.py backup
  ```
  Puis copiez `backend/data/backups/` et `backend/data/uploads/` **hors de la machine** (clé USB ou second disque), au moins chaque semaine.
- Aucun port n'est ouvert vers Internet : seul le tunnel sort. Gardez le système à jour (`sudo apt upgrade`) et un mot de passe fort sur la machine.
- Après la bascule, gardez l'archive `morgue-data.tgz` du téléphone en lieu sûr pendant quelques semaines, puis détruisez-la : elle contient des données de défunts.

## 7. Retour arrière
Si quelque chose ne va pas : sur le serveur `sudo systemctl stop morgue` et `sudo systemctl stop cloudflared`, puis sur le téléphone `pm2 start cloudflared-morgue` et `pm2 start morgue`. Les données du téléphone n'ont pas été modifiées.
