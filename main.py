from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
    # טבלת משמרות
    conn.execute('''CREATE TABLE IF NOT EXISTS shifts 
                 (date TEXT, type TEXT, staff TEXT, hours TEXT, PRIMARY KEY (date, type))''')
    # טבלת בקשות משופרת עם סטטוס
    conn.execute('''CREATE TABLE IF NOT EXISTS requests 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, date TEXT, req_type TEXT, reason TEXT, status TEXT DEFAULT 'ממתין')''')
    conn.commit()
    conn.close()

init_db()

class Shift(BaseModel):
    date: str
    shift_type: str
    staff: str
    hours: str

class RequestData(BaseModel):
    name: str
    req_type: str
    date: str
    reason: str

class StatusUpdate(BaseModel):
    req_id: int
    status: str

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
def save_shift(shift: Shift):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT OR REPLACE INTO shifts (date, type, staff, hours) VALUES (?, ?, ?, ?)", 
                 (shift.date, shift.shift_type, shift.staff, shift.hours))
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
def save_request(req: RequestData):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO requests (name, date, req_type, reason) VALUES (?, ?, ?, ?)", 
                 (req.name, req.date, req.req_type, req.reason))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/requests/status")
def update_request_status(data: StatusUpdate):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE requests SET status = ? WHERE id = ?", (data.status, data.req_id))
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
