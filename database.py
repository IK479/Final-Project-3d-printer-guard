import sqlite3

# Setting the DB path relative to the project folder
DB_FILE = "print_guard.db"

current_session_id= None # Variable to store the active session ID

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn