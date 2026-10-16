# Cahier des charges — PEGINTI Morgue (registres, statistiques, gardes) — version 2.1.0

*Application de gestion des registres d'une morgue hospitalière au Cameroun. Domaine : **pegintichat.online** · Port : **3001**. Mise à jour après réalisation et exécution du code.*

## 1. Objectif
Numériser les registres (dépôt, transfert, levée, sortie définitive), garantir leur traçabilité, facturer les levées, produire des statistiques fiables sur le trafic du service de thanatopraxie et gérer les gardes. Chaque hôpital installe sa propre copie (base vide + un seul administrateur).

## 2. Architecture et modes d'usage
- Backend **Python** (Flask 3, SQLite WAL, PyJWT, waitress) ; frontend **JavaScript natif** (sans bibliothèque, graphiques SVG internes). Le serveur sert l'API et l'interface sur une seule adresse.
- **Application installable (PWA)** sur Android, PC et iPhone : « Installer l'application » / « Ajouter à l'écran d'accueil » ; l'interface s'adapte automatiquement (téléphone, tablette, PC, impression A4 paysage). Le service worker garde l'interface disponible si le serveur est momentanément injoignable ; **les données ne sont jamais mises en cache** (confidentialité).
- **Trois modes** : (1) *poste seul* : tout tourne sur l'appareil (PC ou Termux), sans Internet ; (2) *réseau d'entreprise* : un appareil sert les autres du même Wi-Fi/câble (`sh demarrer.sh reseau`), sans Internet ; (3) *en ligne* : derrière un tunnel HTTPS (pegintichat.online).
- **Limite assumée** : la synchronisation automatique de plusieurs appareils déconnectés (saisie hors ligne puis fusion) n'est pas réalisée ; elle est l'objectif ultérieur. En poste seul ou réseau local, aucune connexion Internet n'est nécessaire.

