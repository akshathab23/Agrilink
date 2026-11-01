import os
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS
from pathlib import Path
from datetime import datetime, timedelta
import jwt
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# ==========================================
# ENVIRONMENT & SECURITY CONFIGURATION
# ==========================================
ENVIRONMENT = os.environ.get("FLASK_ENV", os.environ.get("AGRILINK_ENV", "development")).lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# 3. CORS Configuration
# In production, require explicitly configured trusted origins via CORS_ALLOWED_ORIGINS.
# Wildcard '*' is strictly avoided when credentials are supported.
cors_origins_env = os.environ.get("CORS_ALLOWED_ORIGINS")
if cors_origins_env:
    ALLOWED_ORIGINS = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
elif IS_PRODUCTION:
    # Fail-safe in production: no cross-origin allowed unless explicitly configured
    ALLOWED_ORIGINS = []
else:
    # Explicit development origins for local Streamlit frontend
    ALLOWED_ORIGINS = [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ]

CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).parent / "data" / "agrilink.db"))

# 1. SECRET_KEY: Loaded from environment. Fails securely in production if missing.
SECRET_KEY = os.environ.get("SECRET_KEY")
if IS_PRODUCTION:
    if not SECRET_KEY:
        raise RuntimeError("CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY environment variable must be set in production.")
    app.config['SECRET_KEY'] = SECRET_KEY
else:
    # Development fallback
    app.config['SECRET_KEY'] = SECRET_KEY or 'agrilink_dev_fallback_secret_key_non_production'

# 3. HTTPS & Cookie Security Configuration
app.config.update(
    SESSION_COOKIE_SECURE=IS_PRODUCTION,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    REMEMBER_COOKIE_SECURE=IS_PRODUCTION,
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SAMESITE='Lax',
)

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if IS_PRODUCTION:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# Admin & Maintenance API Key configuration
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY")
if IS_PRODUCTION and not ADMIN_API_KEY:
    # Fail-closed in production if ADMIN_API_KEY is not configured
    # We do not crash the entire app if maintenance is not enabled, but the endpoint fails closed.
    pass

# Trusted Reverse Proxy Configuration
# When deployed behind a reverse proxy (e.g., Nginx, ALB, Cloudflare), set NUM_PROXIES=1 (or corresponding hops)
# to safely extract the real client IP via ProxyFix without allowing client header spoofing.
NUM_PROXIES = int(os.environ.get("NUM_PROXIES", "0"))
if NUM_PROXIES > 0:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=NUM_PROXIES, x_proto=NUM_PROXIES, x_host=NUM_PROXIES)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# 2. Session Cleanup Utility
def cleanup_expired_sessions(retention_days=30):
    """
    Safely prunes expired or revoked sessions older than retention_days.
    Preserves all active unexpired sessions AND recent audit records within retention_days.
    
    Criteria for safe deletion:
    1. Must be older than retention_days cutoff.
    2. Must be expired (expires_at < now) OR revoked (is_revoked = 1).
    3. Active sessions (expires_at >= now AND is_revoked = 0) are NEVER deleted.
    """
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """DELETE FROM user_sessions 
           WHERE expires_at < ? 
             AND (is_revoked = 1 OR expires_at < ?)""",
        (cutoff_str, now_str)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted

# 4. Rate Limiting Configuration & Persistent SQLite-backed Limiter
RATE_LIMIT_LOGIN_MAX = int(os.environ.get("RATE_LIMIT_LOGIN_MAX", 5))
RATE_LIMIT_LOGIN_WINDOW = int(os.environ.get("RATE_LIMIT_LOGIN_WINDOW", 60))
RATE_LIMIT_REGISTER_MAX = int(os.environ.get("RATE_LIMIT_REGISTER_MAX", 5))
RATE_LIMIT_REGISTER_WINDOW = int(os.environ.get("RATE_LIMIT_REGISTER_WINDOW", 60))

