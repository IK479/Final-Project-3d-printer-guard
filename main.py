from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks
import inference
import asyncio
import base64
import os
from dotenv import load_dotenv
from auth_service import router as auth_router, get_current_user

from notification_service import send_telegram_alert, telegram_bot_listener, execute_emergency_stop
from inference import generate_video_frames
load_dotenv()

is_monitoring = False
current_session_id = 0

async def purge_old_data():
    """מנגנון ניקוי מדמה בזיכרון"""
    while True:
        print("[System] Memory auto-purge skipped (Database bypassed).")
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
        
        await asyncio.sleep(2)

@asynccontextmanager
async def lifespan(app: FastAPI):

    purge_task = asyncio.create_task(purge_old_data())
    telegram_task = asyncio.create_task(telegram_bot_listener())
    telemetry_task = asyncio.create_task(broadcast_telemetry())
    loop = asyncio.get_running_loop()
    if hasattr(inference, 'run_inference_loop'):
        loop.run_in_executor(None, inference.run_inference_loop)
    yield
    
    # ביטול משימות וסגירה בטוחה של המצלמה בעת כיבוי השרת
    purge_task.cancel()
    telegram_task.cancel()
    telemetry_task.cancel()
    inference.release_camera()

# מיושר לחלוטין לשמאל (ברמת ה-Global Scope) למניעת שגיאת ASGI app
app = FastAPI(title="Print Guard API", lifespan=lifespan)

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
    image_base64: Optional[str] = None

class SystemSettings(BaseModel):
    confidence_threshold: float

@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(generate_video_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

# =================================================================
#  API Routes
# =================================================================   
@app.get("/")
async def read_dashboard():
    return FileResponse("script/Live Monitoring Dashboard.html")

@app.get("/config")
async def read_config():
    return FileResponse("script/System Settings.html")

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
#  WebSocket layer
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
        
    current_session_id += 1
    new_session = {
        "session_id": current_session_id,
        "start_time": datetime.now().isoformat(),
        "printer_name": request.printer_name,
        "filament_type": request.filament_type
    }
    memory_sessions.append(new_session)
    
    is_monitoring = True
    return {"status": "success", "message": "Monitoring started", "session_id": current_session_id}


@app.post("/session/stop")
async def stop_session():
    global is_monitoring, current_session_id
    is_monitoring = False
    inference.release_camera()
    return {"status": "success", "message": "Monitoring session stopped"}

@app.get("/api/session/status")
async def get_session_status():
    global is_monitoring, current_session_id
    return {"is_monitoring": is_monitoring, "session_id": current_session_id}

@app.post("/api/settings")
async def update_settings(settings: SystemSettings):
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

    last_detection_id = len(memory_detections) + 1
    
    detection_entry = {
        "detection_id": last_detection_id,
        "session_id": result.session_id,
        "defect_type": result.defect_type,
        "confidence": result.confidence,
        "timestamp": result.timestamp.isoformat()
    }
    memory_detections.append(detection_entry)
    
    if alert_created:
        os.makedirs("images/alerts", exist_ok=True)
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
                
        alert_entry = {
            "detection_id": last_detection_id,
            "image_path": db_image_path,
            "timestamp": result.timestamp.isoformat(),
            "defect_type": result.defect_type,
            "confidence": result.confidence
        }
        memory_alerts.append(alert_entry)
        
        background_tasks.add_task(send_telegram_alert, result.defect_type, result.confidence)
        
        alert_data = {
            "type": "NEW_ALERT",
            "defect_type": result.defect_type,
            "confidence": result.confidence,
            "timestamp": result.timestamp.strftime("%H:%M:%S")
        }
        await manager.broadcast(alert_data)
        
    return {
        "status": "success", 
        "action": "alert_created" if alert_created else "ignored",
        "detection_id": last_detection_id
    }

@app.get("/api/recent-alerts")
async def get_recent_alerts():
    high_conf_alerts = [d for d in memory_detections if d["confidence"] > 0.85]
    sorted_alerts = sorted(high_conf_alerts, key=lambda x: x["timestamp"], reverse=True)[:5]
    return {"status": "success", "alerts": sorted_alerts}
    
@app.get("/api/history-data")
async def get_history_data():
    events = []
    for a in sorted(memory_alerts, key=lambda x: x["timestamp"], reverse=True)[:50]:
        events.append({
            "timestamp": a["timestamp"],
            "snapshot_url": a["image_path"],
            "defect_type": a["defect_type"],
            "confidence": a["confidence"],
            "layer_id": f"#{a['detection_id']}"
        })
    return {"status": "success", "events": events}

os.makedirs("images/alerts", exist_ok=True)
app.mount("/images", StaticFiles(directory="images"), name="images")
app.mount("/", StaticFiles(directory="script"), name="static")