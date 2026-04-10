from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
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

BASE_DIR = Path(__file__).resolve().parent
DB_NAME = str(BASE_DIR / "soc_data.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    # טבלת משמרות
    conn.execute('''CREATE TABLE IF NOT EXISTS shifts 
                 (date TEXT, type TEXT, staff TEXT, hours TEXT, PRIMARY KEY (date, type))''')
    # טבלת בקשות
    conn.execute('''CREATE TABLE IF NOT EXISTS requests 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, date TEXT, req_type TEXT, reason TEXT, status TEXT DEFAULT 'ממתין')''')
    # טבלת משתמשים
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                 (email TEXT PRIMARY KEY, password TEXT, name TEXT, role TEXT)''')
    
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email='raz@soc.com'")
    if not cur.fetchone():
        conn.execute("INSERT INTO users (email, password, name, role) VALUES (?, ?, ?, ?)",
                     ("raz@soc.com", "123456", "רז ברהום", "Admin"))
    
    conn.commit()
    conn.close()

init_db()

class LoginData(BaseModel):
    email: str
    password: str

class UserData(BaseModel):
    email: str
    password: str
    name: str
    role: str

@app.get("/", response_class=HTMLResponse)
def get_index():
    html_file = BASE_DIR / "index.html"
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
    return "<h1>Error: index.html not found</h1>"

@app.post("/api/login")
def login(data: LoginData):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=? AND password=?", (data.email, data.password))
    user = cur.fetchone()
    conn.close()
    if user:
        return {"status": "success", "user": {"name": user["name"], "role": user["role"], "email": user["email"]}}
    raise HTTPException(status_code=401, detail="פרטים שגויים")

@app.get("/api/users")
def get_users():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT email, name, role FROM users")
    users = cur.fetchall()
    conn.close()
    return [dict(u) for u in users]

@app.post("/api/users")
def add_user(user: UserData):
    conn = sqlite3.connect(DB_NAME)
    try:
        conn.execute("INSERT INTO users (email, password, name, role) VALUES (?, ?, ?, ?)",
                     (user.
