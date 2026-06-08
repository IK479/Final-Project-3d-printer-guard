import cv2
import time
import requests
from datetime import datetime
from ultralytics import YOLO

from database import get_db_connection

# 1. Loading the trained model
MODEL_PATH = "model/best.onnx"
try:
    model = YOLO(MODEL_PATH)
    print(f"[System] YOLO Model loaded successfully from {MODEL_PATH}")
except Exception as e:
    print(f"[System] Critical Error loading YOLO model: {e}")
    model = None

# Variables for managing the physical camera
last_alert_time = 0
camera_active = False
cap = None

# Global variables for telemetry
current_fps = 0.0
current_inference_time = 0.0
current_alert_threshold = 0.85 # default

# The address of the FastAPI server
API_ENDPOINT = "http://127.0.0.1:8000/internal/detection"

# Helper function to pull the last active session
def get_active_session_id():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT session_id FROM sessions ORDER BY session_id DESC LIMIT 1")
        row = cursor.fetchone()
        return row[0] if row else 1
    
def generate_video_frames():
    global last_alert_time, camera_active, cap, current_fps, current_inference_time
    # Direct hardware connection
    # 0 represents the camera connected via USB or the board's camera port
    if cap is None or not cap.isOpened():
        cap = cv2.VideoCapture(0)
        
    if not cap.isOpened():
        print("Hardware Error: Camera not detected.")
        return

    camera_active = True
    print("Hardware camera streaming started...")

    while camera_active:
        loop_start = time.time()
        success, frame = cap.read()
        if not success:
            print("Warning: Dropped frame from hardware.")
            break

        # 1. Hard resolution change to 640x640
        frame_resized = cv2.resize(frame, (640, 640))
        # 2. Convert color channels from OpenCV's BGR format to RGB format for the model
        frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)

        # --- Inference phase vs. YOLO model ---
        if model is not None:
            inf_start = time.time() # Start loop time measurement (FPS)
            #Transfer the frame to the model adapted to the three classes (Normal, Spaghetti, Stringing)
            results = model(frame_rgb, verbose=False)

            # Calculate the time taken by the model (in milliseconds)
            current_inference_time = (time.time() - inf_start) * 1000
            # Extracting the coordinates of the bounding square for drawing
            annotated_frame = results[0].plot()

            highest_conf = 0.0
            defect_type = "Normal"
            
            for box in results[0].boxes:
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = model.names[cls_id]
                
                if label != "Normal" and conf > highest_conf:
                    highest_conf = conf
                    defect_type = label
                    
            # --- Alerting Engine Phase ---
            # Uses the dynamic security threshold that the user defined in the settings screen
            # Overflow prevention mechanism: sends an alert only once every 10 seconds even if there is a sequence of detections
            if highest_conf > current_alert_threshold and (time.time() - last_alert_time > 10):
                last_alert_time = time.time()
                # Pulling the active session securely directly from the database
                active_session = get_active_session_id()
                payload = {
                    "session_id": active_session,
                    "defect_type": defect_type,
                    "confidence": highest_conf,
                    "timestamp": datetime.now().isoformat()
                }
                
                try:
                    requests.post("http://127.0.0.1:8000/internal/detection", json=payload, timeout=2)
                except Exception as e:
                    print(f"Failed to trigger alert: {e}")
        else:
            annotated_frame = frame_resized

        time_diff = time.time() - loop_start
        if time_diff > 0:
            current_fps = 1.0 / time_diff
        # Encoding the processed frame to JPEG for streaming in the Web interface
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

if cap is not None:
        cap.release()
        cap = None