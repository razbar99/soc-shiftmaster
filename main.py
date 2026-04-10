import os, psycopg2, sqlite3, random
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pathlib import Path
from datetime import datetime, timedelta

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if DATABASE_URL: return psycopg2.connect(DATABASE_URL, sslmode='require')
    conn = sqlite3.connect("soc_master_final.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password TEXT, name TEXT, role TEXT, phone TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS shifts (date TEXT, type TEXT, staff TEXT, is_draft INTEGER DEFAULT 1, hours TEXT, PRIMARY KEY (date, type))')
    cur.execute('CREATE TABLE IF NOT EXISTS requests (id SERIAL PRIMARY KEY, name TEXT, email TEXT, date TEXT, req_type TEXT, reason TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS vacations (id SERIAL PRIMARY KEY, email TEXT, name TEXT, start_date TEXT, end_date TEXT, vac_type TEXT, status TEXT DEFAULT "PENDING")')
    cur.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    
    # משתמש מנהל (רז)
    cur.execute("INSERT INTO users VALUES (%s,%s,%s,%s,%s) ON CONFLICT (email) DO NOTHING", 
                ('razbar@gmail.com', 'Razbar123#', 'רז ברהום', 'Admin', '0500000000'))
    
    # הגדרות דדליין (חמישי ב-23:59)
    cur.execute("INSERT INTO settings VALUES ('deadline_day', '4') ON CONFLICT (key) DO NOTHING")
    cur.execute("INSERT INTO settings VALUES ('deadline_time', '23:59') ON CONFLICT (key) DO NOTHING")
    
    conn.commit(); cur.close(); conn.close()

init_db()

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def home(): return Path("index.html").read_text(encoding="utf-8")

@app.post("/api/login")
def login(d: dict):
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=RealDictCursor) if DATABASE_URL else conn.cursor()
    q = "SELECT * FROM users WHERE email=%s AND password=%s" if DATABASE_URL else "SELECT * FROM users WHERE email=? AND password=?"
    cur.execute(q, (d['email'], d['password'])); u = cur.fetchone(); conn.close()
    if u: return {"status": "success", "user": dict(u)}
    raise HTTPException(401)

@app.get("/api/shifts")
def get_s():
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=RealDictCursor) if DATABASE_URL else conn.cursor()
    cur.execute("SELECT * FROM shifts"); res = [dict(r) for r in cur.fetchall()]; conn.close()
    return {"shifts": res}

@app.post("/api/shifts/save")
def save_s(s: dict):
    conn = get_db_connection(); cur = conn.cursor()
    q = "INSERT INTO shifts (date, type, staff, is_draft, hours) VALUES (%s,%s,%s,1,%s) ON CONFLICT (date, type) DO UPDATE SET staff=EXCLUDED.staff, hours=EXCLUDED.hours" if DATABASE_URL else "INSERT OR REPLACE INTO shifts VALUES (?,?,?,1,?)"
    cur.execute(q, (s['date'], s['type'], s['staff'], s.get('hours', '')))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/shifts/auto-assign-preview")
def auto_preview(d: dict):
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=RealDictCursor) if DATABASE_URL else conn.cursor()
    cur.execute("SELECT * FROM users WHERE role != 'Admin'"); users = [dict(u) for u in cur.fetchall()]
    start_dt = datetime.strptime(d['start'], "%Y-%m-%d")
    preview = []; last_night = {}
    for i in range(7):
        dt = (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")
        assigned = []
        cur.execute("SELECT email, req_type FROM requests WHERE date=%s" if DATABASE_URL else "SELECT email, req_type FROM requests WHERE date=?", (dt,))
        blks = {b['email']: b['req_type'] for b in cur.fetchall()}
        for t in ['בוקר', 'ערב', 'לילה']:
            avail = [u for u in users if f"חסום: {t}" not in blks.get(u['email'], "") and u['name'] not in assigned and (t != 'בוקר' or last_night.get(u['name']) != True)]
            if avail:
                c = random.choice(avail); preview.append({"date": dt, "type": t, "staff": c['name'], "hours": ""})
                assigned.append(c['name']); last_night[c['name']] = (t == 'לילה')
            else: last_night[c['name']] = False
    cur.close(); conn.close(); return {"status": "ok", "suggested": preview}

@app.post("/api/shifts/save-bulk")
def save_bulk(d: dict):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM shifts WHERE is_draft=1 AND date BETWEEN %s AND %s" if DATABASE_URL else "DELETE FROM shifts WHERE is_draft=1 AND date BETWEEN ? AND ?", (d['start'], d['end']))
    q = "INSERT INTO shifts (date, type, staff, is_draft, hours) VALUES (%s,%s,%s,1,%s) ON CONFLICT (date, type) DO UPDATE SET staff=EXCLUDED.staff" if DATABASE_URL else "INSERT OR REPLACE INTO shifts VALUES (?,?,?,1,?)"
    for s in d['shifts']: cur.execute(q, (s['date'], s['type'], s['staff'], s.get('hours', '')))
    conn.commit(); cur.close(); conn.close(); return {"status": "ok"}

@app.get("/api/users")
def get_u():
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=RealDictCursor) if DATABASE_URL else conn.cursor()
    cur.execute("SELECT * FROM users"); res = [dict(r) for r in cur.fetchall()]; conn.close(); return res

