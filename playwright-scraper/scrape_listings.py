from playwright.sync_api import sync_playwright
import time
import csv
import base64
import json


def decode_property_data(encoded_str):
    try:
        decoded_bytes = base64.b64decode(encoded_str)
        decoded_str = decoded_bytes.decode("utf-8", errors="replace")  # replace bad bytes instead of crashing
        return json.loads(decoded_str)
    except Exception as e:
        return {"decode_error": str(e)}


def extract_all_pages(page, city_name):
    """Extract listings from the current search results, looping through pagination."""
    all_listings = []
    page_num = 1

    while True:
        page.wait_for_timeout(2000)
        listings = page.query_selector_all("form#submitOffer_search")

        for listing in listings:
            details_link = listing.query_selector("a.view-more-details")
            if not details_link:
                print(f"    WARNING: no details link found for a listing in {city_name}")
                continue

            encoded = details_link.get_attribute("data-property")
            if not encoded:
                print(f"    WARNING: no data-property attribute for a listing in {city_name}")
                continue

            data = decode_property_data(encoded)

            if "decode_error" in data:
                print(f"    DECODE FAILED for a listing in {city_name}: {data['decode_error']}")
                continue  # skip this broken record instead of appending it

            data["city_searched"] = city_name
            all_listings.append(data)

        print(f"  Page {page_num}: extracted {len(listings)} listings (running total: {len(all_listings)})")

        next_button = page.query_selector("a:has-text('Next'), li.next a, [aria-label='Next']")
        if next_button:
            classes = next_button.get_attribute("class") or ""
            if "disabled" in classes.lower():
                break
            try:
                next_button.click()
                page_num += 1
                page.wait_for_timeout(3000)
            except Exception:
                break
        else:
            break

    return all_listings

def validate_listings(listings, city_name, min_expected=1):
    """Catch silent failures before they reach the CSV -- this is exactly
    the kind of check that would have caught the Biñan encoding bug
    automatically instead of relying on manual spot-checking."""
    issues = []

    if len(listings) < min_expected:
        issues.append(f"{city_name}: only {len(listings)} listings found (expected at least {min_expected})")

    critical_fields = ["ropa_id", "min_sellprice", "prop_location"]
    for i, listing in enumerate(listings):
        for field in critical_fields:
            if not listing.get(field):
                issues.append(f"{city_name}: listing #{i} missing critical field '{field}'")

    return issues


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
                wait_time = 60 * (2 ** attempt)
                print(f"Non-200 status, waiting {wait_time}s...")
                time.sleep(wait_time)
        except Exception as e:
            wait_time = 60 * (2 ** attempt)
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(wait_time)

    if not loaded:
        print("Could not load page. Try again later.")
        browser.close()
        exit()

    page.locator("#region").scroll_into_view_if_needed()
    page.select_option("#region", "040000000")  # CALABARZON
    page.wait_for_timeout(2000)

    page.select_option("#province", "043400000")  # LAGUNA
    page.wait_for_timeout(2000)

    city_options = page.eval_on_selector_all(
        "#city option",
        "opts => opts.filter(o => o.value).map(o => ({value: o.value, text: o.textContent.trim()}))"
    )
    print(f"Found {len(city_options)} cities in Laguna\n")

    master_listings = []

    for city in city_options:
            print(f"--- Scraping {city['text']} ---")
            try:
                page.select_option("#city", city["value"])
                page.wait_for_timeout(1500)

                selected_value = page.eval_on_selector("#city", "el => el.value")
                if selected_value != city["value"]:
                    print(f"  WARNING: selection mismatch, retrying...")
                    page.select_option("#city", city["value"])
                    page.wait_for_timeout(1500)

                page.click("#search-button")
                page.wait_for_load_state("networkidle")  # wait for network to settle, not just a fixed timeout
                page.wait_for_timeout(2000)  # small extra buffer after network settles

                city_listings = extract_all_pages(page, city["text"])

                # Validate before accepting this city's data
                issues = validate_listings(city_listings, city["text"])
                if issues:
                    print(f"  VALIDATION ISSUES for {city['text']}:")
                    for issue in issues:
                        print(f"    - {issue}")
                    
                print(f"  {city['text']}: {len(city_listings)} listings")
                master_listings.extend(city_listings)

            except Exception as e:
                print(f"  Error scraping {city['text']}: {e}")

            time.sleep(8)

    print(f"\nTotal listings across all Laguna cities: {len(master_listings)}")

    # Save to CSV -- using the real decoded field names from Pag-IBIG's own data
    fieldnames = [
        "ropa_id", "batch_no", "subdivision", "prop_location", "prop_type",
        "tct_cct_no", "lot_area", "floor_area", "min_sellprice", "occupancy",
        "status", "status_bid", "disposal_type", "start_datetime", "end_datetime",
        "appr_date", "inspection_date", "ins_remarks", "remarks", "city_muni",
        "handling_hbc", "contact_hbc", "email_hbc", "survey_no", "city_searched"
    ]

    with open("laguna_all_listings.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in master_listings:
            writer.writerow(row)

    print(f"Saved {len(master_listings)} listings to laguna_all_listings.csv")
    browser.close()