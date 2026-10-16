#!/usr/bin/env python3
"""Met à jour catalogue.json : calcule la taille et l'empreinte SHA-256 de chaque fichier déposé, ainsi que le plan du site.

Usage (depuis le dossier site-outils, à côté du dossier site-web) :
    python maj-catalogue.py                  # dossier du site : ../site-web
    python maj-catalogue.py /chemin/du/site

Ajouter un logiciel : copiez un bloc de « produits » dans site-web/catalogue.json, changez les textes, déposez le fichier
dans site-web/telechargements/fichiers/, indiquez son chemin dans « fichiers », puis relancez ce script.
Valeurs : statut = « disponible » ou « bientot » ; acces = « libre » (téléchargement direct) ou « sur-demande » (bouton « Demander l'accès »).
"""
import hashlib
import json
import os
import sys
from datetime import datetime

site = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "site-web"))
cat_path = os.path.join(site, "catalogue.json")
cat = json.load(open(cat_path, encoding="utf-8"))
LIMITE = 25 * 1024 * 1024  # limite d'un fichier sur Cloudflare Pages


def humain(n):
    return f"{n / 1024 / 1024:.1f} Mo".replace(".", ",") if n >= 1024 * 1024 else f"{max(1, round(n / 1024))} Ko"


problemes = 0
for p in cat["produits"]:
    for f in p.get("fichiers", []):
        if f["fichier"].startswith("http"):
            print(f"  {p['nom']}: fichier hébergé ailleurs ({f['fichier']}) : taille et empreinte à renseigner à la main"); continue
        chemin = os.path.join(site, f["fichier"])
        if not os.path.isfile(chemin):
            print(f"  MANQUANT : {f['fichier']}  ({p['nom']})"); problemes += 1
            continue
        taille = os.path.getsize(chemin)
        h = hashlib.sha256(open(chemin, "rb").read()).hexdigest()
        f["taille"], f["sha256"] = humain(taille), h
        print(f"  {p['nom']}: {os.path.basename(chemin)}  {humain(taille)}  sha256 {h[:16]}…")
        if taille > LIMITE:
            print("  ATTENTION : plus de 25 Mo, Cloudflare Pages refusera ce fichier (utiliser Cloudflare R2 ou GitHub Releases)."); problemes += 1
    for d in p.get("documents", []):
        if not d["fichier"].startswith("http") and not os.path.isfile(os.path.join(site, d["fichier"])):
            print(f"  MANQUANT : {d['fichier']}  ({p['nom']})"); problemes += 1
json.dump(cat, open(cat_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

pages = [""] + [p["page"] for p in cat["produits"] if p.get("page")] + ["telechargements/"]
with open(os.path.join(site, "sitemap.xml"), "w", encoding="utf-8") as fh:
    fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
    for pg in pages:
        fh.write(f"  <url><loc>https://pegintichat.online/{pg}</loc></url>\n")
    fh.write("</urlset>\n")
print("catalogue.json et sitemap.xml mis à jour." + (f"  {problemes} problème(s) à corriger." if problemes else ""))
