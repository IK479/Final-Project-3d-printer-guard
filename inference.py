import cv2
import time
import requests
import base64
from datetime import datetime
from ultralytics import YOLO
from database import get_db_connection

# 1. טעינת המודל - משתמש ב-ONNX המותאם ל-Pi 5
MODEL_PATH = "model/best.onnx"
try:
    model = YOLO(MODEL_PATH, task="detect")
    print(f"[System] YOLO Model loaded successfully from {MODEL_PATH}")
except Exception as e:
    print(f"[System] Critical Error loading YOLO model: {e}")
    model = None

# משתני טלמטריה גלובליים
current_fps = 0.0
current_inference_time = 0.0
current_alert_threshold = 0.85  # ברירת מחדל
last_alert_time = 0.0
cap = None
latest_annotated_frame = None  # הפריים המעובד שמוזרק לדף ה-Web

# הכתובת של שרת ה-FastAPI המקומי
API_ENDPOINT = "http://127.0.0.1:8000/internal/detection"

def get_active_session_id():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT session_id FROM sessions ORDER BY session_id DESC LIMIT 1")
            row = cursor.fetchone()
            return row[0] if row else 1
    except Exception:
        return 1
    
def run_inference_loop():
    """הלולאה המרכזית שרצה ברקע בשרת ומעבדת את הפריימים עם אופטימיזציית גנרטור"""
    global last_alert_time, cap, current_fps, current_inference_time, latest_annotated_frame
    
    if cap is None or not cap.isOpened():
        # שימוש מפורש בדרייבר V4L2 של ה-Pi 5 למניעת מסך שחור
        cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        
    if not cap.isOpened():
        print("[Hardware Error] Camera not detected via V4L2 on index 0.")
        return

    # הגדרות רזולוציה קלות לשיפור ה-FPS ב-Raspberry Pi
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 15)
    print("[Hardware] Camera hardware & YOLO pipeline activated successfully.")

    while cap is not None and cap.isOpened():
        loop_start = time.time()
        success, frame = cap.read()
        if not success:
            time.sleep(0.01)
            continue

        # התאמת גודל קלט קבוע ל-YOLO
        frame_resized = cv2.resize(frame, (640, 640))
        
        # מנגנון הגנה מפני חושך או מצלמה מכוסה
        gray_frame = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)
        mean_brightness = cv2.mean(gray_frame)[0]

        if mean_brightness < 15:
            annotated_frame = frame_resized.copy()
            cv2.putText(annotated_frame, "WARNING: CAMERA COVERED / NO SIGNAL", 
                        (40, 320), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3, cv2.LINE_AA)
            current_inference_time = 0.0   
        else:     
            if model is not None:
                inf_start = time.time()
                
                # שימוש ב-stream=True לחסכון אדיר בזיכרון (RAM) על ה-Pi
                results = model(frame_resized, stream=True, verbose=False)

                highest_conf = 0.0
                defect_type = "Normal"
                annotated_frame = frame_resized.copy()
                
                # שליפת התוצאות מתוך ה-Generator של הסטרים
                for result in results:
                    annotated_frame = result.plot()
                    
                    for box in result.boxes:
                        conf = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        label = model.names[cls_id]
                    
                        if label != "Normal" and conf > highest_conf:
                            highest_conf = conf
                            defect_type = label
                
                current_inference_time = (time.time() - inf_start) * 1000
                    
                # --- מנגנון שליחת התראות לשרת המקומי ---
                if highest_conf > current_alert_threshold and (time.time() - last_alert_time > 10):
                    last_alert_time = time.time()
                    active_session = get_active_session_id()
                    
                    _, buffer = cv2.imencode('.jpg', annotated_frame)
                    image_b64 = base64.b64encode(buffer).decode('utf-8')
                    
                    payload = {
                        "session_id": active_session,
                        "defect_type": defect_type,
                        "confidence": highest_conf,
                        "timestamp": datetime.now().isoformat(),
                        "image_base64": image_b64
                    }
                    
                    try:
                        print(f"[Alert Engine] Defect detected: {defect_type} ({highest_conf*100:.1f}%)")
                        
                        # שליחה אמינה החוצה אל שרת ה-FastAPI מתוך ה-Thread
                        requests.post(API_ENDPOINT, json=payload, timeout=0.5)
                    except Exception as e:
                        print(f"Failed to sync alert to local server: {e}")
            else:
                annotated_frame = frame_resized

        # עדכון הפריים הגלובלי שה-StreamingResponse של main.py קורא ושולח לדפדפן
        latest_annotated_frame = annotated_frame.copy()

        # חישוב ה-FPS האמיתי של הלולאה
        time_diff = time.time() - loop_start
        if time_diff > 0:
            current_fps = 1.0 / time_diff
            
        time.sleep(0.01)

def generate_video_frames():
    """מזרים את הפריימים המעובדים בפורמט multipart/x-mixed-replace ישירות לתגית ה-img בדפדפן"""
    global latest_annotated_frame
    while True:
        if latest_annotated_frame is not None:
            ret, buffer = cv2.imencode('.jpg', latest_annotated_frame)
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.05)  # הגבלת קצב רענון ה-Stream ב-Web ל-20 FPS כדי לחסוך רוחב פס רשת

def release_camera():
    global cap, latest_annotated_frame
    if cap is not None:
        cap.release()
        cap = None
        latest_annotated_frame = None
        print("[Hardware] Camera hardware released safely.")