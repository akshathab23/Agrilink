import os
import sqlite3
import pandas as pd
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "data" / "agrilink.db"))
CSV_PATH = Path(os.environ.get("CSV_PATH", BASE_DIR / "data" / "raw" / "agmarknet_sample.csv"))
SCHEMA_PATH = BASE_DIR / "schema.sql"

def init_db(db_path=None):
    target_db = Path(db_path) if db_path else DB_PATH
    print(f"Initializing database schema at {target_db}...")
    target_db.parent.mkdir(parents=True, exist_ok=True)
    
    with sqlite3.connect(target_db) as conn:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
    print("Database schema verified successfully.")

def load_and_clean_data():
    print(f"Reading CSV from {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)
    original_rows = len(df)
    
    print("\n--- Data Cleaning Process ---")
    print(f"Original row count: {original_rows}")
    
    # 1. Validate Columns
    expected_cols = ["State", "District", "Market", "Commodity", "Variety", "Grade", "Arrival_Date", "Min_Price", "Max_Price", "Modal_Price"]
    missing_cols = [col for col in expected_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing expected columns in CSV: {missing_cols}")

    # 2. Handle duplicates
    df_cleaned = df.drop_duplicates()
    duplicates_removed = original_rows - len(df_cleaned)
    print(f"Duplicates removed: {duplicates_removed}")

    # 3. Handle Missing Values
    # We drop rows without a Modal_Price since it's the core metric we track
    missing_prices_before = df_cleaned['Modal_Price'].isnull().sum()
    df_cleaned = df_cleaned.dropna(subset=['Modal_Price'])
    print(f"Rows dropped due to missing Modal_Price: {missing_prices_before}")

    # Fill missing Variety and Grade
    df_cleaned['Variety'] = df_cleaned['Variety'].fillna('Other')
    df_cleaned['Grade'] = df_cleaned['Grade'].fillna('FAQ')
    
    # Ensure Min and Max prices exist, fill with Modal if missing
    df_cleaned['Min_Price'] = df_cleaned['Min_Price'].fillna(df_cleaned['Modal_Price'])
    df_cleaned['Max_Price'] = df_cleaned['Max_Price'].fillna(df_cleaned['Modal_Price'])

    # 4. Convert Dates
    df_cleaned['Arrival_Date'] = pd.to_datetime(df_cleaned['Arrival_Date'], format="%d/%m/%Y").dt.strftime('%Y-%m-%d')

    # 5. Numeric validations (ensure prices are float/int)
    for col in ['Min_Price', 'Max_Price', 'Modal_Price']:
        df_cleaned[col] = pd.to_numeric(df_cleaned[col], errors='coerce')
    
    df_cleaned = df_cleaned.dropna(subset=['Modal_Price', 'Min_Price', 'Max_Price'])
    final_rows = len(df_cleaned)
    print(f"Final records to load: {final_rows}")
    print("-----------------------------\n")
    
    return df_cleaned, original_rows, duplicates_removed, final_rows

def populate_database(df, db_path=None, clear_existing=False):
    target_db = Path(db_path) if db_path else DB_PATH
    print(f"Connecting to database {target_db} to insert records...")
    with sqlite3.connect(target_db) as conn:
        cursor = conn.cursor()
        
        # Insert unique markets
        markets_df = df[['State', 'District', 'Market']].drop_duplicates()
        
        # Use executemany with OR IGNORE to handle existing markets gracefully
        cursor.executemany(
            '''INSERT OR IGNORE INTO markets (state, district, market_name) 
               VALUES (?, ?, ?)''',
            markets_df.itertuples(index=False, name=None)
        )
        
        # Fetch market IDs to map them to prices
        cursor.execute("SELECT id, state, district, market_name FROM markets")
        market_rows = cursor.fetchall()
        
        # Create a mapping dict for fast lookup: (state, district, market) -> id
        market_map = {(row[1], row[2], row[3]): row[0] for row in market_rows}
        
        # Map market_id to the main dataframe
        df['market_id'] = df.apply(lambda row: market_map.get((row['State'], row['District'], row['Market'])), axis=1)
        
        # Prepare prices data
        prices_data = df[['market_id', 'Commodity', 'Variety', 'Grade', 'Arrival_Date', 'Min_Price', 'Max_Price', 'Modal_Price']]
        
        # Clear existing prices ONLY if explicitly requested
        if clear_existing:
            cursor.execute("DELETE FROM market_prices")
        
        # Insert prices
        cursor.executemany(
            '''INSERT INTO market_prices (market_id, commodity, variety, grade, arrival_date, min_price, max_price, modal_price)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            prices_data.itertuples(index=False, name=None)
        )
        
        conn.commit()
    print("Data successfully loaded into SQLite database.")

def seed_dataset_if_empty(db_path=None, force=False):
    """
    Safely seeds the original agricultural dataset only when market_prices is empty.
    If market_prices already has records, skips loading to prevent unnecessary startup delays.
    Never modifies or touches farmer, buyer, listing, offer, or user account tables.
    """
    target_db = Path(db_path) if db_path else DB_PATH
    init_db(target_db)
    
    with sqlite3.connect(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM market_prices")
        count = cursor.fetchone()[0]
        
    if count > 0 and not force:
        print(f"==> Database at {target_db} already contains {count:,} market price records. Skipping seed.")
        return False
        
    if not CSV_PATH.exists():
        print(f"WARNING: Agricultural dataset not found at {CSV_PATH}. Cannot seed market prices.")
        return False
        
    print(f"==> market_prices table is empty. Loading dataset from {CSV_PATH}...")
    cleaned_df, orig_rows, dupes_removed, final_rows = load_and_clean_data()
    populate_database(cleaned_df, db_path=target_db, clear_existing=force)
    print(f"==> Successfully initialized {final_rows:,} market price records.")
    return True

if __name__ == "__main__":
    import sys
    force_reload = "--force" in sys.argv
    seed_dataset_if_empty(force=force_reload)