def check_rate_limit(endpoint, max_attempts=5, window_seconds=60):
    """
    Persistent, multi-worker safe rate limiter backed by SQLite.
    Returns (allowed: bool, retry_after: int).
    """
    if app.config.get('TESTING') and not app.config.get('TEST_RATE_LIMIT'):
        return True, 0

    # Secure Client IP Resolution:
    # In test mode, allow X-Forwarded-For header override for automated test isolation.
    # In production/normal mode, rely on request.remote_addr (which is sanitized by ProxyFix
    # if behind a trusted proxy, or the direct socket address), preventing untrusted clients from spoofing headers.
    if app.config.get('TESTING') and 'X-Forwarded-For' in request.headers:
        client_ip = request.headers.get("X-Forwarded-For").split(",")[0].strip()
    else:
        client_ip = request.remote_addr or "127.0.0.1"
    cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ensure rate limit table exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auth_rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_ip TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rate_limits ON auth_rate_limits(client_ip, endpoint, attempt_time)")
    
    # Prune stale records to keep table compact
    cursor.execute("DELETE FROM auth_rate_limits WHERE attempt_time < ?", (cutoff_str,))
    
    # Count attempts in current window
    cursor.execute(
        "SELECT COUNT(*) FROM auth_rate_limits WHERE client_ip = ? AND endpoint = ? AND attempt_time >= ?",
        (client_ip, endpoint, cutoff_str)
    )
    count = cursor.fetchone()[0]
    
    if count >= max_attempts:
        conn.commit()
        conn.close()
        return False, window_seconds
        
    cursor.execute(
        "INSERT INTO auth_rate_limits (client_ip, endpoint, attempt_time) VALUES (?, ?, ?)",
        (client_ip, endpoint, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()
    return True, 0

# ==========================================
# AUTHENTICATION & AUTHORIZATION DECORATORS
# ==========================================

def require_auth(allowed_roles=None):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = None
            if 'Authorization' in request.headers:
                parts = request.headers['Authorization'].split()
                if len(parts) == 2 and parts[0] == 'Bearer':
                    token = parts[1]
                    
            if not token:
                return jsonify({'error': 'Authentication required. Token missing.'}), 401
                
            try:
                data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            except jwt.ExpiredSignatureError:
                return jsonify({'error': 'Token has expired.'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'error': 'Invalid token.'}), 401

            # Verify with server-side session store to enforce token invalidation and expiration
            conn = get_db_connection()
            session_record = conn.execute(
                "SELECT is_revoked, expires_at FROM user_sessions WHERE token = ?", (token,)
            ).fetchone()
            conn.close()
            
            if not session_record:
                return jsonify({'error': 'Session not found or terminated.'}), 401
            if session_record['is_revoked'] == 1:
                return jsonify({'error': 'Token has been revoked. Please log in again.'}), 401

            # Validate database-stored expiration date
            raw_exp = session_record['expires_at']
            if raw_exp:
                try:
                    exp_dt = datetime.strptime(str(raw_exp)[:19], "%Y-%m-%d %H:%M:%S")
                    if exp_dt < datetime.utcnow():
                        return jsonify({'error': 'Session has expired. Please log in again.'}), 401
                except Exception:
                    pass

            request.user = data
            request.token = token

            if allowed_roles and request.user.get('role') not in allowed_roles:
                return jsonify({'error': 'Permission denied. Unauthorized role.'}), 403
                
            return f(*args, **kwargs)
        return decorated
    return decorator

# ==========================================
# AUTHENTICATION ENDPOINTS
# ==========================================

@app.route('/api/register', methods=['POST'])
def register():
    # 1. Rate limiting check
    allowed, retry_after = check_rate_limit('register', max_attempts=RATE_LIMIT_REGISTER_MAX, window_seconds=RATE_LIMIT_REGISTER_WINDOW)
    if not allowed:
        resp = jsonify({"error": "Too many registration attempts. Please try again later."})
        resp.status_code = 429
        resp.headers['Retry-After'] = str(retry_after)
        return resp

    data = request.json
    if not data or not all(k in data for k in ('phone', 'password', 'role')):
        return jsonify({"error": "Missing required fields (phone, password, role)"}), 400
        
    role = data['role']
    # Prevent privilege escalation: Users CANNOT register as Village Centre operators
    if role not in ['Farmer', 'Buyer']:
        return jsonify({"error": "Registration is only permitted for Farmer and Buyer roles. Village Centre operators must be assigned administratively."}), 400
        
    phone = str(data['phone']).strip()
    email = str(data['email']).strip() if data.get('email') else None
    password = str(data['password'])
    
    if len(phone) < 10:
        return jsonify({"error": "Invalid phone number"}), 400
        
    # Enforce at least 12 characters for new passwords, allowing strong passphrases without arbitrary complexity hurdles
    if len(password) < 12:
        return jsonify({"error": "Password must be at least 12 characters long. Passphrases are encouraged."}), 400
        
    hashed_pw = generate_password_hash(password)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (phone, email, password_hash, role) VALUES (?, ?, ?, ?)", 
            (phone, email, hashed_pw, role)
        )
        user_id = cursor.lastrowid
        
        if role == 'Farmer':
            if not all(k in data for k in ('name', 'state', 'district')):
                conn.rollback()
                conn.close()
                return jsonify({"error": "Missing farmer profile fields: name, state, district"}), 400
            cursor.execute(
                "INSERT INTO farmers (user_id, name, phone, state, district, village) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, data['name'].strip(), phone, data['state'].strip(), data['district'].strip(), data.get('village', '').strip())
            )
        elif role == 'Buyer':
            if not all(k in data for k in ('name', 'state', 'district')):
                conn.rollback()
                conn.close()
                return jsonify({"error": "Missing buyer profile fields: name, state, district"}), 400
            cursor.execute(
                "INSERT INTO buyers (user_id, name, buyer_type, state, district, phone) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, data['name'].strip(), data.get('buyer_type', 'Individual'), data['state'].strip(), data['district'].strip(), phone)
            )
        
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        conn.close()
        # Non-enumerating error: avoid revealing whether a phone number or email address exists
        return jsonify({"error": "Registration could not be completed with the provided details. Please check your information or log in."}), 409
        
    conn.close()
    return jsonify({"message": "User registered successfully"}), 201

@app.route('/api/login', methods=['POST'])
def login():
    # 1. Rate limiting check
    allowed, retry_after = check_rate_limit('login', max_attempts=RATE_LIMIT_LOGIN_MAX, window_seconds=RATE_LIMIT_LOGIN_WINDOW)
    if not allowed:
        resp = jsonify({"error": "Too many login attempts. Please try again later."})
        resp.status_code = 429
        resp.headers['Retry-After'] = str(retry_after)
        return resp

    data = request.json
    if not data or not (data.get('phone') or data.get('email')) or not data.get('password'):
        return jsonify({"error": "Missing identifier (phone/email) or password"}), 400
        
    identifier = data.get('phone') or data.get('email')
    password = data['password']
    
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE phone = ? OR (email IS NOT NULL AND email = ?)", 
        (identifier, identifier)
    ).fetchone()
    
    if not user or not check_password_hash(user['password_hash'], password):
        conn.close()
        # Non-enumerating generic message
        return jsonify({"error": "Invalid credentials. Incorrect phone/email or password."}), 401
        
    profile_id = None
    centre_id = None
    
    if user['role'] == 'Farmer':
        prof = conn.execute("SELECT id FROM farmers WHERE user_id = ?", (user['id'],)).fetchone()
        if prof: profile_id = prof['id']
    elif user['role'] == 'Buyer':
        prof = conn.execute("SELECT id FROM buyers WHERE user_id = ?", (user['id'],)).fetchone()
        if prof: profile_id = prof['id']
    elif user['role'] == 'Village Centre':
        vc = conn.execute("SELECT id FROM village_centres WHERE operator_user_id = ?", (user['id'],)).fetchone()
        if vc: 
            centre_id = vc['id']
            profile_id = vc['id']
        
    import uuid
    expires_at = datetime.utcnow() + timedelta(hours=24)
    token_payload = {
        'jti': str(uuid.uuid4()),
        'user_id': user['id'],
        'phone': user['phone'],
        'role': user['role'],
        'profile_id': profile_id,
        'centre_id': centre_id,
        'exp': expires_at
    }
    token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm="HS256")
    
    # Store in server-side session table
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO user_sessions (token, user_id, is_revoked, expires_at) VALUES (?, ?, 0, ?)",
        (token, user['id'], expires_at.strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()
    
    return jsonify({
        "message": "Login successful",
        "token": token,
        "role": user['role'],
        "profile_id": profile_id,
        "centre_id": centre_id
    })

@app.route('/api/logout', methods=['POST'])
@require_auth()
def logout():
    token = request.token
    conn = get_db_connection()
    conn.execute("UPDATE user_sessions SET is_revoked = 1 WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Logged out successfully. Session invalidated."}), 200

