import sqlite3

# ניצור את הקובץ ישירות בתיקיית הפרויקט
conn = sqlite3.connect("print_guard.db")
cursor = conn.cursor()

# הפעלת מפתחות זרים
conn.execute("PRAGMA foreign_keys = ON;")

# מחיקת טבלאות ישנות אם קיימות
cursor.executescript("""
DROP TABLE IF EXISTS "alerts";
DROP TABLE IF EXISTS "detections";
DROP TABLE IF EXISTS "sessions";

-- 1. יצירת טבלת סשנים
CREATE TABLE "sessions" (
    "session_id"    INTEGER PRIMARY KEY AUTOINCREMENT,
    "start_time"    TEXT,
    "printer_name"  TEXT,
    "filament_type" TEXT
);

-- 2. יצירת טבלת זיהויים
CREATE TABLE "detections" (
    "detection_id"  INTEGER PRIMARY KEY AUTOINCREMENT,
    "session_id"    INTEGER,
    "defect_type"   TEXT,
    "confidence"    REAL,
    "timestamp"     TEXT,
    FOREIGN KEY("session_id") REFERENCES "sessions" ("session_id")
);

-- 3. יצירת טבלת התראות
CREATE TABLE "alerts" (
    "alert_id"      INTEGER PRIMARY KEY AUTOINCREMENT,
    "detection_id"  INTEGER,
    "image_path"    TEXT,
    FOREIGN KEY("detection_id") REFERENCES "detections" ("detection_id")
);
""")

conn.commit()
conn.close()
print("Database 'print_guard.db' initialized successfully!")