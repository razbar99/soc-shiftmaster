from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import os

app = FastAPI()

# הגדרת CORS - מאפשר לכל מכשיר (טלפון/מחשב בבית) לדבר עם השרת
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "soc_data.db"

# יצירת בסיס הנתונים אם הוא לא קיים
def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute('''CREATE TABLE IF NOT EXISTS shifts 
                 (date TEXT, type TEXT, staff TEXT, hours TEXT, PRIMARY KEY (date, type))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS requests 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, date TEXT, req_type TEXT, reason TEXT)''')
    conn.commit()
    conn.close()

init_db()

class Shift(BaseModel):
    date: str
    shift_type: str
    staff: str
    hours: str

class RequestData(BaseModel):
    req_type: str
    date: str
    reason: str

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

@app.post("/api/requests")
def save_request(req: RequestData):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO requests (date, req_type, reason) VALUES (?, ?, ?)", 
                 (req.date, req.req_type, req.reason))
    conn.commit()
    conn.close()
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    # שימוש בפורט דינמי עבור שרתי ענן
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)