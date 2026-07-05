

https://github.com/user-attachments/assets/0afb983c-44a3-4230-bac7-7b8ac427039a


# PrintGuard: AI-Based Real-Time Defect Detection on Raspberry Pi

![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)
![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%204%2F5-C51A4A?logo=raspberry-pi)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![YOLO](https://img.shields.io/badge/YOLO-v11--ONNX-yellow)

---

## 📌 Abstract / Overview

**PrintGuard**, also known as **Aegis Print Guard**, is an edge-optimized, real-time AI monitoring system designed to automatically detect and mitigate 3D printing defects directly on a Raspberry Pi.

Developed as a **Bachelor's Degree Final Project in Computer Science** for the academic year **2025–2026**, the system uses a custom-trained **YOLOv11 ONNX model** optimized for embedded ARM architectures.

The system detects critical extrusion-related failures such as:

* **Spaghetti defects**
* **Stringing defects**
* Camera occlusion or poor lighting conditions

PrintGuard runs locally on the Raspberry Pi without relying on external cloud computing. It combines a lightweight **FastAPI backend**, an optimized **OpenCV frame-processing loop**, a WebSocket-based dashboard, and automated **Telegram alerts** with interactive emergency-stop triggers.


| File                      | Description                                                                                |
| ------------------------- | ------------------------------------------------------------------------------------------ |
| `main.py`                 | Core FastAPI router, WebSocket pipeline, data serving, and background cleanup tasks        |
| `inference.py`            | Camera handling, brightness safety checks, frame processing, and YOLOv11 inference mapping |
| `notification_service.py` | Telegram alert delivery, asynchronous notification stream, and remote emergency actions    |
| `database.py`             | SQLite storage layer, detection history, session records, and telemetry logging            |


## 👥 Project Development Group
**Emily Myaskovsksi** B.Sc. Computer Science Academic Project Academic Year: **2025–2026**<br>
**Ido Katz** B.Sc. Computer Science Academic Project Academic Year: **2025–2026**

---

## 📄 License
This project was developed as part of an academic final project.
