from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import sqlite3
import os
from pathlib import Path
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
DB_NAME = str(BASE_DIR / "soc_data.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    # טבלאות קיימות
    conn.execute('CREATE TABLE IF NOT EXISTS shifts (date TEXT, type TEXT, staff TEXT, hours TEXT, PRIMARY KEY (date, type))')
    conn.execute('CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, date TEXT, req_type TEXT, reason TEXT, status TEXT DEFAULT "ממתין")')
    conn.execute('CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password TEXT, name TEXT, role TEXT)')
    
    # טבלאות חדשות ל-Enterprise
    conn.execute('CREATE TABLE IF NOT EXISTS handovers (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, shift_type TEXT, author TEXT, content TEXT, timestamp TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, action TEXT, timestamp TEXT)')
    
    # משתמש מנהל
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email='raz@soc.com'")
    if not cur.fetchone():
        conn.execute("INSERT INTO users (email, password, name, role) VALUES (?, ?, ?, ?)", ("raz@soc.com", "123456", "רז ברהום", "Admin"))
    
    conn.commit()
    conn.close()

init_db()

# --- לוגיקת אבטחה (Audit) ---
def log_action(user, action):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO audit_logs (user, action, timestamp) VALUES (?, ?, ?)", (user, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# --- API חדש לחפיפות משמרת ---
@app.get("/api/handovers")
def get_handovers():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM handovers ORDER BY id DESC LIMIT 10")
    data = [dict(r) for r in cur.fetchall()]
    conn.close()
    return data

@app.post("/api/handovers")
def add_handover(data: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO handovers (date, shift_type, author, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                 (datetime.now().strftime("%Y-%m-%d"), data['shift_type'], data['author'], data['content'], datetime.now().strftime("%H:%M")))
    conn.commit()
    conn.close()
    log_action(data['author'], f"הוסיף חפיפת משמרת: {data['shift_type']}")
    return {"status": "success"}

# --- עדכון פונקציות קיימות עם Audit ---
@app.post("/api/login")
def login(data: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=? AND password=?", (data['email'], data['password']))
    user = cur.fetchone()
    conn.close()
    if user:
        log_action(user['name'], "התחבר למערכת")
        return {"status": "success", "user": {"name": user["name"], "role": user["role"], "email": user["email"]}}
    raise HTTPException(status_code=401)

@app.post("/api/shifts")
def save_shift(shift: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT OR REPLACE INTO shifts (date, type, staff, hours) VALUES (?, ?, ?, ?)", (shift['date'], shift['shift_type'], shift['staff'], '00:00'))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/stats")
def get_stats():
    conn = sqlite3.connect(DB_NAME)
    shifts_count = conn.execute("SELECT COUNT(*) FROM shifts").fetchone()[0]
    users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    req_count = conn.execute("SELECT COUNT(*) FROM requests WHERE status='ממתין'").fetchone()[0]
    conn.close()
    return {"shifts": shifts_count, "users": users_count, "pending_reqs": req_count}

# שאר הפונקציות (get_shifts, get_requests, etc.) נשארות כפי שהיו
@app.get("/", response_class=HTMLResponse)
def get_index():
    return (BASE_DIR / "index.html").read_text(encoding="utf-8")

@app.get("/api/shifts")
def get_shifts():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    data = [dict(r) for r in conn.execute("SELECT * FROM shifts").fetchall()]
    conn.close()
    return data

@app.get("/api/users")
def get_users():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    data = [dict(r) for r in conn.execute("SELECT email, name, role FROM users").fetchall()]
    conn.close()
    return data

@app.post("/api/users")
def add_user(user: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user['email'], user['password'], user['name'], user['role']))
    conn.commit()
    conn.close()
    return {"status": "user added"}

@app.post("/api/users/delete")
def delete_user(data: dict):
    if data['email'] == "raz@soc.com": return {"status": "error"}
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM users WHERE email=?", (data['email'],))
    conn.commit()
    conn.close()
    return {"status": "user deleted"}

@app.get("/api/requests")
def get_requests():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    data = [dict(r) for r in conn.execute("SELECT * FROM requests").fetchall()]
    conn.close()
    return data

@app.post("/api/requests")
def save_request(req: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO requests (name, date, req_type, reason) VALUES (?, ?, ?, ?)", (req['name'], req['date'], req['req_type'], req['reason']))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/requests/status")
def update_req(data: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE requests SET status=? WHERE id=?", (data['status'], data['req_id']))
    conn.commit()
    conn.close()
    return {"status": "updated"}

@app.delete("/api/shifts/{date}/{shift_type}")
def del_shift(date, shift_type):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM shifts WHERE date=? AND type=?", (date, shift_type))
    conn.commit()
    conn.close()
    return {"status": "deleted"}
