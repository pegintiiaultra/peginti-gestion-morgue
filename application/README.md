# PEGINTI Morgue — registres, statistiques et gardes

Application web de gestion des registres d'une morgue (entrées, transferts, sorties), plan des box,
statistiques sur le trafic enregistré, planning des gardes et comptes nominatifs.

- **Backend** : Python (Flask) + SQLite — `backend/`
- **Frontend** : JavaScript natif, sans bibliothèque externe — `frontend/`
- **Port réservé : 3001** — **domaine : pegintichat.online**
- Le backend sert aussi le frontend : en local `http://localhost:3001`

## Installation
Voir **GUIDE-INSTALLATION.md** (Android/Termux, Windows, Linux, réseau d'entreprise, en ligne, mise à jour).
Livraison : un seul paquet `PEGINTI-Morgue-v1.0.0.0.zip` (dossiers `application/`, `documentation/`, `site-web/`, plus `LISEZ-MOI.txt`).
Installation automatique selon l'appareil : `sh INSTALLER.sh` (Android/Termux, Linux, macOS) ou double-clic sur `INSTALLER.bat` (Windows) ; l'installateur détecte l'appareil, installe ce qui manque et met à jour sans perte une installation existante. Résumé, depuis `application/` : `sh installer.sh` puis `sh demarrer.sh` → http://localhost:3001 (compte `admin` / `Admin123!`, à changer à la première connexion).

### 3. Nom de domaine pegintichat.online (HTTPS obligatoire)
L'application écoute en local sur le port 3001 ; exposez-la uniquement via HTTPS :
- Cloudflare Tunnel : modèle dans `deploy/cloudflared-config.yml`
- ou serveur avec Caddy : `deploy/Caddyfile`

## Modifier / Supprimer
Chaque liste et chaque formulaire a ses boutons **✎ Modifier** et **Supprimer**. Dans les registres, « Supprimer » = annulation motivée (traçabilité : la ligne reste, barrée). Dans le paramétrage (box, divisions, services, raisons), les gardes (équipes, agents), les comptes et les annonces, la suppression est refusée si l'élément a déjà servi : utiliser « Désactiver ».
Un transfert peut concerner un corps **non conservé** (demande de la famille, obédience religieuse) : choisir « Corps non conservé » dans le formulaire.

## Comptes : le fonctionnement
0. L'administration peut aussi créer un compte directement (mot de passe provisoire à changer à la première connexion).
1. **Chaque thanatopracteur crée sa demande** depuis l'écran de connexion (« Créer mon compte ») :
   *identifiant = son nom*, mot de passe saisi puis confirmé. Le compte reste **en attente, sans accès**.
2. **L'administration valide ou refuse** (menu *Comptes*) et attribue le rôle.
3. **Suppression : réservée à l'administration.** Elle choisit le motif (**révocation, décès ou démission**) et
   confirme avec son mot de passe. Le compte **n'a plus aucun accès** ; son historique (registres, journal) est
   conservé et il apparaît dans les archives. Le nom archivé n'est pas réutilisable.
4. Il doit toujours rester au moins un administrateur actif ; on ne peut pas supprimer son propre compte.

Menus d'administration : **Comptes** (validation, suspension, réinitialisation, suppression, sauvegarde),
**Journal** (toutes les connexions et actions sensibles).

## Premier paramétrage (administrateur)
*Paramétrage* → *Ajouter un box* : nom (A, B…), nombre de divisions, capacité (24 = lettres a à x), option « sol ».
*Gardes* : équipes, agents, système 12 h ou 24 h, génération du planning du mois.

## Règles appliquées automatiquement
- Emplacement = box + division + lettre ; un seul corps par emplacement (garanti par la base).
- Le **sol (X0)** n'est proposé que si toutes les divisions numérotées du box sont pleines (sinon dérogation motivée).
- **Mercredi** = levée / vidange systématique de la chambre froide ; la sortie définitive (remise à la famille) suit la levée.
- Les levées sont facturées automatiquement (nuitées, majoration, chapelle) ; paiements suivis jusqu'au solde.
- N° d'ordre séquentiel **par année** pour chaque registre.
- **Pas de suppression de données** : annulation motivée par le thanatopracteur ; correction possible (✎ Modifier) ; tout est journalisé.
- Gardes : 12 h (permanence 7h30–17h00, garde 17h–7h30) ou 24 h (7h30 → 7h30) ; présence obligatoire le jeudi et le
  vendredi sauf l'équipe sortante ; levée / vidange le mercredi.

## Rôles
| Rôle | Droits |
|---|---|
| Thanatopracteur | seul à saisir, modifier et annuler les registres ; consultation, boîte de réception |
| Administrateur | supervision (lecture/export), paramétrage et tarifs, comptes thanatopracteurs, annonces |
| Super administrateur (DG) | unique ; supprime tous les comptes, administrateurs compris |

## Sécurité
Mots de passe hachés (scrypt), jetons signés (8 h), blocage après 5 échecs, limitation des demandes d'inscription,
SQL paramétré, interface sans `innerHTML`, CSP stricte, HSTS en HTTPS, fichiers vérifiés (PDF/PNG/JPEG, 5 Mo).
Clé de signature : `backend/data/secret.key` (droits 600).

## Double authentification (TOTP)
Code à 6 chiffres via une application d'authentification, codes de secours, politique « facultative / administrateurs / tous » (Paramètres). Exigée des administrateurs sur une installation neuve. Réinitialisation : bouton « Réinit. 2FA » ou `python manage.py reset2fa <identifiant>`.

## Sauvegarde
- Menu *Comptes* → **Sauvegarde de la base** (téléchargement), ou `python manage.py backup` (30 dernières conservées).
- Copiez aussi `backend/data/uploads/` (plans de localisation) **hors du téléphone**.

## Diagnostic (en cas de problème)
```bash
cd backend && python diagnostic.py        # rejoue un parcours complet sur une base temporaire
curl -s localhost:3001/api/sante          # état du serveur et de la base
tail -n 30 backend/data/erreurs.log       # erreurs détaillées du serveur
```
Après toute mise à jour des fichiers : `pm2 restart morgue`.

## Tests
```bash
cd backend && python -m unittest discover -s tests -v     # 55 tests
```

## Exports
Chaque registre : **Exporter Excel (.xlsx)**, **Exporter CSV**, **Imprimer / PDF** (A4 paysage, en-tête de l'établissement,
zones de visa du thanatopracteur et de la direction ; sur téléphone : Imprimer → Enregistrer au format PDF).
Le nom de l'établissement se règle dans *Paramétrage*.

## Non réalisé
Mode hors connexion avec synchronisation (objectif ultérieur ; l'application est prévue pour être utilisée en ligne).
