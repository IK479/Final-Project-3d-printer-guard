import cv2
import requests
from datetime import datetime
from ultralytics import YOLO

# 1. Loading the trained model
MODEL_PATH = "model/best.pt"
model = YOLO(MODEL_PATH)

# The address of the FastAPI server
API_ENDPOINT = "http://127.0.0.1:8000/internal/detection"
SESSION_ID = 1 # We will temporarily use a permanent session, until we dynamically pull the active session.

# Path to the test image
IMAGE_PATH = r"c:\3d-print-defect-detect\test_image.webp"

# 2. Opening the camera (0 represents the original laptop/raspberry camera)
cap = cv2.VideoCapture(0)

print("Starting Inference Service... Press 'q' to stop.")

# Reading the static image instead of the camera
frame = cv2.imread(IMAGE_PATH)
if frame is None:
    print(f"Error: Could not load image at {IMAGE_PATH}. Check if the file exists.")
else:
    while True:
        # Transferring the frame to the YOLO model
        results = model(frame, verbose=False)
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])
                defect_type = model.names[class_id]
                
                # If the security is high enough, an alert will be sent.
                if confidence > 0.80:
                    payload = {
                        "session_id": SESSION_ID,
                        "defect_type": defect_type,
                        "confidence": confidence,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    try:
                        print(f"Sending alert: {defect_type} ({confidence*100:.1f}%)")
                        requests.post(API_ENDPOINT, json=payload)
                    except requests.exceptions.ConnectionError:
                        print("Error: Could not connect to FastAPI server.")

        # Displaying the analyzed image on the screen
        annotated_frame = results[0].plot()
        cv2.imshow("Aegis Print Guard - Simulation", annotated_frame)

        # Wait 2 seconds between "frames" to avoid flooding the server, or exit by pressing q
        if cv2.waitKey(2000) & 0xFF == ord('q'):
            break

# while cap.isOpened():
#     success, frame = cap.read()
#     if not success:
#         break

#     # 3. Transferring the frame to the YOLO model
#     results = model(frame, verbose=False)
    
#     for result in results:
#         boxes = result.boxes
#         for box in boxes:
#             # Obtaining the confidence percentage and defect type from the model
#             confidence = float(box.conf[0])
#             class_id = int(box.cls[0])
#             defect_type = model.names[class_id] # 'Spaghetti' or 'Stringing'
            
#             # If the confidence is higher than 80%, a report is sent to the server
#             if confidence > 0.80:
#                 payload = {
#                     "session_id": SESSION_ID,
#                     "defect_type": defect_type,
#                     "confidence": confidence,
#                     "timestamp": datetime.now().isoformat()
#                 }
                
#                 try:
#                     # Transmitting data to the FastAPI server we created earlier
#                     requests.post(API_ENDPOINT, json=payload)
#                 except requests.exceptions.ConnectionError:
#                     print("Error: Could not connect to FastAPI server.")

#     # Displaying the video on the screen for development and testing purposes
#     annotated_frame = results[0].plot()
#     cv2.imshow("Aegis Print Guard - Camera Feed", annotated_frame)

#     if cv2.waitKey(1) & 0xFF == ord('q'):
#         break

# cap.release()
cv2.destroyAllWindows()