-- AgriLink SQLite Schema

-- 1. Markets
CREATE TABLE IF NOT EXISTS markets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    district TEXT NOT NULL,
    market_name TEXT NOT NULL,
    UNIQUE(state, district, market_name)
);

-- 2. Market Price Records
CREATE TABLE IF NOT EXISTS market_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id INTEGER NOT NULL,
    commodity TEXT NOT NULL,
    variety TEXT NOT NULL,
    grade TEXT NOT NULL,
    arrival_date DATE NOT NULL,
    min_price REAL NOT NULL,
    max_price REAL NOT NULL,
    modal_price REAL NOT NULL,
    FOREIGN KEY (market_id) REFERENCES markets (id)
);

-- Index for faster price lookups and trend generation
CREATE INDEX IF NOT EXISTS idx_market_prices_commodity ON market_prices(commodity);
CREATE INDEX IF NOT EXISTS idx_market_prices_date ON market_prices(arrival_date);

-- 3. Farmers
CREATE TABLE IF NOT EXISTS farmers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    state TEXT NOT NULL,
    district TEXT NOT NULL
);

-- 4. Farmer Crop Requirements / Listings
CREATE TABLE IF NOT EXISTS farmer_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    commodity TEXT NOT NULL,
    quantity REAL NOT NULL, 
    quality_grade TEXT NOT NULL,
    expected_price REAL,
    timeline TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farmer_id) REFERENCES farmers (id)
);



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
    