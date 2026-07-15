import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="CALABARZON Listings", page_icon="🏠", layout="wide")

st.title("Pag-IBIG Acquired Asset Listings")
st.caption("CALABARZON region — scraped from the Online Public Auction platform")

@st.cache_data
def load_data():
    csv_path = os.path.join(os.path.dirname(__file__), "calabarzon_all_listings.csv")
    df = pd.read_csv(csv_path)

    # Parse GPS coordinates out of ins_remarks (format: "lat, lng")
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

df = load_data()

# --- Sidebar filters ---
st.sidebar.header("Filters")

provinces = sorted(df["city_searched"].dropna().unique())
selected_city = st.sidebar.multiselect("City / Municipality", provinces, default=provinces)

prop_types = sorted(df["prop_type"].dropna().unique())
selected_type = st.sidebar.multiselect("Property Type", prop_types, default=prop_types)

occupancy_options = sorted(df["occupancy"].dropna().unique())
selected_occupancy = st.sidebar.multiselect("Occupancy", occupancy_options, default=occupancy_options)

min_price = int(df["min_sellprice"].min())
max_price = int(df["min_sellprice"].max())
price_range = st.sidebar.slider("Price range (₱)", min_price, max_price, (min_price, max_price))

# --- Apply filters ---
filtered = df[
    df["city_searched"].isin(selected_city) &
    df["prop_type"].isin(selected_type) &
    df["occupancy"].isin(selected_occupancy) &
    df["min_sellprice"].between(price_range[0], price_range[1])
]

st.write(f"**{len(filtered)}** listings match your filters (out of {len(df)} total)")

# --- Table view ---
display_cols = [
    "subdivision", "prop_location", "prop_type", "occupancy",
    "min_sellprice", "lot_area", "floor_area", "city_searched", "disposal_type"
]
st.dataframe(
    filtered[display_cols].sort_values("min_sellprice"),
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
col2.metric("Median Price", f"₱{int(filtered['min_sellprice'].median()):,}")
col3.metric("Avg Floor Area", f"{filtered['floor_area'].astype(float).mean():.1f} sqm")