## 3. Rôles (3)
| Rôle | Droits |
|---|---|
| **Thanatopracteur** (l'ouvrier) | **Seul** à saisir, **modifier** et annuler les registres ; consulte statistiques, plan, gardes, boîte de réception |
| **Administrateur** | Supervise : consulte et exporte les registres et les statistiques, ne modifie aucun registre ; paramètre (box, services, raisons, **tarifs**, gardes) ; crée/valide/suspend/supprime les comptes **thanatopracteurs** ; crée l'unique super administrateur ; publie des annonces |
| **Super administrateur (DG)** | Unique en base ; mêmes pouvoirs de supervision + **seul à pouvoir supprimer tous les comptes**, administrateurs compris ; crée des administrateurs |
- Un administrateur ne peut supprimer ni un autre administrateur ni le super administrateur. Garde-fou : jamais de suppression du dernier superviseur actif ni de son propre compte. Suppression = archivage avec motif (révocation, décès, démission) + mot de passe du demandeur ; l'historique reste lisible.
- Les anciens rôles *responsable* et *direction* sont migrés en *administrateur*.
- Inscription libre (« Créer mon compte ») : compte **en attente**, sans accès, validé par l'administration.
- Mot de passe provisoire (installation, compte créé ou réinitialisé par l'administration) : **changement obligatoire** à la première connexion.
- **Récupération du compte** : à son premier mot de passe personnel, chacun reçoit un **code de récupération** (16 caractères, affiché une seule fois, conservé haché). « Mot de passe oublié ? » : identifiant + code + nouveau mot de passe ; le code est renouvelé après usage ; tentatives limitées par adresse et par compte. À défaut, l'administration réinitialise.

## 4. Registres (menu numéroté)
1. **Dépôt (bleu)** : n° d'ordre annuel, date/heure, défunt (nom, prénoms, âge, sexe), responsable (nom, contact, adresse, visa), cas externe/interne (+ service), thanatopracteur de service + visa. Deux types : *conservation en chambre froide* (type de chambre **commune/individuelle** obligatoire, emplacement box + division + lettre, ex. `A1a`) ou *entrée directe pour transfert* depuis un service interne (aucune entrée en chambre froide, aucune conservation facturée, seulement les frais de transfert ; service d'origine + destination ; crée automatiquement le transfert lié).
2. **Transfert (orange)** : mêmes champs + raison (liste paramétrable : autopsie, rapatriement, demande de la famille, obédience religieuse, « autre » avec précision…), lieu, frais de transfert. **Deux origines** : un corps en chambre froide (l'emplacement est libéré), ou un **corps non conservé** venant directement d'un service de l'hôpital (demande de la famille, obédience religieuse refusant la conservation) : l'entrée directe et le transfert sont créés ensemble, avec la raison choisie, sans frais de conservation. Le formulaire propose ce mode automatiquement quand aucun corps n'est en chambre froide.
3. **Levée (orange foncé)** : opération chambre froide → funérarium (le **mercredi** : « Levée / vidange systématique de la chambre froide »). Calcul automatique : nuitées × prix selon la chambre, majoration, chapelle. Versement (montant, mode espèces / MoMo / Orange Money / virement), « Soldé », reste à payer, versements complémentaires ultérieurs (historique des paiements).
4. **Sortie définitive (rouge)** : remise à la famille après levée ; genre de mort, lieu d'inhumation (région, département, arrondissement, village) et date, colonne **Localisation** (import du plan PDF/JPG/PNG ≤ 5 Mo, icône 👁 pour consulter).
- **Modifier** : le thanatopracteur corrige tout enregistrement (✎ Modifier) ; seules les zones changées sont envoyées ; garde-fous de cohérence (dates, emplacement libre, recalcul des montants d'une levée) ; mention « corrigé le … par … » et journal avant/après.
- Registres : le bouton « Supprimer » enregistre une annulation motivée (la ligne reste visible, barrée, avec motif, date et auteur) : traçabilité d'un registre officiel. Chaque ligne a aussi « ✎ Modifier ».
- Paramétrage, gardes, comptes, annonces : boutons « Modifier » et « Supprimer » partout. Un box, une division, un service, une raison ou une équipe qui a déjà servi ne peut pas être supprimé (refus clair) : utiliser « Désactiver ». Les raisons système (« Autre », transfert direct) sont protégées. Un agent supprimé disparaît des effectifs ; une équipe supprimée laisse ses agents sans équipe. Recherche rapide (n°, nom, téléphone), exports Excel/CSV, impression/PDF.

## 5. Majoration automatique des levées
Heures de levée par défaut 7h–18h (paramétrables). Lundi, mardi, samedi : normal 7–18 h ; jeudi, vendredi : normal 7–18 h, majoré après 18 h ; mercredi : majoré après 18 h ; **dimanche : toute la journée majorée**. Alerte orange « Majoration applicable : [motif] » à la saisie.

## 6. Paramètres et tarifs (administrateur / super administrateur)
Nuitée chambre commune, nuitée chambre individuelle, petite et grande chapelle (location le jour de la levée), majoration, frais de transfert, heures de levée, devise (FCFA). Montants entiers. Nuitées = nuits calendaires, minimum 1.

## 7. Statistiques (trafic enregistré, sans tenir compte de la capacité de la chambre froide)
Corps par mois, transferts par mois et raison dominante, externes/internes, service ayant le plus de décès, levées, sorties, genres de mort, flux (entrées → transférés/levés/sortis), **chiffre d'affaires par mois (12 mois)**, répartition (conservations, majorations, chapelles petites/grandes, transferts), levées soldées / non soldées avec tableau des impayés. Filtres : période, cas, service, mois.

## 8. Box et plan
Box saisis par l'administration ; division 0 = sol (utilisable uniquement si le box est saturé, sinon dérogation motivée) ; un corps par emplacement (contrainte en base) ; plan d'occupation en temps réel.

## 9. Gardes
Systèmes 12 h (permanence 7h30–17h00, garde 17h00–7h30) ou 24 h (7h30 → 7h30) ; équipes, agents, planning mensuel, génération automatique ; présence obligatoire jeudi et vendredi sauf équipe sortante ; **mercredi : levée / vidange systématique de la chambre froide**.

## 10. Annonces et boîte de réception
Un administrateur rédige une annonce (titre, message, option « important ») ; **tous les comptes actifs la reçoivent**, administrateurs compris (pastille de non-lus, « marquer comme lu »). Retrait possible par l'auteur ou le super administrateur.

## 11. Sécurité
Jeton signé 8 h, contrôle du compte à chaque requête, blocage après échecs (par adresse et par compte), SQL paramétré, interface sans `innerHTML`, CSP stricte (scripts, worker, manifest en `self`), HSTS en HTTPS, ProxyFix, mots de passe hachés (scrypt), **double authentification TOTP** (voir 11 bis), index unique du super administrateur, journal de sécurité, sauvegarde cohérente téléchargeable, fichiers vérifiés.

## 11 bis. Double authentification (v2.1.0)
Code à 6 chiffres (TOTP, RFC 6238) généré par une application d'authentification (Google/Microsoft Authenticator, Aegis, FreeOTP). Connexion en deux étapes : identifiant + mot de passe, puis code ; le jeton de session n'est délivré qu'après le second facteur. Activation guidée (clé à saisir, code de contrôle), **8 codes de secours** à usage unique (hachés), rejeu d'un code refusé, tolérance d'un pas de 30 s, blocage après 5 échecs. **Politique de la morgue** (Paramètres) : facultative, **exigée de tous les comptes par défaut à l'installation** (réglable : aucun, administrateurs, tous ; `python manage.py mfa <valeur>`) ; un compte concerné doit l'activer avant d'entrer. Téléphone perdu : code de secours, ou réinitialisation par un administrateur autorisé (super administrateur pour un administrateur), ou `python manage.py reset2fa <identifiant>` par l'administrateur système. Toutes ces actions sont journalisées.

## 11 quater. Installateur protégé et journal lisible
**Sauvegarde automatique** : l'application copie elle-même la base une fois par jour dans `backend/data/backups/` (fichiers `auto-AAAAMMJJ-….db`, 30 derniers gardés) ; aucune action requise. Copiez régulièrement ce dossier hors de l'appareil (carte SD, clé USB, ordinateur) : une sauvegarde sur le même téléphone ne protège pas d'une perte du téléphone.

`installer.sh` refuse d'effacer une base contenant des données (confirmation par phrase exacte, copie de sécurité systématique) ; la mise à jour passe par `--maj`. Le journal de sécurité affiche des libellés en français et des changements « avant → après » ; un enregistrement des tarifs sans modification ne crée aucune ligne.

## 11 ter. Impressions
Registres, planning des gardes (toutes les colonnes, listes en texte) et **journal de sécurité** s'impriment en A4 paysage avec en-tête de l'établissement, date et auteur de l'impression, et zones de visa/signature.

## 12. Fiabilité et évolutivité
SQLite WAL (repli automatique), `busy_timeout`, transactions `BEGIN IMMEDIATE`, index sur les colonnes de recherche, pagination des listes, migration automatique des bases v1 avec **copie de sécurité préalable** (`data/backups/avant-migration-*.db`) et script manuel `migration_v2_final.sql`.

## 13. Qualité
55 tests automatisés du backend (authentification, registres, majoration, nuitées, chapelle, transfert direct, modification, droits, tarifs, finances, récupération, annonces, migration v1→v2, double authentification, modifier/supprimer, installateur protégé) et parcours navigateur (dépôt, entrée directe, modification, levée majorée avec chapelle et versement partiel, statistiques, annonces, mobile).

## 14. Installation automatique
Installation automatique selon l'appareil : `sh INSTALLER.sh` (Android/Termux, Linux, macOS : détecte le système, installe Python, Node et PM2 si absents) ou double-clic sur `INSTALLER.bat` (Windows). Elle prépare les dépendances, une base vide, le compte `admin` / `Admin123!` (changement obligatoire) et impose la double authentification (TOTP) à tous les comptes ; sur une installation existante elle bascule seule en mise à jour sans perte (`--maj`) ; `--maj` pour une mise à jour sans perte. Démarrage : `sh demarrer.sh [reseau|enligne]`, ou PM2 (`ecosystem.config.js`). Voir `GUIDE-INSTALLATION.md`.
