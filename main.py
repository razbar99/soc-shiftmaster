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
    # יצירת טבלאות
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                 (email TEXT PRIMARY KEY, password TEXT, name TEXT, role TEXT, max_blocks INTEGER DEFAULT 2)''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS shifts 
                 (date TEXT, type TEXT, staff TEXT, hours TEXT, is_draft INTEGER DEFAULT 1, PRIMARY KEY (date, type))''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS requests 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, date TEXT, req_type TEXT, reason TEXT, status TEXT DEFAULT "ממתין")''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS handovers 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, shift_type TEXT, author TEXT, content TEXT, timestamp TEXT)''')
    
    # משתמש מנהל ראשוני
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email='raz@soc.com'")
    if not cur.fetchone():
        conn.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", ("raz@soc.com", "123456", "רז ברהום", "Admin", 99))
    
    conn.commit()
    conn.close()

init_db()

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
def get_index():
    html_file = BASE_DIR / "index.html"
    return html_file.read_text(encoding="utf-8") if html_file.exists() else "<h1>Error: index.html not found</h1>"

@app.post("/api/login")
def login(data: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (data['email'], data['password'])).fetchone()
    conn.close()
    if user:
        return {"status": "success", "user": dict(user)}
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
    except: return {"status": "error", "message": "קיים כבר"}
    finally: conn.close()

@app.post
