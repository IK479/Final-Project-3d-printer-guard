from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # for serving CSS/JS files
from fastapi.responses import FileResponse    # To return HTML pages
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks
import sqlite3
import requests
import asyncio
import os
from dotenv import load_dotenv

# Loading environment variables from file
load_dotenv()

# Setting the DB path relative to the project folder
DB_FILE = "print_guard.db"
is_monitoring = False
current_session_id= None # Variable to store the active session ID

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn
# =================================================================
#  Helpers
# =================================================================
def send_telegram_alert(defect_type, confidence):
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    if not TOKEN or not CHAT_ID: return
        
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    text = f"⚠️ *Aegis Alert!*\nDefect: {defect_type}\nConfidence: {confidence*100:.1f}%\nStatus: Requires Attention."
    keyboard = {"inline_keyboard": [[{"text": "🛑 EMERGENCY STOP", "callback_data": "stop_printer"}]]}
    
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "reply_markup": keyboard})
    except Exception as e:
        print(f"Telegram error: {e}")

def execute_emergency_stop():
    url = os.getenv("PRINTER_API_URL")
    api_key = os.getenv("PRINTER_API_KEY")
    
    if not url or not api_key:
        return False, "Printer credentials missing in .env"

    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    payload = {"command": "cancel"}
    
    try:
        response = requests.post(f"{url}/api/job", headers=headers, json=payload)
        response.raise_for_status()
        return True, "Printer stopped successfully!"
    except Exception as e:
        print(f"Error stopping printer: {e}")
        return False, "Failed to communicate with printer."
    
# =================================================================
#  Background Tasks & Listeners
# =================================================================    

async def telegram_bot_listener():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN: return

    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    offset = None

    while True:
        try:
            params = {"timeout": 30, "offset": offset}
            # מבקשים עדכונים מטלגרם מבלי לתקוע את השרת (באמצעות to_thread)
            response = await asyncio.to_thread(requests.get, url, params=params, timeout=35)
            data = response.json()

            if data.get("ok"):
                for update in data["result"]:
                    # מעדכנים את ה-offset כדי שלא נקבל את אותה לחיצה פעמיים
                    offset = update["update_id"] + 1

                    # אם מישהו לחץ על כפתור בהודעה
                    if "callback_query" in update:
                        callback = update["callback_query"]
                        
                        if callback["data"] == "stop_printer":
                            print("[Telegram] Received Emergency Stop command!")
                            
                            # 1. עוצרים את המדפסת בפועל!
                            success, msg = execute_emergency_stop()
                            
                            # 2. שולחים פופ-אפ קטן בטלגרם שמאשר שהלחיצה נקלטה
                            answer_url = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
                            requests.post(answer_url, json={
                                "callback_query_id": callback["id"], 
                                "text": "🛑 Printer Halted Successfully!" if success else "❌ Error stopping printer.",
                                "show_alert": True
                            })
                            
                            # 3. מעדכנים את ההודעה כדי שהכפתור יעלם (שלא ילחצו פעמיים)
                            edit_url = f"https://api.telegram.org/bot{TOKEN}/editMessageText"
                            requests.post(edit_url, json={
                                "chat_id": callback["message"]["chat"]["id"],
                                "message_id": callback["message"]["message_id"],
                                "text": callback["message"]["text"] + "\n\n⛔ *ACTION TAKEN: PRINTER HALTED BY USER*",
                                "parse_mode": "Markdown"
                            })

        except Exception as e:
            print(f"[Telegram] Listener error: {e}")

        await asyncio.sleep(1)

async def purge_old_data():
    while True:
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM alerts WHERE detection_id IN (SELECT detection_id FROM detections WHERE timestamp < datetime("now", "-30 days"))')
                cursor.execute('DELETE FROM detections WHERE timestamp < datetime("now", "-30 days")')
                conn.commit()
            print("[System] Auto-purge completed.")
        except Exception as e:
            print(f"[System] Auto-purge error: {e}")
        await asyncio.sleep(86400)

@asynccontextmanager
async def lifespan(app: FastAPI):
    purge_task = asyncio.create_task(purge_old_data())
    telegram_task = asyncio.create_task(telegram_bot_listener())
    yield
    purge_task.cancel()
    telegram_task.cancel()