@app.route('/api/admin/cleanup-sessions', methods=['POST'])
def trigger_cleanup_sessions():
    """
    Dedicated maintenance endpoint for session cleanup.
    Restricted to authenticated Administrator or trusted maintenance job (X-Admin-Key header).
    Village Centre operators, farmers, and buyers are strictly forbidden.
    Fails closed if admin key is not configured.
    """
    import hmac
    is_authorized = False
    
    # 1. Check for dedicated maintenance API key header
    auth_header = request.headers.get("X-Admin-Key")
    current_admin_key = os.environ.get("ADMIN_API_KEY")
    if current_admin_key and auth_header:
        # Constant-time comparison to prevent timing attacks
        if hmac.compare_digest(str(auth_header), str(current_admin_key)):
            is_authorized = True
        
    # 2. Check for authenticated Admin token (Admin role user)
    if not is_authorized and 'Authorization' in request.headers:
        parts = request.headers['Authorization'].split()
        if len(parts) == 2 and parts[0] == 'Bearer':
            token = parts[1]
            try:
                data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
                # Must have dedicated 'Admin' role
                if data.get('role') == 'Admin':
                    conn = get_db_connection()
                    session_record = conn.execute(
                        "SELECT is_revoked, expires_at FROM user_sessions WHERE token = ?", (token,)
                    ).fetchone()
                    conn.close()
                    if session_record and session_record['is_revoked'] == 0:
                        is_authorized = True
            except Exception:
                pass
                
    if not is_authorized:
        return jsonify({
            "error": "Permission denied. Restricted to dedicated system administrators or authorized maintenance tasks."
        }), 403

    # Input validation for retention_days (integer between 1 and 365)
    raw_days = request.args.get('retention_days', 30)
    try:
        days = int(raw_days)
        if days < 1 or days > 365:
            return jsonify({"error": "Invalid retention_days. Must be an integer between 1 and 365."}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid retention_days parameter. Must be an integer."}), 400

    deleted_count = cleanup_expired_sessions(retention_days=days)
    return jsonify({
        "message": "Session cleanup completed successfully",
        "pruned_sessions_count": deleted_count,
        "retention_days": days
    }), 200

# ==========================================
# PUBLIC MARKET DATA ENDPOINTS
# ==========================================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "message": "AgriLink Backend is running."})

@app.route('/api/markets', methods=['GET'])
def get_markets():
    conn = get_db_connection()
    state = request.args.get('state')
    district = request.args.get('district')
    
    if not state and not district:
        states = conn.execute('SELECT DISTINCT state FROM markets ORDER BY state').fetchall()
        conn.close()
        return jsonify([row['state'] for row in states])
    
    if state and not district:
        districts = conn.execute('SELECT DISTINCT district FROM markets WHERE state = ? ORDER BY district', (state,)).fetchall()
        conn.close()
        return jsonify([row['district'] for row in districts])
        
    markets = conn.execute('SELECT id, market_name FROM markets WHERE state = ? AND district = ? ORDER BY market_name', (state, district)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in markets])

