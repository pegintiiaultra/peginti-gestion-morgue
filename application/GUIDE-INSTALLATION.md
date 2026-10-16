# Guide d'installation — PEGINTI Morgue (version consolidée)

Le paquet `PEGINTI-Morgue-v1.0.0.0.zip` contient : `INSTALLER.sh` et `INSTALLER.bat` (point d'entrée unique), `application/` (le programme), `documentation/` et `site-web/` (plateforme de téléchargement). **Un seul geste suffit : lancer l'installateur de votre appareil.** Il détecte l'appareil, installe ce qui manque, installe ou met à jour, puis démarre l'application.

Compte initial : **admin** / **Admin123!** (changement obligatoire à la première connexion ; un *code de récupération* est alors remis : notez-le). La **double authentification est exigée de tous les comptes** : avant la première connexion, installez sur le téléphone une application d'authentification (Google Authenticator, Microsoft Authenticator, Aegis ou FreeOTP).

## A. Android (Termux)
1. Installez **Termux** depuis F-Droid. Téléchargez le zip ; il se place dans Téléchargements.
2. Dans Termux, copiez ces lignes :
```bash
termux-setup-storage        # accepter l'autorisation (une seule fois)
pkg install -y unzip
unzip -o "/storage/emulated/0/Download/PEGINTI-Morgue-v1.0.0.0.zip" -d ~
sh ~/PEGINTI-Morgue-v1.0.0.0/INSTALLER.sh
```
(si Android a ajouté un suffixe au fichier, par exemple `-1`, utilisez ce nom exact.)
L'installateur ajoute Python, Node.js et PM2 s'ils manquent, empêche la mise en veille de Termux, installe, puis démarre l'application en permanence. Ouvrez ensuite `http://localhost:3001` dans Chrome, menu ⋮ → **Installer l'application**.

## B. PC Windows
Décompressez le zip, puis **double-cliquez sur `INSTALLER.bat`**. Si Python est absent, l'installateur tente de l'installer (winget) ; fermez alors la fenêtre et relancez-le. Il installe, crée un raccourci **PEGINTI Morgue** sur le Bureau, démarre l'application et ouvre le navigateur. Ensuite : double-clic sur le raccourci pour démarrer. (Si winget est absent : installez Python 3 depuis python.org en cochant **Add Python to PATH**, puis relancez.)

## C. PC Linux / macOS
```bash
unzip PEGINTI-Morgue-v1.0.0.0.zip && sh PEGINTI-Morgue-v1.0.0.0/INSTALLER.sh
```

## Mise à jour : la même commande, sans perte de données
Décompressez la nouvelle version **par-dessus le dossier existant** (le dossier `data/` n'est jamais dans le zip) puis relancez l'installateur : s'il détecte une installation existante, il **met à jour sans rien effacer** (copie de sécurité automatique de la base). Ensuite : `pm2 restart morgue` si PM2 est utilisé.
Une base contenant des données ne peut pas être effacée par erreur : `python install.py --force` la refuse, sauf `--force --effacer-donnees` (ou la phrase exacte `EFFACER MES DONNEES`), et même alors une copie est gardée dans `backend/data/backups/avant-installation-<date>/`.
Restaurer cette copie : arrêter PM2 (`pm2 stop morgue`), recopier `morgue.db*` (avec `-wal` et `-shm`) et le dossier `uploads` dans `backend/data/`, puis relancer l'installateur et `pm2 restart morgue`.

## Réseau d'entreprise (plusieurs postes, sans Internet)
Sur **un** appareil (le « serveur », allumé pendant les gardes) : `sh demarrer.sh reseau` (Windows : `demarrer.bat reseau`). L'adresse s'affiche (ex. `http://192.168.1.20:3001`). Les autres PC/téléphones connectés au **même Wi-Fi/câble** ouvrent cette adresse et peuvent l'installer comme application. Autorisez le port 3001 dans le pare-feu si nécessaire. Réseau privé uniquement : ne l'ouvrez pas sur Internet sans HTTPS.

## En ligne (pegintichat.online)
`sh demarrer.sh enligne` (écoute locale + proxy de confiance), puis exposez le port 3001 en **HTTPS** : Cloudflare Tunnel (`deploy/cloudflared-config.yml`) ou Caddy (`deploy/Caddyfile`). Avec PM2, `ecosystem.config.js` est déjà réglé pour ce mode.
**Erreur « error parsing YAML in config file … config.yml » / erreur 530 du domaine** : `~/.cloudflared/config.yml` est mal indenté (modèle copié avec `<ID>` non remplacé). Corrigez avec `sh deploy/configurer-tunnel.sh`, puis `pm2 restart cloudflared`.

## Pièges fréquents
- **Deux dossiers, deux applications.** `pm2 restart morgue` relance le programme *du dossier où PM2 l'a démarré*. Après une installation dans un **nouveau** dossier : `pm2 delete morgue`, puis dans le nouveau `application/` : `pm2 start ecosystem.config.js && pm2 save`. Une installation dans un nouveau dossier crée une **base vide** ; l'ancienne reste dans l'ancien dossier (copiez `backend/data/` pour la reprendre).
- **L'ancienne interface reste affichée sur le domaine.** Cloudflare gardait une copie des fichiers ; le serveur interdit désormais toute mise en cache. Une seule fois : Cloudflare → Caching → Configuration → **Purge Everything**, puis fermer et rouvrir l'application installée.
- **Compte admin refusé** après une installation neuve : `cd backend && python install.py --force` puis `pm2 restart morgue` (ajouter `--effacer-donnees` si la base contient des données).
- **« Permission denied » sur le zip** (Android) : lancer `termux-setup-storage` et accepter.

## Premiers pas
1. Connexion `admin` → changer le mot de passe → noter le code de récupération → activer la double authentification (noter les **8 codes de secours**).
2. **Paramétrage** : créer les box ; **Paramètres et tarifs** : saisir les prix (nuitées, chapelles, majoration, transfert) ; **Gardes** : équipes et agents.
3. **Comptes** : créer les thanatopracteurs (ou ils s'inscrivent eux-mêmes puis vous validez). Le super administrateur (DG) se crée depuis un compte administrateur.
4. Seuls les thanatopracteurs saisissent et modifient les registres ; les administrateurs supervisent.
5. Partout, les boutons **✎ Modifier** et **Supprimer** : dans les registres, « Supprimer » enregistre une annulation motivée (la ligne reste visible, barrée) ; dans le paramétrage, les gardes, les comptes et les annonces, un élément qui a déjà servi ne peut pas être supprimé : utilisez « Désactiver ».

## Double authentification (exigée de tous)
Après le changement du mot de passe, l'application guide l'activation : installer l'application d'authentification, saisir la clé, entrer le code, **noter les 8 codes de secours**. L'heure du téléphone doit être automatique. La règle (aucun / administrateurs / tous) se modifie dans « Paramètres et tarifs » ou en ligne de commande : `cd backend && python manage.py mfa tous`. **Installation existante** : pour exiger la double authentification de tous, lancez `python manage.py mfa tous` (chaque compte l'active à sa prochaine connexion).
Téléphone perdu : code de secours, ou un administrateur autorisé clique « Réinit. 2FA » (Comptes), ou `cd backend && python manage.py reset2fa <identifiant>`.

## Mot de passe oublié
Écran de connexion → **Mot de passe oublié ?** → identifiant + code de récupération. Sans code : l'administration réinitialise le mot de passe (Comptes → Mot de passe).

## Sauvegarde, diagnostic
- Sauvegarde : *Comptes → Sauvegarde de la base* ou `python manage.py backup` ; copiez aussi `backend/data/uploads/`. **Gardez une copie hors de l'appareil** (ordinateur, clé USB) : un téléphone perdu emporte la base et ses copies.
- Problème : `cd backend && python diagnostic.py` ; `curl localhost:3001/api/sante` ; `backend/data/erreurs.log`. Après mise à jour des fichiers : `pm2 restart morgue`.

## Hors connexion : ce qui est possible
Poste seul et réseau local fonctionnent **sans Internet**. L'interface installée reste ouverte si le serveur est coupé un instant, mais la saisie exige que le serveur soit joignable (synchronisation multi-appareils hors ligne : évolution future).

## Sauvegarde automatique
**Sauvegarde automatique** : l'application copie elle-même la base une fois par jour dans `backend/data/backups/` (fichiers `auto-AAAAMMJJ-….db`, 30 derniers gardés) ; aucune action requise. Copiez régulièrement ce dossier hors de l'appareil (carte SD, clé USB, ordinateur) : une sauvegarde sur le même téléphone ne protège pas d'une perte du téléphone.
