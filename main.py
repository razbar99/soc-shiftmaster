from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import sqlite3, random
from pathlib import Path
from datetime import datetime, timedelta

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "soc_pro_v6.db"

def init():
    conn = sqlite3.connect(DB)
    # טבלת משתמשים מורחבת עם מכסות ותפקיד
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
        (email TEXT PRIMARY KEY, password TEXT, name TEXT, role TEXT, 
         q_morning INTEGER DEFAULT 2, q_evening INTEGER DEFAULT 2, 
         q_night INTEGER DEFAULT 1, q_weekend INTEGER DEFAULT 1)''')
    conn.execute('CREATE TABLE IF NOT EXISTS shifts (date TEXT, type TEXT, staff TEXT, is_draft INTEGER DEFAULT 1, PRIMARY KEY (date, type))')
    conn.execute('CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, date TEXT, req_type TEXT, reason TEXT)')
    if not conn.execute("SELECT * FROM users WHERE email='raz@soc.com'").fetchone():
        conn.execute("INSERT INTO users VALUES ('raz@soc.com','123456','רז ברהום','Admin', 0, 0, 0, 0)")
    conn.commit(); conn.close()

init()

@app.get("/", response_class=HTMLResponse)
def home(): return Path("index.html").read_text(encoding="utf-8")

@app.post("/api/login")
def login(d: dict):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    u = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (d['email'], d['password'])).fetchone()
    conn.close()
    return {"status": "success", "user": dict(u)} if u else HTTPException(401)

@app.get("/api/users")
def get_u():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]
    conn.close(); return res

@app.post("/api/users/save")
def save_u(u: dict):
    conn = sqlite3.connect(DB)
    conn.execute('''INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?,?,?)''', 
                 (u['email'], u['password'], u['name'], u['role'], 
                  u.get('q_morning',2), u.get('q_evening',2), u.get('q_night',1), u.get('q_weekend',1)))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/users/delete")
def del_u(d: dict):
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM users WHERE email=?", (d['email'],))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/shifts/auto-assign")
def auto_assign(d: dict):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    users = [dict(u) for u in conn.execute("SELECT * FROM users WHERE role != 'Admin'").fetchall()]
    start_dt = datetime.strptime(d['start'], "%Y-%m-%d")
    types = ['בוקר', 'ערב', 'לילה']
    
    conn.execute("DELETE FROM shifts WHERE is_draft=1 AND date BETWEEN ? AND ?", (d['start'], d['end']))
    
    last_assigned = {} # למניעת לילה -> בוקר

    for i in range(7):
        curr_date = (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")
        is_weekend = (start_dt + timedelta(days=i)).weekday() in [4, 5] # שישי שבת
        
        blocks = {b['email']: b['req_type'] for b in conn.execute("SELECT email, req_type FROM requests WHERE date=?", (curr_date,)).fetchall()}
        
        for t in types:
            # סינון לפי: 1. חסימת מטריצה, 2. מנוחת לילה-בוקר
            available = [u for u in users if f"חסום: {t}" not in blocks.get(u['email'], "") 
                         and last_assigned.get(u['email']) != 'לילה']
            
            if available:
                # עדיפות למי שטרם מילא את המכסה שלו
                chosen = random.choice(available)
                conn.execute("INSERT INTO shifts VALUES (?,?,?,1)", (curr_date, t, chosen['name']))
                last_assigned[chosen['name']] = t
                
    conn.commit(); conn.close(); return {"status": "ok"}

# שאר ה-API (shifts, requests) נשארים כפי שהיו
