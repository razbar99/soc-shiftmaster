from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
import sqlite3
import csv
import io
from pathlib import Path
from datetime import datetime

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR = Path(__file__).resolve().parent
DB_NAME = str(BASE_DIR / "soc_data.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute('CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password TEXT, name TEXT, role TEXT, max_blocks INTEGER DEFAULT 2)')
    conn.execute('CREATE TABLE IF NOT EXISTS shifts (date TEXT, type TEXT, staff TEXT, is_draft INTEGER DEFAULT 1, PRIMARY KEY (date, type))')
    conn.execute('CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, date TEXT, req_type TEXT, reason TEXT, status TEXT DEFAULT "ממתין")')
    conn.execute('CREATE TABLE IF NOT EXISTS handovers (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, author TEXT, content TEXT, timestamp TEXT)')
    # טבלת החלפות (Swaps)
    conn.execute('CREATE TABLE IF NOT EXISTS swaps (id INTEGER PRIMARY KEY AUTOINCREMENT, requester_email TEXT, target_email TEXT, date TEXT, shift_type TEXT, status TEXT DEFAULT "ממתין_לאישור_עובד")')
    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
def get_index(): return (BASE_DIR / "index.html").read_text(encoding="utf-8")

# --- מנוע החלפות ---
@app.post("/api/swaps/request")
def request_swap(data: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO swaps (requester_email, target_email, date, shift_type) VALUES (?, ?, ?, ?)",
                 (data['from'], data['to'], data['date'], data['type']))
    conn.commit(); conn.close()
    return {"status": "success"}

@app.get("/api/swaps/pending/{email}")
def get_pending_swaps(email: str):
    conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row
    res = conn.execute("SELECT * FROM swaps WHERE (target_email=? OR requester_email=?) AND status != 'מאושר'", (email, email)).fetchall()
    conn.close(); return [dict(r) for r in res]

# --- ייצוא דוחות לאקסל (CSV) ---
@app.get("/api/reports/export")
def export_csv():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT date, type, staff FROM shifts WHERE is_draft=0 ORDER BY date DESC")
    rows = cursor.fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['תאריך', 'משמרת', 'עובד'])
    writer.writerows(rows)
    
    conn.close()
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=soc_report.csv"})

# --- פונקציות ליבה ---
@app.post("/api/login")
def login(data: dict):
    conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (data['email'], data['password'])).fetchone()
    conn.close()
    if user: return {"status": "success", "user": dict(user)}
    raise HTTPException(status_code=401)

@app.get("/api/shifts")
def get_shifts():
    conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row
    data = [dict(r) for r in conn.execute("SELECT * FROM shifts").fetchall()]
    conn.close(); return data

@app.post("/api/shifts/save")
def save_shift(shift: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT OR REPLACE INTO shifts (date, type, staff, is_draft) VALUES (?, ?, ?, 1)", (shift['date'], shift['type'], shift['staff']))
    conn.commit(); conn.close()
    return {"status": "success"}

@app.get("/api/users")
def get_users():
    conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row
    data = [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]
    conn.close(); return data
