import express from "express";
import jwt from "jsonwebtoken";
import initSqlJs from "sql.js";
import fs from "fs";

const app = express();
app.use(express.json());

let db;
const DB_PATH = "morgue.db";
const SECRET = "PEGINTI_SECRET_2026";

function saveDb(){ fs.writeFileSync(DB_PATH, Buffer.from(db.export())); }

async function initDB(){
  const SQL = await initSqlJs();
  db = fs.existsSync(DB_PATH)? new SQL.Database(fs.readFileSync(DB_PATH)) : new SQL.Database();
  // Recréation propre
  db.exec(`DROP TABLE IF EXISTS depot; DROP TABLE IF EXISTS transfert; DROP TABLE IF EXISTS sortie;`);
  db.run(`CREATE TABLE depot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_depot TEXT UNIQUE,
    nom_defunt TEXT,
    casier TEXT UNIQUE,
    date_entree TEXT,
    provenance TEXT,
    motif TEXT,
    statut TEXT
  );`);
  db.run(`CREATE TABLE transfert (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_transfert TEXT UNIQUE,
    nom_defunt TEXT,
    date_transfert TEXT,
    provenance TEXT,
    destination TEXT,
    motif TEXT,
    statut TEXT
  );`);
  db.run(`CREATE TABLE sortie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_sortie TEXT UNIQUE,
    nom_defunt TEXT,
    date_sortie TEXT,
    provenance TEXT,
    motif TEXT,
    statut TEXT
  );`);
  saveDb();
  console.log("DB recréée PROPRE ✅");
}

// --- Middleware JWT ---
function auth(req,res,next){
  const h = req.headers.authorization;
  if(!h) return res.status(401).json({error:"Token manquant"});
  const token = h.split(" ")[1];
  try{ jwt.verify(token, SECRET); next(); }catch{ return res.status(401).json({error:"Token invalide"}); }
}

// Helper pour transformer exec en JSON
function toJson(execResult){
  if(!execResult.length) return [];
  const cols = execResult[0].columns;
  return execResult[0].values.map(v=>{ let o={}; cols.forEach((c,i)=>o[c]=v[i]); return o; });
}

// --- Routes ---
app.post("/api/login", (req,res)=>{
  const {username,password}=req.body;
  if(username==="peginti" && password==="secret"){
    return res.json({token: jwt.sign({username}, SECRET, {expiresIn:"1h"})});
  }
  res.status(401).json({error:"Identifiants invalides"});
});

// Dépôt
app.post("/api/depot", auth, (req,res)=>{
  try{
    const {numero_depot,nom_defunt,casier,date_entree,provenance,motif}=req.body;
    db.run("INSERT INTO depot (numero_depot,nom_defunt,casier,date_entree,provenance,motif,statut) VALUES (?,?,?,?,?,?,?)",
      [numero_depot,nom_defunt,casier,date_entree,provenance,motif,"EN_DEPOT"]);
    saveDb();
    res.json({message:"Corps admis en dépôt"});
  }catch(e){
    if(e.message.includes("UNIQUE")) return res.status(409).json({error:"Doublon: numéro ou casier déjà occupé"});
    res.status(500).json({error:e.message});
  }
});

// Transfert
app.post("/api/transfert", auth, (req,res)=>{
  try{
    const {numero_transfert,nom_defunt,date_transfert,provenance,destination,motif}=req.body;
    db.run("INSERT INTO transfert VALUES (NULL,?,?,?,?,?,?,?)",
      [numero_transfert,nom_defunt,date_transfert,provenance,destination,motif,"TRANSFERT_EFFECTUE"]);
    saveDb(); res.json({message:"Transfert enregistré"});
  }catch(e){ res.status(409).json({error:e.message}); }
});

// Sortie
app.post("/api/sortie", auth, (req,res)=>{
  try{
    const {numero_sortie,nom_defunt,date_sortie,provenance,motif}=req.body;
    db.run("INSERT INTO sortie VALUES (NULL,?,?,?,?,?,?)",
      [numero_sortie,nom_defunt,date_sortie,provenance,motif,"SORTIE_EFFECTUEE"]);
    db.run("DELETE FROM depot WHERE nom_defunt =?",[nom_defunt]); // libère casier
    saveDb(); res.json({message:"Sortie enregistrée, casier libéré"});
  }catch(e){ res.status(409).json({error:e.message}); }
});

// Liste des dépôts
app.get("/api/depot", auth, (req,res)=>{
  res.json(toJson(db.exec("SELECT * FROM depot ORDER BY id DESC")));
});

// Liste des casiers
app.get("/api/casiers", auth, (req,res)=>{
  const all = Array.from({length:20},(_,i)=>`C${String(i+1).padStart(2,'0')}`);
  const occ = toJson(db.exec("SELECT casier,nom_defunt,numero_depot FROM depot"));
  const map = Object.fromEntries(occ.map(o=>[o.casier,o]));
  res.json(all.map(c=>({casier:c, occupe:!!map[c],...map[c]})));
});

// Statistiques
app.get("/api/statistiques", auth, (req,res)=>{
  const cnt=t=>{ const r=db.exec(`SELECT COUNT(*) as c FROM ${t}`); return r[0]?r[0].values[0][0]:0; };
  res.json({
    total_entrees:cnt("depot"),
    total_transferts:cnt("transfert"),
    total_sorties:cnt("sortie"),
    corps_restants:cnt("depot"),
    casiers_occupes:cnt("depot"),
    casiers_libres:20-cnt("depot")
  });
});

app.get("/", (req,res)=>res.send("PEGINTI Morgue API en ligne ✅"));

initDB().then(()=>app.listen(3001,()=>console.log("Serveur démarré sécurisé")));
