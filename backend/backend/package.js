// Configuration du projet PEGINTI Gestion Morgue
// Ce fichier exporte les métadonnées et dépendances

export default {
  name: "peginti-gestion-morgue",
  version: "1.0.0",
  type: "module",
  main: "server.js",
  scripts: {
    start: "node backend/server.js",
    dev: "nodemon backend/server.js"
  },
  dependencies: {
    express: "^4.19.2",
    cors: "^2.8.5",
    helmet: "^7.0.0",
    sql.js: "^1.9.0",
    jsonwebtoken: "^9.0.2"
  }
};
