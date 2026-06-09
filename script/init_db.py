import sqlite3
from passlib.context import CryptContext

# Password encryption
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# create the file directly in the project folder.
conn = sqlite3.connect("print_guard.db")
cursor = conn.cursor()

# Enabling foreign keys
conn.execute("PRAGMA foreign_keys = ON;")

# Delete old tables if they exist
cursor.executescript("""
DROP TABLE IF EXISTS "alerts";
DROP TABLE IF EXISTS "detections";
DROP TABLE IF EXISTS "sessions";

-- 1. Create the system user table                     
CREATE TABLE "users" (
    "user_id"       INTEGER PRIMARY KEY AUTOINCREMENT,
    "username"      TEXT UNIQUE NOT NULL,
    "password_hash" TEXT NOT NULL
);
                                          
-- 2. Create a session table
CREATE TABLE "sessions" (
    "session_id"    INTEGER PRIMARY KEY AUTOINCREMENT,
    "start_time"    TEXT,
    "printer_name"  TEXT,
    "filament_type" TEXT
);

-- 3. Creating a detection table
CREATE TABLE "detections" (
    "detection_id"  INTEGER PRIMARY KEY AUTOINCREMENT,
    "session_id"    INTEGER,
    "defect_type"   TEXT,
    "confidence"    REAL,
    "timestamp"     TEXT,
    FOREIGN KEY("session_id") REFERENCES "sessions" ("session_id")
);

-- 4. Create an alert table
CREATE TABLE "alerts" (
    "alert_id"      INTEGER PRIMARY KEY AUTOINCREMENT,
    "detection_id"  INTEGER,
    "image_path"    TEXT,
    FOREIGN KEY("detection_id") REFERENCES "detections" ("detection_id")
);
""")

# Create the first dynamic administrator (Admin) user for the system
default_username = "admin"
default_password = "admin123"
hashed_password = pwd_context.hash(default_password)

cursor.execute('''
               INSERT INTO users (username, password_hash)
               VALUES (?,?)''',(default_username, hashed_password))
conn.commit()
conn.close()
print("Database 'print_guard.db' initialized successfully!")