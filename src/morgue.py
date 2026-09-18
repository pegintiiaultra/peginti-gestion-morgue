import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3, csv, json, requests
from datetime import datetime
DB_NAME = "database/morgue.db"
API_URL = "http://localhost:3000/api/data"
API_KEY = "PEGINTI_SECRET_2024"
def init_db():
    import os; os.makedirs("database", exist_ok=True)
    with sqlite3.connect(DB_NAME) as conn:
        c=conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS depot (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL, casier TEXT UNIQUE NOT NULL, statut TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS sync_queue (id INTEGER PRIMARY KEY AUTOINCREMENT, data_json TEXT)')
        conn.commit()
def ajouter():
    n=entry_nom.get().strip(); cs=entry_casier.get().strip()
    if not n or not cs: return
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT INTO depot (nom,casier,statut) VALUES (?,?,?)",(n,cs,"EN DÉPÔT")); conn.commit()
        afficher()
    except sqlite3.IntegrityError: messagebox.showerror("Erreur", f"Casier {cs} occupé")
def liberer():
    sel=tree.selection()
    if sel and messagebox.askyesno("Confirmer","Libérer ce casier?"):
        v=tree.item(sel[0])['values']
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("UPDATE depot SET statut='LIBÉRÉ' WHERE id=?",(v[0],)); conn.commit()
        afficher()
def afficher():
    for i in tree.get_children(): tree.delete(i)
    with sqlite3.connect(DB_NAME) as conn:
        for r in conn.execute("SELECT id,nom,casier,statut FROM depot ORDER BY id DESC").fetchall():
            tree.insert("",tk.END,values=r)
init_db(); root=tk.Tk(); root.title("Gestion Service Morgue - PEGINTI Pro"); root.geometry("850x550")
f=tk.Frame(root,pady=10); f.pack(fill=tk.X,padx=10)
tk.Label(f,text="Nom:").pack(side=tk.LEFT); entry_nom=tk.Entry(f,width=25); entry_nom.pack(side=tk.LEFT,padx=5)
tk.Label(f,text="Casier:").pack(side=tk.LEFT); entry_casier=tk.Entry(f,width=10); entry_casier.pack(side=tk.LEFT,padx=5)
tk.Button(f,text="Enregistrer",command=ajouter,bg="#27ae60",fg="white").pack(side=tk.LEFT,padx=10)
ft=tk.Frame(root); ft.pack(fill=tk.BOTH,expand=True,padx=10,pady=10)
tree=ttk.Treeview(ft,columns=("id","nom","casier","statut"),show="headings")
for c,t in [("id","ID"),("nom","NOM"),("casier","CASIER"),("statut","STATUT")]: tree.heading(c,text=t)
tree.pack(fill=tk.BOTH,expand=True)
tk.Button(root,text="LIBÉRER",command=liberer,bg="#2980b9",fg="white").pack(pady=5)
afficher(); root.mainloop()