@app.route('/api/commodities', methods=['GET'])
def get_commodities():
    conn = get_db_connection()
    commodities = conn.execute('SELECT DISTINCT commodity FROM market_prices ORDER BY commodity').fetchall()
    conn.close()
    return jsonify([row['commodity'] for row in commodities])

@app.route('/api/prices', methods=['GET'])
@app.route('/api/prices/current', methods=['GET'])
def get_current_prices():
    commodity = request.args.get('commodity')
    state = request.args.get('state')
    district = request.args.get('district')
    
    if not commodity:
        return jsonify({"error": "commodity parameter is required"}), 400
        
    query = '''
        SELECT m.market_name, m.district, p.variety, p.grade, p.modal_price, p.min_price, p.max_price, p.arrival_date 
        FROM market_prices p
        JOIN markets m ON p.market_id = m.id
        WHERE p.commodity = ?
    '''
    params = [commodity]
    
    if state:
        query += ' AND m.state = ?'
        params.append(state)
    if district:
        query += ' AND m.district = ?'
        params.append(district)
        
    query += ' ORDER BY p.arrival_date DESC LIMIT 20'
    
    conn = get_db_connection()
    prices = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(row) for row in prices])

@app.route('/api/trends', methods=['GET'])
@app.route('/api/prices/trend', methods=['GET'])
def get_price_trend():
    commodity = request.args.get('commodity')
    if not commodity:
        return jsonify({"error": "commodity parameter is required"}), 400
        
    query = '''
        SELECT arrival_date, AVG(modal_price) as avg_modal_price 
        FROM market_prices 
        WHERE commodity = ? 
        GROUP BY arrival_date 
        ORDER BY arrival_date DESC 
        LIMIT 30
    '''
    conn = get_db_connection()
    trends = conn.execute(query, (commodity,)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in reversed(trends)])

# ==========================================
# PROTECTED: LISTINGS API (Strict Ownership)
# ==========================================

