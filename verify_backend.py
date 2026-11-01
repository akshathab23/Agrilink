import sqlite3
import json
from pathlib import Path
import sys

# Ensure backend can be imported
sys.path.append(str(Path(__file__).parent.parent.absolute()))
from backend.app import app

db_path = Path("backend/data/agrilink.db")

print("="*60)
print("SQLITE DATABASE VERIFICATION")
print("="*60)
try:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 1. market_prices count
    c.execute("SELECT COUNT(*) FROM market_prices")
    prices_count = c.fetchone()[0]
    print(f"Records in 'market_prices': {prices_count} (Expected: 99850)")
    
    # 2. markets count
    c.execute("SELECT COUNT(*) FROM markets")
    markets_count = c.fetchone()[0]
    print(f"Records in 'markets'      : {markets_count}")
    
    # Check some sample markets
    c.execute("SELECT state, district, market_name FROM markets LIMIT 3")
    sample_markets = c.fetchall()
    print(f"Sample unique markets     : {sample_markets}")
    
    # 3. NULL checks
    null_query = '''SELECT COUNT(*) FROM market_prices 
                    WHERE commodity IS NULL 
                       OR arrival_date IS NULL 
                       OR min_price IS NULL 
                       OR max_price IS NULL 
                       OR modal_price IS NULL'''
    c.execute(null_query)
    null_count = c.fetchone()[0]
    print(f"NULL values in req cols   : {null_count} (Expected: 0)")
    
    conn.close()
except Exception as e:
    print(f"Database error: {e}")


print("\n" + "="*60)
print("FLASK API ENDPOINT VERIFICATION")
print("="*60)
client = app.test_client()

def test_endpoint(name, path):
    print(f"Testing {name} ({path})...")
    resp = client.get(path)
    print(f"  HTTP Status : {resp.status_code}")
    data_text = resp.get_data(as_text=True)
    
    # Pretty print a snippet
    try:
        data_json = json.loads(data_text)
        if isinstance(data_json, list) and len(data_json) > 2:
            snippet = json.dumps(data_json[:2], indent=2) + "\n  ... (truncated list)"
        else:
            snippet = json.dumps(data_json, indent=2)
    except json.JSONDecodeError:
        snippet = data_text[:200]
        
    print(f"  Response    :\n{snippet}\n")

test_endpoint("/api/health", "/api/health")
test_endpoint("/api/markets", "/api/markets")
test_endpoint("/api/prices", "/api/prices?commodity=Tomato")
test_endpoint("/api/trends", "/api/trends?commodity=Tomato")
