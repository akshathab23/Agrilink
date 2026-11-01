import os
import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import requests
from pathlib import Path

# --- CONFIGURATION ---
st.set_page_config(page_title="AgriLink Marketplace", page_icon="🌾", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main-header { font-size: 2.5rem; color: #2E8B57; font-weight: 700; margin-bottom: 0rem; }
    .sub-header { font-size: 1.2rem; color: #555; margin-bottom: 2rem; }
    .card-title { font-size: 1.2rem; font-weight: 600; color: #1E4620; }
    .highlight-text { color: #2E8B57; font-weight: bold; }
    .disclaimer { font-size: 0.9rem; color: #856404; background-color: #fff3cd; padding: 10px; border-radius: 5px; border-left: 5px solid #ffeeba; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #2E8B57; }
    .status-badge-pending { background-color: #ffeeba; color: #856404; padding: 4px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: bold; }
    .status-badge-verified { background-color: #d4edda; color: #155724; padding: 4px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- GLOBALS & STATE ---
DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).parent.parent / "backend" / "data" / "agrilink.db"))
API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:5000/api")

if 'role' not in st.session_state:
    st.session_state.role = 'Public'
if 'page' not in st.session_state:
    st.session_state.page = 'Home'

# --- UTILITY FUNCTIONS ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def format_inr(amount):
    if pd.isna(amount) or amount is None:
        return "N/A"
    return f"₹ {float(amount):,.2f}"

@st.cache_data(ttl=60)
def load_data(query, params=()):
    conn = get_db_connection()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def get_headers():
    headers = {}
    if 'token' in st.session_state and st.session_state.token:
        headers['Authorization'] = f"Bearer {st.session_state.token}"
    return headers

def fetch_api(endpoint, params=None):
    try:
        response = requests.get(f"{API_BASE_URL}/{endpoint}", params=params, headers=get_headers(), timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data: {e.response.json().get('error', str(e)) if hasattr(e, 'response') and e.response else str(e)}")
        return []

def post_api(endpoint, payload):
    try:
        response = requests.post(f"{API_BASE_URL}/{endpoint}", json=payload, headers=get_headers(), timeout=5)
        if response.status_code in [200, 201]:
            return True, response.json()
        return False, response.json().get("error", "Unknown error")
    except requests.exceptions.RequestException as e:
        return False, f"Connection error: {str(e)}"

def patch_api(endpoint, payload):
    try:
        response = requests.patch(f"{API_BASE_URL}/{endpoint}", json=payload, headers=get_headers(), timeout=5)
        if response.status_code in [200, 201]:
            return True, response.json()
        return False, response.json().get("error", "Unknown error")
    except requests.exceptions.RequestException as e:
        return False, f"Connection error: {str(e)}"

# --- NAVIGATION SETTINGS ---
ROLE_PAGES = {
    "Public": ["Home", "How It Works", "Market Prices", "Login / Register"],
    "Farmer": ["Dashboard", "My Produce", "Add Produce", "Quality Verification", "Offers", "Price Discovery"],
    "Buyer": ["Dashboard", "Find Produce", "My Requirements", "Offers", "Market Intelligence"],
    "Village Centre": ["Dashboard", "Incoming Produce", "Quality Assessment", "Price Verification", "Verified Listings", "Offers"]
}

# --- SIDEBAR ---
st.sidebar.markdown("<h2 style='color:#2E8B57;'>🌾 AgriLink</h2>", unsafe_allow_html=True)
st.sidebar.markdown("Village-Level Market Linkage")

st.sidebar.markdown("---")
if 'token' in st.session_state and st.session_state.token:
    st.sidebar.success(f"Logged in as: {st.session_state.role}")
    if st.sidebar.button("Logout", use_container_width=True):
        post_api("logout", {})
        st.session_state.token = None
        st.session_state.role = 'Public'
        st.session_state.page = 'Home'
        st.rerun()
else:
    st.sidebar.info("Currently viewing as Public")
    if st.session_state.page not in ROLE_PAGES["Public"]:
        st.session_state.role = "Public"
        st.session_state.page = "Home"
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.write("**Navigation**")
for p in ROLE_PAGES[st.session_state.role]:
    if st.sidebar.button(p, use_container_width=True, type="primary" if st.session_state.page == p else "secondary"):
        st.session_state.page = p
        st.rerun()


# ==========================================
# PUBLIC PAGES
# ==========================================
if st.session_state.page == "Home":
    st.markdown("<div class='main-header'>🌾 AgriLink</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Connect Farmers with Better Markets</div>", unsafe_allow_html=True)
    
    st.write("Helping farmers discover market prices, connect with buyers, and make informed selling decisions.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("I'm a Farmer", use_container_width=True, type="primary"):
            if 'token' in st.session_state and st.session_state.token and st.session_state.role == 'Farmer':
                st.session_state.page = "Dashboard"
            else:
                st.session_state.page = "Login / Register"
                st.session_state.login_intent = "Farmer"
            st.rerun()
    with col2:
        if st.button("I'm a Buyer", use_container_width=True, type="secondary"):
            if 'token' in st.session_state and st.session_state.token and st.session_state.role == 'Buyer':
                st.session_state.page = "Dashboard"
            else:
                st.session_state.page = "Login / Register"
                st.session_state.login_intent = "Buyer"
            st.rerun()
            
    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        with st.container(border=True):
            st.markdown("#### 📊 Transparent Market Prices")
    with c2:
        with st.container(border=True):
            st.markdown("#### 🧪 Verified Quality Information")
    with c3:
        with st.container(border=True):
            st.markdown("#### 🤝 Direct Buyer Connections")
    with c4:
        with st.container(border=True):
            st.markdown("#### 💰 Better Price Discovery")
            
    st.markdown("<div class='disclaimer'>Historical market data is SYNTHETIC DEVELOPMENT DATA and is not live AGMARKNET/government data.</div>", unsafe_allow_html=True)

elif st.session_state.page == "How It Works":
    st.title("🔄 How AgriLink Works")
    st.markdown("""
    1. **Produce Collection:** Farmer brings produce to village collection centre.
    2. **Quality Assessment:** Quality is physically assessed at the village collection centre. AgriLink records and shares the assessment information.
    3. **Verification:** Farmer verifies the recorded information.
    4. **Discovery:** Buyers discover produce.
    5. **Offers:** Buyer makes an offer.
    6. **Decision:** Farmer accepts or rejects.
    """)
    st.info("💡 Quality is physically assessed at the village collection centre. AgriLink records and shares the assessment information. It does not use automated AI/image detection.")

elif st.session_state.page == "Login / Register":
    st.title("🔐 Login / Register")
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        with st.form("login_form"):
            l_phone = st.text_input("Phone Number")
            l_pass = st.text_input("Password", type="password")
            if st.form_submit_button("Login", type="primary"):
                succ, res = post_api("login", {"phone": l_phone, "password": l_pass})
                if succ:
                    st.session_state.token = res['token']
                    st.session_state.role = res['role']
                    st.session_state.page = "Dashboard"
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error(res)
                    
    with tab2:
        with st.form("register_form"):
            r_role = st.selectbox("Role", ["Farmer", "Buyer"])
            r_name = st.text_input("Full Name")
            r_phone = st.text_input("Phone Number")
            r_pass = st.text_input("Password", type="password")
            states = load_data("SELECT DISTINCT state FROM markets ORDER BY state")['state'].tolist()
            r_state = st.selectbox("State", states)
            r_district = st.text_input("District")
            
            if st.form_submit_button("Register", type="primary"):
                if not r_phone or not r_pass or not r_name or not r_district:
                    st.error("Please fill all fields.")
                else:
                    succ, res = post_api("register", {
                        "role": r_role, "name": r_name, "phone": r_phone, "password": r_pass,
                        "state": r_state, "district": r_district
                    })
                    if succ:
                        st.success("Registered successfully! Please login.")
                    else:
                        st.error(res)


# ==========================================
# FARMER PAGES
# ==========================================
elif st.session_state.page == "Dashboard" and st.session_state.role == "Farmer":
    st.markdown("<div class='main-header'>🧑‍🌾 Farmer Dashboard</div>", unsafe_allow_html=True)
    
    listings = fetch_api("listings")
    offers = fetch_api("offers")
    
    my_listings_count = len(listings) if listings else 0
    active_offers = len([o for o in offers if o['status'] == 'Pending']) if offers else 0
    accepted_offers = len([o for o in offers if o['status'] == 'Accepted']) if offers else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("My Listings", my_listings_count)
    col2.metric("Active Offers", active_offers)
    col3.metric("Accepted Offers", accepted_offers)
    col4.metric("Latest Market Price", "Available via Explorer")
    
    st.markdown("---")
    st.subheader("Quick Actions")
    c1, c2 = st.columns(2)
    if c1.button("➕ Add Produce", use_container_width=True):
        st.session_state.page = "Add Produce"
        st.rerun()
    if c2.button("🔍 Verify Quality Assessment", use_container_width=True):
        st.session_state.page = "Quality Verification"
        st.rerun()

elif st.session_state.page == "My Produce" and st.session_state.role == "Farmer":
    st.title("📋 My Produce")
    listings = fetch_api("listings")
    if not listings:
        st.info("No listings available yet.")
    else:
        for l in listings:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                c1.markdown(f"#### 🌾 {l['commodity']}")
                c1.write(f"**Location:** {l['district']}, {l['state']}")
                c1.write(f"**Timeline:** {l['timeline']}")
                
                c2.write(f"**Quantity:** {l['quantity']} q")
                c2.write(f"**Grade:** {l['quality_grade']}")
                
                c3.write(f"**Expected Price:** {format_inr(l['expected_price'])}")
                if l['verified_viable_price']:
                    c3.write(f"**Verified Price:** {format_inr(l['verified_viable_price'])}")
                
                c4.markdown(f"**Status:** {l['status']}")
                if c4.button("View Details / Offers", key=f"fbtn_{l['id']}", use_container_width=True):
                    st.session_state.page = "Offers"
                    st.rerun()

elif st.session_state.page == "Add Produce" and st.session_state.role == "Farmer":
    st.title("➕ Add Produce")
    
    with st.form("add_produce_form"):
        st.subheader("Produce Information")
        c1, c2 = st.columns(2)
        commodities = load_data("SELECT DISTINCT commodity FROM market_prices ORDER BY commodity")['commodity'].tolist()
        f_commodity = c1.selectbox("Commodity *", commodities)
        f_quantity = c2.number_input("Quantity (Quintals) *", min_value=0.1)
        f_expected_price = c1.number_input("Farmer Expected Price (₹/Quintal)", min_value=0)
        f_timeline = c2.date_input("Selling Timeline")
        
        if st.form_submit_button("Submit to Village Centre", type="primary"):
            payload = {
                "commodity": f_commodity, "quantity": f_quantity, 
                "expected_price": f_expected_price if f_expected_price > 0 else None,
                "timeline": f_timeline.strftime("%Y-%m-%d")
            }
            succ, res = post_api("listings", payload)
            if succ:
                st.success("✅ Produce submitted! Status: Awaiting Village Centre Verification.")
            else:
                st.error("Failed to create listing: " + str(res))

elif st.session_state.page == "Quality Verification" and st.session_state.role == "Farmer":
    st.title("✅ Verify Quality Assessment")
    st.write("Review the physical quality assessment recorded by the Village Collection Centre.")
    
    listings = fetch_api("listings")
    if not listings:
        st.info("No listings found.")
    else:
        pending_verif = [l for l in listings if l['status'] == 'Awaiting Village Centre Verification' and not l.get('quality_verified_by_farmer')]
        if not pending_verif:
            st.info("No pending quality verifications at the moment.")
        else:
            opts = {f"Listing #{l['id']} - {l['commodity']}": l for l in pending_verif}
            sel = st.selectbox("Select Listing to Verify", list(opts.keys()))
            sel_l = opts[sel]
            
            qa = fetch_api(f"quality-assessments/{sel_l['id']}")
            if not qa or "error" in qa:
                st.warning("The Village Centre has not yet recorded the physical assessment for this listing.")
            else:
                st.markdown("### QUALITY ASSESSMENT")
                st.write("*Assessment performed at Village Collection Centre*")
                with st.container(border=True):
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"**Moisture:** {qa.get('moisture_pct')}%")
                    c2.write(f"**Foreign Matter:** {qa.get('foreign_matter_pct')}%")
                    c3.write(f"**Damaged Grains:** {qa.get('damaged_pct')}%")
                    c1.write(f"**Size:** {qa.get('size_category')}")
                    c2.write(f"**Ripeness:** {qa.get('ripeness')}")
                    c3.write(f"**Visual Damage:** {qa.get('visual_damage')}")
                    c1.write(f"**Final Grade:** {qa.get('final_grade')}")
                    c2.write(f"**Assessor:** {qa.get('assessor_name')}")
                    c3.write(f"**Assessment Date:** {qa.get('assessment_date')}")
                    
                st.info("I confirm that the quality information recorded above is correct.")
                if st.button("Confirm & Verify", type="primary"):
                    succ, res = patch_api(f"listings/{sel_l['id']}", {"quality_verified_by_farmer": 1})
                    if succ:
                        st.success("Quality Verified! Awaiting final Price Verification from Centre.")
                        st.rerun()
                    else:
                        st.error(res)


# ==========================================
# VILLAGE CENTRE PAGES
# ==========================================
elif st.session_state.page == "Dashboard" and st.session_state.role == "Village Centre":
    st.markdown("<div class='main-header'>🏘️ Village Centre Dashboard</div>", unsafe_allow_html=True)
    
    listings = fetch_api("listings")
    offers = fetch_api("offers")
    
    pend_prod = len([l for l in listings if l['status'] == 'Awaiting Village Centre Verification']) if listings else 0
    verif_prod = len([l for l in listings if l['status'] == 'Centre Verified']) if listings else 0
    pend_offers = len([o for o in offers if o['status'] == 'Pending']) if offers else 0
    acc_offers = len([o for o in offers if o['status'] == 'Accepted']) if offers else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Pending Produce", pend_prod)
    c2.metric("Verified Listings", verif_prod)
    c3.metric("Completed Offers", acc_offers)

elif st.session_state.page == "Incoming Produce" and st.session_state.role == "Village Centre":
    st.title("📥 Incoming Produce")
    listings = fetch_api("listings")
    if listings:
        incoming = [l for l in listings if l['status'] == 'Awaiting Village Centre Verification']
        if not incoming:
            st.info("No incoming produce awaiting assessment.")
        else:
            for l in incoming:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(f"#### {l['commodity']} ({l['quantity']} quintals)")
                    c1.write(f"**Farmer Expected Price:** {format_inr(l['expected_price'])}/q")
                    c1.write(f"**Village:** {l['village']}")
                    c2.markdown(f"**Status:** {l['status']}")
    else:
        st.info("No listings found.")

elif st.session_state.page == "Quality Assessment" and st.session_state.role == "Village Centre":
    st.title("🧪 Quality Assessment")
    st.write("Physical quality assessment is performed at the Village Collection Centre. The operator records the measured results in AgriLink.")
    
    listings = fetch_api("listings")
    if not listings:
        st.info("No incoming produce.")
    else:
        opts = {f"Listing #{l['id']} - {l['commodity']} ({l['quantity']}q)": l['id'] for l in listings if l['status'] == 'Awaiting Village Centre Verification'}
        if not opts:
            st.info("All current listings have been assessed.")
        else:
            sel = st.selectbox("Select Incoming Produce", list(opts.keys()))
            l_id = opts[sel]
            
            existing = fetch_api(f"quality-assessments/{l_id}")
            if existing and "error" not in existing:
                st.success("✅ Assessment Recorded.")
                st.json(existing)
                st.info("Awaiting Farmer Verification.")
            else:
                with st.form("qa_form"):
                    qc1, qc2, qc3 = st.columns(3)
                    q_moist = qc1.number_input("Moisture %", value=12.0)
                    q_foreign = qc2.number_input("Foreign Matter %", value=1.0)
                    q_damage = qc3.number_input("Damaged %", value=2.0)
                    q_size = qc1.selectbox("Size Category", ["Medium", "Large", "Small", "Mixed"])
                    q_ripeness = qc2.selectbox("Ripeness", ["Optimal", "Under-ripe", "Over-ripe"])
                    q_visual = qc3.selectbox("Visual Damage", ["None", "Low", "Medium", "High"])
                    q_grade = qc1.selectbox("Final Grade", ["FAQ", "Grade A", "Reject"])
                    q_assessor = qc2.text_input("Assessor Name")
                    
                    if st.form_submit_button("Record Assessment", type="primary"):
                        succ, res = post_api("quality-assessments", {
                            "listing_id": l_id, "moisture_pct": q_moist, "foreign_matter_pct": q_foreign,
                            "damaged_pct": q_damage, "size_category": q_size, "ripeness": q_ripeness,
                            "visual_damage": q_visual, "final_grade": q_grade, "assessor_name": q_assessor
                        })
                        if succ:
                            st.success("Assessment Recorded. Farmer can now verify.")
                            st.rerun()
                        else:
                            st.error(res)

elif st.session_state.page == "Price Verification" and st.session_state.role == "Village Centre":
    st.title("⚖️ Price Verification & Viability Calculation")
    st.write("Calculate a transparent viable price. Compare with market references to protect farmers and buyers.")
    
    listings = fetch_api("listings")
    if not listings:
        st.info("No listings.")
    else:
        # Needs QA verified by farmer but still Awaiting Centre Verification
        pending = [l for l in listings if l['status'] == 'Awaiting Village Centre Verification' and l.get('quality_verified_by_farmer')]
        if not pending:
            st.info("No listings ready for Price Verification. (Requires Farmer Quality Verification first).")
        else:
            opts = {f"Listing #{l['id']} - {l['commodity']}": l for l in pending}
            sel = st.selectbox("Select Listing", list(opts.keys()))
            l = opts[sel]
            
            # Fetch synthetic reference
            hist = load_data("SELECT AVG(modal_price) as avg_price FROM market_prices WHERE commodity = ?", (l['commodity'],))
            ref_price = round(hist.iloc[0]['avg_price'], 2) if not hist.empty and not pd.isna(hist.iloc[0]['avg_price']) else 0
            
            c1, c2 = st.columns([1, 1])
            with c1:
                with st.form("price_form"):
                    st.write("**Calculate Transparent Viable Price**")
                    base_price = st.number_input("Farmer Expected Price (₹/q)", value=float(l['expected_price'] or 0), disabled=True)
                    t_cost = st.number_input("Transport Cost (₹/q)", value=80.0)
                    l_cost = st.number_input("Labour/Handling Cost (₹/q)", value=40.0)
                    o_cost = st.number_input("Centre Operating Cost (₹/q)", value=20.0)
                    m_cost = st.number_input("Centre Sustainability Margin (₹/q)", value=20.0)
                    
                    viable_price = base_price + t_cost + l_cost + o_cost + m_cost
                    st.markdown(f"### Calculated Viable Price: {format_inr(viable_price)}")
                    
                    if st.form_submit_button("Save & Verify Listing", type="primary"):
                        succ, res = patch_api(f"listings/{l['id']}", {
                            "transport_cost": t_cost,
                            "labour_cost": l_cost,
                            "centre_operating_cost": o_cost,
                            "centre_margin": m_cost,
                            "verified_viable_price": viable_price,
                            "market_reference_price": ref_price,
                            "status": "Centre Verified"
                        })
                        if succ:
                            st.success("✅ Listing is now Centre Verified and visible to buyers!")
                            st.rerun()
                        else:
                            st.error(res)
                            
            with c2:
                st.write("**Market Price Reference**")
                st.markdown(f"<h2>{format_inr(ref_price)}/q</h2>", unsafe_allow_html=True)
                st.markdown("<div class='disclaimer'>Historical market data is SYNTHETIC DEVELOPMENT DATA and is not live AGMARKNET/government data.</div>", unsafe_allow_html=True)
                
                # Validation status preview
                diff = abs((viable_price - ref_price) / ref_price) if ref_price > 0 else 0
                st.write("---")
                if diff > 0.3:
                    st.warning("⚠️ **Requires Review:** Calculated price is significantly different from synthetic reference.")
                else:
                    st.success("✅ **Within Acceptable Range**")

elif st.session_state.page == "Verified Listings" and st.session_state.role == "Village Centre":
    st.title("✅ Verified Listings")
    listings = fetch_api("listings?status=Centre Verified")
    if not listings:
        st.info("No centre verified listings.")
    else:
        for l in listings:
            with st.container(border=True):
                st.write(f"**Listing #{l['id']} - {l['commodity']} ({l['quantity']}q)**")
                st.write(f"Verified Viable Price: {format_inr(l.get('verified_viable_price'))}")


# ==========================================
# BUYER PAGES
# ==========================================
elif st.session_state.page == "Dashboard" and st.session_state.role == "Buyer":
    st.markdown("<div class='main-header'>🏢 Buyer Dashboard</div>", unsafe_allow_html=True)
    reqs = fetch_api("buyer-requirements")
    offers = fetch_api("offers")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Requirements", len(reqs) if reqs else 0)
    c2.metric("Pending Offers", len([o for o in offers if o['status'] == 'Pending']) if offers else 0)
    c3.metric("Accepted Offers", len([o for o in offers if o['status'] == 'Accepted']) if offers else 0)
    
    st.markdown("---")
    if st.button("🔍 Find Verified Produce", use_container_width=True, type="primary"):
        st.session_state.page = "Find Produce"
        st.rerun()

elif st.session_state.page == "Find Produce" and st.session_state.role == "Buyer":
    st.title("🔍 Find Produce")
    st.write("Browse Village Centre Verified produce.")
    
    listings = fetch_api("listings")
    if listings:
        verified = [l for l in listings if l['status'] == 'Centre Verified']
        if not verified:
            st.info("No verified listings available right now.")
        else:
            for l in verified:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    with c1:
                        st.markdown(f"#### 🌾 {l['commodity']}")
                        st.write(f"**Quantity:** {l['quantity']} Quintals")
                        st.write(f"**Grade:** {l['quality_grade']}")
                        st.write(f"**Location:** {l['village']}, {l['district']}")
                        st.markdown("<span class='status-badge-verified'>CENTRE VERIFIED</span>", unsafe_allow_html=True)
                    with c2:
                        qa = fetch_api(f"quality-assessments/{l['id']}")
                        if qa and "error" not in qa:
                            st.write(f"**Moisture:** {qa.get('moisture_pct')}%")
                            st.write(f"**Foreign Matter:** {qa.get('foreign_matter_pct')}%")
                            st.write(f"**Damaged:** {qa.get('damaged_pct')}%")
                            st.caption("*Quality assessment recorded at Village Collection Centre.*")
                    with c3:
                        st.write(f"**Farmer Base:** {format_inr(l['expected_price'])}")
                        st.markdown(f"**Verified Viable Price:**")
                        st.markdown(f"<h3 style='color:#2E8B57; margin:0;'>{format_inr(l.get('verified_viable_price'))}</h3>", unsafe_allow_html=True)
                        if st.button("Make Offer", key=f"mkoffer_{l['id']}", type="primary", use_container_width=True):
                            st.session_state.page = "Offers"
                            st.session_state.target_listing_id = l['id']
                            st.rerun()
    else:
        st.info("No listings found.")

elif st.session_state.page == "My Requirements" and st.session_state.role == "Buyer":
    st.title("📋 My Requirements")
    
    with st.expander("➕ Post New Requirement"):
        with st.form("req_form"):
            c1, c2 = st.columns(2)
            commodities = load_data("SELECT DISTINCT commodity FROM market_prices ORDER BY commodity")['commodity'].tolist()
            r_commodity = c1.selectbox("Commodity", commodities)
            r_qty = c2.number_input("Quantity Required (q)", min_value=1.0)
            r_price = c1.number_input("Target Price (₹/q)", min_value=0.0)
            r_date = c2.date_input("Required By")
            
            if st.form_submit_button("Post Requirement", type="primary"):
                succ, res = post_api("buyer-requirements", {
                    "commodity": r_commodity, "quantity": r_qty,
                    "target_price": r_price if r_price > 0 else None, "required_by": r_date.strftime("%Y-%m-%d")
                })
                if succ:
                    st.success("Requirement posted!")
                    st.rerun()
                else:
                    st.error("Failed: " + str(res))
                    
    st.markdown("---")
    reqs = fetch_api("buyer-requirements?mine=true")
    if reqs:
        for r in reqs:
            with st.container(border=True):
                st.write(f"**Req #{r['id']} | {r['commodity']}** - {r['quantity']}q by {r['required_by']} | Target: {format_inr(r['target_price'])}")
    else:
        st.info("No requirements yet.")


# ==========================================
# SHARED / OFFERS
# ==========================================
elif st.session_state.page == "Offers":
    st.title("🤝 Offers")
    
    tab_m, tab_v = st.tabs(["Make an Offer", "Manage Existing Offers"])
    
    with tab_m:
        st.subheader("Submit an Offer")
        listings = fetch_api("listings")
        if listings:
            listings = [l for l in listings if l['status'] == 'Centre Verified']
            
        if not listings:
            st.warning("No Centre Verified listings available for offers.")
        else:
            list_opts = {f"Listing #{l['id']} - {l['commodity']} ({l['quantity']}q)": l for l in listings}
            idx = 0
            if hasattr(st.session_state, 'target_listing_id'):
                target_keys = [k for k, v in list_opts.items() if v['id'] == st.session_state.target_listing_id]
                if target_keys:
                    idx = list(list_opts.keys()).index(target_keys[0])
                    
            sel_l_key = st.selectbox("Select Listing", list(list_opts.keys()), index=idx)
            l_data = list_opts[sel_l_key]
            
            # Transparent Cost Breakdown
            with st.expander("View Transparent Cost Breakdown"):
                st.write(f"**Base Farmer Price:** {format_inr(l_data.get('expected_price'))}")
                st.write(f"**Transport:** {format_inr(l_data.get('transport_cost'))}")
                st.write(f"**Labour:** {format_inr(l_data.get('labour_cost'))}")
                st.write(f"**Centre Operations:** {format_inr(l_data.get('centre_operating_cost'))}")
                st.write(f"**Centre Sustainability Margin:** {format_inr(l_data.get('centre_margin'))}")
                st.markdown(f"**Verified Viable Price: {format_inr(l_data.get('verified_viable_price'))}**")
            
            with st.form("offer_form"):
                o_price = st.number_input("Offer Price (₹/Quintal) *", min_value=1.0)
                o_qty = st.number_input("Quantity *", min_value=0.1)
                o_pickup = st.selectbox("Pickup Preference", ["Buyer Arranges Transport", "Farmer Delivers"])
                o_valid = st.date_input("Offer Validity")
                
                submitted = st.form_submit_button("Submit Offer", type="primary")
                if submitted:
                    viable_price = float(l_data.get('verified_viable_price') or 0)
                    if viable_price > 0 and o_price < viable_price:
                        st.warning("⚠️ Offer is below the centre verified viable price. It will be recorded, but may be rejected by the farmer.")
                        
                    succ, res = post_api("offers", {
                        "listing_id": l_data['id'], "offered_price": o_price,
                        "quantity": o_qty, "pickup_preference": o_pickup, "validity_date": o_valid.strftime("%Y-%m-%d")
                    })
                    if succ:
                        st.success("Offer successfully placed!")
                    else:
                        st.error(f"Failed to place offer: {res}")
                        
    with tab_v:
        st.subheader("Manage Offers")
        offers = fetch_api("offers")
        if not offers:
            st.info("No offers exist.")
        else:
            for o in offers:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    c1.write(f"**Offer #{o['id']}** (Buyer #{o['buyer_id']} → Listing #{o['listing_id']})")
                    c1.write(f"**Status:** {o['status']}")
                    
                    c2.write(f"**Quantity:** {o['quantity']}q")
                    c2.write(f"**Offered Price:** {format_inr(o['offered_price'])}")
                    
                    val = o['quantity'] * o['offered_price']
                    c3.write(f"**Total Value:**")
                    c3.markdown(f"<span style='color:#2E8B57; font-weight:bold;'>{format_inr(val)}</span>", unsafe_allow_html=True)
                    
                    if o['status'] == 'Pending':
                        with c4:
                            if st.session_state.role == "Farmer":
                                if st.button("Accept", key=f"acc_{o['id']}", type="primary", use_container_width=True):
                                    succ, res = patch_api(f"offers/{o['id']}", {"status": "Accepted"})
                                    if succ:
                                        st.success("Offer accepted! Listing is now Sold.")
                                        st.rerun()
                                    else:
                                        st.error(res)
                                if st.button("Reject", key=f"rej_{o['id']}", use_container_width=True):
                                    patch_api(f"offers/{o['id']}", {"status": "Rejected"})
                                    st.rerun()
                            else:
                                st.write("*Awaiting Farmer Decision*")

elif st.session_state.page == "Price Discovery":
    st.title("💡 Price Discovery")
    st.write("Compare expected prices against actual market trends and existing buyer offers to make informed selling decisions.")
    
    listings = fetch_api("listings")
    if not listings:
        st.info("No listings available yet.")
    else:
        list_opts = {f"Listing #{l['id']} - {l['commodity']}": l['id'] for l in listings}
        sel = st.selectbox("Select a Listing to Discover Prices", list(list_opts.keys()))
        l_id = list_opts[sel]
        
        discovery = fetch_api(f"price-discovery/{l_id}")
        
        if discovery:
            st.markdown("---")
            st.markdown(f"<h3 style='text-align:center;'>Price Signals for {discovery['commodity']}</h3>", unsafe_allow_html=True)
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                with st.container(border=True):
                    st.markdown("<p style='text-align:center; color:#555;'>Farmer Expected</p>", unsafe_allow_html=True)
                    st.markdown(f"<h3 style='text-align:center; color:#1E4620;'>{format_inr(discovery.get('farmer_expected_price'))}</h3>", unsafe_allow_html=True)
            with c2:
                with st.container(border=True):
                    st.markdown("<p style='text-align:center; color:#555;'>Verified Viable</p>", unsafe_allow_html=True)
                    st.markdown(f"<h3 style='text-align:center; color:#1E4620;'>{format_inr(discovery.get('verified_viable_price'))}</h3>", unsafe_allow_html=True)
            with c3:
                with st.container(border=True):
                    st.markdown("<p style='text-align:center; color:#555;'>Highest Offer</p>", unsafe_allow_html=True)
                    st.markdown(f"<h3 style='text-align:center; color:#2E8B57;'>{format_inr(discovery.get('buyer_offered_price_highest'))}</h3>", unsafe_allow_html=True)
            with c4:
                with st.container(border=True):
                    st.markdown("<p style='text-align:center; color:#555;'>Historical Reference</p>", unsafe_allow_html=True)
                    st.markdown(f"<h3 style='text-align:center; color:#6c757d;'>{format_inr(discovery.get('historical_market_reference_price'))}</h3>", unsafe_allow_html=True)
            
            st.markdown(f"<div class='disclaimer'><strong>Note:</strong> {discovery.get('data_disclaimer')}</div>", unsafe_allow_html=True)

elif st.session_state.page == "Market Prices":
    st.title("📊 Market Price Analytics")
    st.markdown("<div class='disclaimer'>Historical market data shown here is SYNTHETIC DEVELOPMENT DATA and is not live AGMARKNET/government data.</div><br>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["Market Price Explorer", "Price Trends", "Market Comparison"])
    
    with tab1:
        st.subheader("Explore Historical Prices")
        c1, c2 = st.columns(2)
        states = load_data("SELECT DISTINCT state FROM markets ORDER BY state")
        sel_state = c1.selectbox("State Filter", ["All"] + states['state'].tolist())
        commodities = load_data("SELECT DISTINCT commodity FROM market_prices ORDER BY commodity")
        sel_comm = c2.selectbox("Commodity Filter", ["All"] + commodities['commodity'].tolist())
        
        query = "SELECT m.state, m.district, m.market_name, p.commodity, p.arrival_date, p.modal_price, p.min_price, p.max_price FROM market_prices p JOIN markets m ON p.market_id = m.id WHERE 1=1"
        params = []
        if sel_state != "All":
            query += " AND m.state = ?"
            params.append(sel_state)
        if sel_comm != "All":
            query += " AND p.commodity = ?"
            params.append(sel_comm)
        query += " ORDER BY p.arrival_date DESC LIMIT 50"
        
        df = load_data(query, params)
        if not df.empty:
            df['modal_price'] = df['modal_price'].apply(format_inr)
            df['min_price'] = df['min_price'].apply(format_inr)
            df['max_price'] = df['max_price'].apply(format_inr)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No records found.")
            
    with tab2:
        sel_c = st.selectbox("Select Commodity", commodities['commodity'].tolist(), key='t_c')
        trend_data = fetch_api(f"trends?commodity={sel_c}")
        if trend_data:
            df_trend = pd.DataFrame(trend_data)
            fig = px.line(df_trend, x="arrival_date", y="avg_modal_price", title=f"30-Day Trend: {sel_c}")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trend data available.")
            
    with tab3:
        sel_comp = st.selectbox("Select Commodity", commodities['commodity'].tolist(), key='c_c')
        comp_query = "SELECT m.market_name, AVG(p.modal_price) as avg_price FROM market_prices p JOIN markets m ON p.market_id = m.id WHERE p.commodity = ? GROUP BY m.id ORDER BY avg_price DESC LIMIT 15"
        df_comp = load_data(comp_query, [sel_comp])
        if not df_comp.empty:
            fig2 = px.bar(df_comp, x="market_name", y="avg_price", title=f"Top 15 Markets for {sel_comp}")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No comparison data available.")

elif st.session_state.page == "Market Intelligence":
    st.title("📈 Market Intelligence")
    
    st.subheader("Platform Demand Analytics")
    reqs = fetch_api("buyer-requirements")
    if not reqs:
        st.info("No buyer requirements available yet.")
    else:
        df_reqs = pd.DataFrame(reqs)
        c1, c2 = st.columns(2)
        
        d_by_crop = df_reqs.groupby("commodity")["quantity"].sum().reset_index()
        fig1 = px.pie(d_by_crop, values='quantity', names='commodity', title='Buyer Quantity Demanded by Commodity')
        c1.plotly_chart(fig1, use_container_width=True)
        
        avg_target = df_reqs.groupby("commodity")["target_price"].mean().reset_index()
        fig2 = px.bar(avg_target, x='commodity', y='target_price', title='Average Buyer Target Price (₹/q)')
        c2.plotly_chart(fig2, use_container_width=True)
        
        offers = fetch_api("offers")
        if offers:
            df_offs = pd.DataFrame(offers)
            st.markdown("---")
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Total Offers Made", len(df_offs))
            accepted = len(df_offs[df_offs['status'] == 'Accepted'])
            mc2.metric("Accepted Transactions", accepted)
            rate = (accepted / len(df_offs)) * 100 if len(df_offs) > 0 else 0
            mc3.metric("Offer Acceptance Rate", f"{rate:.1f}%")
