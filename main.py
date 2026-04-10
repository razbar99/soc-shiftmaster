from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import sqlite3, random
from pathlib import Path
from datetime import datetime, timedelta

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "soc_v20.db"

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute('''CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password TEXT, name TEXT, role TEXT, phone TEXT)''')
    # הוספת עמודת hours לטבלה
    conn.execute('''CREATE TABLE IF NOT EXISTS shifts 
        (date TEXT, type TEXT, staff TEXT, is_draft INTEGER DEFAULT 1, hours TEXT, PRIMARY KEY (date, type))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, date TEXT, req_type TEXT, reason TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS swaps (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, shift_type TEXT, from_user TEXT, to_user TEXT, status TEXT DEFAULT 'OPEN')''')
    conn.execute('''CREATE TABLE IF NOT EXISTS vacations (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, name TEXT, start_date TEXT, end_date TEXT, vac_type TEXT, status TEXT DEFAULT 'PENDING')''')
    if not conn.execute("SELECT * FROM users WHERE email='raz@soc.com'").fetchone():
        conn.execute("INSERT INTO users VALUES ('raz@soc.com','123456','רז ברהום','Admin','0500000000')")
    conn.commit(); conn.close()

init_db()

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def home(): return Path("index.html").read_text(encoding="utf-8")

@app.post("/api/shifts/save")
def save_s(s: dict):
    conn = sqlite3.connect(DB)
    # בדיקת כפילות
    existing = conn.execute("SELECT type FROM shifts WHERE date=? AND staff=? AND type != ?", (s['date'], s['staff'], s['type'])).fetchone()
    if existing:
        conn.close()
        return {"status": "error", "message": f"העובד כבר משובץ למשמרת {existing[0]} ביום זה"}
    
    # שמירה כולל שעות
    conn.execute("INSERT OR REPLACE INTO shifts (date, type, staff, is_draft, hours) VALUES (?,?,?,1,?)", 
                 (s['date'], s['type'], s['staff'], s.get('hours', '')))
    conn.commit(); conn.close(); return {"status": "ok"}

# שאר הפונקציות (login, get_s, get_u, auto-assign) נשארות כפי שהיו ב-v19.5
@app.post("/api/login")
def login(d: dict):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    u = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (d['email'], d['password'])).fetchone()
    conn.close()
    if u: return {"status": "success", "user": dict(u)}
    raise HTTPException(401)

@app.get("/api/shifts")
def get_s():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = {"shifts": [dict(r) for r in conn.execute("SELECT * FROM shifts").fetchall()],
           "swaps": [dict(r) for r in conn.execute("SELECT * FROM swaps WHERE status IN ('OPEN', 'WAITING_APPROVAL')").fetchall()]}
    conn.close(); return res

@app.get("/api/users")
def get_u():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]
    conn.close(); return res

@app.post("/api/users/save")
def save_u(u: dict):
    conn = sqlite3.connect(DB); conn.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?,?)", (u['email'], u['password'], u['name'], u['role'], u.get('phone',''))); conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/users/delete")
def del_u(d: dict):
    conn = sqlite3.connect(DB); conn.execute("DELETE FROM users WHERE email=?", (d['email'],)); conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/shifts/publish")
def pub_s(d: dict):
    conn = sqlite3.connect(DB); conn.execute("UPDATE shifts SET is_draft=0 WHERE date BETWEEN ? AND ?", (d['start'], d['end'])); conn.commit(); conn.close(); return {"status": "ok"}
