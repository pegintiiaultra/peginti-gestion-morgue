// Coordonnées : modifier ici, rien d'autre à changer dans la page.
var CONTACT = { email: "contact@pegintichat.online", tel: "" };

(function () {
  var $ = function (id) { return document.getElementById(id); };
  if ($("email-txt")) $("email-txt").textContent = CONTACT.email;
  if ($("an")) $("an").textContent = new Date().getFullYear();
  if (CONTACT.tel && $("tel-txt")) { $("tel-txt").textContent = CONTACT.tel; $("tel-line").hidden = false; }
  if (!$("contact-form")) return;

  $("copy-email").addEventListener("click", function () {
    var btn = this;
    var done = function () { btn.textContent = "Copié"; setTimeout(function () { btn.textContent = "Copier"; }, 1800); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(CONTACT.email).then(done, function () {});
  });

  $("contact-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var f = e.target, v = function (n) { return f.elements[n].value.trim(); };
    if (!v("nom")) { f.elements.nom.focus(); $("form-note").textContent = "Indiquez votre nom pour préparer le message."; return; }
    var lines = ["Bonjour,", "", "Je souhaite une démonstration de PEGINTI Morgue.", "",
      "Nom : " + v("nom"), "Établissement : " + (v("etab") || "-"), "Ville : " + (v("ville") || "-"),
      "Déploiement envisagé : " + v("modele"), "", v("msg")];
    location.href = "mailto:" + CONTACT.email + "?subject=" + encodeURIComponent("Demande de démonstration PEGINTI Morgue") +
      "&body=" + encodeURIComponent(lines.join("\n"));
  });
})();