@app.route('/api/listings', methods=['GET', 'POST'])
@require_auth()
def manage_listings():
    conn = get_db_connection()
    if request.method == 'POST':
        # ONLY Farmers can create listings
        if request.user['role'] != 'Farmer':
            conn.close()
            return jsonify({"error": "Permission denied. Only farmers can create produce listings."}), 403
            
        data = request.json
        if not data or not all(k in data for k in ('commodity', 'quantity', 'timeline')):
            conn.close()
            return jsonify({"error": "Missing required fields (commodity, quantity, timeline)"}), 400

        # Identity derived strictly from token
        farmer_profile_id = request.user.get('profile_id')
        if not farmer_profile_id:
            conn.close()
            return jsonify({"error": "Farmer profile missing or unlinked."}), 400

        # Associate with village centre (either explicitly if provided and valid, or default)
        centre_id = data.get('village_centre_id')
        if not centre_id:
            first_vc = conn.execute("SELECT id FROM village_centres ORDER BY id LIMIT 1").fetchone()
            centre_id = first_vc['id'] if first_vc else None

        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO farmer_listings 
               (farmer_id, commodity, quantity, quality_grade, expected_price, timeline, status, village_centre_id) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (farmer_profile_id, data['commodity'], data['quantity'], data.get('quality_grade', 'FAQ'), 
             data.get('expected_price'), data['timeline'], 'Awaiting Village Centre Verification', centre_id)
        )
        listing_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"message": "Listing created successfully!", "listing_id": listing_id}), 201
        
    else:
        # GET listings scoped safely by role
        commodity = request.args.get('commodity')
        status = request.args.get('status')
        mine = request.args.get('mine') == 'true'
        
        query = '''
            SELECT l.id, f.name, f.state, f.district, f.village, l.commodity, l.quantity, 
                   l.quality_grade, l.expected_price, l.timeline, l.status, l.created_at,
                   l.quality_verified_by_farmer, l.transport_cost, l.labour_cost, 
                   l.centre_operating_cost, l.centre_margin, l.verified_viable_price, 
                   l.market_reference_price, l.village_centre_id
            FROM farmer_listings l
            JOIN farmers f ON l.farmer_id = f.id
            WHERE 1=1
        '''
        params = []
        if commodity:
            query += ' AND l.commodity = ?'
            params.append(commodity)
        if status:
            query += ' AND l.status = ?'
            params.append(status)
            
        # Strict Role Scoping
        if request.user['role'] == 'Farmer':
            # A farmer requesting their listings gets only their own
            if mine:
                query += ' AND l.farmer_id = ?'
                params.append(request.user['profile_id'])
            else:
                # General market view for farmers only shows Centre Verified listings
                query += " AND l.status = 'Centre Verified'"
        elif request.user['role'] == 'Buyer':
            # Buyers can only browse Centre Verified listings
            query += " AND l.status = 'Centre Verified'"
        elif request.user['role'] == 'Village Centre':
            # Operators only see listings assigned to their centre
            assigned_centre = request.user.get('centre_id')
            if assigned_centre:
                query += ' AND l.village_centre_id = ?'
                params.append(assigned_centre)

        query += ' ORDER BY l.created_at DESC LIMIT 50'
        listings = conn.execute(query, params).fetchall()
        conn.close()
        return jsonify([dict(row) for row in listings])

@app.route('/api/listings/<int:listing_id>', methods=['PATCH'])
@require_auth()
def update_listing(listing_id):
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    conn = get_db_connection()
    listing = conn.execute("SELECT * FROM farmer_listings WHERE id = ?", (listing_id,)).fetchone()
    if not listing:
        conn.close()
        return jsonify({"error": "Listing not found"}), 404
        
    update_fields = []
    params = []
    
    # IDOR and Mass-Assignment Prevention
    if request.user['role'] == 'Farmer':
        # Farmers can ONLY update their own listings
        if listing['farmer_id'] != request.user.get('profile_id'):
            conn.close()
            return jsonify({"error": "Permission denied. You cannot modify another farmer's listing."}), 403
        # Farmers can only confirm/verify their quality
        allowed_fields = ['quality_verified_by_farmer']
        for k in data.keys():
            if k not in allowed_fields:
                conn.close()
                return jsonify({"error": f"Farmer cannot update field '{k}'"}), 403
                
    elif request.user['role'] == 'Village Centre':
        # Centre operators can ONLY update listings assigned to their specific centre
        assigned_centre = request.user.get('centre_id')
        if assigned_centre and listing['village_centre_id'] != assigned_centre:
            conn.close()
            return jsonify({"error": "Permission denied. This listing belongs to a different village centre."}), 403
            
        allowed_fields = [
            'status', 'transport_cost', 'labour_cost', 
            'centre_operating_cost', 'centre_margin', 
            'verified_viable_price', 'market_reference_price'
        ]
        for k in data.keys():
            if k not in allowed_fields:
                conn.close()
                return jsonify({"error": f"Invalid field for centre verification: '{k}'"}), 403
    else:
        conn.close()
        return jsonify({"error": "Permission denied. Buyers cannot update listings."}), 403
        
    for field in allowed_fields:
        if field in data:
            update_fields.append(f"{field} = ?")
            params.append(data[field])
            
    if not update_fields:
        conn.close()
        return jsonify({"error": "No valid fields provided for update"}), 400
        
    params.append(listing_id)
    query = f"UPDATE farmer_listings SET {', '.join(update_fields)} WHERE id = ?"
    
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Listing updated successfully"})

