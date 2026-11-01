import sqlite3
from pathlib import Path
import shutil
from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).parent.parent / "data" / "agrilink.db"
BACKUP_PATH = Path(__file__).parent.parent / "data" / "agrilink_backup_auth.db"

def migrate():
    print(f"Creating backup at {BACKUP_PATH}...")
    shutil.copy2(DB_PATH, BACKUP_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    for table in ['farmers', 'buyers']:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cursor.fetchall()]
        if 'user_id' not in columns:
            print(f"Adding user_id to {table}...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id)")
    
    default_hash = generate_password_hash("password123")
    
    cursor.execute("SELECT id, phone, name FROM farmers WHERE user_id IS NULL AND phone IS NOT NULL")
    farmers = cursor.fetchall()
    for f in farmers:
        f_id, phone, name = f
        try:
            cursor.execute("INSERT INTO users (phone, password_hash, role) VALUES (?, ?, ?)", (phone, default_hash, 'Farmer'))
            user_id = cursor.lastrowid
            cursor.execute("UPDATE farmers SET user_id = ? WHERE id = ?", (user_id, f_id))
        except sqlite3.IntegrityError:
            pass
            
    cursor.execute("SELECT id, phone, name FROM buyers WHERE user_id IS NULL AND phone IS NOT NULL")
    buyers = cursor.fetchall()
    for b in buyers:
        b_id, phone, name = b
        try:
            cursor.execute("INSERT INTO users (phone, password_hash, role) VALUES (?, ?, ?)", (phone, default_hash, 'Buyer'))
            user_id = cursor.lastrowid
            cursor.execute("UPDATE buyers SET user_id = ? WHERE id = ?", (user_id, b_id))
        except sqlite3.IntegrityError:
            pass
            
    # Optionally, create a default Village Centre Operator for testing
    try:
        cursor.execute("INSERT INTO users (phone, password_hash, role) VALUES (?, ?, ?)", ("9999999999", default_hash, 'Village Centre'))
    except sqlite3.IntegrityError:
        pass
        
    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
