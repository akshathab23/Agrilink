import sqlite3
from pathlib import Path
import os
import shutil

DB_PATH = Path(__file__).parent.parent / "data" / "agrilink.db"
BACKUP_PATH = Path(__file__).parent.parent / "data" / "agrilink_backup_phase4.db"

def migrate():
    print(f"Creating backup at {BACKUP_PATH}...")
    shutil.copy2(DB_PATH, BACKUP_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    columns_to_add = [
        ("quality_verified_by_farmer", "INTEGER DEFAULT 0"),
        ("transport_cost", "REAL DEFAULT 0"),
        ("labour_cost", "REAL DEFAULT 0"),
        ("centre_operating_cost", "REAL DEFAULT 0"),
        ("centre_margin", "REAL DEFAULT 0"),
        ("verified_viable_price", "REAL"),
        ("market_reference_price", "REAL")
    ]
    
    print("Checking existing columns in farmer_listings...")
    cursor.execute("PRAGMA table_info(farmer_listings)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    
    for col_name, col_def in columns_to_add:
        if col_name not in existing_columns:
            print(f"Adding column {col_name}...")
            cursor.execute(f"ALTER TABLE farmer_listings ADD COLUMN {col_name} {col_def}")
        else:
            print(f"Column {col_name} already exists. Skipping.")
            
    # Update existing 'Available' listings to 'Centre Verified' for backward compatibility,
    # or keep them as 'Available' and just update the frontend. 
    # Let's update 'Available' to 'Centre Verified' so they remain visible in the new workflow.
    print("Updating existing 'Available' statuses to 'Centre Verified'...")
    cursor.execute("UPDATE farmer_listings SET status = 'Centre Verified' WHERE status = 'Available'")
            
    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