# ==========================================
# PROTECTED: BUYER REQUIREMENTS API
# ==========================================

@app.route('/api/buyer-requirements', methods=['GET', 'POST'])
@require_auth(allowed_roles=['Buyer', 'Village Centre'])
def manage_buyer_requirements():
    conn = get_db_connection()
    if request.method == 'POST':
        # ONLY Buyers can post requirements
        if request.user['role'] != 'Buyer':
            conn.close()
            return jsonify({"error": "Permission denied. Only registered buyers can post requirements."}), 403
            
        data = request.json
        required_fields = ['commodity', 'quantity', 'required_by']
        if not data or not all(k in data for k in required_fields):
            conn.close()
            return jsonify({"error": "Missing required fields (commodity, quantity, required_by)"}), 400
            
        buyer_id = request.user['profile_id']
            
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO buyer_requirements 
               (buyer_id, commodity, quantity, min_grade, target_price, required_by, pref_state, pref_district)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (buyer_id, data['commodity'], data['quantity'], data.get('min_grade'),
             data.get('target_price'), data['required_by'], data.get('pref_state'), data.get('pref_district'))
        )
        req_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"message": "Requirement created", "requirement_id": req_id}), 201
    else:
        commodity = request.args.get('commodity')
        location = request.args.get('district')
        mine = request.args.get('mine') == 'true'
        
        query = "SELECT * FROM buyer_requirements WHERE 1=1"
        params = []
        
        # Scoping: if a Buyer requests their requirements, strictly filter to their buyer_id
        if request.user['role'] == 'Buyer':
            if mine:
                query += " AND buyer_id = ?"
                params.append(request.user['profile_id'])
            
        if commodity:
            query += " AND commodity = ?"
            params.append(commodity)
        if location:
            query += " AND pref_district = ?"
            params.append(location)
            
        query += " ORDER BY created_at DESC"
        reqs = conn.execute(query, params).fetchall()
        conn.close()
        return jsonify([dict(r) for r in reqs])

# ==========================================
# PROTECTED: QUALITY ASSESSMENTS API
# ==========================================

@app.route('/api/quality-assessments', methods=['POST'])
@require_auth(allowed_roles=['Village Centre'])
def create_quality_assessment():
    data = request.json
    if not data or 'listing_id' not in data:
        return jsonify({"error": "Missing listing_id"}), 400
        
    conn = get_db_connection()
    listing = conn.execute("SELECT id, village_centre_id FROM farmer_listings WHERE id = ?", (data['listing_id'],)).fetchone()
    if not listing:
        conn.close()
        return jsonify({"error": "Invalid listing ID"}), 404
        
    # Verify centre operator authorization: operator can only assess listings for their assigned centre
    assigned_centre = request.user.get('centre_id')
    if assigned_centre and listing['village_centre_id'] != assigned_centre:
        conn.close()
        return jsonify({"error": "Permission denied. Listing is not assigned to your village centre."}), 403
        
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO quality_assessments 
           (listing_id, moisture_pct, foreign_matter_pct, damaged_pct, size_category, ripeness, visual_damage, final_grade, assessor_name)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (data['listing_id'], data.get('moisture_pct'), data.get('foreign_matter_pct'), data.get('damaged_pct'),
         data.get('size_category'), data.get('ripeness'), data.get('visual_damage'), data.get('final_grade'), data.get('assessor_name'))
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Quality assessment recorded successfully"}), 201

