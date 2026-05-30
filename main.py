from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # for serving CSS/JS files
from fastapi.responses import FileResponse    # To return HTML pages
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import sqlite3

app = FastAPI(title="Print Guard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setting the DB path relative to the project folder
DB_FILE = "print_guard.db"
is_monitoring = False
current_session_id= None # Variable to store the active session ID

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

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
#  Frontend paths (HTML page submission)
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

# =================================================================
#  REST API paths (logic and data)
# =================================================================

@app.post("/session/start")
async def start_session(request: SessionStartRequest):
    global is_monitoring, current_session_id

    if is_monitoring:
        return {"status": "error", "message": "Monitoring already active"}
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create a new session in the database and save its ID
    cursor.execute('''
        INSERT INTO sessions (start_time, printer_name, filament_type)
        VALUES (?, ?, ?)
    ''', (datetime.now().isoformat(), request.printer_name, request.filament_type))
    
    current_session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    is_monitoring = True
    return {"status": "success", "message": "Monitoring started", "session_id": current_session_id}


@app.post("/session/stop")
async def stop_session():
    global is_monitoring, current_session_id
    is_monitoring = False
    current_session_id = None
    return {"status": "success", "message": "Monitoring session stopped"}

@app.post("/internal/detection")
async def receive_detection(result: DetectionResult):
    print(f"Received analysis for session {result.session_id}: {result.defect_type} ({result.confidence*100}%)")

    CONFIDENCE_THRESHOLD = 0.85
    alert_created = result.confidence > CONFIDENCE_THRESHOLD

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Saving in the detections table
        cursor.execute('''
            INSERT INTO detections (session_id, defect_type, confidence, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (result.session_id, result.defect_type, result.confidence, result.timestamp.isoformat()))
        
        last_detection_id = cursor.lastrowid
        
        # If confidence is high, create an alert and send it to the Dashboard!
        if alert_created:
            image_path = f"images/alerts/session_{result.session_id}_{last_detection_id}.jpg"
            cursor.execute('''
                INSERT INTO alerts (detection_id, image_path)
                VALUES (?, ?)
            ''', (last_detection_id, image_path))
            
            # --- Connecting the code to the user interface ---
            # Broadcasting the alert in real time to the Frontend
            alert_data = {
                "type": "NEW_ALERT",
                "defect_type": result.defect_type,
                "confidence": result.confidence,
                "timestamp": result.timestamp.strftime("%H:%M:%S")
            }
            # Since we are in an asynchronous function, we can broadcast directly
            await manager.broadcast(alert_data)
        
        conn.commit()
        
    except sqlite3.IntegrityError as e:
        conn.rollback()
        return {"status": "error", "message": f"Database integrity error: {str(e)}"}
        
    finally:
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