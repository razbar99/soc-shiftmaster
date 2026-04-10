from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import sqlite3
import os
from pathlib import Path

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# מוצא את התיקייה שבה נמצא main.py
BASE_DIR = Path(__file__).resolve().parent
DB_NAME = str(BASE_DIR / "soc_data.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute('''CREATE TABLE IF NOT EXISTS shifts 
                 (date TEXT, type TEXT, staff TEXT, hours TEXT, PRIMARY KEY (date, type))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS requests 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, date TEXT, req_type TEXT, reason TEXT, status TEXT DEFAULT 'ממתין')''')
    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
def get_index():
    # חיפוש הקובץ בנתיב אבסולוטי
    html_path = BASE_DIR / "index.html"
    
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    else:
        # אבחון אם הקובץ עדיין נעלם
        files = [f.name for f in BASE_DIR.iterdir()]
        return f"<h1>Error 404</h1><p>Path: {html_path}</p><p>Files in folder: {files}</p>"

# API Endpoint לדוגמה כדי לבדוק שהשרת חי
@app.get("/health")
def health_check():
    return {"status": "ok", "db": DB_NAME}

# פונקציות ה-API של המערכת (השארתי רק את אלו לקיצור, תוודא שהן קיימות אצלך)
@app.get("/api/shifts")
def get_shifts():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM shifts")
    rows = cur.fetchall()
    conn.close()
    return [{"date": r["date"], "shift_type": r["type"], "staff": r["staff"], "hours": r["hours"]} for r in rows]

# ... (שאר הפונקציות: save_shift, get_requests, save_request וכו')
