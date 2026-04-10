from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import sqlite3, random
from pathlib import Path
from datetime import datetime, timedelta

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "soc_final_v21_3.db"

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute('CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password TEXT, name TEXT, role TEXT, phone TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS shifts (date TEXT, type TEXT, staff TEXT, is_draft INTEGER DEFAULT 1, hours TEXT, PRIMARY KEY (date, type))')
    conn.execute('CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, date TEXT, req_type TEXT, reason TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    
    # עדכון פרטי רז כמנהל מערכת
    conn.execute("INSERT OR REPLACE INTO users VALUES ('razbar@gmail.com','Razbar123#','רז ברהום','Admin','0500000000')")
    
    if not conn.execute("SELECT * FROM settings WHERE key='deadline_day'").fetchone():
        conn.execute("INSERT INTO settings VALUES ('deadline_day', '4'), ('deadline_time', '23:59')")
    conn.commit(); conn.close()

init_db()

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def home(): return Path("index.html").read_text(encoding="utf-8")

@app.post("/api/login")
def login(d: dict):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    u = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (d['email'], d['password'])).fetchone()
    conn.close()
    if u: return {"status": "success", "user": dict(u)}
    raise HTTPException(401)

@app.post("/api/shifts/auto-assign")
def auto(d: dict):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    users = [dict(u) for u in conn.execute("SELECT * FROM users WHERE role != 'Admin'").fetchall()]
    start_dt = datetime.strptime(d['start'], "%Y-%m-%d")
    conn.execute("DELETE FROM shifts WHERE is_draft=1 AND date BETWEEN ? AND ?", (d['start'], d['end']))
    last_night = {}
    for i in range(7):
        dt = (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")
        assigned = []
        blks = {b['email']: b['req_type'] for b in conn.execute("SELECT email, req_type FROM requests WHERE date=?", (dt,)).fetchall()}
        for t in ['בוקר', 'ערב', 'לילה']:
            avail = [u for u in users if f"חסום: {t}" not in blks.get(u['email'], "") and u['name'] not in assigned and (t != 'בוקר' or last_night.get(u['name']) != True)]
            if avail:
                c = random.choice(avail)
                conn.execute("INSERT INTO shifts (date, type, staff, is_draft, hours) VALUES (?,?,?,1,'')", (dt, t, c['name']))
                assigned.append(c['name']); last_night[c['name']] = (t == 'לילה')
            else: last_night[c['name']] = False
    conn.commit(); conn.close(); return {"status": "ok"}

@app.get("/api/shifts")
def get_s():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute("SELECT * FROM shifts").fetchall()]
    conn.close(); return {"shifts": res}

@app.post("/api/shifts/save")
def save_s(s: dict):
    conn = sqlite3.connect(DB)
    dup = conn.execute("SELECT type FROM shifts WHERE date=? AND staff=? AND type != ?", (s['date'], s['staff'], s['type'])).fetchone()
    if dup:
        conn.close(); return {"status": "error", "message": f"העובד כבר משובץ למשמרת {dup[0]}"}
    conn.execute("INSERT OR REPLACE INTO shifts (date, type, staff, is_draft, hours) VALUES (?,?,?,1,?)", (s['date'], s['type'], s['staff'], s.get('hours', '')))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/shifts/publish")
def pub_s(d: dict):
    conn = sqlite3.connect(DB); conn.execute("UPDATE shifts SET is_draft=0 WHERE date BETWEEN ? AND ?", (d['start'], d['end'])); conn.commit(); conn.close(); return {"status": "ok"}

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

@app.get("/api/admin/settings")
def get_sets():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = {r['key']: r['value'] for r in conn.execute("SELECT * FROM settings").fetchall()}
    conn.close(); return res

@app.post("/api/admin/settings")
def save_sets(d: dict):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT OR REPLACE INTO settings VALUES ('deadline_day', ?)", (d['day'],)); conn.execute("INSERT OR REPLACE INTO settings VALUES ('deadline_time', ?)", (d['time'],)); conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/requests")
def add_r(r: dict):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    sets = {row['key']: row['value'] for row in conn.execute("SELECT * FROM settings").fetchall()}
    u = conn.execute("SELECT role FROM users WHERE email=?", (r['email'],)).fetchone()
    if u and u[0] != 'Admin':
        now = datetime.now(); d_day = int(sets['deadline_day']); d_time = datetime.strptime(sets['deadline_time'], "%H:%M").time()
        if now.weekday() > d_day or (now.weekday() == d_day and now.time() > d_time):
            conn.close(); raise HTTPException(status_code=403, detail="הדדליין עבר!")
    conn.execute("INSERT INTO requests (name,email,date,req_type,reason) VALUES (?,?,?,?,?)", (r['name'],r['email'],r['date'],r['req_type'],r['reason'])); conn.commit(); conn.close(); return {"status": "ok"}

@app.get("/api/admin/availability/{date}/{shift_type}")
def get_av(date: str, shift_type: str):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    blks = [r['email'] for r in conn.execute("SELECT email FROM requests WHERE date=? AND req_type=?", (date, f"חסום: {shift_type}")).fetchall()]
    working = [r['staff'] for r in conn.execute("SELECT staff FROM shifts WHERE date=?", (date,)).fetchall()]
    users = [dict(u) for u in conn.execute("SELECT name, email, phone FROM users").fetchall()]
    for u in users: u['is_blocked'] = u['email'] in blks; u['working'] = u['name'] in working
    conn.close(); return users
