from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import sqlite3, csv, io
from pathlib import Path
from datetime import datetime

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "soc_final.db"

def init_db():
    conn = sqlite3.connect(DB)
    # יצירת טבלאות
    conn.execute('CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password TEXT, name TEXT, role TEXT, max_blocks INTEGER DEFAULT 2)')
    conn.execute('CREATE TABLE IF NOT EXISTS shifts (date TEXT, type TEXT, staff TEXT, is_draft INTEGER DEFAULT 1, PRIMARY KEY (date, type))')
    conn.execute('CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, date TEXT, req_type TEXT, reason TEXT, status TEXT DEFAULT "ממתין")')
    conn.execute('CREATE TABLE IF NOT EXISTS handovers (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, author TEXT, content TEXT, timestamp TEXT)')
    # יצירת משתמש מנהל ראשוני
    if not conn.execute("SELECT * FROM users WHERE email='raz@soc.com'").fetchone():
        conn.execute("INSERT INTO users VALUES ('raz@soc.com','123456','רז ברהום','Admin',99)")
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
    raise HTTPException(401, "Unauthorized")

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

@app.get("/api/admin/availability/{date}")
def get_avail(date: str):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    blocks = {r['email']: r['reason'] for r in conn.execute("SELECT email, reason FROM requests WHERE date=? AND status='אושר'", (date,)).fetchall()}
    users = [dict(u) for u in conn.execute("SELECT name, email FROM users").fetchall()]
    for u in users:
        u['is_blocked'] = u['email'] in blocks
        u['reason'] = blocks.get(u['email'], "")
    conn.close(); return users

@app.get("/api/users")
def get_users():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute("SELECT name, email, role FROM users").fetchall()]
    conn.close(); return res

@app.post("/api/requests")
def add_request(r: dict):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO requests (name,email,date,req_type,reason) VALUES (?,?,?,?,?)", (r['name'],r['email'],r['date'],r['req_type'],r['reason']))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.get("/api/requests")
def get_requests():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute("SELECT * FROM requests WHERE status='ממתין'").fetchall()]
    conn.close(); return res

@app.post("/api/requests/status")
def update_request(d: dict):
    conn = sqlite3.connect(DB)
    conn.execute("UPDATE requests SET status=? WHERE id=?", (d['status'], d['req_id']))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.get("/api/handovers")
def get_handovers():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute("SELECT * FROM handovers ORDER BY id DESC LIMIT 10").fetchall()]
    conn.close(); return res

@app.post("/api/handovers")
def add_handover(d: dict):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO handovers (date,author,content,timestamp) VALUES (?,?,?,?)", 
                 (datetime.now().strftime("%Y-%m-%d"), d['author'], d['content'], datetime.now().strftime("%H:%M")))
    conn.commit(); conn.close(); return {"status": "ok"}

@app.get("/api/reports/export")
def export_report():
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT date, type, staff FROM shifts WHERE is_draft=0 ORDER BY date DESC").fetchall()
    out = io.StringIO(); writer = csv.writer(out)
    writer.writerow(['Date', 'Shift Type', 'Staff Member']); writer.writerows(rows)
    conn.close()
    return Response(content=out.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=soc_report.csv"})
