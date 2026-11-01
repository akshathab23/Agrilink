import unittest
import tempfile
import shutil
import sqlite3
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
import app as flask_app

class AgriLinkWorkflowIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp()
        cls.test_db = Path(cls.test_dir) / "agrilink_workflow_test.db"
        live_db = Path(__file__).resolve().parent.parent / "data" / "agrilink.db"
        shutil.copy2(live_db, cls.test_db)
        flask_app.DB_PATH = cls.test_db
        flask_app.app.config['TESTING'] = True
        cls.client = flask_app.app.test_client()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_complete_farmer_centre_buyer_workflow(self):
        """End-to-End Test: Farmer -> Centre QA -> Farmer QA Verification -> Centre Price Verification -> Buyer Offer -> Farmer Accept"""
        # 1. Register Farmer
        f_reg = self.client.post("/api/register", json={
            "role": "Farmer", "name": "Vikas Shinde", "phone": "9123456780",
            "password": "FarmerPassword#1", "state": "Maharashtra", "district": "Pune", "village": "Manchar"
        })
        self.assertEqual(f_reg.status_code, 201)
        f_token = self.client.post("/api/login", json={"phone": "9123456780", "password": "FarmerPassword#1"}).get_json()["token"]

        # 2. Farmer creates produce listing
        # Should be initially 'Awaiting Village Centre Verification' and NOT visible to buyers
        f_create = self.client.post("/api/listings", json={
            "commodity": "Onion", "quantity": 80.0, "expected_price": 2200.0, "timeline": "2026-11-15"
        }, headers={"Authorization": f"Bearer {f_token}"})
        self.assertEqual(f_create.status_code, 201)
        listing_id = f_create.get_json()["listing_id"]

        # 3. Register Buyer
        b_reg = self.client.post("/api/register", json={
            "role": "Buyer", "name": "Maha Agri Traders", "phone": "9123456781",
            "password": "BuyerPassword#1", "state": "Maharashtra", "district": "Pune"
        })
        self.assertEqual(b_reg.status_code, 201)
        b_token = self.client.post("/api/login", json={"phone": "9123456781", "password": "BuyerPassword#1"}).get_json()["token"]

        # 4. Buyer cannot see unverified listing
        b_listings = self.client.get("/api/listings", headers={"Authorization": f"Bearer {b_token}"}).get_json()
        self.assertNotIn(listing_id, [l["id"] for l in b_listings])

        # 5. Buyer cannot make offer on unverified listing
        b_bad_offer = self.client.post("/api/offers", json={
            "listing_id": listing_id, "offered_price": 2300.0, "quantity": 40.0
        }, headers={"Authorization": f"Bearer {b_token}"})
        self.assertEqual(b_bad_offer.status_code, 400)
        self.assertIn("centre verified", b_bad_offer.get_json()["error"].lower())

        # 6. Village Centre Operator inspects and records quality assessment
        op_token = self.client.post("/api/login", json={"phone": "9999999999", "password": "password123"}).get_json()["token"]
        qa_res = self.client.post("/api/quality-assessments", json={
            "listing_id": listing_id, "moisture_pct": 10.0, "foreign_matter_pct": 0.5,
            "damaged_pct": 1.0, "final_grade": "Grade A", "assessor_name": "Ramesh Patil"
        }, headers={"Authorization": f"Bearer {op_token}"})
        self.assertEqual(qa_res.status_code, 201)

        # 7. Farmer verifies recorded quality measurements
        verif_res = self.client.patch(f"/api/listings/{listing_id}", json={
            "quality_verified_by_farmer": 1
        }, headers={"Authorization": f"Bearer {f_token}"})
        self.assertEqual(verif_res.status_code, 200)

        # 8. Village Centre Operator performs transparent price calculation and verifies listing
        price_verif = self.client.patch(f"/api/listings/{listing_id}", json={
            "transport_cost": 70.0, "labour_cost": 30.0, "centre_operating_cost": 20.0,
            "centre_margin": 20.0, "verified_viable_price": 2340.0, "market_reference_price": 2400.0,
            "status": "Centre Verified"
        }, headers={"Authorization": f"Bearer {op_token}"})
        self.assertEqual(price_verif.status_code, 200)

        # 9. Now Buyer CAN discover the listing
        b_listings_now = self.client.get("/api/listings", headers={"Authorization": f"Bearer {b_token}"}).get_json()
        self.assertIn(listing_id, [l["id"] for l in b_listings_now])

        # 10. Buyer submits purchase offer
        offer_res = self.client.post("/api/offers", json={
            "listing_id": listing_id, "offered_price": 2350.0, "quantity": 80.0,
            "pickup_preference": "Buyer Arranges Transport", "validity_date": "2026-11-20"
        }, headers={"Authorization": f"Bearer {b_token}"})
        self.assertEqual(offer_res.status_code, 201)
        offer_id = offer_res.get_json()["offer_id"]

        # 11. Buyer cannot accept/reject the offer
        b_accept = self.client.patch(f"/api/offers/{offer_id}", json={"status": "Accepted"}, headers={"Authorization": f"Bearer {b_token}"})
        self.assertEqual(b_accept.status_code, 403)

        # 12. Operator cannot accept/reject the offer
        op_accept = self.client.patch(f"/api/offers/{offer_id}", json={"status": "Accepted"}, headers={"Authorization": f"Bearer {op_token}"})
        self.assertEqual(op_accept.status_code, 403)

        # 13. Only the owning Farmer can Accept the offer
        f_accept = self.client.patch(f"/api/offers/{offer_id}", json={"status": "Accepted"}, headers={"Authorization": f"Bearer {f_token}"})
        self.assertEqual(f_accept.status_code, 200)

        # 14. Listing is marked as 'Sold'
        conn = sqlite3.connect(self.test_db)
        status = conn.execute("SELECT status FROM farmer_listings WHERE id = ?", (listing_id,)).fetchone()[0]
        offer_status = conn.execute("SELECT status FROM buyer_offers WHERE id = ?", (offer_id,)).fetchone()[0]
        conn.close()
        self.assertEqual(status, "Sold")
        self.assertEqual(offer_status, "Accepted")

if __name__ == "__main__":
    unittest.main()
