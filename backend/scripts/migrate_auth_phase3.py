import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).parent.parent / "data" / "agrilink.db"))

def run_migration(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Ensure users table exists with proper unique constraints
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Check if email column exists in users (idempotent addition)
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [c[1] for c in cursor.fetchall()]
    if 'email' not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
        # Add unique index if not present
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL")
        
    # 2. Add user_id to farmers and buyers if missing
    for table in ['farmers', 'buyers']:
        cursor.execute(f"PRAGMA table_info({table})")
        cols = [c[1] for c in cursor.fetchall()]
        if 'user_id' not in cols:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id)")
            
    # 3. Add user_id or operator_user_id to village_centres
    cursor.execute("PRAGMA table_info(village_centres)")
    vc_cols = [c[1] for c in cursor.fetchall()]
    if 'operator_user_id' not in vc_cols:
        cursor.execute("ALTER TABLE village_centres ADD COLUMN operator_user_id INTEGER REFERENCES users(id)")
        
    # 4. Add village_centre_id to farmer_listings so listings can be scoped to a centre
    cursor.execute("PRAGMA table_info(farmer_listings)")
    fl_cols = [c[1] for c in cursor.fetchall()]
    if 'village_centre_id' not in fl_cols:
        cursor.execute("ALTER TABLE farmer_listings ADD COLUMN village_centre_id INTEGER REFERENCES village_centres(id)")

    # 5. Create user_sessions table for server-side token/session tracking and revocation
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            is_revoked INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(token)")

    # 6. Ensure default village centre exists for testing/operations if none exist
    cursor.execute("SELECT COUNT(*) FROM village_centres")
    if cursor.fetchone()[0] == 0:
        # Find existing village centre user if any (user_id 3 is Village Centre)
        cursor.execute("SELECT id FROM users WHERE role = 'Village Centre' LIMIT 1")
        vc_user = cursor.fetchone()
        vc_user_id = vc_user[0] if vc_user else None
        
        cursor.execute('''
            INSERT INTO village_centres (name, operator_name, state, district, phone, operator_user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('Khed Main Collection Centre', 'Ramesh Patil', 'Maharashtra', 'Pune', '9999999999', vc_user_id))
        
        default_vc_id = cursor.lastrowid
        # Update existing farmer_listings to link to this centre
        cursor.execute("UPDATE farmer_listings SET village_centre_id = ? WHERE village_centre_id IS NULL", (default_vc_id,))
    else:
        # Link any unlinked village centre user
        cursor.execute("SELECT id FROM users WHERE role = 'Village Centre' LIMIT 1")
        vc_user = cursor.fetchone()
        if vc_user:
            cursor.execute("UPDATE village_centres SET operator_user_id = ? WHERE operator_user_id IS NULL", (vc_user[0],))

    # 7. Create auth_rate_limits table for persistent multi-worker rate limiting
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auth_rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_ip TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rate_limits ON auth_rate_limits(client_ip, endpoint, attempt_time)")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    run_migration()
