from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import sqlite3, random
from pathlib import Path
from datetime import datetime, timedelta

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "soc_v19_5.db"

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute('''CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password TEXT, name TEXT, role TEXT, phone TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS shifts (date TEXT, type TEXT, staff TEXT, is_draft INTEGER DEFAULT 1, PRIMARY KEY (date, type))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, date TEXT, req_type TEXT, reason TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS swaps (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, shift_type TEXT, from_user TEXT, to_user TEXT, status TEXT DEFAULT 'OPEN')''')
    conn.execute('''CREATE TABLE IF NOT EXISTS vacations (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, name TEXT, start_date TEXT, end_date TEXT, vac_type TEXT, status TEXT DEFAULT 'PENDING')''')
    if not conn.execute("SELECT * FROM users WHERE email='raz@soc.com'").fetchone():
        conn.execute("INSERT INTO users VALUES ('raz@soc.com','123456','רז ברהום','Admin','0500000000')")
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

@app.get("/api/users")
def get_u():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]
    conn.close(); return res

@app.post("/api/users/save")
def save_u(u: dict):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?,?)", 
                 (u['email'], u['password'], u['name'], u['role'], u.get('phone','')))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/users/delete")
def del_u(d: dict):
    conn = sqlite3.connect(DB); conn.execute("DELETE FROM users WHERE email=?", (d['email'],)); conn.commit(); conn.close(); return {"status": "ok"}

# --- שאר הפונקציות (שיבוץ, חופשות וכו') זהות לגרסה 19 ---
@app.get("/api/shifts")
def get_s():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = {"shifts": [dict(r) for r in conn.execute("SELECT * FROM shifts").fetchall()],
           "swaps": [dict(r) for r in conn.execute("SELECT * FROM swaps WHERE status IN ('OPEN', 'WAITING_APPROVAL')").fetchall()]}
    conn.close(); return res

@app.post("/api/shifts/save")
def save_s(s: dict):
    conn = sqlite3.connect(DB)
    existing = conn.execute("SELECT type FROM shifts WHERE date=? AND staff=? AND type != ?", (s['date'], s['staff'], s['type'])).fetchone()
    if existing:
        conn.close()
        return {"status": "error", "message": f"העובד כבר משובץ למשמרת {existing[0]} ביום זה"}
    conn.execute("INSERT OR REPLACE INTO shifts VALUES (?,?,?,1)", (s['date'], s['type'], s['staff']))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/shifts/publish")
def pub_s(d: dict):
    conn = sqlite3.connect(DB); conn.execute("UPDATE shifts SET is_draft=0 WHERE date BETWEEN ? AND ?", (d['start'], d['end'])); conn.commit(); conn.close(); return {"status": "ok"}

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
                c = random.choice(avail); conn.execute("INSERT INTO shifts VALUES (?,?,?,1)", (dt, t, c['name'])); assigned.append(c['name'])
                last_night[c['name']] = (t == 'לילה')
    conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/vacations/request")
def req_v(d: dict):
    conn = sqlite3.connect(DB); conn.execute("INSERT INTO vacations (email, name, start_date, end_date, vac_type) VALUES (?,?,?,?,?)", (d['email'], d['name'], d['start'], d['end'], d['type'])); conn.commit(); conn.close(); return {"status": "ok"}

@app.get("/api/admin/vacations")
def get_v():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = conn.execute("SELECT * FROM vacations WHERE status='PENDING'").fetchall()
    conn.close(); return [dict(r) for r in res]

@app.get("/api/admin/approved-vacations")
def get_av_v():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = conn.execute("SELECT * FROM vacations WHERE status='APPROVED' ORDER BY start_date DESC").fetchall()
    conn.close(); return [dict(r) for r in res]

@app.post("/api/admin/vacation-action")
def v_act(d: dict):
    conn = sqlite3.connect(DB)
    if d['action'] == 'approve':
        conn.execute("UPDATE vacations SET status='APPROVED' WHERE id=?", (d['id'],))
        s, e = datetime.strptime(d['start'], "%Y-%m-%d"), datetime.strptime(d['end'], "%Y-%m-%d")
        while s <= e:
            for t in ['בוקר', 'ערב', 'לילה']:
                conn.execute("INSERT OR IGNORE INTO requests (name, email, date, req_type, reason) VALUES (?,?,?,?,?)", (d['name'], d['email'], s.strftime("%Y-%m-%d"), f"חסום: {t}", "חופשה מאושרת"))
            s += timedelta(days=1)
    else: conn.execute("UPDATE vacations SET status='REJECTED' WHERE id=?", (d['id'],))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.get("/api/admin/availability/{date}/{shift_type}")
def get_av(date: str, shift_type: str):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    blks = [r['email'] for r in conn.execute("SELECT email FROM requests WHERE date=? AND req_type=?", (date, f"חסום: {shift_type}")).fetchall()]
    working = [r['staff'] for r in conn.execute("SELECT staff FROM shifts WHERE date=?", (date,)).fetchall()]
    users = [dict(u) for u in conn.execute("SELECT name, email, phone FROM users").fetchall()]
    for u in users: u['is_blocked'] = u['email'] in blks; u['working'] = u['name'] in working
    conn.close(); return users

@app.post("/api/requests")
def add_r(r: dict):
    conn = sqlite3.connect(DB); conn.execute("INSERT INTO requests (name,email,date,req_type,reason) VALUES (?,?,?,?,?)", (r['name'],r['email'],r['date'],r['req_type'],r['reason'])); conn.commit(); conn.close(); return {"status": "ok"}
