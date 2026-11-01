"""
AgriLink – Synthetic Development Data Generator
================================================
DISCLAIMER: This script generates SYNTHETIC / SIMULATED data for
development and demonstration purposes ONLY.

The values produced are NOT real government market prices.
They are NOT sourced from Agmarknet, data.gov.in, or any official body.
They are generated algorithmically to mimic the structure and rough
price ranges of real Indian mandi data for educational purposes.

Output: backend/data/raw/agmarknet_sample.csv
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date

# ── Reproducibility ──────────────────────────────────────────────────────────
SEED = 42
rng = np.random.default_rng(SEED)
TARGET_ROWS = 100_000

# ── Output path ──────────────────────────────────────────────────────────────
OUT_DIR = Path(__file__).parent / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "agmarknet_sample.csv"

# ── Market geography ─────────────────────────────────────────────────────────
# (State, District, Market) triples.
# Karnataka gets ~40 % of all markets to satisfy the extra-representation rule.

MARKETS = [
    # ── Karnataka (extra representation) ────────────────────────────────
    ("Karnataka", "Bengaluru Rural",    "Yelahanka APMC"),
    ("Karnataka", "Bengaluru Rural",    "Attibele APMC"),
    ("Karnataka", "Mysuru",             "Mysuru APMC"),
    ("Karnataka", "Mysuru",             "Nanjangud APMC"),
    ("Karnataka", "Tumakuru",           "Tumakuru APMC"),
    ("Karnataka", "Tumakuru",           "Tiptur APMC"),
    ("Karnataka", "Kolar",              "Kolar APMC"),
    ("Karnataka", "Kolar",              "Mulbagal APMC"),
    ("Karnataka", "Hassan",             "Hassan APMC"),
    ("Karnataka", "Hassan",             "Holenarasipur APMC"),
    ("Karnataka", "Shivamogga",         "Shivamogga APMC"),
    ("Karnataka", "Dharwad",            "Dharwad APMC"),
    ("Karnataka", "Dharwad",            "Hubli APMC"),
    ("Karnataka", "Belagavi",           "Belagavi APMC"),
    ("Karnataka", "Belagavi",           "Gokak APMC"),
    ("Karnataka", "Vijayapura",         "Vijayapura APMC"),
    ("Karnataka", "Vijayapura",         "Indi APMC"),
    ("Karnataka", "Raichur",            "Raichur APMC"),
    ("Karnataka", "Raichur",            "Manvi APMC"),
    ("Karnataka", "Bagalkot",           "Bagalkot APMC"),
    ("Karnataka", "Chikkamagaluru",     "Chikkamagaluru APMC"),
    ("Karnataka", "Dakshina Kannada",   "Mangaluru APMC"),
    ("Karnataka", "Udupi",              "Udupi APMC"),
    ("Karnataka", "Ballari",            "Ballari APMC"),
    ("Karnataka", "Koppal",             "Koppal APMC"),
    ("Karnataka", "Gadag",              "Gadag APMC"),
    ("Karnataka", "Haveri",             "Haveri APMC"),
    ("Karnataka", "Mandya",             "Mandya APMC"),
    ("Karnataka", "Chamarajanagar",     "Chamarajanagar APMC"),
    ("Karnataka", "Bidar",              "Bidar APMC"),
    # ── Maharashtra ──────────────────────────────────────────────────────
    ("Maharashtra", "Pune",             "Pune (Gultekdi) APMC"),
    ("Maharashtra", "Nashik",           "Nashik APMC"),
    ("Maharashtra", "Nashik",           "Lasalgaon APMC"),
    ("Maharashtra", "Sangli",           "Sangli APMC"),
    ("Maharashtra", "Kolhapur",         "Kolhapur APMC"),
    ("Maharashtra", "Solapur",          "Solapur APMC"),
    ("Maharashtra", "Aurangabad",       "Aurangabad APMC"),
    ("Maharashtra", "Amravati",         "Amravati APMC"),
    ("Maharashtra", "Nagpur",           "Nagpur APMC"),
    # ── Andhra Pradesh ───────────────────────────────────────────────────
    ("Andhra Pradesh", "Kurnool",       "Kurnool APMC"),
    ("Andhra Pradesh", "Guntur",        "Guntur APMC"),
    ("Andhra Pradesh", "Krishna",       "Vijayawada APMC"),
    ("Andhra Pradesh", "Nellore",       "Nellore APMC"),
    ("Andhra Pradesh", "Chittoor",      "Chittoor APMC"),
    # ── Telangana ────────────────────────────────────────────────────────
    ("Telangana", "Hyderabad",          "Bowenpally APMC"),
    ("Telangana", "Warangal",           "Warangal APMC"),
    ("Telangana", "Nizamabad",          "Nizamabad APMC"),
    # ── Tamil Nadu ───────────────────────────────────────────────────────
    ("Tamil Nadu", "Coimbatore",        "Coimbatore APMC"),
    ("Tamil Nadu", "Salem",             "Salem APMC"),
    ("Tamil Nadu", "Madurai",           "Madurai APMC"),
    ("Tamil Nadu", "Vellore",           "Vellore APMC"),
    ("Tamil Nadu", "Erode",             "Erode APMC"),
    # ── Uttar Pradesh ────────────────────────────────────────────────────
    ("Uttar Pradesh", "Agra",           "Agra Mandi"),
    ("Uttar Pradesh", "Lucknow",        "Lucknow Mandi"),
    ("Uttar Pradesh", "Kanpur",         "Kanpur Mandi"),
    ("Uttar Pradesh", "Varanasi",       "Varanasi Mandi"),
    # ── Punjab ───────────────────────────────────────────────────────────
    ("Punjab", "Ludhiana",              "Ludhiana Grain Market"),
    ("Punjab", "Amritsar",              "Amritsar Grain Market"),
    ("Punjab", "Patiala",               "Patiala Grain Market"),
    # ── Rajasthan ────────────────────────────────────────────────────────
    ("Rajasthan", "Jaipur",             "Jaipur Mandi"),
    ("Rajasthan", "Jodhpur",            "Jodhpur Mandi"),
    ("Rajasthan", "Kota",               "Kota Mandi"),
    # ── Madhya Pradesh ───────────────────────────────────────────────────
    ("Madhya Pradesh", "Indore",        "Indore Mandi"),
    ("Madhya Pradesh", "Bhopal",        "Bhopal Mandi"),
    ("Madhya Pradesh", "Jabalpur",      "Jabalpur Mandi"),
    # ── Gujarat ──────────────────────────────────────────────────────────
    ("Gujarat", "Ahmedabad",            "Ahmedabad APMC"),
    ("Gujarat", "Rajkot",               "Rajkot APMC"),
    ("Gujarat", "Surat",                "Surat APMC"),
    # ── West Bengal ──────────────────────────────────────────────────────
    ("West Bengal", "Kolkata",          "Sealdah Market"),
    ("West Bengal", "Hooghly",          "Shyambazar Market"),
    # ── Odisha ───────────────────────────────────────────────────────────
    ("Odisha", "Bhubaneswar",           "Bhubaneswar APMC"),
    ("Odisha", "Cuttack",               "Cuttack APMC"),
    # ── Haryana ──────────────────────────────────────────────────────────
    ("Haryana", "Hisar",                "Hisar Mandi"),
    ("Haryana", "Karnal",               "Karnal Mandi"),
    # ── Kerala ───────────────────────────────────────────────────────────
    ("Kerala", "Ernakulam",             "Ernakulam Market"),
    ("Kerala", "Thrissur",              "Thrissur Market"),
]

# ── Commodity catalogue ───────────────────────────────────────────────────────
# Each entry: (Commodity, Variety, Grade, base_price, seasonal_amp, seasonality_peak_month)
# Prices in ₹/quintal.  seasonal_amp = fraction of base price that swings seasonally.
COMMODITIES = [
    # Vegetables
    ("Tomato",       "Local",          "FAQ",        1200,  0.80, 12),   # cheapest in winter
    ("Tomato",       "Hybrid",         "Grade A",    1600,  0.75, 12),
    ("Onion",        "Local Red",      "FAQ",        1500,  0.60,  5),   # peak May
    ("Onion",        "Nasik Red",      "Grade A",    1800,  0.55,  5),
    ("Potato",       "Jyoti",          "FAQ",        1200,  0.40,  3),
    ("Potato",       "Kufri Chandra",  "Grade A",    1500,  0.35,  3),
    ("Chilli",       "Byadagi",        "FAQ",        8000,  0.50,  2),
    ("Chilli",       "Guntur Sannam",  "Grade A",   10000,  0.45,  2),
    ("Coriander",    "Local",          "FAQ",        6000,  0.40,  3),
    # Fruits
    ("Banana",       "Robusta",        "FAQ",        1500,  0.30,  6),
    ("Banana",       "Nendran",        "Grade A",    2500,  0.25,  6),
    ("Coconut",      "Hybrid",         "FAQ",        2800,  0.20, 11),
    # Cereals / Grains
    ("Paddy",        "IR-64",          "FAQ",        2100,  0.10, 11),   # peak post-kharif
    ("Paddy",        "Sona Masuri",    "Grade A",    2400,  0.12, 11),
    ("Maize",        "Yellow",         "FAQ",        1800,  0.20, 10),
    ("Wheat",        "Lok-1",          "FAQ",        2100,  0.10,  4),
    ("Wheat",        "GW-322",         "Grade A",    2300,  0.08,  4),
    ("Ragi",         "Local",          "FAQ",        2200,  0.15, 10),
    ("Ragi",         "GPU-28",         "Grade A",    2500,  0.12, 10),
    # Pulses
    ("Bengal Gram",  "Local",          "FAQ",        5000,  0.20,  3),
    ("Bengal Gram",  "Desi",           "Grade A",    5500,  0.18,  3),
    ("Tur Dal",      "Local",          "FAQ",        7000,  0.25,  1),
    ("Green Gram",   "Local",          "FAQ",        6500,  0.20,  5),
    # Oilseeds / Cash crops
    ("Groundnut",    "Bold",           "FAQ",        5500,  0.30,  2),
    ("Groundnut",    "Runner",         "Grade A",    6000,  0.25,  2),
    ("Sunflower",    "KBSH-44",        "FAQ",        6000,  0.20,  5),
    ("Sesame",       "Local",          "FAQ",        9000,  0.30,  3),
    ("Cotton",       "Long Staple",    "FAQ",       65000,  0.15, 11),   # ₹/quintal
    ("Cotton",       "Medium Staple",  "Grade A",   60000,  0.12, 11),
    ("Sugarcane",    "CO-86032",       "FAQ",         3500, 0.10,  2),
    ("Sugarcane",    "CO-419",         "Grade A",     3800, 0.08,  2),
    ("Soybean",      "Local",          "FAQ",         4500, 0.20, 10),
    ("Turmeric",     "Nizamabad",      "FAQ",        10000, 0.35,  3),
    ("Ginger",       "Green",          "FAQ",        10000, 0.50,  5),
    ("Garlic",       "Local",          "FAQ",         8000, 0.55,  4),
]

# ── Date range ────────────────────────────────────────────────────────────────
START_DATE = date(2024, 1, 1)
END_DATE   = date(2025, 12, 31)
all_dates  = pd.date_range(START_DATE, END_DATE, freq="D")

# ── Market weights (Karnataka ~40 %) ─────────────────────────────────────────
karnataka_idx  = [i for i, m in enumerate(MARKETS) if m[0] == "Karnataka"]
other_idx      = [i for i, m in enumerate(MARKETS) if m[0] != "Karnataka"]
n_k = len(karnataka_idx)
n_o = len(other_idx)

# Each Karnataka market gets weight 0.40/n_k, others share 0.60
weights = np.zeros(len(MARKETS))
weights[karnataka_idx] = 0.40 / n_k
weights[other_idx]     = 0.60 / n_o

print("Generating synthetic data...")

rows = []
base_count = TARGET_ROWS

for _ in range(base_count):
    # Pick market
    market_idx = rng.choice(len(MARKETS), p=weights)
    state, district, market = MARKETS[market_idx]

    # Pick commodity
    comm_idx = rng.integers(len(COMMODITIES))
    commodity, variety, grade, base_price, seasonal_amp, peak_month = COMMODITIES[comm_idx]

    # Pick date
    date_idx = rng.integers(len(all_dates))
    date_val = all_dates[date_idx]
    month = date_val.month

    # Seasonal multiplier: sinusoidal, peaks at peak_month
    angle = 2 * np.pi * (month - peak_month) / 12
    seasonal_factor = 1.0 + seasonal_amp * np.sin(angle + np.pi / 2)

    # Market-level jitter (each market is ~±15 % from seasonal price)
    market_seed = (market_idx * 31 + comm_idx * 7) % 1000
    market_offset = (market_seed / 1000 - 0.5) * 0.30

    modal = int(base_price * seasonal_factor * (1 + market_offset))
    modal = max(100, modal)  # floor

    # Spread: Min and Max are ±5–25 % around Modal
    spread_low  = rng.uniform(0.05, 0.25)
    spread_high = rng.uniform(0.05, 0.20)
    min_price   = max(50, int(modal * (1 - spread_low)))
    max_price   = int(modal * (1 + spread_high))

    # Ensure min <= modal <= max
    min_price = min(min_price, modal)
    max_price = max(max_price, modal)

    rows.append({
        "State":        state,
        "District":     district,
        "Market":       market,
        "Commodity":    commodity,
        "Variety":      variety,
        "Grade":        grade,
        "Arrival_Date": date_val.strftime("%d/%m/%Y"),
        "Min_Price":    min_price,
        "Max_Price":    max_price,
        "Modal_Price":  modal,
    })

df = pd.DataFrame(rows)

# ── Inject intentional missing values (~1.5 %) ───────────────────────────────
n_missing = int(len(df) * 0.015)
# Grade missing (common in real Agmarknet data)
grade_missing_idx = rng.choice(df.index, size=n_missing // 2, replace=False)
df.loc[grade_missing_idx, "Grade"] = np.nan

# Variety missing
variety_missing_idx = rng.choice(df.index, size=n_missing // 2, replace=False)
df.loc[variety_missing_idx, "Variety"] = np.nan

# Some Modal_Price missing (rare)
price_missing_idx = rng.choice(df.index, size=int(n_missing * 0.1), replace=False)
df.loc[price_missing_idx, "Modal_Price"] = np.nan

# ── Inject intentional duplicate rows (~0.5 %) ───────────────────────────────
n_dupes = int(len(df) * 0.005)
dupe_src = df.sample(n=n_dupes, random_state=SEED)
df = pd.concat([df, dupe_src], ignore_index=True)

# Shuffle
df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)

# ── Save ──────────────────────────────────────────────────────────────────────
df.to_csv(OUT_FILE, index=False)

# ── Report ────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("SYNTHETIC DATASET GENERATION COMPLETE")
print("="*60)
print(f"File location   : {OUT_FILE.resolve()}")
print(f"Total rows      : {len(df):,}")
print(f"Total columns   : {len(df.columns)}")
print(f"Columns         : {list(df.columns)}")
print(f"States          : {sorted(df['State'].dropna().unique().tolist())}")
print(f"No. of states   : {df['State'].nunique()}")
print(f"Commodities     : {sorted(df['Commodity'].dropna().unique().tolist())}")
print(f"No. of commod.  : {df['Commodity'].nunique()}")
print(f"Date range      : {df['Arrival_Date'].min()}  -->  {df['Arrival_Date'].max()}")
print(f"\nMissing values per column:")
print(df.isnull().sum().to_string())
print(f"\nDuplicate rows  : {df.duplicated().sum():,}")
print(f"File size       : {OUT_FILE.stat().st_size / 1024 / 1024:.2f} MB")
print("="*60)
print("\nNOTE: This is SYNTHETIC data for development only.")
print("Not sourced from Agmarknet or any government database.")