app = FastAPI(title="Print Guard API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Schemas ---
class SessionStartRequest(BaseModel):
    printer_name: Optional[str] = "Unit 01-Alpha"
    filament_type: Optional[str] = "PLA"

class DetectionResult(BaseModel):
    session_id: int
    defect_type: str
    confidence: float
    timestamp: datetime

 # =================================================================
#  API Routes
# =================================================================   
# When entering the main address, the server will display the Dashboard.
@app.get("/")
async def read_dashboard():
    return FileResponse("script/Live Monitoring Dashboard.html")

# path to the settings screen
@app.get("/config")
async def read_config():
    return FileResponse("script/System Settings.html")

# Dedicated path to the alerts and history screen
@app.get("/history")
async def read_history():
    return FileResponse("script/Alerts & History.html")

# =================================================================
#  WebSocket layer (streaming real-time notifications)
# =================================================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws/alerts")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)   


@app.post("/printer/emergency-stop")
async def api_emergency_stop():
    success, message = execute_emergency_stop()
    if success:
        send_telegram_alert("EMERGENCY STOP INITIATED FROM DASHBOARD", 1.0)
        return {"status": "success", "message": message}
    return {"status": "error", "message": message}    


@app.post("/session/start")
async def start_session(request: SessionStartRequest):
    global is_monitoring, current_session_id

    if is_monitoring:
        return {"status": "error", "message": "Monitoring already active"}
        
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sessions (start_time, printer_name, filament_type)
            VALUES (?, ?, ?)
        ''', (datetime.now().isoformat(), request.printer_name, request.filament_type))
        current_session_id = cursor.lastrowid
    
    is_monitoring = True
    return {"status": "success", "message": "Monitoring started", "session_id": current_session_id}


@app.post("/session/stop")
async def stop_session():
    global is_monitoring, current_session_id
    is_monitoring = False
    current_session_id = None
    return {"status": "success", "message": "Monitoring session stopped"}

@app.post("/internal/detection")
async def receive_detection(result: DetectionResult, background_tasks: BackgroundTasks):
    print(f"Received analysis for session {result.session_id}: {result.defect_type} ({result.confidence*100}%)")

    CONFIDENCE_THRESHOLD = 0.85
    alert_created = result.confidence > CONFIDENCE_THRESHOLD

    conn = get_db_connection()

    try:
        # Saving in the detections table
      with conn:
            cursor = conn.cursor()
            
            # 1. Saving the identification
            cursor.execute('''
                INSERT INTO detections (session_id, defect_type, confidence, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (result.session_id, result.defect_type, result.confidence, result.timestamp.isoformat()))
            
            last_detection_id = cursor.lastrowid
            
            # 2. Alert handling (only if security is high enough)
            if alert_created:
                image_path = f"images/alerts/session_{result.session_id}_{last_detection_id}.jpg"
                
                cursor.execute('''
                    INSERT INTO alerts (detection_id, image_path)
                    VALUES (?, ?)
                ''', (last_detection_id, image_path))
                
                # Transferring the report to Telegram to a background task so as not to jam the server
                background_tasks.add_task(send_telegram_alert, result.defect_type, result.confidence)
                
                # Live broadcast to dashboard
                alert_data = {
                    "type": "NEW_ALERT",
                    "defect_type": result.defect_type,
                    "confidence": result.confidence,
                    "timestamp": result.timestamp.strftime("%H:%M:%S")
                }
                await manager.broadcast(alert_data)

    except sqlite3.IntegrityError as e:
        # In case of a database error, we will return a clear error
        return {"status": "error", "message": f"Database integrity error: {str(e)}"}
        
    finally:
        # The database connection will always be closed, even if the code crashes in the middle
        conn.close()
        
    return {
        "status": "success", 
        "action": "alert_created" if alert_created else "ignored",
        "detection_id": last_detection_id
    }

# =================================================================
#  Serving static files (CSS, JS) - must remain at the end of the file!
# =================================================================
app.mount("/", StaticFiles(directory="script"), name="static")