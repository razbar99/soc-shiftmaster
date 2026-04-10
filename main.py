from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import sqlite3, csv, io, random
from pathlib import Path
from datetime import datetime, timedelta

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "soc_v9_1.db"

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
        (email TEXT PRIMARY KEY, password TEXT, name TEXT, role TEXT, phone TEXT,
         q_m INTEGER DEFAULT 2, q_e INTEGER DEFAULT 2, q_n INTEGER DEFAULT 1, q_w INTEGER DEFAULT 1)''')
    conn.execute('CREATE TABLE IF NOT EXISTS shifts (date TEXT, type TEXT, staff TEXT, is_draft INTEGER DEFAULT 1, PRIMARY KEY (date, type))')
    conn.execute('CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, date TEXT, req_type TEXT, reason TEXT)')
    if not conn.execute("SELECT * FROM users WHERE email='raz@soc.com'").fetchone():
        conn.execute("INSERT INTO users VALUES ('raz@soc.com','123456','רז ברהום','Admin','0500000000',0,0,0,0)")
    conn.commit(); conn.close()

init_db()

# תיקון השגיאה 405 Method Not Allowed
@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
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
def get_u():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]
    conn.close(); return res

@app.post("/api/users/save")
def save_u(u: dict):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?,?,?,?)", 
                 (u['email'], u['password'], u['name'], u['role'], u.get('phone',''),
                  u.get('q_m',2), u.get('q_e',2), u.get('q_n',1), u.get('q_w',1)))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/users/delete")
def del_u(d: dict):
    conn = sqlite3.connect(DB); conn.execute("DELETE FROM users WHERE email=?", (d['email'],)); conn.commit(); conn.close(); return {"status": "ok"}

@app.get("/api/shifts")
def get_s():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute("SELECT * FROM shifts").fetchall()]
    conn.close(); return res

@app.post("/api/shifts/save")
def save_s(s: dict):
    conn = sqlite3.connect(DB); conn.execute("INSERT OR REPLACE INTO shifts VALUES (?,?,?,1)", (s['date'], s['type'], s['staff'])); conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/shifts/publish")
def pub_s(d: dict):
    conn = sqlite3.connect(DB); conn.execute("UPDATE shifts SET is_draft=0 WHERE date BETWEEN ? AND ?", (d['start'], d['end'])); conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/shifts/auto-assign")
def auto(d: dict):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    users = [dict(u) for u in conn.execute("SELECT * FROM users WHERE role != 'Admin'").fetchall()]
    start_dt = datetime.strptime(d['start'], "%Y-%m-%d")
    conn.execute("DELETE FROM shifts WHERE is_draft=1 AND date BETWEEN ? AND ?", (d['start'], d['end']))
    last = {}
    for i in range(7):
        dt = (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")
        blks = {b['email']: b['req_type'] for b in conn.execute("SELECT email, req_type FROM requests WHERE date=?", (dt,)).fetchall()}
        for t in ['בוקר', 'ערב', 'לילה']:
            avail = [u for u in users if f"חסום: {t}" not in blks.get(u['email'], "") and last.get(u['name']) != 'לילה']
            if avail:
                c = random.choice(avail)
                conn.execute("INSERT INTO shifts VALUES (?,?,?,1)", (dt, t, c['name']))
                last[c['name']] = t
    conn.commit(); conn.close(); return {"status": "ok"}

@app.get("/api/admin/availability/{date}")
def get_av(date: str):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    blks = {r['email']: r['req_type'] for r in conn.execute("SELECT email, req_type FROM requests WHERE date=?", (date,)).fetchall()}
    users = [dict(u) for u in conn.execute("SELECT name, email, phone FROM users").fetchall()]
    for u in users:
        u['is_blocked'] = u['email'] in blks
        u['reason'] = blks.get(u['email'], "")
    conn.close(); return users

@app.post("/api/requests")
def add_r(r: dict):
    conn = sqlite3.connect(DB); conn.execute("INSERT INTO requests (name,email,date,req_type,reason) VALUES (?,?,?,?,?)", (r['name'],r['email'],r['date'],r['req_type'],r['reason'])); conn.commit(); conn.close(); return {"status": "ok"}
