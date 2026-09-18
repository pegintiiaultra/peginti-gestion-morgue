import sqlite3, requests
from datetime import datetime
from flask import Flask, request, redirect

DB="morgue.db"
API="http://localhost:3001/api/data"
KEY="PEGINTI_SECRET_2024"

conn=sqlite3.connect(DB)
conn.execute("CREATE TABLE IF NOT EXISTS depot (id INTEGER PRIMARY KEY, nom TEXT, casier TEXT, statut TEXT, date_entree TEXT)")
conn.commit(); conn.close()

app=Flask(__name__)

@app.route("/")
def index():
    conn=sqlite3.connect(DB)
    rows=conn.execute("SELECT nom,casier FROM depot").fetchall()
    conn.close()
    txt="<h2>Morgue v4.0 - Port 3001 OK</h2>"
    for r in rows: txt+=f"<p>{r[1]} - {r[0]}</p>"
    txt+="<form method=post action=/add><input name=nom placeholder=Nom><input name=casier placeholder=Casier><button>Add</button></form>"
    return txt

@app.route("/add",methods=["POST"])
def add():
    conn=sqlite3.connect(DB)
    conn.execute("INSERT INTO depot (nom,casier,statut,date_entree) VALUES (?,?,?,?)",(request.form["nom"],request.form["casier"],"OCCUPE",datetime.now().isoformat()))
    conn.commit(); conn.close()
    return redirect("/")

app.run(host="0.0.0.0",port=5000)