@app.post("/api/users/save")
def save_u(u: dict):
    conn = get_db_connection(); cur = conn.cursor()
    q = "INSERT INTO users VALUES (%s,%s,%s,%s,%s) ON CONFLICT (email) DO UPDATE SET password=EXCLUDED.password, name=EXCLUDED.name, role=EXCLUDED.role, phone=EXCLUDED.phone" if DATABASE_URL else "INSERT OR REPLACE INTO users VALUES (?,?,?,?,?)"
    cur.execute(q, (u['email'], u['password'], u['name'], u['role'], u.get('phone','')))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/vacations/request")
def req_v(d: dict):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("INSERT INTO vacations (email, name, start_date, end_date, vac_type) VALUES (%s,%s,%s,%s,%s)", (d['email'], d['name'], d['start'], d['end'], d['type']))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.get("/api/admin/vacations")
def get_v():
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=RealDictCursor) if DATABASE_URL else conn.cursor()
    cur.execute("SELECT * FROM vacations WHERE status='PENDING'"); res = [dict(r) for r in cur.fetchall()]; conn.close(); return res

@app.get("/api/admin/approved-vacations")
def get_av_v():
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=RealDictCursor) if DATABASE_URL else conn.cursor()
    cur.execute("SELECT * FROM vacations WHERE status='APPROVED' ORDER BY start_date DESC"); res = [dict(r) for r in cur.fetchall()]; conn.close(); return res

@app.post("/api/admin/vacation-action")
def v_act(d: dict):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("UPDATE vacations SET status=%s WHERE id=%s", ('APPROVED' if d['action'] == 'approve' else 'REJECTED', d['id']))
    if d['action'] == 'approve':
        s, e = datetime.strptime(d['start'], "%Y-%m-%d"), datetime.strptime(d['end'], "%Y-%m-%d")
        while s <= e:
            for t in ['בוקר', 'ערב', 'לילה']: cur.execute("INSERT INTO requests (name, email, date, req_type, reason) VALUES (%s,%s,%s,%s,%s)", (d['name'], d['email'], s.strftime("%Y-%m-%d"), f"חסום: {t}", "חופשה מאושרת"))
            s += timedelta(days=1)
    conn.commit(); conn.close(); return {"status": "ok"}

@app.get("/api/admin/settings")
def get_sets():
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=RealDictCursor) if DATABASE_URL else conn.cursor()
    cur.execute("SELECT * FROM settings"); res = {r['key']: r['value'] for r in cur.fetchall()}; conn.close(); return res

@app.post("/api/admin/settings")
def save_sets(d: dict):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("UPDATE settings SET value=%s WHERE key='deadline_day'", (d['day'],))
    cur.execute("UPDATE settings SET value=%s WHERE key='deadline_time'", (d['time'],))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.post("/api/requests")
def add_r(r: dict):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("INSERT INTO requests (name, email, date, req_type, reason) VALUES (%s,%s,%s,%s,%s)", (r['name'], r['email'], r['date'], r['req_type'], r['reason']))
    conn.commit(); conn.close(); return {"status": "ok"}
