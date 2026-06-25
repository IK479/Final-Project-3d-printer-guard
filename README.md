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

---

## 🛠️ Hardware Requirements & Topology

### 1. Embedded Components

| Component             | Requirement                                                       |
| --------------------- | ----------------------------------------------------------------- |
| **SBC**               | Raspberry Pi 4, 4GB/8GB, or Raspberry Pi 5                        |
| **Operating System**  | Raspberry Pi OS 64-bit                                            |
| **Camera**            | Raspberry Pi Camera Module via CSI ribbon or standard USB webcam  |
| **Network**           | Local Wi-Fi or Ethernet connection                                |
| **Printer Interface** | Local connection to OctoPrint, Klipper, or compatible printer API |

The camera should be mounted on the 3D printer frame and positioned toward the build plate to provide a clear view of the printed object and extrusion area.

---

## ⚙️ Hardware-Level Optimizations

To prevent unnecessary CPU load, reduce thermal throttling, and improve runtime stability on Raspberry Pi hardware, PrintGuard includes several edge-level optimizations.

### Resolution and FPS Capping

Frame acquisition is fixed to:

```text
640x640 @ 15 FPS
```

This resolution is selected to balance real-time inference speed with sufficient visual quality for defect detection.

### Luminance Guard — Edge-Save Mode

Before running the YOLO inference cycle, the system performs a lightweight brightness check on each frame.

If the average frame brightness drops below the defined threshold:

```text
μ < 15
```

the system identifies one of the following possible conditions:

* Covered or occluded camera
* Poor lighting
* Camera failure
* Possible power or visibility issue

In this case, PrintGuard bypasses the heavy YOLO inference cycle to preserve CPU resources and reduce unnecessary thermal load.

---

## 💻 Software Installation & Deployment on Raspberry Pi

Follow the steps below directly from the Raspberry Pi terminal, either through SSH or the desktop terminal.

---

### 1. Update System Dependencies

Install the native system libraries required for OpenCV, NumPy, and ONNX Runtime on ARM64.

```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y python3-pip python3-venv python3-dev \
                    libgl1-mesa-glx libglib2.0-0 \
                    libgfortran5 libatlas-base-dev
```

---

### 2. Clone the Repository

```bash
git clone https://github.com/EmilyMyaskovski/3d-print-defect-detect.git
cd 3d-print-defect-detect
```

---

### 3. Create an Isolated Virtual Environment

Create a local Python virtual environment to avoid conflicts with system-level packages.

```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 4. Install Python Dependencies

Upgrade the Python package manager and install the project dependencies.

```bash
pip install --upgrade pip setuptools wheel
pip install ultralytics fastapi uvicorn pydantic requests python-dotenv
```

> **Note:**
> The exported ONNX model is designed for efficient CPU inference on ARM-based Raspberry Pi hardware.

---

### 5. Configure Local Environment Variables

Create a `.env` file in the project root directory.

```bash
nano .env
```

Add the following configuration:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
PRINTER_API_URL=http://your-3d-printer-local-ip
PRINTER_API_KEY=your_printer_octoprint_or_klipper_api_key
```

---

### 6. Initialize the Local Database

Build the local database schema for session storage, detection indexing, telemetry logging, and automated data purging.

```bash
python3 -c "from database import init_db; init_db()"
```

---

## 🚀 Running the Production Server

To allow access from any device on the same local network, run the FastAPI server on all available network interfaces.

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Network Access

| Device                          | URL                                      |
| ------------------------------- | ---------------------------------------- |
| Raspberry Pi locally            | `http://127.0.0.1:8000/`                 |
| Laptop or phone on same network | `http://<RASPBERRY_PI_IP_ADDRESS>:8000/` |

---

## 🎛️ Optional: Run as a Background Service

To make PrintGuard start automatically whenever the Raspberry Pi powers on, create a `systemd` service.

### 1. Create the Service File

```bash
sudo nano /etc/systemd/system/printguard.service
```

### 2. Paste the Service Configuration

```ini
[Unit]
Description=PrintGuard Real-Time AI Defect Detection Service
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/3d-print-defect-detect
ExecStart=/home/pi/3d-print-defect-detect/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 3. Enable and Start the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable printguard.service
sudo systemctl start printguard.service
```

### 4. Check Service Status

```bash
sudo systemctl status printguard.service
```

---

## 📂 Project Module Index

| File                      | Description                                                                                |
| ------------------------- | ------------------------------------------------------------------------------------------ |
| `main.py`                 | Core FastAPI router, WebSocket pipeline, data serving, and background cleanup tasks        |
| `inference.py`            | Camera handling, brightness safety checks, frame processing, and YOLOv11 inference mapping |
| `notification_service.py` | Telegram alert delivery, asynchronous notification stream, and remote emergency actions    |
| `database.py`             | SQLite storage layer, detection history, session records, and telemetry logging            |

---

## 🔔 Alerting and Emergency Response

PrintGuard supports automated remote alerts through Telegram.

When a critical defect is detected, the system can:

* Send real-time Telegram notifications
* Include detection confidence and timestamp
* Trigger remote emergency-stop actions
* Store the event in the local database
* Display the alert in the live dashboard through WebSocket updates

---

## 🧹 Data Retention Policy

The system includes automated local cleanup logic to prevent uncontrolled database growth on Raspberry Pi storage.

By default, detection records and telemetry logs are retained for:

```text
30 days
```

Older records are automatically purged during scheduled cleanup cycles.

---

## 👥 Project Development Group

**Emily Myaskovsksi** B.Sc. Computer Science Academic Project Academic Year: **2025–2026**<br>
**Ido Katz** B.Sc. Computer Science Academic Project Academic Year: **2025–2026**

---

## 📄 License

This project was developed as part of an academic final project.
Usage, modification, and distribution should follow the academic and institutional guidelines of the project owners.
