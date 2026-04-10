from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import sqlite3, csv, io, random
from pathlib import Path
from datetime import datetime, timedelta

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "soc_ultimate_v8.db"

def init_db():
    conn = sqlite3.connect(DB)
    # טבלת משתמשים כולל טלפון, תפקיד ומכסות
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
        (email TEXT PRIMARY KEY, password TEXT, name TEXT, role TEXT, phone TEXT,
         q_m INTEGER DEFAULT 2, q_e INTEGER DEFAULT 2, 
         q_n INTEGER DEFAULT 1, q_w INTEGER DEFAULT 1)''')
    # טבלת משמרות
    conn.execute('CREATE TABLE IF NOT EXISTS shifts (date TEXT, type TEXT, staff TEXT, is_draft INTEGER DEFAULT 1, PRIMARY KEY (date, type))')
    # טבלת בקשות/חסימות מהמטריצה
    conn.execute('CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, date TEXT, req_type TEXT, reason TEXT)')
    # טבלת חפיפות
    conn.execute('CREATE TABLE IF NOT EXISTS handovers (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, author TEXT, content TEXT, timestamp TEXT)')
    
    # יצירת מנהל על (רז) אם לא קיים
    if not conn.execute("SELECT * FROM users WHERE email='raz@soc.com'").fetchone():
        conn.execute("INSERT INTO users VALUES ('raz@soc.com','123456','רז ברהום','Admin','0501234567',0,0,0,0)")
    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
def home():
    return Path("index.html").read_text(encoding="utf-8")

@app.post("/api/login")
def login(d: dict):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    u = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (d['email'], d['password'])).fetchone()
    conn.close()
    if u: return {"status": "success", "user": dict(u)}
    raise HTTPException(401)

@app.get("/api/users")
def get_users():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]
    conn.close(); return res

@app.post("/api/users/save")
def save_user(u: dict):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?,?,?,?)", 
                 (u['email'], u['password'], u['name'], u['role'], u.get('phone',''),
                  u.get('q_m',2), u.get('q_e',2), u.get('q_n',1), u.get('q_w',1)))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/users/delete")
def delete_user(d: dict):
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM users WHERE email=?", (d['email'],))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.get("/api/shifts")
def get_shifts():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute("SELECT * FROM shifts").fetchall()]
    conn.close(); return res

@app.post("/api/shifts/save")
def save_shift(s: dict):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT OR REPLACE INTO shifts VALUES (?,?,?,1)", (s['date'], s['type'], s['staff']))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/shifts/publish")
def publish_shifts(d: dict):
    conn = sqlite3.connect(DB)
    conn.execute("UPDATE shifts SET is_draft=0 WHERE date BETWEEN ? AND ?", (d['start'], d['end']))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/shifts/auto-assign")
def auto_assign(d: dict):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    users = [dict(u) for u in conn.execute("SELECT * FROM users WHERE role != 'Admin'").fetchall()]
