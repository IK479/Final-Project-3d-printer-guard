from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks
import sqlite3
import inference
import asyncio
import base64
import os
from dotenv import load_dotenv
from auth_service import router as auth_router, get_current_user

from database import get_db_connection
from notification_service import send_telegram_alert, telegram_bot_listener, execute_emergency_stop
from inference import generate_video_frames
load_dotenv()

is_monitoring = False
current_session_id = 0

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

async def broadcast_telemetry():
    while True:
        try:
            telemetry_data = {
                "type": "TELEMETRY",
                "fps": round(inference.current_fps, 1),
                "inference_time": round(inference.current_inference_time, 1),
            }
            await manager.broadcast(telemetry_data)
        except Exception as e:
            print(f"[Telemetry Error] {e}")
            pass
        
        await asyncio.sleep(2) # Transmits every two seconds to avoid overloading the network

@asynccontextmanager
async def lifespan(app: FastAPI):

    purge_task = asyncio.create_task(purge_old_data())
    telegram_task = asyncio.create_task(telegram_bot_listener())
    telemetry_task = asyncio.create_task(broadcast_telemetry())
    loop = asyncio.get_running_loop()
    if hasattr(inference, 'run_inference_loop'):
        loop.run_in_executor(None, inference.run_inference_loop)
    yield
    purge_task.cancel()
    telegram_task.cancel()
    telemetry_task.cancel()
    inference.release_camera()

app = FastAPI(title="Print Guard API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

# --- Schemas ---
class SessionStartRequest(BaseModel):
    printer_name: Optional[str] = "Unit 01-Alpha"
    filament_type: Optional[str] = "PLA"

class DetectionResult(BaseModel):
    session_id: int
    defect_type: str
    confidence: float
    timestamp: datetime
    image_base64: Optional[str] = None

class SystemSettings(BaseModel):
    confidence_threshold: float

@app.get("/video_feed")
async def video_feed():
    # A special FastAPI function that keeps an HTTP connection open and streams the frames sequentially
    return StreamingResponse(generate_video_frames(), media_type="multipart/x-mixed-replace; boundary=frame")
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

# Path to login screen
@app.get("/login")
async def read_login():
    return FileResponse("script/Login.html")

# Path to register screen
@app.get("/register")
async def read_register():
    return FileResponse("script/Register.html")

# Path to delete data
@app.delete("/api/history")
async def clear_history(user: dict = Depends(get_current_user)):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM alerts")
            cursor.execute("DELETE FROM detections")
            conn.commit()
        return {"status": "success", "message": "History cleared successfully"}
    except sqlite3.Error as e:
        return {"status": "error", "message": f"Database error: {str(e)}"}

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
    inference.release_camera()
    return {"status": "success", "message": "Monitoring session stopped"}

@app.get("/api/session/status")
async def get_session_status():
    # Returns to the browser whether the camera is currently running in the background
    global is_monitoring, current_session_id
    return {"is_monitoring": is_monitoring, "session_id": current_session_id}

@app.post("/api/settings")
async def update_settings(settings: SystemSettings, user: dict = Depends(get_current_user)):
    # Updating the live variable in inference.py
    inference.current_alert_threshold = settings.confidence_threshold
    return {"status": "success", "message": "Threshold updated successfully"}

@app.get("/api/settings")
async def get_settings():
    return {"confidence_threshold": inference.current_alert_threshold}

@app.post("/internal/detection")
async def receive_detection(result: DetectionResult, background_tasks: BackgroundTasks):
    print(f"Received analysis for session {result.session_id}: {result.defect_type} ({result.confidence*100}%)")

    CONFIDENCE_THRESHOLD = inference.current_alert_threshold
    alert_created = result.confidence > CONFIDENCE_THRESHOLD and (result.defect_type.lower() != "normal")

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
                # Create a path to save the image
                os.makedirs("images/alerts", exist_ok=True) # Verify that the folder exists
                image_filename = f"session_{result.session_id}_{last_detection_id}.jpg"
                image_path = f"images/alerts/{image_filename}"
                db_image_path = f"/images/alerts/{image_filename}"
                
                if result.image_base64:
                    try:
                        img_data = base64.b64decode(result.image_base64)
                        with open(image_path, "wb") as f:
                            f.write(img_data)
                    except Exception as e:
                        print(f"Error saving image: {e}")
                cursor.execute('''
                    INSERT INTO alerts (detection_id, image_path)
                    VALUES (?, ?)
                ''', (last_detection_id, db_image_path))
                
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

@app.get("/api/recent-alerts")
async def get_recent_alerts():
    # Retrieving the last 5 alerts (over 85% confidence) from the DB
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT defect_type, confidence, timestamp 
            FROM detections 
            WHERE confidence > 0.85
            ORDER BY timestamp DESC LIMIT 5
        ''')
        rows = cursor.fetchall()
        
        alerts = []
        for row in rows:
            alerts.append({
                "defect_type": row[0],
                "confidence": row[1],
                "timestamp": row[2]
            })
        return {"status": "success", "alerts": alerts}
    
@app.get("/api/history-data")
async def get_history_data():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Retrieving faults along with their images from the alerts table
        cursor.execute('''
            SELECT d.timestamp, a.image_path, d.defect_type, d.confidence, d.detection_id
            FROM detections d
            JOIN alerts a ON d.detection_id = a.detection_id
            ORDER BY d.timestamp DESC
            LIMIT 50
        ''')
        rows = cursor.fetchall()
        
        events = []
        for row in rows:
            events.append({
                "timestamp": row[0],
                "snapshot_url": row[1] if row[1] else "",
                "defect_type": row[2],
                "confidence": row[3],
                "layer_id": f"#{row[4]}"
            })
        return {"status": "success", "events": events}

# # Exposing the image folder to the browser
os.makedirs("images/alerts", exist_ok=True)
app.mount("/images", StaticFiles(directory="images"), name="images")

# =================================================================
#  Serving static files (CSS, JS) - must remain at the end of the file!
# =================================================================
app.mount("/", StaticFiles(directory="script"), name="static")