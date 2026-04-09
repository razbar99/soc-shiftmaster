from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse # חדש
from pydantic import BaseModel
import sqlite3
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "soc_data.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute('''CREATE TABLE IF NOT EXISTS shifts 
                 (date TEXT, type TEXT, staff TEXT, hours TEXT, PRIMARY KEY (date, type))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS requests 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, date TEXT, req_type TEXT, reason TEXT, status TEXT DEFAULT 'ממתין')''')
    conn.commit()
    conn.close()

init_db()

# --- פונקציה חדשה: מגישה את האתר למי שנכנס לקישור ---
@app.get("/", response_class=HTMLResponse)
def get_index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>קובץ index.html לא נמצא בשרת</h1>"

# --- שאר הפונקציות של ה-API (נשארות אותו דבר) ---
@app.get("/api/shifts")
def get_shifts():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM shifts")
    rows = cur.fetchall()
    conn.close()
    return [{"date": r["date"], "shift_type": r["type"], "staff": r["staff"], "hours": r["hours"]} for r in rows]

@app.post("/api/shifts")
def save_shift(shift: dict): # שיניתי ל-dict כדי להיות גמיש יותר
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT OR REPLACE INTO shifts (date, type, staff, hours) VALUES (?, ?, ?, ?)", 
                 (shift['date'], shift['shift_type'], shift['staff'], shift['hours']))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/requests")
def get_requests():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM requests ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "date": r["date"], "req_type": r["req_type"], "reason": r["reason"], "status": r["status"]} for r in rows]

@app.post("/api/requests")
def save_request(req: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO requests (name, date, req_type, reason) VALUES (?, ?, ?, ?)", 
                 (req['name'], req['date'], req['req_type'], req['reason']))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/requests/status")
def update_request_status(data: dict):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE requests SET status = ? WHERE id = ?", (data['status'], data['req_id']))
    conn.commit()
    conn.close()
    return {"status": "updated"}

@app.delete("/api/shifts/{date}/{shift_type}")
def delete_shift(date: str, shift_type: str):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM shifts WHERE date = ? AND type = ?", (date, shift_type))
    conn.commit()
    conn.close()
    return {"status": "deleted"}
