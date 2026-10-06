import streamlit as st
import pandas as pd
import os
from city_province_map import CITY_TO_PROVINCE

st.set_page_config(page_title="CALABARZON Listings", page_icon="🏠", layout="wide")

st.title("Pag-IBIG Acquired Asset Listings")
st.caption("CALABARZON region — scraped from the Online Public Auction platform")

HERE = os.path.dirname(__file__)
CSV_PATH = os.path.join(HERE, "calabarzon_all_listings.csv")

# Show when the data was last refreshed
last_updated_path = os.path.join(HERE, "last_updated.txt")
if os.path.exists(last_updated_path):
    with open(last_updated_path) as f:
        st.caption(f"📅 Last updated: {f.read().strip()}")
else:
    st.caption("📅 Last updated: not yet recorded")


@st.cache_data
def load_data(csv_mtime):
    """csv_mtime is not used inside; it is an argument so that the cache is
    refreshed whenever the CSV file changes (e.g. after a new scrape is pushed)."""
    try:
        df = pd.read_csv(CSV_PATH)
    except (pd.errors.EmptyDataError, FileNotFoundError):
        return pd.DataFrame()

    if "min_sellprice" not in df.columns:
        return pd.DataFrame()

    # Drop rows without a usable price so min()/max() can never return NaN
    df["min_sellprice"] = pd.to_numeric(df["min_sellprice"], errors="coerce")
    df = df.dropna(subset=["min_sellprice"])

    def parse_coords(val):
        try:
            lat, lon = str(val).split(",")
            return float(lat.strip()), float(lon.strip())
        except Exception:
            return None, None

    coords = df["ins_remarks"].apply(parse_coords)
    df["lat"] = coords.apply(lambda x: x[0])
    df["lon"] = coords.apply(lambda x: x[1])

    return df


csv_mtime = os.path.getmtime(CSV_PATH) if os.path.exists(CSV_PATH) else 0
df = load_data(csv_mtime)

if df.empty:
    st.error(
        "No valid listings in the latest scrape, so there is nothing to show. "
        "The data is probably stale; check the scraper log on the VM."
    )
    st.stop()

# --- Read URL parameters from Telegram bot links ---
query_params = st.query_params
url_province = query_params.get("province", None)
url_sort = query_params.get("sort", None)

if url_province:
    st.info(f"🔗 Filtered from Telegram link — showing **{url_province}** province")

# --- Sidebar filters ---
st.sidebar.header("Filters")

provinces = sorted(df["city_searched"].dropna().unique())

# If a province came from a Telegram link, pre-select only that
# province's cities; otherwise default to showing everything
if url_province:
    default_cities = [c for c in provinces if CITY_TO_PROVINCE.get(c) == url_province]
    if not default_cities:  # fallback if the province name didn't match anything
        default_cities = provinces
else:
    default_cities = provinces

selected_city = st.sidebar.multiselect("City / Municipality", provinces, default=default_cities)

prop_types = sorted(df["prop_type"].dropna().unique())
selected_type = st.sidebar.multiselect("Property Type", prop_types, default=prop_types)

occupancy_options = sorted(df["occupancy"].dropna().unique())
selected_occupancy = st.sidebar.multiselect("Occupancy", occupancy_options, default=occupancy_options)

min_price = int(df["min_sellprice"].min())
max_price = int(df["min_sellprice"].max())
if min_price < max_price:
    price_range = st.sidebar.slider("Price range (₱)", min_price, max_price, (min_price, max_price))
else:
    # A slider needs a range; with a single price there is nothing to filter
    price_range = (min_price, max_price)

# --- Apply filters ---
filtered = df[
    df["city_searched"].isin(selected_city) &
    df["prop_type"].isin(selected_type) &
    df["occupancy"].isin(selected_occupancy) &
    df["min_sellprice"].between(price_range[0], price_range[1])
]

# Apply sort from Telegram link, if present
if url_sort == "price_asc":
    filtered = filtered.sort_values("min_sellprice", ascending=True)
else:
    filtered = filtered.sort_values("min_sellprice")

st.write(f"**{len(filtered)}** listings match your filters (out of {len(df)} total)")

# --- Table view ---
display_cols = [
    "subdivision", "prop_location", "prop_type", "occupancy",
    "min_sellprice", "lot_area", "floor_area", "city_searched", "disposal_type"
]
st.dataframe(
    filtered[display_cols],
    use_container_width=True,
    hide_index=True
)

# --- Map view ---
st.subheader("Map")
map_data = filtered.dropna(subset=["lat", "lon"])
if len(map_data) > 0:
    st.map(map_data[["lat", "lon"]], zoom=8)
else:
    st.info("No valid GPS coordinates found in the current filter selection.")

# --- Quick stats ---
col1, col2, col3 = st.columns(3)
col1.metric("Total Listings", len(filtered))

median_price = filtered["min_sellprice"].median()
col2.metric("Median Price", f"₱{int(median_price):,}" if pd.notna(median_price) else "—")

avg_floor = pd.to_numeric(filtered["floor_area"], errors="coerce").mean()
col3.metric("Avg Floor Area", f"{avg_floor:.1f} sqm" if pd.notna(avg_floor) else "—")
