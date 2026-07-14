from playwright.sync_api import sync_playwright
import time
import re
import csv

def parse_listing(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    data = {
        "name": lines[0] if len(lines) > 0 else None,
        "house_type": None,
        "auction_dates": None,
        "status": None, 
        "price": None,
        "floor_area_sqm": None,
        "lot_area_sqm": None,
        "auction_type": "First Auction (New Listing)" # this scrape only covers this tab
    }

    # NOTE: Same property name appearing multiple times is expected behavior —
    # each row represents a distinct unit/lot within that subdivision, with its
    # own price, area, and auction schedule. Not a scraping bug.

    sqm_values = []
    for line in lines:
        if "occupied" in line.lower():
            data["status"] = line
        elif "-" in line and any(m in line for m in ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]):
            data["auction_dates"] = line.replace("\xa0", " ").replace("|", "").strip()
        elif "₱" in line:
            data["price"] = line
        elif "sqm" in line.lower():
            sqm_values.append(line)
        elif line in ["Row House", "Single Attached", "Single Detached", "Townhouse", "Condominium", "Duplex"]:
            data["house_type"] = line

    # First sqm value = floor area, second = lot area 
    if len(sqm_values) >=1:
        data["floor_area_sqm"] = sqm_values[0]
    if len(sqm_values) >=2:
        data["lot_area_sqm"] = sqm_values[1]

    return data

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    max_retries = 3
    loaded = False

    for attempt in range(max_retries):
        try:
            response = page.goto(
                "https://www.pagibigfundservices.com/OnlinePublicAuction",
                timeout=30000
            )
            print(f"Attempt {attempt + 1} - Status code: {response.status}")

            if response.status == 200:
                page.wait_for_load_state("networkidle")
                print("Page loaded successfully")
                loaded = True
                break
            else:
                wait_time = 60 * (attempt + 1)  # 60s, then 120s, then 180s
                print(f"Non-200 status ({response.status}), waiting {wait_time}s before retry...")
                time.sleep(wait_time)

        except Exception as e:
            wait_time = 60 * (attempt + 1)
            print(f"Attempt {attempt + 1} failed: {e}")
            print(f"Waiting {wait_time}s before retry...")
            time.sleep(wait_time)

    if not loaded:
        print("Could not load the page after retries. Try again later.")
        browser.close()
        exit()

    page.locator("#region").scroll_into_view_if_needed()
    page.select_option("#region", "040000000") # CALABARZON
    page.wait_for_timeout(2000)

    page.select_option("#province", "043400000") # LAGUNA
    page.wait_for_timeout(2000) # 

    page.select_option("#city", "043405000") # CITY OF CALAMBA
    page.wait_for_timeout(2000)

    # Click the Search button (it's an <a> tag, not a <button>)
    page.click("#search-button")
    page.wait_for_timeout(5000) # give results time to load

    # Extract all listing cards
    listings = page.query_selector_all("form#submitOffer_search")
    print(f"Found {len(listings)} listing forms")


    parsed_listings = []
    for listing in listings:
        text = listing.inner_text()
        parsed = parse_listing(text)
        parsed_listings.append(parsed)
    

    for i, p_data in enumerate(parsed_listings):
        print(f"{i+1}. {p_data}")

    # CSV export
    fieldnames = ["name", "house_type", "auction_dates", "status", "price", "floor_area_sqm", "lot_area_sqm", "auction_type"]
    with open("laguna_calamba_listings.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p_data in parsed_listings:
            writer.writerow(p_data)
    
    print(f"Saved {len(parsed_listings)} listings to laguna_calamba_listings.csv")

    page.screenshot(path="search_results_screenshot.png", full_page=True)
    print("Done. Closing in 15 seconds.")
    time.sleep(15)
    browser.close()