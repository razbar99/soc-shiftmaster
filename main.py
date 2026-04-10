from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import sqlite3, random
from pathlib import Path
from datetime import datetime, timedelta

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "soc_v21.db"

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute('CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password TEXT, name TEXT, role TEXT, phone TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS shifts (date TEXT, type TEXT, staff TEXT, is_draft INTEGER DEFAULT 1, hours TEXT, PRIMARY KEY (date, type))')
    conn.execute('CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, date TEXT, req_type TEXT, reason TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS swaps (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, shift_type TEXT, from_user TEXT, to_user TEXT, status TEXT DEFAULT "OPEN")')
    conn.execute('CREATE TABLE IF NOT EXISTS vacations (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, name TEXT, start_date TEXT, end_date TEXT, vac_type TEXT, status TEXT DEFAULT "PENDING")')
    # טבלת הגדרות חדשה
    conn.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    
    if not conn.execute("SELECT * FROM users WHERE email='raz@soc.com'").fetchone():
        conn.execute("INSERT INTO users VALUES ('raz@soc.com','123456','רז ברהום','Admin','0500000000')")
    
    # הגדרת דדליין ברירת מחדל (יום חמישי, 23:59)
    if not conn.execute("SELECT * FROM settings WHERE key='deadline_day'").fetchone():
        conn.execute("INSERT INTO settings VALUES ('deadline_day', '4')") # 4 = Thursday
        conn.execute("INSERT INTO settings VALUES ('deadline_time', '23:59')")
        
    conn.commit(); conn.close()

init_db()

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def home(): return Path("index.html").read_text(encoding="utf-8")

# --- הגדרות מנהל ---
@app.get("/api/admin/settings")
def get_settings():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = {r['key']: r['value'] for r in conn.execute("SELECT * FROM settings").fetchall()}
    conn.close(); return res

@app.post("/api/admin/settings")
def save_settings(d: dict):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT OR REPLACE INTO settings VALUES ('deadline_day', ?)", (d['day'],))
    conn.execute("INSERT OR REPLACE INTO settings VALUES ('deadline_time', ?)", (d['time'],))
    conn.commit(); conn.close(); return {"status": "ok"}

# --- בדיקת דדליין לפני שמירת זמינות ---
@app.post("/api/requests")
def add_r(r: dict):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    sets = {row['key']: row['value'] for row in conn.execute("SELECT * FROM settings").fetchall()}
    
    # בדיקה האם המשתמש הוא אדמין (אדמין תמיד יכול לעקוף)
    is_admin = conn.execute("SELECT role FROM users WHERE email=?", (r['email'],)).fetchone()
    
    if is_admin and is_admin[0] != 'Admin':
        now = datetime.now()
        deadline_day = int(sets['deadline_day'])
        deadline_time = datetime.strptime(sets['deadline_time'], "%H:%M").time()
        
        # אם היום הנוכחי גדול מהדדליין, או אותו יום אבל אחרי השעה
        if now.weekday() > deadline_day or (now.weekday() == deadline_day and now.time() > deadline_time):
            conn.close()
            raise HTTPException(status_code=403, detail="הדדליין להגשת זמינות עבר. פנה למנהל.")

    conn.execute("INSERT INTO requests (name,email,date,req_type,reason) VALUES (?,?,?,?,?)", 
                 (r['name'],r['email'],r['date'],r['req_type'],r['reason']))
    conn.commit(); conn.close(); return {"status": "ok"}

# שאר הפונקציות (login, shifts, users) נשארות כפי שהיו
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
