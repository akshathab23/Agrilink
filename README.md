# 🌾 AgriLink: Transparent Digital Agricultural Marketplace

🌐 **Live Demo:** [AgriLink – Visit Website](https://agrilink-pn3i.onrender.com)

> A secure, role-based agricultural platform connecting **Farmers**, **Village Collection Centre Operators**, and **Commodity Buyers** through verified crop listings, standardized physical quality grading, automated demand-supply matching, and transparent mandi price discovery.

---

## 📋 Table of Contents

- [Overview & Problem Statement](#-overview--problem-statement)
- [Key Objectives](#-key-objectives)
- [Core Features](#-core-features)
- [System Architecture](#-system-architecture)
- [Technology Stack](#-technology-stack)
- [Project Directory Structure](#-project-directory-structure)
- [Installation & Setup](#-installation--setup)
- [Configuration & Environment Variables](#-configuration--environment-variables)
- [Running Locally](#-running-locally)
- [Database Initialization & Data Seeding](#-database-initialization--data-seeding)
- [Automated Testing & Quality Assurance](#-automated-testing--quality-assurance)
- [Security Architecture & Implementation](#-security-architecture--implementation)
- [Deployment Status](#-deployment-status)
- [Future Enhancements (Planned Work)](#-future-enhancements-planned-work)
- [Screenshots & User Interface](#-screenshots--user-interface)
- [Author & Acknowledgments](#-author--acknowledgments)
- [License](#-license)

---

## 📌 Overview & Problem Statement

Agricultural supply chains in developing economies frequently suffer from **information asymmetry**, **excessive intermediary markups**, and **lack of localized quality standardization at the farmgate**. Smallholder farmers often sell their produce under distress without access to real-time prevailing market rates or formal quality verification. Conversely, institutional buyers and agribusinesses struggle to source verified, quality-graded commodities directly from local aggregators.

**AgriLink** resolves these challenges by introducing a structured, verifiable three-tier agricultural trading workflow:

$$\text{Farmer} \longrightarrow \text{Village Centre Operator} \longrightarrow \text{Buyer}$$

1. **Farmers** list harvest lots with expected prices and availability timelines.
2. **Village Collection Centre Operators** inspect physical quality parameters (moisture, foreign matter, grain damage, ripeness) and verify fair local viability pricing.
3. **Buyers** browse centre-verified lots, access automated demand matching, and place formal binding purchase offers.
4. **Farmers** retain ultimate sovereignty: **only the farmer can accept or reject buyer offers**.

---

## 🎯 Key Objectives

- **Fair Price Discovery:** Empower farmers with real-time and historical wholesale price analytics calculated across 99,850+ official Agmarknet mandi records.
- **Farmgate Quality Assurance:** Provide verifiable physical grading at regional collection centres before produce is published to institutional buyers.
- **Direct Matching & Bidding:** Eliminate speculative middlemen through direct buyer requirement-to-listing matchmaking and binding purchase bids.
- **Enterprise-Grade Security:** Ensure multi-tenant isolation, role-based authorization, brute-force rate limiting, and cryptographic session protection.

---

## ✨ Core Features

### 1. Farmer Module
- **Crop Listing Creation:** Create listings specifying commodity, variety, quantity (in quintals), expected price, quality grade, and harvest availability timeline.
- **Listing Lifecycle Tracking:** Real-time visibility into listing status (`Pending Verification`, `Centre Verified`, `Completed`).
- **Offer Management:** View incoming buyer offers with offered price, volume, pickup preferences, and validity dates.
- **Farmer Sovereignty:** Dedicated, exclusive action controls to **Accept** or **Reject** offers. Other roles see `"Awaiting Farmer Decision"`.

### 2. Village Centre Operator Module
- **Regional Centre Scoping:** Operators are strictly confined to their assigned collection centre (e.g., Khed Main Collection Centre) and cannot view or alter other centres' records.
- **Physical Quality Inspection:** Standardized recording of moisture content (%), foreign matter (%), grain damage (%), ripeness, and visual appearance.
- **Viability Verification:** Validate local viability pricing and promote listings to `Centre Verified` status.

### 3. Institutional Buyer Module
- **Requirement Posting:** Publish procurement requirements with minimum quality thresholds, target prices, and required delivery deadlines.
- **Automated Matchmaking:** Algorithmically discover matching centre-verified farmer listings based on commodity and volume.
- **Binding Offer Submission:** Submit formal purchase offers specifying price per quintal, quantity, and logistics pickup preferences.

### 4. Public Mandi Price Discovery
- **Live & Historical Market Analytics:** Interactive search and trend exploration across 76+ agricultural mandis.
- **Time-Series Visualizations:** Dynamic modal price, minimum price, and maximum price charts powered by Plotly and Pandas.
- **Public API Access:** Public endpoints for commodities, markets, and price trends remain accessible without authentication.

---

## 🏗️ System Architecture

AgriLink employs a lightweight, decoupled micro-architecture combining a high-performance **Flask REST API** backend with an interactive **Streamlit** frontend, backed by a persistent **SQLite 3** relational database:

```
┌────────────────────────────────────────────────────────────────────────┐
│                          User Web Browser                              │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │ HTTPS (Port 443)
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Streamlit Frontend Server                       │
│                        (frontend/app.py :8501)                         │
│                                                                        │
│   • Multi-Role Navigation (Farmer / Operator / Buyer / Public)         │
│   • Interactive Plotly Market Visualizations                           │
│   • Session Token & User Profile Management (st.session_state)         │
└──────────────────┬─────────────────────────────────┬───────────────────┘
                   │                                 │
                   │ HTTP Internal API (Loopback)    │ Direct Read-Only
                   │ http://127.0.0.1:5000/api       │ Analytical Queries
                   ▼                                 ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│          Flask REST Backend          │  │       SQLite 3 Database      │
│         (backend/app.py :5000)       │  │   (backend/data/agrilink.db) │
│                                      │  │                              │
│  • JWT Auth & Server Session Store   │──┼─► • users & user_sessions    │
│  • SQLite-backed Rate Limiter        │  │   • auth_rate_limits         │
│  • Multi-Tenant Isolation Controls   │  │   • farmer_listings & offers │
│  • Role-Based Access Control (RBAC)  │  │   • quality_assessments      │
│  • ProxyFix Security Middleware      │  │   • 99,850+ market_prices    │
└──────────────────────────────────────┘  └──────────────────────────────┘
```

---

## 💻 Technology Stack

| Layer | Component | Technology / Library | Description |
|---|---|---|---|
| **Frontend** | UI Framework | `Streamlit (>= 1.30.0)` | Reactive, data-centric web user interface |
| | Visualizations | `Plotly Express` | Interactive time-series price charts |
| | Data Manipulation | `Pandas` | Tabular data processing and statistical aggregations |
| | HTTP Client | `Requests` | Communicates with the Flask REST API |
| **Backend** | Web Framework | `Flask` | Lightweight Python RESTful API framework |
| | WSGI Server | `Gunicorn` / `Waitress` | Production-grade WSGI application servers |
| | Security & Hashing | `Werkzeug` | Modern `scrypt` cryptographic password hashing |
| | Authentication | `PyJWT` | Stateless JSON Web Tokens with server revocation |
| | CORS Management | `Flask-CORS` | Strict origin allowlists with credential support |
| **Database** | Storage Engine | `SQLite 3` | ACID-compliant relational embedded database |
| | Dataset | Agmarknet Wholesale Records | 99,850 verified historical commodity price rows |
| **Testing** | QA Framework | Python `unittest` | 19 security regression tests + 1 E2E workflow test |

---

## 📁 Project Directory Structure

```text
Agrilink/
├── .env.example                       # Safe environment variable configuration template
├── .gitignore                         # Comprehensive exclusion rules for secrets, DBs, and caches
├── requirements.txt                   # Consolidated production Python dependencies
├── start.sh                           # Production startup script for automated deployment
├── verify_backend.py                  # Standalone backend health and connectivity verification
│
├── backend/
│   ├── app.py                         # Flask REST API server, security decorators & endpoints
│   ├── requirements.txt               # Backend-specific package requirements
│   ├── schema.sql                     # Base relational database DDL schema (idempotent)
│   │
│   ├── data/
│   │   ├── README.md                  # Dataset documentation and schema definitions
│   │   ├── generate_sample.py         # Synthetic/sample price generator utility
│   │   ├── verify_dataset.py          # Dataset schema and integrity verification script
│   │   └── raw/
│   │       └── agmarknet_sample.csv   # Raw historical wholesale market prices (8.36 MB)
│   │
│   ├── scripts/
│   │   ├── load_data.py               # Database initialization and CSV ingestion pipeline
│   │   ├── migrate_auth_phase3.py     # Idempotent migration for auth, sessions & rate limits
│   │   ├── migrate_auth.py            # Phase 1 schema helper script
│   │   ├── migrate_phase1.py          # Historical schema setup script
│   │   ├── migrate_phase4.py          # Historical matching helper script
│   │   └── test_phase2.py             # Phase 2 database verification script
│   │
│   └── tests/
│       ├── test_auth_security.py      # 19 automated regression tests for authentication & security
│       └── test_workflow_e2e.py       # End-to-end integration test (Farmer -> Centre -> Buyer)
│
└── frontend/
    ├── app.py                         # Streamlit multi-role web application
    └── requirements.txt               # Frontend-specific package requirements
```

---

## ⚙️ Installation & Setup

### Prerequisites
- **Python 3.10 to 3.12** installed on your system.
- Git installed.

### 1. Clone the Repository
```bash
git clone https://github.com/akshathab23/Agrilink.git
cd Agrilink
```

### 2. Create and Activate a Virtual Environment

**On Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 🔐 Configuration & Environment Variables

The project uses environment variables for operational modes and cryptographic keys. A template is provided in [.env.example](file:///c:/Users/aksha/OneDrive/Documents/Desktop/Agrilink/.env.example).

Create your local `.env` file (which is excluded from Git):
```bash
cp .env.example .env
```

### Supported Configuration Keys

| Variable | Default Value | Production Requirement | Purpose |
|---|---|:---:|---|
| `FLASK_ENV` | `development` | `production` | Controls cookie security, HSTS, and error reporting. |
| `AGRILINK_ENV` | `development` | `production` | Enforces fail-closed rules on missing secrets. |
| `SECRET_KEY` | *(dev fallback)* | **REQUIRED** | High-entropy key used to sign JWT tokens. |
| `ADMIN_API_KEY` | *(none)* | **REQUIRED** | Secret key required for session pruning (`/api/admin/cleanup-sessions`). |
| `CORS_ALLOWED_ORIGINS` | *(localhost)* | **REQUIRED** | Comma-separated list of approved frontend domains. |
| `NUM_PROXIES` | `0` | Recommended (`1`) | Number of trusted reverse proxy hops (activates Werkzeug `ProxyFix`). |
| `RATE_LIMIT_LOGIN_MAX` | `5` | Optional | Maximum allowed failed logins per time window. |
| `RATE_LIMIT_LOGIN_WINDOW`| `60` | Optional | Rate limit window in seconds. |
| `DB_PATH` | *(local relative)* | Optional | Custom path for SQLite database (e.g. persistent volume mount). |
| `API_BASE_URL` | `http://127.0.0.1:5000/api` | Optional | Internal API URL called by Streamlit. |

> ⚠️ **Security Warning:** In production (`FLASK_ENV=production`), the application will **fail securely and refuse to start** if `SECRET_KEY` is not provided.

---

## 🚀 Running Locally

Running AgriLink locally requires starting the backend API and the frontend application in two terminal tabs:

### Terminal 1: Start the Flask Backend
```bash
python backend/app.py
```
*The backend API will start on `http://127.0.0.1:5000`.*  
*Health Check: Verify with `curl http://127.0.0.1:5000/api/health`.*

### Terminal 2: Start the Streamlit Frontend
```bash
streamlit run frontend/app.py
```
*The frontend application will launch automatically in your browser at `http://localhost:8501`.*

---

## 🗄️ Database Initialization & Data Seeding

To maintain a clean Git repository and avoid binary bloat, **live SQLite database files (`*.db`) and database backups are excluded from version control**. 

When setting up the project on a new machine or a fresh deployment volume, the database is initialized and seeded from source files:

### 1. Initialize Database Schema & Authentication Tables
```bash
python backend/scripts/migrate_auth_phase3.py
```
*This idempotently creates all 13 relational tables and indexes defined in `schema.sql` and `migrate_auth_phase3.py`.*

### 2. Seed Historical Wholesale Market Prices (99,850 Records)
```bash
python backend/scripts/load_data.py
```
*This pipeline reads, cleans, validates, and ingests `backend/data/raw/agmarknet_sample.csv` directly into `market_prices` and `markets`.*

---

## 🧪 Automated Testing & Quality Assurance

AgriLink includes a comprehensive test suite verifying authentication security, role authorization, tenant isolation, and the complete business workflow:

### 1. Run the Security & Authentication Test Suite
```bash
python backend/tests/test_auth_security.py
```

**Scope of the 19 Automated Security Tests:**
- Registration validation and `scrypt` password hashing.
- Anti-enumeration error handling for login (HTTP 401) and registration (HTTP 409).
- Password policy enforcement (`len >= 12` chars, passphrase support).
- Persistent SQLite rate limiting (HTTP 429 with `Retry-After` header).
- Cross-tenant isolation (Farmer A cannot view or alter Farmer B's listings/offers).
- Strict role boundaries (Buyers cannot accept/reject offers; Operators restricted to assigned centre).
- Immediate session revocation upon logout.
- Session cleanup API security (`X-Admin-Key` verification, audit record retention).
- Origin-restricted CORS checks and reverse proxy spoofing prevention.

### 2. Run the End-to-End Workflow Test
```bash
python backend/tests/test_workflow_e2e.py
```
*Validates the complete transaction lifecycle: Farmer creates listing $\rightarrow$ Village Centre verifies quality and price $\rightarrow$ Buyer submits offer $\rightarrow$ Farmer accepts offer.*

---

## 🔒 Security Architecture & Implementation

AgriLink implements security-in-depth principles across all layers:

1. **Password Security:** Passwords are never stored in plaintext and are hashed using Werkzeug's `scrypt` key derivation function (`scrypt:32768:8:1`). Minimum password length is enforced at **12 characters**, allowing long passphrases without arbitrary complexity barriers.
2. **Persistent Rate Limiting:** Login and registration endpoints are protected by an SQLite-backed rate limiter (`auth_rate_limits`) that tracks attempts across multiple WSGI worker processes and server restarts.
3. **Anti-Enumeration Protections:** Authentication failure responses do not disclose whether a given phone number or email address is registered.
4. **Server-Side Session Revocation:** JWTs are paired with a server-side session registry (`user_sessions`). Logging out immediately marks the session as revoked, instantly rejecting further API calls.
5. **Proxy Header Spoofing Protection:** Integrates Werkzeug `ProxyFix` middleware (controlled via `NUM_PROXIES`), ensuring client rate limits track authentic peer IP addresses rather than spoofed headers.
6. **HTTPS & Cookie Hardening:** In production mode, cookies are marked `HttpOnly`, `SameSite=Lax`, and `Secure`. Responses include `Strict-Transport-Security` (HSTS), `X-Content-Type-Options: nosniff`, and `X-Frame-Options: SAMEORIGIN`.

---

## 🌐 Deployment Status

- **Current Status:** **Live in Production** on Render: [https://agrilink-pn3i.onrender.com](https://agrilink-pn3i.onrender.com)
- **Production Architecture (Render / Linux PaaS):**
  The repository includes a production launcher ([start.sh](file:///c:/Users/aksha/OneDrive/Documents/Desktop/Agrilink/start.sh)) engineered for unified single-service hosting:
  - Runs safe schema migrations automatically on startup.
  - Launches the Flask API on `127.0.0.1:5000` via Gunicorn in the background.
  - Waits for backend health checks to pass.
  - Launches Streamlit in the foreground bound to `0.0.0.0:$PORT`.
  - Captures `SIGTERM` / `SIGINT` signals for clean multi-process termination.
- **Persistent Storage Recommendation:** When deploying on cloud providers (e.g., Render or Railway), mount a **Persistent Disk** at `/app/backend/data` to ensure user accounts, crop listings, and offers persist across container restarts.

---

## 🔮 Future Enhancements (Planned Work)

The following features represent planned future work and are not yet present in the current codebase:

- [ ] **Digital Escrow & Payment Integration:** Integration with UPI and escrow smart contracts for automated payment release upon physical delivery.
- [ ] **SMS / IVR Farmer Gateway:** Lightweight SMS and automated voice response gateways for farmers without smartphone access.
- [ ] **IoT Quality Hardware Integration:** Integration with Bluetooth-enabled grain moisture meters and digital weighing scales at collection centres.
- [ ] **Cold Storage & Logistics Network:** Real-time visibility into nearby rural cold storage facilities and transportation aggregators.
- [ ] **Dedicated Native Mobile Apps:** Flutter or React Native mobile applications for offline field operations.

---

## 📸 Screenshots & User Interface

*(Add screenshots of your application here before final presentation)*

| View | Screenshot Placeholder |
|---|---|
| **Public Market Trends & Analytics** | *`<!-- Place screenshot of Market Prices & Trends page here -->`* |
| **Farmer Listing Management** | *`<!-- Place screenshot of Farmer Dashboard & Crop Listing page here -->`* |
| **Village Centre Quality Grading** | *`<!-- Place screenshot of Quality Assessment & Viability Verification page here -->`* |
| **Buyer Marketplace & Bidding** | *`<!-- Place screenshot of Buyer Demand Matching & Offer submission here -->`* |

---

## 👤 Author & Acknowledgments

- **Developed by:** Akshatha B
- **GitHub Profile:** [akshathab23](https://github.com/akshathab23)
- **Project Repository:** [AgriLink](https://github.com/akshathab23/Agrilink)
- **Dataset Attribution:** Wholesale agricultural market data sourced from the **Agmarknet** portal (Directorate of Marketing & Inspection, Ministry of Agriculture and Farmers Welfare, Government of India).

---

## 📄 License

This project is currently maintained for academic demonstration and portfolio purposes. License terms will be added when an appropriate open-source license is selected.
