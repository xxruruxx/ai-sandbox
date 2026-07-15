from playwright.sync_api import sync_playwright
import threading
import time
import csv
import base64
import json


def decode_property_data(encoded_str):
    try:
        decoded_bytes = base64.b64decode(encoded_str)
        decoded_str = decoded_bytes.decode("utf-8", errors="replace")
        return json.loads(decoded_str)
    except Exception as e:
        return {"decode_error": str(e)}


def wait_for_dropdown_populated(page, selector, min_options=2, timeout_ms=15000):
    """Wait until a dropdown has REAL populated options, filtering out
    anything that looks like a placeholder by text, not just by value
    truthiness (which proved unreliable under concurrent load)."""
    page.wait_for_function(
        f"""() => {{
            const opts = document.querySelector('{selector}').options;
            const real = Array.from(opts).filter(o =>
                o.value &&
                o.value.trim() !== '' &&
                !o.textContent.toLowerCase().includes('select')
            );
            return real.length >= {min_options - 1};
        }}""",
        timeout=timeout_ms
    )
    page.wait_for_timeout(500)


def validate_listings(listings, city_name, min_expected=1):
    issues = []
    if len(listings) < min_expected:
        issues.append(f"{city_name}: only {len(listings)} listings found")
    critical_fields = ["ropa_id", "min_sellprice", "prop_location"]
    for i, listing in enumerate(listings):
        for field in critical_fields:
            if not listing.get(field):
                issues.append(f"{city_name}: listing #{i} missing '{field}'")
    return issues


def extract_all_pages(page, city_name, log_prefix):
    all_listings = []
    page_num = 1
    while True:
        page.wait_for_timeout(2000)
        listings = page.query_selector_all("form#submitOffer_search")
        for listing in listings:
            details_link = listing.query_selector("a.view-more-details")
            if not details_link:
                continue
            encoded = details_link.get_attribute("data-property")
            if not encoded:
                continue
            data = decode_property_data(encoded)
            if "decode_error" in data:
                print(f"{log_prefix} DECODE FAILED in {city_name}: {data['decode_error']}")
                continue
            data["city_searched"] = city_name
            all_listings.append(data)

        print(f"{log_prefix} Page {page_num}: {len(listings)} listings (total: {len(all_listings)})")

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


def scrape_province(province_value, province_name, all_results, results_lock):
    log_prefix = f"[{province_name}]"
    province_listings = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        max_retries = 3
        loaded = False
        for attempt in range(max_retries):
            try:
                response = page.goto(
                    "https://www.pagibigfundservices.com/OnlinePublicAuction",
                    timeout=30000
                )
                if response.status == 200:
                    page.wait_for_load_state("networkidle")
                    loaded = True
                    break
                else:
                    wait_time = 60 * (2 ** attempt)
                    print(f"{log_prefix} Non-200 status, waiting {wait_time}s...")
                    time.sleep(wait_time)
            except Exception as e:
                wait_time = 60 * (2 ** attempt)
                print(f"{log_prefix} Attempt {attempt + 1} failed: {e}")
                time.sleep(wait_time)

        if not loaded:
            print(f"{log_prefix} Could not load page, giving up.")
            browser.close()
            return

        try:
            page.select_option("#region", "040000000")
            wait_for_dropdown_populated(page, "#province")
            page.select_option("#province", province_value)
            wait_for_dropdown_populated(page, "#city", min_options=2)

            city_options = page.eval_on_selector_all(
                "#city option",
                """opts => opts
                    .filter(o => o.value && o.value.trim() !== '' && !o.textContent.toLowerCase().includes('select'))
                    .map(o => ({value: o.value, text: o.textContent.trim()}))"""
            )
            print(f"{log_prefix} Found {len(city_options)} cities")

            for city in city_options:
                print(f"{log_prefix} --- Scraping {city['text']} ---")
                try:
                    page.select_option("#city", city["value"])
                    page.wait_for_timeout(1500)

                    selected_value = page.eval_on_selector("#city", "el => el.value")
                    if selected_value != city["value"]:
                        page.select_option("#city", city["value"])
                        page.wait_for_timeout(1500)

                    page.click("#search-button")
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(2000)

                    city_listings = extract_all_pages(page, city["text"], log_prefix)

                    issues = validate_listings(city_listings, city["text"])
                    if issues:
                        for issue in issues:
                            print(f"{log_prefix} VALIDATION: {issue}")

                    print(f"{log_prefix} {city['text']}: {len(city_listings)} listings")
                    province_listings.extend(city_listings)

                except Exception as e:
                    print(f"{log_prefix} Error scraping {city['text']}: {e}")

                time.sleep(8)

        except Exception as e:
            print(f"{log_prefix} Error: {e}")

        browser.close()

    with results_lock:
        all_results.extend(province_listings)
    print(f"{log_prefix} DONE - {len(province_listings)} total listings")


provinces = [
    ("041000000", "BATANGAS"),
    ("042100000", "CAVITE"),
    ("043400000", "LAGUNA"),
    ("045600000", "QUEZON"),
    ("045800000", "RIZAL"),
]

all_results = []
results_lock = threading.Lock()

threads = [
    threading.Thread(target=scrape_province, args=(val, name, all_results, results_lock))
    for val, name in provinces
]

print(f"Starting {len(threads)} province threads in parallel...")
start = time.time()

for t in threads:
    t.start()
    time.sleep(3)

for t in threads:
    t.join()

elapsed = time.time() - start
print(f"All provinces finished in {elapsed/60:.1f} minutes")
print(f"Total listings across CALABARZON: {len(all_results)}")

fieldnames = [
    "ropa_id", "batch_no", "subdivision", "prop_location", "prop_type",
    "tct_cct_no", "lot_area", "floor_area", "min_sellprice", "occupancy",
    "status", "status_bid", "disposal_type", "start_datetime", "end_datetime",
    "appr_date", "inspection_date", "ins_remarks", "remarks", "city_muni",
    "handling_hbc", "contact_hbc", "email_hbc", "survey_no", "city_searched"
]

with open("calabarzon_all_listings.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in all_results:
        writer.writerow(row)

print(f"Saved {len(all_results)} listings to calabarzon_all_listings.csv")