@app.route('/api/quality-assessments/<int:listing_id>', methods=['GET'])
@require_auth()
def get_quality_assessment(listing_id):
    conn = get_db_connection()
    listing = conn.execute("SELECT id, farmer_id, village_centre_id, status FROM farmer_listings WHERE id = ?", (listing_id,)).fetchone()
    if not listing:
        conn.close()
        return jsonify({"error": "Listing not found"}), 404
        
    # Access control:
    # Farmer: only if owner
    # Village Centre: only if assigned to centre
    # Buyer: only if listing is Centre Verified
    if request.user['role'] == 'Farmer' and listing['farmer_id'] != request.user.get('profile_id'):
        conn.close()
        return jsonify({"error": "Permission denied. You cannot view assessments for another farmer's listing."}), 403
    elif request.user['role'] == 'Village Centre':
        assigned_centre = request.user.get('centre_id')
        if assigned_centre and listing['village_centre_id'] != assigned_centre:
            conn.close()
            return jsonify({"error": "Permission denied. Listing is not at your centre."}), 403
    elif request.user['role'] == 'Buyer' and listing['status'] != 'Centre Verified':
        conn.close()
        return jsonify({"error": "Permission denied. Assessment is not verified yet."}), 403
        
    qa = conn.execute("SELECT * FROM quality_assessments WHERE listing_id = ? ORDER BY assessment_date DESC LIMIT 1", (listing_id,)).fetchone()
    conn.close()
    if not qa:
        return jsonify({"error": "No quality assessment found for this listing"}), 404
    return jsonify(dict(qa))

# ==========================================
# PROTECTED: BUYER OFFERS API
# ==========================================

@app.route('/api/offers', methods=['GET', 'POST'])
@require_auth()
def manage_offers():
    conn = get_db_connection()
    if request.method == 'POST':
        if request.user['role'] != 'Buyer':
            conn.close()
            return jsonify({"error": "Permission denied. Only buyers can submit purchase offers."}), 403
            
        data = request.json
        required = ['listing_id', 'offered_price', 'quantity']
        if not data or not all(k in data for k in required):
            conn.close()
            return jsonify({"error": "Missing required fields (listing_id, offered_price, quantity)"}), 400
            
        buyer_id = request.user['profile_id']
        if not buyer_id:
            conn.close()
            return jsonify({"error": "Buyer profile unlinked or not found."}), 400
        
        try:
            offered_price = float(data['offered_price'])
            quantity = float(data['quantity'])
        except (ValueError, TypeError):
            conn.close()
            return jsonify({"error": "Price and quantity must be numeric"}), 400
            
        if offered_price <= 0 or quantity <= 0:
            conn.close()
            return jsonify({"error": "Price and quantity must be greater than 0"}), 400
            
        listing = conn.execute("SELECT quantity, status FROM farmer_listings WHERE id = ?", (data['listing_id'],)).fetchone()
        if not listing:
            conn.close()
            return jsonify({"error": "Listing not found"}), 404
            
        if listing['status'] == 'Sold':
            conn.close()
            return jsonify({"error": "This listing is already Sold and cannot accept new offers"}), 400
            
        if listing['status'] != 'Centre Verified':
            conn.close()
            return jsonify({"error": "Offers can only be made on Centre Verified listings"}), 400
            
        if quantity > listing['quantity']:
            conn.close()
            return jsonify({"error": "Offered quantity exceeds available listing quantity"}), 400
            
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO buyer_offers 
               (buyer_id, listing_id, offered_price, quantity, pickup_preference, validity_date, notes, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (buyer_id, data['listing_id'], offered_price, quantity,
             data.get('pickup_preference'), data.get('validity_date'), data.get('notes'), 'Pending')
        )
        offer_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"message": "Offer created successfully", "offer_id": offer_id}), 201
        
    else:
        # GET Offers scoped by ownership
        query = '''
            SELECT o.*, l.commodity, l.farmer_id 
            FROM buyer_offers o
            JOIN farmer_listings l ON o.listing_id = l.id
            WHERE 1=1
        '''
        params = []
        
        if request.user['role'] == 'Buyer':
            # Buyer only sees their own offers
            query += " AND o.buyer_id = ?"
            params.append(request.user['profile_id'])
        elif request.user['role'] == 'Farmer':
            # Farmer only sees offers made on their listings
            query += " AND l.farmer_id = ?"
            params.append(request.user['profile_id'])
        elif request.user['role'] == 'Village Centre':
            # Centre sees offers for listings at their centre
            assigned_centre = request.user.get('centre_id')
            if assigned_centre:
                query += " AND l.village_centre_id = ?"
                params.append(assigned_centre)
            
        query += " ORDER BY o.created_at DESC"
        offers = conn.execute(query, params).fetchall()
        conn.close()
        return jsonify([dict(o) for o in offers])

