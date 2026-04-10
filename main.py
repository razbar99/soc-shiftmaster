from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR = Path(__file__).resolve().parent
DB_NAME = str(BASE_DIR / "soc_data.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    # טבלאות ליבה
    conn.execute('CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password TEXT, name TEXT, role TEXT, max_blocks INTEGER DEFAULT 2)')
    conn.execute('CREATE TABLE IF NOT EXISTS shifts (date TEXT, type TEXT, staff TEXT, is_draft INTEGER DEFAULT 1, PRIMARY KEY (date, type))')
    conn.execute('CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, date TEXT, req_type TEXT, reason TEXT, status TEXT DEFAULT "ממתין")')
    conn.execute('CREATE TABLE IF NOT EXISTS handovers (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, author TEXT, content TEXT, timestamp TEXT)')
    # טבלת החלפות חדשה
    conn.execute('CREATE TABLE IF NOT EXISTS swap_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, from_email TEXT, to_email TEXT, date TEXT, shift_type TEXT, status TEXT DEFAULT "ממתין")')
    
    conn.commit()
    conn.close()

init_db()

# --- מנוע שיבוץ חכם ---
@app.get("/api/admin/availability/{date}")
def get_availability(date: str):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    # מושך את כל האילוצים לתאריך הזה
    blocks = {r['email']: r['reason'] for r in conn.execute("SELECT email, reason FROM requests WHERE date=? AND status='אושר'", (date,)).fetchall()}
    users = [dict(u) for u in conn.execute("SELECT name, email FROM users").fetchall()]
    conn.close()
    
    result = []
    for u in users:
        u['is_blocked'] = u['email'] in blocks
        u['block_reason'] = blocks.get(u['email'], "")
        result.append(u)
    return result

@app.post("/api/shifts/secure-save")
def save_shift_secure(shift: dict):
    conn = sqlite3.connect(DB_NAME)
    # 1. בדיקת כפילות (האם העובד כבר משובץ באותו יום במשמרת אחרת?)
    existing = conn.execute("SELECT type FROM shifts WHERE date=? AND staff LIKE ?", (shift['date'], f"%{shift['staff']}%")).fetchone()
    if existing:
        conn.close()
        return {"status": "error", "message": f"העובד כבר משובץ ביום זה למשמרת {existing[0]}"}
    
    # 2. שמירה כטיוטה
    conn.execute("INSERT OR REPLACE INTO shifts (date, type, staff, is_draft) VALUES (?, ?, ?, 1)", 
                 (shift['date'], shift['shift_type'], shift['staff']))
    conn.commit()
    conn.close()
    return {"status": "success"}

# --- דוחות שכר/שעות ---
@app.get("/api/reports/monthly/{month}")
def get_monthly_report(month: str): # format YYYY-MM
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    data = conn.execute("SELECT staff, COUNT(*) as shift_count FROM shifts WHERE date LIKE ? AND is_draft=0 GROUP BY staff", (f"{month}%",)).fetchall()
    conn.close()
    return [dict(r) for r in data]

# --- המשך ה-API הקיים (Login, Users, Publish) ---
@app.get("/", response_class=HTMLResponse)
def get_index(): return (BASE_DIR / "index.html").read_text(encoding="utf-8")

@app.post("/api/login")
def login(data: dict):
    conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (data['email'], data['password'])).fetchone()
    conn.close()
    if user: return {"status": "success", "user": dict(user)}
    raise HTTPException(status_code=401)

@app.get("/api/users")
def get_u():
    conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]
    conn.close(); return res

@app.
