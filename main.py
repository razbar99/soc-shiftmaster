import os
from fastapi.responses import HTMLResponse

# מוצא את התיקייה שבה נמצא הקובץ הנוכחי (main.py)
base_path = os.path.dirname(os.path.abspath(__file__))

@app.get("/", response_class=HTMLResponse)
def get_index():
    # בונה נתיב מדויק לקובץ index.html
    html_path = os.path.join(base_path, "index.html")
    
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        # אם הוא עדיין לא מוצא, הוא ידפיס לנו את כל הקבצים שהוא כן רואה
        files_in_dir = os.listdir(base_path)
        return f"<h1>קובץ לא נמצא</h1><p>חיפשתי ב: {html_path}</p><p>קבצים בתיקייה: {files_in_dir}</p>"
