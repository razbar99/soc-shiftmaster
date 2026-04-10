from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR = Path(__file__).resolve().parent
DB_NAME = str(BASE_DIR / "soc_data.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    # טבלת משתמשים כולל מכסה
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                 (email TEXT PRIMARY KEY, password TEXT, name TEXT, role TEXT, max_blocks INTEGER DEFAULT 2)''')
    # טבלת משמרות כולל מצב טיוטה
    conn.execute('''CREATE TABLE IF NOT EXISTS shifts 
                 (date TEXT, type TEXT, staff TEXT, hours TEXT, is_draft INTEGER DEFAULT 1, PRIMARY KEY (date, type))''')
    # טבלת בקשות
    conn.execute('''CREATE TABLE IF NOT EXISTS requests 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, date TEXT, req_type TEXT, reason TEXT, status TEXT DEFAULT "ממתין")''')
    # טבלת חפיפות
    conn.execute('''CREATE TABLE IF NOT EXISTS handovers 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, shift_type TEXT, author TEXT, content TEXT, timestamp TEXT)''')
    
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email='raz@soc.com'")
    if not cur.fetchone():
        conn.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", ("raz@soc.com", "123456", "רז ברהום", "Admin", 99))
    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
def get_index():
    html_file = BASE_DIR / "index.html"
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
    return "<h1>index.html not found</h1>"

@app.post("/api/login")
def login(data: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (data['email'], data['password'])).fetchone()
    conn.close()
    if user: return {"status": "success", "user": dict(user)}
    raise HTTPException(status_code=401)

@app.get("/api/users")
def get_users():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    users = [dict(u) for u in conn.execute("SELECT * FROM users").fetchall()]
    conn.close()
    return users

@app.post("/api/users")
def add_user(user: dict):
    conn = sqlite3.connect(DB_NAME)
    try:
        conn.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", (user['email'], user['password'], user['name'], user['role'], 2))
        conn.commit()
        return {"status": "user added"}
    except: return {"status": "error", "message": "User exists"}
    finally: conn.close()

@app.post("/api/users/delete")
def delete_user(data: dict):
    if data['email'] == "raz@soc.com": return {"status": "error"}
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM users WHERE email=?", (data['email'],))
    conn.commit()
    conn.close()
    return {"status": "user deleted"}

@app.post("/api/users/quota")
def update_quota(data: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE users SET max_blocks = ? WHERE email = ?", (data['max_blocks'], data['email']))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/shifts")
def get_shifts():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    data = [dict(r) for r in conn.execute("SELECT * FROM shifts").fetchall()]
    conn.close()
    return data

@app.post("/api/shifts")
def save_shift(shift: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT OR REPLACE INTO shifts (date, type, staff, hours, is_draft) VALUES (?, ?, ?, ?, 1)", 
                 (shift['date'], shift['shift_type'], shift['staff'], '00:00'))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/shifts/publish")
def publish_shifts(data: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE shifts SET is_draft = 0 WHERE date BETWEEN ? AND ?", (data['start'], data['end']))
    conn.commit()
    conn.close()
    return {"status": "published"}

@app.delete("/api/shifts/{date}/{shift_type}")
def delete_shift(date: str, shift_type: str):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM shifts WHERE date=? AND type=?", (date, shift_type))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

@app.post("/api/requests")
def save_request(req: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    req_date = datetime.strptime(req['date'], '%Y-%m-%d')
    start_w = (req_date - timedelta(days=req_date.weekday() + 1)).strftime('%Y-%m-%d')
    end_w = (req_date + timedelta(days=6)).strftime('%Y-%m-%d')
    
    count = conn.execute("SELECT COUNT(*) FROM requests WHERE email=? AND date BETWEEN ? AND ? AND status != 'נדחה'", 
                         (req['email'], start_w, end_w)).fetchone()[0]
    user = conn.execute("SELECT max_blocks FROM users WHERE email=?", (req['email'],)).fetchone()
    
    if user and count >= user['max_blocks'] and req['req_type'] == 'אילוץ':
        conn.close()
        return {"status": "error", "message": f"חרגת ממכסת האילוצים השבועית שלך ({user['max_blocks']})"}

    conn.execute("INSERT INTO requests (name, email, date, req_type, reason) VALUES (?, ?, ?, ?, ?, ?)", 
                 (req['name'], req['email'], req['date'], req['req_type'], req['reason'], "ממתין"))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/requests")
def get_requests():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    data = [dict(r) for r in conn.execute("SELECT * FROM requests").fetchall()]
    conn.close()
    return data

@app.post("/api/requests/status")
def update_req(data: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE requests SET status=? WHERE id=?", (data['status'], data['req_id']))
    conn.commit()
    conn.close()
    return {"status": "updated"}

@app.get("/api/handovers")
def get_handovers():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    data = [dict(r) for r in conn.execute("SELECT * FROM handovers ORDER BY id DESC LIMIT 15").fetchall()]
    conn.close()
    return data

@app.post("/api/handovers")
def add_handover(data: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO handovers (date, shift_type, author, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                 (datetime.now().strftime("%Y-%m-%d"), "חפיפה", data['author'], data['content'], datetime.now().strftime("%H:%M")))
    conn.commit()
    conn.close()
    return {"status": "success"}
