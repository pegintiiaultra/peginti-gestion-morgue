// Plateforme TOMTECH : affiche le catalogue (catalogue.json). Aucun innerHTML : tout passe par textContent.
(function () {
  "use strict";
  var racine = document.body.getAttribute("data-racine") || "";
  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  function lien(cls, txt, href, dl) { var a = el("a", cls, txt); a.href = href; if (dl) a.setAttribute("download", ""); return a; }
  function mail(cat, sujet) { return "mailto:" + cat.contact + "?subject=" + encodeURIComponent(sujet); }
  function url(f) { return /^https?:/.test(f) ? f : racine + f; }
  function dateFr(iso) { if (!iso) return ""; var d = new Date(iso + "T00:00:00"); return isNaN(d) ? iso : d.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" }); }

  function actionPrincipale(p, cat, vers) {
    if (p.statut !== "disponible") return lien("btn btn-line", "Être prévenu de la sortie", mail(cat, "Être prévenu : " + p.nom));
    var f = (p.fichiers || []).filter(function (x) { return x.principal; })[0] || (p.fichiers || [])[0];
    if (p.acces === "sur-demande" || !f) return lien("btn btn-navy", "Demander l'accès", mail(cat, "Demande d'accès : " + p.nom));
    return lien("btn btn-amber", "Télécharger" + (f.taille ? " (" + f.taille + ")" : ""), url(f.fichier), true);
  }

  function carte(p, cat) {
    var c = el("article", "pcard" + (p.statut === "disponible" ? "" : " pcard-soon"));
    var tete = el("div", "pcard-head");
    tete.appendChild(el("h3", null, p.nom));
    tete.appendChild(el("span", "tag " + (p.statut === "disponible" ? "tag-ok" : "tag-soon"), p.statut === "disponible" ? "Disponible" : "Bientôt"));
    c.appendChild(tete);
    c.appendChild(el("p", "pcard-slogan", p.slogan));
    c.appendChild(el("p", "pcard-desc", p.description));
    if ((p.plateformes || []).length) c.appendChild(el("p", "small muted", "Pour : " + p.plateformes.join(" · ")));
    var act = el("div", "cta-row");
    act.appendChild(actionPrincipale(p, cat));
    if (p.page) act.appendChild(lien("btn btn-line", "Découvrir", racine + p.page));
    if (p.statut === "disponible") act.appendChild(lien("link-plain", "Détails du téléchargement", racine + "telechargements/#" + p.id));
    c.appendChild(act);
    return c;
  }

  function copier(texte, btn) {
    var fin = function () { var t = btn.textContent; btn.textContent = "Copié"; setTimeout(function () { btn.textContent = t; }, 1600); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(texte).then(fin, function () {});
  }

  function fiche(p, cat) {
    var s = el("section", "dl"); s.id = p.id;
    var tete = el("div", "dl-head");
    var t = el("div"); t.appendChild(el("h2", null, p.nom)); t.appendChild(el("p", "sec-lead", p.slogan));
    tete.appendChild(t);
    tete.appendChild(el("span", "tag " + (p.statut === "disponible" ? "tag-ok" : "tag-soon"), p.statut === "disponible" ? "Disponible" : "Bientôt disponible"));
    s.appendChild(tete);
    if (p.statut !== "disponible") { s.appendChild(el("p", null, p.description)); var a = el("div", "cta-row"); a.appendChild(actionPrincipale(p, cat)); s.appendChild(a); return s; }

    var meta = el("p", "small muted", ["Version " + p.version, p.date ? "mise à jour le " + dateFr(p.date) : "", (p.plateformes || []).join(" · ")].filter(Boolean).join(" · "));
    s.appendChild(meta);
    (p.fichiers || []).forEach(function (f) {
      var box = el("div", "dl-box");
      var gauche = el("div"); gauche.appendChild(el("b", null, f.libelle));
      gauche.appendChild(el("div", "small muted mono", f.fichier.split("/").pop() + (f.taille ? " · " + f.taille : "")));
      box.appendChild(gauche);
      if (p.acces === "sur-demande") box.appendChild(lien("btn btn-navy", "Demander l'accès", mail(cat, "Demande d'accès : " + p.nom)));
      else box.appendChild(lien("btn btn-amber", "Télécharger", url(f.fichier), true));
      s.appendChild(box);
      if (f.sha256 && p.acces !== "sur-demande") {
        var v = el("div", "sha"); v.appendChild(el("span", "small muted", "Empreinte SHA-256 (pour vérifier le fichier) :"));
        var code = el("code", "mono", f.sha256); v.appendChild(code);
        var b = el("button", "copy", "Copier"); b.type = "button"; b.addEventListener("click", function () { copier(f.sha256, b); }); v.appendChild(b);
        s.appendChild(v);
      }
    });
    if ((p.documents || []).length) {
      var d = el("div", "docs"); d.appendChild(el("b", null, "Documentation"));
      var ul = el("ul"); p.documents.forEach(function (x) { var li = el("li"); li.appendChild(lien("", x.libelle, url(x.fichier))); ul.appendChild(li); });
      d.appendChild(ul); s.appendChild(d);
    }
    if ((p.installation || []).length) {
      var det = el("details", "inst"); det.appendChild(el("summary", null, "Comment l'installer"));
      var ol = el("ol"); p.installation.forEach(function (x) { ol.appendChild(el("li", null, x)); });
      det.appendChild(ol); s.appendChild(det);
    }
    if (p.page) { var pl = el("p"); pl.appendChild(lien("link-plain", "Présentation complète de " + p.nom, racine + p.page)); s.appendChild(pl); }
    return s;
  }

  fetch(racine + "catalogue.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(function (cat) {
    var g = document.getElementById("catalogue");
    if (g) { g.textContent = ""; cat.produits.forEach(function (p) { g.appendChild(carte(p, cat)); }); }
    var l = document.getElementById("liste-telechargements");
    if (l) {
      l.textContent = "";
      cat.produits.forEach(function (p) { l.appendChild(fiche(p, cat)); });
      if (location.hash) { var cible = document.getElementById(location.hash.slice(1)); if (cible) cible.scrollIntoView(); }
    }
  }).catch(function () {
    var z = document.getElementById("catalogue") || document.getElementById("liste-telechargements");
    if (z) z.textContent = "Le catalogue n'a pas pu être chargé. Réessayez dans un instant ou écrivez-nous.";
  });
})();
