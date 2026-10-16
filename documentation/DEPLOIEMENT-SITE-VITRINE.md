# Plateforme pegintichat.online — mise en ligne et gestion

Site statique (aucun serveur à gérer) : accueil de la gamme PEGINTI, page de chaque logiciel, **page de téléchargements**. Tout le catalogue vient d'un seul fichier, `catalogue.json`.

```
site-web/
  index.html                  accueil : liste des logiciels (cartes)
  morgue/index.html           présentation de PEGINTI Morgue
  telechargements/index.html  fichiers, empreintes SHA-256, guides, étapes d'installation
  telechargements/fichiers/   les fichiers à télécharger (zip, PDF)
  catalogue.json              la liste des logiciels (à modifier pour en ajouter)
site-outils/maj-catalogue.py  calcule tailles et empreintes, régénère sitemap.xml
```

## 1. Publier (Cloudflare Pages, gratuit)
1. Cloudflare → **Workers & Pages** → **Create** → **Pages** → **Upload assets**, projet `pegintichat`.
2. Glissez le **contenu** du dossier `site-web/` (pas le dossier lui-même ; `index.html` à la racine) → **Deploy**.
3. **Custom domains** → `pegintichat.online`. L'application reste sur `morgue.pegintichat.online` (tunnel inchangé).
Limite : **25 Mo par fichier** sur Cloudflare Pages. Au-delà (futur PEGINTI IA volumineux), hébergez le fichier sur Cloudflare R2 ou GitHub Releases et mettez son adresse complète (`https://…`) dans `fichier` — l'adresse est utilisée telle quelle si elle commence par `http`.

## 2. Mettre à jour une nouvelle version d'un logiciel
1. Déposez le nouveau fichier dans `site-web/telechargements/fichiers/` (même nom ou nouveau nom).
2. Dans `catalogue.json`, changez `version`, `date` et, si le nom a changé, `fichier`.
3. Lancez `python site-outils/maj-catalogue.py` : tailles, empreintes SHA-256 et plan du site sont recalculés.
4. Redéployez le dossier `site-web/` sur Cloudflare Pages (**Create deployment**).

## 3. Ajouter un logiciel (PEGINTI IA, etc.)
Copiez un bloc de la liste `produits` dans `catalogue.json` et adaptez-le :
- `statut` : `disponible` (téléchargeable) ou `bientot` (affiche « Bientôt », bouton « Être prévenu »).
- `acces` : `libre` (téléchargement direct) ou `sur-demande` (bouton « Demander l'accès » qui écrit à `contact@pegintichat.online`, **le fichier n'est alors pas à publier**).
- `page` : dossier de la page de présentation (ex. `ia/`) ; laissez `""` s'il n'y en a pas encore.
- `fichiers`, `documents`, `installation` : voir le bloc de PEGINTI Morgue.
Puis `python site-outils/maj-catalogue.py` et redéployez. PEGINTI IA est déjà dans le catalogue avec le statut `bientot` : le jour de sa sortie, passez `statut` à `disponible`, ajoutez le fichier et son guide.

## 4. À décider avant de communiquer
- **Téléchargement libre = logiciel complet utilisable par tout le monde sans licence ni contrôle.** Pour garder la vente et l'installation par TOMTECH.INC, mettez `"acces": "sur-demande"` (un seul mot) et ne déposez pas le zip sur le site : remettez-le au client après accord. Un fichier publié sur Internet ne peut plus être retiré des copies déjà téléchargées.
- Ajoutez dans le pied de page vos mentions légales (raison sociale, adresse, immatriculation) si votre activité l'exige, et vos conditions d'utilisation.

## 5. E-mail de contact
Les boutons « Demander l'accès » et « Être prévenu » ouvrent un e-mail vers `contact@pegintichat.online` (modifiable dans `catalogue.json`, champ `contact`, et en haut de `site.js`). Pour la faire exister gratuitement : Cloudflare → domaine → **Email** → **Email Routing**.

## 6. Vérifier un téléchargement
Chaque fichier affiche son empreinte SHA-256. Windows : `certutil -hashfile fichier.zip SHA256` ; Termux/Linux : `sha256sum fichier.zip`.
