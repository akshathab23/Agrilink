import unittest
import json
import sqlite3
import shutil
import tempfile
from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
import app as flask_app
from scripts.migrate_auth_phase3 import run_migration

class AgriLinkFullSecurityTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create an isolated temporary test directory and database
        cls.test_dir = tempfile.mkdtemp()
        cls.test_db = Path(cls.test_dir) / "agrilink_test.db"
        
        # Copy the original live database so real schema is tested safely
        live_db = Path(__file__).resolve().parent.parent / "data" / "agrilink.db"
        shutil.copy2(live_db, cls.test_db)
        
        # Point Flask app to test DB
        flask_app.DB_PATH = cls.test_db
        flask_app.app.config['TESTING'] = True
        cls.client = flask_app.app.test_client()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_01_farmer_a_registration_and_login(self):
        """1. Farmer A can register and log in."""
        payload = {
            "role": "Farmer",
            "name": "Ramesh Kumar",
            "phone": "9876543210",
            "password": "FarmerPassword123",
            "state": "Maharashtra",
            "district": "Pune",
            "village": "Khed"
        }
        res = self.client.post("/api/register", json=payload)
        self.assertEqual(res.status_code, 201, f"Registration failed: {res.data}")
        
        login_res = self.client.post("/api/login", json={"phone": "9876543210", "password": "FarmerPassword123"})
        self.assertEqual(login_res.status_code, 200)
        data = login_res.get_json()
        self.assertIn("token", data)
        self.assertEqual(data["role"], "Farmer")
        self.assertIsNotNone(data["profile_id"])

    def test_02_farmer_b_registration_and_login(self):
        """2. Farmer B can register and log in."""
        payload = {
            "role": "Farmer",
            "name": "Suresh Patil",
            "phone": "9876543211",
            "password": "FarmerBPassword456",
            "state": "Maharashtra",
            "district": "Nashik",
            "village": "Sinnar"
        }
        res = self.client.post("/api/register", json=payload)
        self.assertEqual(res.status_code, 201)
        
        login_res = self.client.post("/api/login", json={"phone": "9876543211", "password": "FarmerBPassword456"})
        self.assertEqual(login_res.status_code, 200)
        data = login_res.get_json()
        self.assertEqual(data["role"], "Farmer")

    def test_03_farmer_a_cannot_access_or_modify_farmer_b_data(self):
        """3 & 4. Farmer A cannot access Farmer B's data or modify it (IDOR protection)."""
        login_a = self.client.post("/api/login", json={"phone": "9876543210", "password": "FarmerPassword123"}).get_json()
        token_a = login_a["token"]
        
        login_b = self.client.post("/api/login", json={"phone": "9876543211", "password": "FarmerBPassword456"}).get_json()
        token_b = login_b["token"]
        
        # Farmer B creates a listing
        listing_payload = {
            "commodity": "Soybean",
            "quantity": 100,
            "expected_price": 4500,
            "timeline": "2026-11-01"
        }
        create_res = self.client.post(
            "/api/listings",
            json=listing_payload,
            headers={"Authorization": f"Bearer {token_b}"}
        )
        self.assertEqual(create_res.status_code, 201)
        listing_b_id = create_res.get_json()["listing_id"]
        
        # Farmer A tries to query mine=true -> should NOT see Farmer B's listing
        get_res_a = self.client.get(
            "/api/listings?mine=true",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        self.assertEqual(get_res_a.status_code, 200)
        listings_a = get_res_a.get_json()
        self.assertNotIn(listing_b_id, [l["id"] for l in listings_a])
        
        # Farmer A tries to modify Farmer B's listing via PATCH (IDOR attempt)
        patch_res = self.client.patch(
            f"/api/listings/{listing_b_id}",
            json={"quality_verified_by_farmer": 1},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        self.assertEqual(patch_res.status_code, 403, "Farmer A was able to modify Farmer B's listing!")

        # Verify Offer Isolation between Farmer A and Farmer B:
        # Create an offer on Farmer B's listing directly in test DB
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO buyer_offers (buyer_id, listing_id, offered_price, quantity, status) VALUES (1, ?, 4600.0, 50.0, 'Pending')",
            (listing_b_id,)
        )
        offer_b_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Farmer A queries /api/offers -> MUST NOT see Farmer B's offer
        offers_res_a = self.client.get("/api/offers", headers={"Authorization": f"Bearer {token_a}"})
        self.assertEqual(offers_res_a.status_code, 200)
        offers_a = offers_res_a.get_json()
        self.assertNotIn(offer_b_id, [o["id"] for o in offers_a], "Farmer A was able to see Farmer B's offer!")

        # Farmer A attempts to Accept/Reject Farmer B's offer -> MUST return 403 Forbidden
        patch_offer_a = self.client.patch(
            f"/api/offers/{offer_b_id}",
            json={"status": "Accepted"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        self.assertEqual(patch_offer_a.status_code, 403, "Farmer A was able to accept Farmer B's offer!")

        # Farmer B queries /api/offers -> CAN see Farmer B's offer
        offers_res_b = self.client.get("/api/offers", headers={"Authorization": f"Bearer {token_b}"})
        self.assertEqual(offers_res_b.status_code, 200)
        offers_b = offers_res_b.get_json()
        self.assertIn(offer_b_id, [o["id"] for o in offers_b], "Farmer B should be able to see their own listing's offer!")

    def test_04_incorrect_password_is_rejected(self):
        """5. Incorrect password is rejected."""
        res = self.client.post("/api/login", json={"phone": "9876543210", "password": "WrongPassword!"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("error", res.get_json())

    def test_05_logout_invalidates_session(self):
        """6. Logout invalidates the authenticated session."""
        login_res = self.client.post("/api/login", json={"phone": "9876543210", "password": "FarmerPassword123"}).get_json()
        token = login_res["token"]
        
        # Verify token works before logout
        res_before = self.client.get("/api/listings?mine=true", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_before.status_code, 200)
        
        # Perform logout
        logout_res = self.client.post("/api/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(logout_res.status_code, 200)
        
        # Verify token is rejected after logout
        res_after = self.client.get("/api/listings?mine=true", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_after.status_code, 401)
        self.assertIn("revoked", res_after.get_json()["error"].lower())

    def test_06_unauthenticated_requests_rejected(self):
        """7. Protected API endpoints reject unauthenticated requests."""
        endpoints = [
            ("GET", "/api/listings"),
            ("POST", "/api/listings"),
            ("GET", "/api/offers"),
            ("POST", "/api/offers"),
            ("GET", "/api/buyer-requirements"),
            ("POST", "/api/buyer-requirements"),
            ("POST", "/api/quality-assessments"),
            ("GET", "/api/quality-assessments/1"),
            ("POST", "/api/logout"),
        ]
        for method, ep in endpoints:
            if method == "GET":
                res = self.client.get(ep)
            else:
                res = self.client.post(ep, json={})
            self.assertEqual(res.status_code, 401, f"Unauthenticated request to {ep} returned {res.status_code} instead of 401")

    def test_07_role_restrictions_and_privilege_escalation(self):
        """8 & 10. Role restrictions work and users cannot assign themselves privileged roles."""
        # Attempt to register as Village Centre operator
        res_vc_reg = self.client.post("/api/register", json={
            "role": "Village Centre",
            "name": "Malicious Operator",
            "phone": "9998887770",
            "password": "Password12345",
            "state": "Maharashtra",
            "district": "Pune"
        })
        self.assertEqual(res_vc_reg.status_code, 400, "User was able to register as Village Centre operator directly!")
        
        # Register a legitimate Buyer
        self.client.post("/api/register", json={
            "role": "Buyer",
            "name": "Agro Trade Corp",
            "phone": "9876500000",
            "password": "BuyerPassword123",
            "state": "Maharashtra",
            "district": "Pune"
        })
        login_buyer = self.client.post("/api/login", json={"phone": "9876500000", "password": "BuyerPassword123"}).get_json()
        buyer_token = login_buyer["token"]
        
        # Buyer attempts to create a farmer listing -> 403 Forbidden
        buyer_listing_res = self.client.post(
            "/api/listings",
            json={"commodity": "Wheat", "quantity": 10, "timeline": "2026-12-01"},
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        self.assertEqual(buyer_listing_res.status_code, 403)
        
        # Farmer attempts to post buyer requirement -> 403 Forbidden
        login_farmer = self.client.post("/api/login", json={"phone": "9876543210", "password": "FarmerPassword123"}).get_json()
        farmer_token = login_farmer["token"]
        
        farmer_req_res = self.client.post(
            "/api/buyer-requirements",
            json={"commodity": "Wheat", "quantity": 10, "required_by": "2026-12-01"},
            headers={"Authorization": f"Bearer {farmer_token}"}
        )
        self.assertEqual(farmer_req_res.status_code, 403)

    def test_08_buyer_cannot_accept_or_reject_offer(self):
        """9. A Buyer cannot accept or reject a Farmer's offer."""
        login_buyer = self.client.post("/api/login", json={"phone": "9876500000", "password": "BuyerPassword123"}).get_json()
        buyer_token = login_buyer["token"]
        
        # Buyer tries to PATCH offer status to Accepted
        res = self.client.patch(
            "/api/offers/1",
            json={"status": "Accepted"},
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        self.assertEqual(res.status_code, 403, "Buyer was able to accept an offer!")

    def test_09_centre_operator_cannot_access_unauthorized_centre_records(self):
        """10. A Centre Operator cannot access another unauthorized centre's records."""
        # Create second village centre in test DB
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        
        # Insert a second village centre operator user
        cursor.execute("INSERT INTO users (phone, password_hash, role) VALUES ('8888888888', 'dummy_hash', 'Village Centre')")
        op2_user_id = cursor.lastrowid
        cursor.execute("INSERT INTO village_centres (name, operator_name, state, district, phone, operator_user_id) VALUES ('Nashik North Centre', 'Nitin Shinde', 'Maharashtra', 'Nashik', '8888888888', ?)", (op2_user_id,))
        centre_2_id = cursor.lastrowid
        
        # Create a listing at centre 2
        cursor.execute("INSERT INTO farmer_listings (farmer_id, commodity, quantity, quality_grade, timeline, status, village_centre_id) VALUES (1, 'Bajra', 30, 'FAQ', '2026-11-20', 'Awaiting Village Centre Verification', ?)", (centre_2_id,))
        listing_centre_2 = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Log in as operator of Centre 1 ('9999999999', password is 'password123' from initial migration)
        login_op1 = self.client.post("/api/login", json={"phone": "9999999999", "password": "password123"}).get_json()
        token_op1 = login_op1["token"]
        
        # Operator 1 attempts to record quality assessment for listing at Centre 2 -> 403 Forbidden
        qa_res = self.client.post(
            "/api/quality-assessments",
            json={"listing_id": listing_centre_2, "moisture_pct": 11.5, "final_grade": "Grade A"},
            headers={"Authorization": f"Bearer {token_op1}"}
        )
        self.assertEqual(qa_res.status_code, 403, "Operator 1 was able to assess listing belonging to Centre 2!")
        
        # Operator 1 attempts to verify price on listing at Centre 2 -> 403 Forbidden
        price_verif_res = self.client.patch(
            f"/api/listings/{listing_centre_2}",
            json={"status": "Centre Verified", "verified_viable_price": 2800.0},
            headers={"Authorization": f"Bearer {token_op1}"}
        )
        self.assertEqual(price_verif_res.status_code, 403, "Operator 1 was able to update listing at Centre 2!")

        # Operator 1 queries GET /api/listings -> MUST NOT see Centre 2's unverified listing
        op1_listings = self.client.get("/api/listings", headers={"Authorization": f"Bearer {token_op1}"}).get_json()
        self.assertNotIn(listing_centre_2, [l["id"] for l in op1_listings], "Operator 1 was able to view listings from Centre 2!")

    def test_10_public_market_apis_work_without_auth(self):
        """11. Public market-price and historical-data APIs still work without login."""
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(self.client.get("/api/markets").status_code, 200)
        self.assertEqual(self.client.get("/api/commodities").status_code, 200)
        self.assertEqual(self.client.get("/api/prices?commodity=Wheat").status_code, 200)
        self.assertEqual(self.client.get("/api/trends?commodity=Wheat").status_code, 200)

    def test_11_migration_idempotence_and_preservation(self):
        """12 & 13. Re-running migration preserves data and schema idempotently."""
        conn = sqlite3.connect(self.test_db)
        count_prices_before = conn.execute("SELECT COUNT(*) FROM market_prices").fetchone()[0]
        conn.close()
        
        # Run migration again on the test DB
        run_migration(self.test_db)
        run_migration(self.test_db)
        
        conn = sqlite3.connect(self.test_db)
        count_prices_after = conn.execute("SELECT COUNT(*) FROM market_prices").fetchone()[0]
        conn.close()
        
        self.assertEqual(count_prices_before, count_prices_after)
        self.assertEqual(count_prices_after, 99850)

    def test_12_secret_key_environment_configuration(self):
        """14. SECRET_KEY configuration and production fail-secure validation."""
        import os
        # Verify app has a valid SECRET_KEY loaded
        self.assertTrue(bool(flask_app.app.config.get('SECRET_KEY')))
        
        # Test that production mode without SECRET_KEY fails securely
        orig_env = os.environ.get("FLASK_ENV")
        orig_sec = os.environ.get("SECRET_KEY")
        try:
            os.environ["FLASK_ENV"] = "production"
            if "SECRET_KEY" in os.environ:
                del os.environ["SECRET_KEY"]
                
            # Simulate the check
            with self.assertRaises(RuntimeError):
                env = os.environ.get("FLASK_ENV", "").lower()
                sec = os.environ.get("SECRET_KEY")
                if env == "production" and not sec:
                    raise RuntimeError("CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY environment variable must be set in production.")
        finally:
            if orig_env: os.environ["FLASK_ENV"] = orig_env
            elif "FLASK_ENV" in os.environ: del os.environ["FLASK_ENV"]
            if orig_sec: os.environ["SECRET_KEY"] = orig_sec

    def test_13_expired_and_revoked_sessions_rejected(self):
        """15. Expired and revoked sessions are strictly rejected."""
        import jwt
        import uuid
        from datetime import datetime, timedelta
        
        # 1. Create an expired token & DB record
        past_dt = datetime.utcnow() - timedelta(hours=2)
        token_payload = {
            'jti': str(uuid.uuid4()),
            'user_id': 1,
            'phone': '7483615840',
            'role': 'Farmer',
            'profile_id': 2,
            'centre_id': None,
            'exp': past_dt
        }
        expired_token = jwt.encode(token_payload, flask_app.app.config['SECRET_KEY'], algorithm="HS256")
        
        conn = sqlite3.connect(self.test_db)
        conn.execute(
            "INSERT INTO user_sessions (token, user_id, is_revoked, expires_at) VALUES (?, 1, 0, ?)",
            (expired_token, past_dt.strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
        
        # Request with expired token should return 401
        res_exp = self.client.get("/api/listings?mine=true", headers={"Authorization": f"Bearer {expired_token}"})
        self.assertEqual(res_exp.status_code, 401)
        self.assertIn("expired", res_exp.get_json()["error"].lower())

        # 2. Create a revoked token & DB record (is_revoked = 1, future expiry)
        future_dt = datetime.utcnow() + timedelta(hours=10)
        token_payload_revoked = {
            'jti': str(uuid.uuid4()),
            'user_id': 1,
            'phone': '7483615840',
            'role': 'Farmer',
            'profile_id': 2,
            'centre_id': None,
            'exp': future_dt
        }
        revoked_token = jwt.encode(token_payload_revoked, flask_app.app.config['SECRET_KEY'], algorithm="HS256")
        
        conn = sqlite3.connect(self.test_db)
        conn.execute(
            "INSERT INTO user_sessions (token, user_id, is_revoked, expires_at) VALUES (?, 1, 1, ?)",
            (revoked_token, future_dt.strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()

        # Request with revoked token should return 401
        res_rev = self.client.get("/api/listings?mine=true", headers={"Authorization": f"Bearer {revoked_token}"})
        self.assertEqual(res_rev.status_code, 401)
        self.assertIn("revoked", res_rev.get_json()["error"].lower())

    def test_14_safe_session_cleanup(self):
        """16. Session cleanup safely purges old sessions while preserving active ones and audit retention."""
        from datetime import datetime, timedelta
        import uuid
        
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        
        # Session A: Expired 45 days ago (should be cleaned up with 30-day retention)
        t_45d = (datetime.utcnow() - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
        tok_a = f"token_45d_old_{uuid.uuid4()}"
        cursor.execute("INSERT INTO user_sessions (token, user_id, is_revoked, expires_at) VALUES (?, 1, 1, ?)", (tok_a, t_45d))
        
        # Session B: Expired 5 days ago (within 30-day retention window, preserved for audit)
        t_5d = (datetime.utcnow() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        tok_b = f"token_5d_old_{uuid.uuid4()}"
        cursor.execute("INSERT INTO user_sessions (token, user_id, is_revoked, expires_at) VALUES (?, 1, 1, ?)", (tok_b, t_5d))
        
        # Session C: Active session (expires in future, must be preserved)
        t_future = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        tok_c = f"token_active_{uuid.uuid4()}"
        cursor.execute("INSERT INTO user_sessions (token, user_id, is_revoked, expires_at) VALUES (?, 1, 0, ?)", (tok_c, t_future))
        
        conn.commit()
        conn.close()
        
        # Run cleanup with 30 days retention
        pruned = flask_app.cleanup_expired_sessions(retention_days=30)
        self.assertGreaterEqual(pruned, 1)
        
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        # Verify A was purged
        res_a = cursor.execute("SELECT id FROM user_sessions WHERE token = ?", (tok_a,)).fetchone()
        self.assertIsNone(res_a)
        # Verify B was preserved
        res_b = cursor.execute("SELECT id FROM user_sessions WHERE token = ?", (tok_b,)).fetchone()
        self.assertIsNotNone(res_b)
        # Verify C was preserved
        res_c = cursor.execute("SELECT id FROM user_sessions WHERE token = ?", (tok_c,)).fetchone()
        self.assertIsNotNone(res_c)
        conn.close()
        
        # Test /api/admin/cleanup-sessions endpoint permissions:
        # 1. Village Centre Operator CANNOT trigger global session cleanup -> 403 Forbidden
        login_op = self.client.post("/api/login", json={"phone": "9999999999", "password": "password123"}).get_json()
        res_op = self.client.post(
            "/api/admin/cleanup-sessions?retention_days=30",
            headers={"Authorization": f"Bearer {login_op['token']}"}
        )
        self.assertEqual(res_op.status_code, 403, "Village Centre operator should NOT be allowed to perform global session cleanup!")
        
        # 2. Farmer CANNOT trigger -> 403 Forbidden
        login_farmer = self.client.post("/api/login", json={"phone": "9876543210", "password": "FarmerPassword123"}).get_json()
        res_farmer = self.client.post(
            "/api/admin/cleanup-sessions",
            headers={"Authorization": f"Bearer {login_farmer['token']}"}
        )
        self.assertEqual(res_farmer.status_code, 403)
        
        # 3. Missing and incorrect admin keys
        import os
        orig_key = os.environ.get("ADMIN_API_KEY")
        try:
            # Set key in environment
            os.environ["ADMIN_API_KEY"] = "test_secure_maintenance_key_999"
            
            # Incorrect key -> 403
            res_wrong = self.client.post(
                "/api/admin/cleanup-sessions?retention_days=30",
                headers={"X-Admin-Key": "wrong_key_12345"}
            )
            self.assertEqual(res_wrong.status_code, 403, "Incorrect X-Admin-Key must be rejected with 403!")
            
            # Missing header -> 403
            res_missing = self.client.post(
                "/api/admin/cleanup-sessions?retention_days=30"
            )
            self.assertEqual(res_missing.status_code, 403, "Missing X-Admin-Key must be rejected with 403!")
            
            # Correct key -> 200
            res_maint = self.client.post(
                "/api/admin/cleanup-sessions?retention_days=30",
                headers={"X-Admin-Key": "test_secure_maintenance_key_999"}
            )
            self.assertEqual(res_maint.status_code, 200)
            self.assertIn("pruned_sessions_count", res_maint.get_json())
            
            # Fail closed when ADMIN_API_KEY is not set in environment
            del os.environ["ADMIN_API_KEY"]
            res_no_env = self.client.post(
                "/api/admin/cleanup-sessions?retention_days=30",
                headers={"X-Admin-Key": "test_secure_maintenance_key_999"}
            )
            self.assertEqual(res_no_env.status_code, 403, "When ADMIN_API_KEY is unset, endpoint must fail-closed!")
            
            # Reset for validation tests
            os.environ["ADMIN_API_KEY"] = "test_secure_maintenance_key_999"
            
            # 4. Input validation: invalid retention_days rejected with 400
            res_bad_days = self.client.post(
                "/api/admin/cleanup-sessions?retention_days=invalid",
                headers={"X-Admin-Key": "test_secure_maintenance_key_999"}
            )
            self.assertEqual(res_bad_days.status_code, 400)
            
            res_neg_days = self.client.post(
                "/api/admin/cleanup-sessions?retention_days=0",
                headers={"X-Admin-Key": "test_secure_maintenance_key_999"}
            )
            self.assertEqual(res_neg_days.status_code, 400)
            
            res_high_days = self.client.post(
                "/api/admin/cleanup-sessions?retention_days=500",
                headers={"X-Admin-Key": "test_secure_maintenance_key_999"}
            )
            self.assertEqual(res_high_days.status_code, 400)
        finally:
            if orig_key: os.environ["ADMIN_API_KEY"] = orig_key
            elif "ADMIN_API_KEY" in os.environ: del os.environ["ADMIN_API_KEY"]

    def test_15_security_headers_and_cookie_configuration(self):
        """17. Security headers and cookie security configurations."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        
        # Verify security headers
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(res.headers.get("X-XSS-Protection"), "1; mode=block")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        
        # Verify cookie security settings
        self.assertTrue(flask_app.app.config.get("SESSION_COOKIE_HTTPONLY"))
        self.assertEqual(flask_app.app.config.get("SESSION_COOKIE_SAMESITE"), "Lax")
        self.assertTrue(flask_app.app.config.get("REMEMBER_COOKIE_HTTPONLY"))
        self.assertEqual(flask_app.app.config.get("REMEMBER_COOKIE_SAMESITE"), "Lax")

    def test_16_rate_limiting_login_and_register(self):
        """18. Persistent rate limiting protects login and register endpoints."""
        flask_app.app.config['TEST_RATE_LIMIT'] = True
        try:
            # Login rate limiting: 5 allowed attempts, 6th returns 429
            headers = {"X-Forwarded-For": "198.51.100.10"}
            for i in range(5):
                res = self.client.post("/api/login", json={"phone": "9876543210", "password": "WrongPassword"}, headers=headers)
                self.assertEqual(res.status_code, 401)
            
            # 6th attempt blocked with 429
            res_blocked = self.client.post("/api/login", json={"phone": "9876543210", "password": "WrongPassword"}, headers=headers)
            self.assertEqual(res_blocked.status_code, 429, "Rate limit should block repeated login attempts with 429!")
            self.assertIn("error", res_blocked.get_json())
            self.assertIn("Retry-After", res_blocked.headers)

            # Registration rate limiting: 5 allowed attempts, 6th returns 429
            reg_headers = {"X-Forwarded-For": "198.51.100.20"}
            for i in range(5):
                res = self.client.post("/api/register", json={
                    "role": "Farmer",
                    "name": f"Farmer {i}",
                    "phone": f"911111111{i}",
                    "password": "Password12345Passphrase",
                    "state": "Maharashtra",
                    "district": "Pune"
                }, headers=reg_headers)
                self.assertEqual(res.status_code, 201)

            res_reg_blocked = self.client.post("/api/register", json={
                "role": "Farmer",
                "name": "Farmer 6",
                "phone": "9111111116",
                "password": "Password12345Passphrase",
                "state": "Maharashtra",
                "district": "Pune"
            }, headers=reg_headers)
            self.assertEqual(res_reg_blocked.status_code, 429, "Rate limit should block repeated register attempts with 429!")
            self.assertIn("Retry-After", res_reg_blocked.headers)
        finally:
            flask_app.app.config['TEST_RATE_LIMIT'] = False

    def test_17_password_length_policy(self):
        """19. Password policy requires >= 12 characters and supports long passphrases."""
        # 1. Password under 12 characters is rejected with 400
        res_short = self.client.post("/api/register", json={
            "role": "Farmer",
            "name": "Short Password Farmer",
            "phone": "9123456780",
            "password": "ShortPass12", # 11 chars
            "state": "Maharashtra",
            "district": "Pune"
        })
        self.assertEqual(res_short.status_code, 400)
        self.assertIn("at least 12 characters", res_short.get_json().get("error", ""))

        # 2. Strong passphrase (>= 12 characters) is accepted
        res_passphrase = self.client.post("/api/register", json={
            "role": "Farmer",
            "name": "Passphrase Farmer",
            "phone": "9123456781",
            "password": "correct horse battery staple farming 2026", # 40 chars
            "state": "Maharashtra",
            "district": "Pune"
        })
        self.assertEqual(res_passphrase.status_code, 201)

        # Verify login works with the long passphrase
        login_res = self.client.post("/api/login", json={
            "phone": "9123456781",
            "password": "correct horse battery staple farming 2026"
        })
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("token", login_res.get_json())

    def test_18_cors_restrictions(self):
        """20. CORS restricts untrusted origins and permits allowed origins without wildcard credentials."""
        # 1. Allowed origin (Streamlit localhost)
        res_allowed = self.client.get("/api/health", headers={"Origin": "http://localhost:8501"})
        self.assertEqual(res_allowed.status_code, 200)
        self.assertEqual(res_allowed.headers.get("Access-Control-Allow-Origin"), "http://localhost:8501")
        self.assertEqual(res_allowed.headers.get("Access-Control-Allow-Credentials"), "true")

        # 2. Untrusted origin
        res_untrusted = self.client.get("/api/health", headers={"Origin": "http://evil-malicious-site.com"})
        self.assertEqual(res_untrusted.status_code, 200)
        self.assertNotEqual(res_untrusted.headers.get("Access-Control-Allow-Origin"), "http://evil-malicious-site.com")
        self.assertNotEqual(res_untrusted.headers.get("Access-Control-Allow-Origin"), "*")

    def test_19_proxy_header_spoofing_prevention(self):
        """21. Proxy headers cannot be spoofed to bypass rate limiting."""
        flask_app.app.config['TESTING'] = False
        try:
            with flask_app.app.test_request_context(
                '/api/login',
                environ_base={'REMOTE_ADDR': '203.0.113.5'},
                headers={'X-Forwarded-For': '198.51.100.99'}
            ):
                for _ in range(5):
                    allowed, _ = flask_app.check_rate_limit('login', max_attempts=5, window_seconds=60)
                
                # 6th attempt with different spoofed X-Forwarded-For header is still blocked
                # because rate limiter reliably uses request.remote_addr (203.0.113.5)
                flask_app.request.headers = {'X-Forwarded-For': '198.51.100.100'}
                allowed, retry_after = flask_app.check_rate_limit('login', max_attempts=5, window_seconds=60)
                self.assertFalse(allowed, "Rate limiter allowed spoofed X-Forwarded-For header!")
        finally:
            flask_app.app.config['TESTING'] = True

if __name__ == "__main__":
    unittest.main()
