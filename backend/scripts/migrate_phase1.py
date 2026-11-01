import sqlite3
import shutil
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "agrilink.db"
BACKUP_PATH = BASE_DIR / "data" / f"agrilink_backup_phase1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"

def get_row_counts(cursor, tables):
    counts = {}
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            counts[table] = "Table not found"
    return counts

def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [col[1] for col in cursor.fetchall()]
    return column in columns

def migrate():
    print("="*50)
    print("PHASE 1: SAFE DATABASE MIGRATION")
    print("="*50)

    # 1. Backup
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        sys.exit(1)
        
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"[OK] Database backed up to: {BACKUP_PATH}")

    conn = sqlite3.connect(DB_PATH)
    
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    existing_tables = ['markets', 'market_prices', 'farmers', 'farmer_listings']
    
    # 2. Pre-migration checks
    print("\n[INFO] Row counts before migration:")
    pre_counts = get_row_counts(cursor, existing_tables)
    for t, c in pre_counts.items():
        print(f"  - {t}: {c}")

    # 3. Create New Tables
    new_tables_sql = """
    -- Buyers
    CREATE TABLE IF NOT EXISTS buyers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        buyer_type TEXT,
        state TEXT,
        district TEXT,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Buyer Requirements
    CREATE TABLE IF NOT EXISTS buyer_requirements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buyer_id INTEGER NOT NULL,
        commodity TEXT NOT NULL,
        quantity REAL NOT NULL,
        min_grade TEXT,
        target_price REAL,
        required_by DATE,
        pref_state TEXT,
        pref_district TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (buyer_id) REFERENCES buyers(id)
    );

    -- Buyer Offers
    CREATE TABLE IF NOT EXISTS buyer_offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buyer_id INTEGER NOT NULL,
        listing_id INTEGER NOT NULL,
        offered_price REAL NOT NULL,
        quantity REAL NOT NULL,
        pickup_preference TEXT,
        validity_date DATE,
        notes TEXT,
        status TEXT DEFAULT 'Pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (buyer_id) REFERENCES buyers(id),
        FOREIGN KEY (listing_id) REFERENCES farmer_listings(id)
    );

    -- Quality Assessments
    CREATE TABLE IF NOT EXISTS quality_assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id INTEGER NOT NULL,
        moisture_pct REAL,
        foreign_matter_pct REAL,
        damaged_pct REAL,
        size_category TEXT,
        ripeness TEXT,
        visual_damage TEXT,
        final_grade TEXT,
        assessor_name TEXT,
        assessment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (listing_id) REFERENCES farmer_listings(id)
    );

    -- Village Centres
    CREATE TABLE IF NOT EXISTS village_centres (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        operator_name TEXT,
        state TEXT,
        district TEXT,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_buyer_req_commodity ON buyer_requirements(commodity);
    CREATE INDEX IF NOT EXISTS idx_offers_listing ON buyer_offers(listing_id);
    """
    
    cursor.executescript(new_tables_sql)
    print("\n[OK] New tables created (if not existed): buyers, buyer_requirements, buyer_offers, quality_assessments, village_centres")

    # 4. Safe Table Alterations (Adding columns)
    if not column_exists(cursor, 'farmers', 'village'):
        cursor.execute("ALTER TABLE farmers ADD COLUMN village TEXT")
        print("[OK] Added 'village' column to 'farmers' table")
    else:
        print("[INFO] 'village' column already exists in 'farmers' table")

    if not column_exists(cursor, 'farmer_listings', 'status'):
        cursor.execute("ALTER TABLE farmer_listings ADD COLUMN status TEXT DEFAULT 'Available'")
        print("[OK] Added 'status' column to 'farmer_listings' table")
    else:
        print("[INFO] 'status' column already exists in 'farmer_listings' table")

    conn.commit()

    # 5. Post-migration checks
    print("\n[INFO] Row counts after migration:")
    post_counts = get_row_counts(cursor, existing_tables)
    for t, c in post_counts.items():
        print(f"  - {t}: {c}")
        if c != pre_counts[t]:
            print(f"    WARNING: Count changed for {t}!")

    new_tables = ['buyers', 'buyer_requirements', 'buyer_offers', 'quality_assessments', 'village_centres']
    new_counts = get_row_counts(cursor, new_tables)
    print("\n[INFO] New tables row counts:")
    for t, c in new_counts.items():
        print(f"  - {t}: {c}")

    conn.close()
    
    # 6. Append to schema.sql
    try:
        with open(SCHEMA_PATH, 'r') as f:
            current_schema = f.read()
        
        if "CREATE TABLE IF NOT EXISTS buyers" not in current_schema:
            with open(SCHEMA_PATH, 'a') as f:
                f.write("\n\n" + new_tables_sql)
            print("\n[OK] Appended new schema definitions to backend/schema.sql")
    except Exception as e:
        print(f"\n[WARN] Failed to append to schema.sql: {e}")

    print("\n" + "="*50)
    print("MIGRATION COMPLETE")
    print("="*50)

if __name__ == "__main__":
    migrate()