@app.route('/api/offers/<int:offer_id>', methods=['PATCH'])
@require_auth(allowed_roles=['Farmer'])
def update_offer_status(offer_id):
    # Strictly the owning Farmer can accept/reject an offer
    data = request.json
    if not data or 'status' not in data:
        return jsonify({"error": "Missing status in request body"}), 400
        
    new_status = data['status']
    if new_status not in ['Accepted', 'Rejected']:
        return jsonify({"error": "Invalid status. Allowed values are 'Accepted' or 'Rejected'."}), 400
        
    conn = get_db_connection()
    offer = conn.execute('''
        SELECT o.listing_id, o.status, l.farmer_id 
        FROM buyer_offers o 
        JOIN farmer_listings l ON o.listing_id = l.id 
        WHERE o.id = ?
    ''', (offer_id,)).fetchone()
    
    if not offer:
        conn.close()
        return jsonify({"error": "Offer not found"}), 404
        
    # IDOR check: Is the logged-in user the farmer who owns the listing?
    if offer['farmer_id'] != request.user['profile_id']:
        conn.close()
        return jsonify({"error": "Permission denied. You do not own the listing associated with this offer."}), 403
        
    cursor = conn.cursor()
    cursor.execute("UPDATE buyer_offers SET status = ? WHERE id = ?", (new_status, offer_id))
    
    if new_status == 'Accepted':
        cursor.execute("UPDATE farmer_listings SET status = 'Sold' WHERE id = ?", (offer['listing_id'],))
        cursor.execute("UPDATE buyer_offers SET status = 'Rejected' WHERE listing_id = ? AND id != ? AND status = 'Pending'", 
                       (offer['listing_id'], offer_id))
                       
    conn.commit()
    conn.close()
    return jsonify({"message": f"Offer status updated to {new_status}"})

# ==========================================
# PROTECTED: MATCHING API
# ==========================================

@app.route('/api/matches', methods=['GET'])
@require_auth(allowed_roles=['Buyer', 'Village Centre'])
def get_matches():
    req_id = request.args.get('buyer_requirement_id')
    if not req_id:
        return jsonify({"error": "buyer_requirement_id is required"}), 400
        
    conn = get_db_connection()
    req = conn.execute("SELECT * FROM buyer_requirements WHERE id = ?", (req_id,)).fetchone()
    
    if not req:
        conn.close()
        return jsonify({"error": "Requirement not found"}), 404
        
    # IDOR prevention: If Buyer, verify ownership of the requirement
    if request.user['role'] == 'Buyer' and req['buyer_id'] != request.user['profile_id']:
        conn.close()
        return jsonify({"error": "Permission denied. You cannot view matches for another buyer's requirement."}), 403
        
    listings = conn.execute('''
        SELECT l.*, f.district as farmer_district, f.state as farmer_state 
        FROM farmer_listings l
        JOIN farmers f ON l.farmer_id = f.id
        WHERE l.commodity = ? AND l.status = 'Centre Verified'
    ''', (req['commodity'],)).fetchall()
    
    matches = []
    for l in listings:
        matches.append({
            "listing_id": l['id'],
            "buyer_requirement_id": req['id'],
            "commodity": req['commodity'],
            "farmer_quantity": l['quantity'],
            "required_quantity": req['quantity'],
            "quality": l['quality_grade'],
            "farmer_expected_price": l['expected_price'],
            "buyer_target_price": req['target_price'],
            "match_score": 1
        })
        
    conn.close()
    return jsonify(matches)

# ==========================================
# PROTECTED: PRICE DISCOVERY API
# ==========================================

@app.route('/api/price-discovery/<int:listing_id>', methods=['GET'])
@require_auth()
def price_discovery(listing_id):
    conn = get_db_connection()
    listing = conn.execute("SELECT farmer_id, commodity, expected_price, verified_viable_price FROM farmer_listings WHERE id = ?", (listing_id,)).fetchone()
    
    if not listing:
        conn.close()
        return jsonify({"error": "Listing not found"}), 404
        
    commodity = listing['commodity']
    
    hist = conn.execute("SELECT AVG(modal_price) as avg_price FROM market_prices WHERE commodity = ?", (commodity,)).fetchone()
    hist_price = round(hist['avg_price'], 2) if hist and hist['avg_price'] else None
    
    offer = conn.execute("SELECT MAX(offered_price) as max_offer FROM buyer_offers WHERE listing_id = ? AND status != 'Rejected'", (listing_id,)).fetchone()
    buyer_offer = round(offer['max_offer'], 2) if offer and offer['max_offer'] else None
    
    conn.close()
    
    return jsonify({
        "listing_id": listing_id,
        "commodity": commodity,
        "farmer_expected_price": listing['expected_price'],
        "verified_viable_price": listing['verified_viable_price'],
        "buyer_offered_price_highest": buyer_offer,
        "historical_market_reference_price": hist_price,
        "data_disclaimer": "Historical market data is SYNTHETIC DEVELOPMENT DATA."
    })

if __name__ == '__main__':
    app.run(debug=False, port=5000, use_reloader=False)
