import requests
import time
import sqlite3
import sys
from pathlib import Path

BASE_URL = "http://127.0.0.1:5000/api"
DB_PATH = Path(__file__).parent.parent / "data" / "agrilink.db"

def run_tests():
    print("Starting API Tests...")
    errors = []
    
    def check(name, condition, error_msg):
        if condition:
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name}: {error_msg}")
            errors.append(f"{name}: {error_msg}")

    # A. Health
    try:
        r = requests.get(f"{BASE_URL}/health")
        check("Health Check", r.status_code == 200, r.text)
    except Exception as e:
        print("Flask is not running or accessible. Start Flask first.")
        sys.exit(1)

    # B. Markets
    r = requests.get(f"{BASE_URL}/markets")
    check("Get Markets", r.status_code == 200 and len(r.json()) > 0, r.text)

    # C. Prices
    r = requests.get(f"{BASE_URL}/prices?commodity=Tomato")
    check("Get Prices", r.status_code == 200, r.text)

    # D. Trends
    r = requests.get(f"{BASE_URL}/trends?commodity=Tomato")
    check("Get Trends", r.status_code == 200, r.text)

    # E. Farmer Listings (Create)
    farmer_payload = {
        "name": "Test Farmer",
        "phone": "9999999999",
        "state": "Karnataka",
        "district": "Tumakuru",
        "village": "Test Village",
        "commodity": "Ragi",
        "quantity": 50,
        "quality_grade": "FAQ",
        "expected_price": 2500,
        "timeline": "2026-11-01"
    }
    r = requests.post(f"{BASE_URL}/listings", json=farmer_payload)
    check("Create Listing", r.status_code == 201, r.text)
    listing_id = r.json().get('listing_id')

    # F. Create Buyer
    buyer_payload = {
        "name": "Test Buyer",
        "phone": "8888888888",
        "state": "Karnataka",
        "district": "Bengaluru"
    }
    r = requests.post(f"{BASE_URL}/buyers", json=buyer_payload)
    check("Create Buyer", r.status_code == 201, r.text)
    buyer_id = r.json().get('buyer_id')

    # G. Create Buyer Requirement
    req_payload = {
        "buyer_id": buyer_id,
        "commodity": "Ragi",
        "quantity": 100,
        "min_grade": "FAQ",
        "target_price": 2600,
        "required_by": "2026-11-15",
        "pref_district": "Tumakuru"
    }
    r = requests.post(f"{BASE_URL}/buyer-requirements", json=req_payload)
    check("Create Requirement", r.status_code == 201, r.text)
    req_id = r.json().get('requirement_id')

    # H. Create Quality Assessment
    qa_payload = {
        "listing_id": listing_id,
        "moisture_pct": 12.5,
        "final_grade": "FAQ",
        "assessor_name": "Test Operator"
    }
    r = requests.post(f"{BASE_URL}/quality-assessments", json=qa_payload)
    check("Create Quality Assessment", r.status_code == 201, r.text)

    # I. Matching
    r = requests.get(f"{BASE_URL}/matches?buyer_requirement_id={req_id}")
    check("Matches", r.status_code == 200 and len(r.json()) > 0, r.text)

    # J. Price Discovery
    r = requests.get(f"{BASE_URL}/price-discovery/{listing_id}")
    check("Price Discovery", r.status_code == 200 and "synthetic" in r.json().get('data_disclaimer', '').lower(), r.text)

    # K. Create Offer
    offer_payload = {
        "buyer_id": buyer_id,
        "listing_id": listing_id,
        "offered_price": 2550,
        "quantity": 20
    }
    r = requests.post(f"{BASE_URL}/offers", json=offer_payload)
    check("Create Offer", r.status_code == 201, r.text)
    offer_id = r.json().get('offer_id')

    # Retrieve Offers
    r = requests.get(f"{BASE_URL}/offers?listing_id={listing_id}")
    check("Retrieve Offers", r.status_code == 200 and len(r.json()) > 0, r.text)

    # L. Invalid Quantity/Price validation
    bad_offer = offer_payload.copy()
    bad_offer['quantity'] = 200 # Listing only has 50
    r = requests.post(f"{BASE_URL}/offers", json=bad_offer)
    check("Reject Over Quantity Offer", r.status_code == 400, "Should have been 400")

    # M. Patch Offer to Accepted (Sets listing to Sold)
    r = requests.patch(f"{BASE_URL}/offers/{offer_id}", json={"status": "Accepted"})
    check("Patch Offer", r.status_code == 200, r.text)

    # N. Attempt Offer on Sold Listing
    r = requests.post(f"{BASE_URL}/offers", json=offer_payload)
    check("Reject Offer on Sold Listing", r.status_code == 400 and "Sold" in r.text, r.text)

    # O. Invalid Buyer ID
    bad_offer2 = offer_payload.copy()
    bad_offer2['buyer_id'] = 99999
    r = requests.post(f"{BASE_URL}/offers", json=bad_offer2)
    check("Invalid Buyer ID", r.status_code == 400, r.text)

    # Clean up DB
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM buyer_offers WHERE listing_id = ?", (listing_id,))
    cur.execute("DELETE FROM quality_assessments WHERE listing_id = ?", (listing_id,))
    cur.execute("DELETE FROM buyer_requirements WHERE id = ?", (req_id,))
    cur.execute("DELETE FROM buyers WHERE id = ?", (buyer_id,))
    cur.execute("DELETE FROM farmer_listings WHERE id = ?", (listing_id,))
    cur.execute("DELETE FROM farmers WHERE phone = '9999999999'")
    conn.commit()
    conn.close()
    print("\nCleanup completed.")
    
    if errors:
        print("\nERRORS DETECTED:")
        for e in errors: print(e)
    else:
        print("\nALL TESTS PASSED SUCCESSFULLY.")

if __name__ == "__main__":
    run_tests()
