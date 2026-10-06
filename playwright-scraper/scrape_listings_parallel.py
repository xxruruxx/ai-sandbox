"""Scrape Pag-IBIG ROPA auction listings for CALABARZON.

Optional environment overrides:
  WORKERS         provinces scraped at the same time          (default 3)
  PAGE_LOAD_MS    timeout for the initial page load           (default 180000)
  MIN_TOTAL_ROWS  refuse to overwrite the CSV below this      (default 50)
  BLOCK_HEAVY     1 = skip images/fonts/analytics requests    (default 1)
  ONLY            scrape just this province, e.g. ONLY=RIZAL  (default: all)
  OUT_CSV         write here instead of calabarzon_all_listings.csv

The CSV is only replaced when every province loaded and the total row count
is at least MIN_TOTAL_ROWS. Otherwise the previous CSV is kept and the script
exits with status 1, so run_scraper.sh (set -e) will not commit anything.
"""
import base64
import csv
import json
import logging
import os
import sys
import tempfile
import threading
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

URL = "https://www.pagibigfundservices.com/OnlinePublicAuction"
HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.getenv("OUT_CSV") or os.path.join(HERE, "calabarzon_all_listings.csv")

WORKERS = int(os.getenv("WORKERS", "3"))
PAGE_LOAD_MS = int(os.getenv("PAGE_LOAD_MS", "180000"))
MIN_TOTAL_ROWS = int(os.getenv("MIN_TOTAL_ROWS", "50"))
BLOCK_HEAVY = os.getenv("BLOCK_HEAVY", "1") == "1"
ONLY = os.getenv("ONLY", "").strip().upper()

DEFAULT_TIMEOUT_MS = 90000
MAX_LOAD_ATTEMPTS = 3
BLOCKED_TYPES = {"image", "font", "media"}
BLOCKED_HOSTS = ("google-analytics.com", "googletagmanager.com")

PROVINCES = [
    ("041000000", "BATANGAS"),
    ("042100000", "CAVITE"),
    ("043400000", "LAGUNA"),
    ("045600000", "QUEZON"),
    ("045800000", "RIZAL"),
]

FIELDNAMES = [
    "ropa_id", "batch_no", "subdivision", "prop_location", "prop_type",
    "tct_cct_no", "lot_area", "floor_area", "min_sellprice", "occupancy",
    "status", "status_bid", "disposal_type", "start_datetime", "end_datetime",
    "appr_date", "inspection_date", "ins_remarks", "remarks", "city_muni",
    "handling_hbc", "contact_hbc", "email_hbc", "survey_no", "city_searched",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s [%(threadName)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("pagibig")


def decode_property_data(encoded_str):
    try:
        decoded_bytes = base64.b64decode(encoded_str)
        decoded_str = decoded_bytes.decode("utf-8", errors="replace")
        return json.loads(decoded_str)
    except Exception as e:
        return {"decode_error": str(e)}


def wait_for_dropdown_populated(page, selector, min_options=2, timeout_ms=60000):
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
        timeout=timeout_ms,
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


def settle(page, timeout_ms=30000):
    """Best-effort wait for the network to go quiet. A timeout is logged but
    never fatal, because this site is slow and has background requests."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeout:
        log.warning("networkidle not reached within %ds, continuing", timeout_ms // 1000)


def _route(route):
    req = route.request
    if req.resource_type in BLOCKED_TYPES or any(h in req.url for h in BLOCKED_HOSTS):
        route.abort()
    else:
        route.continue_()


def load_page(page):
    """Load the auction page. The server is slow (the page can take ~60s),
    so wait for DOMContentLoaded instead of the full load event."""
    for attempt in range(1, MAX_LOAD_ATTEMPTS + 1):
        t = time.time()
        try:
            response = page.goto(URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_MS)
            if response is not None and response.status == 200:
                page.wait_for_selector("#region", timeout=DEFAULT_TIMEOUT_MS)
                settle(page)
                log.info("Page loaded in %.1fs (attempt %d)", time.time() - t, attempt)
                return True
            status = response.status if response is not None else "no response"
            log.warning("Attempt %d: HTTP %s after %.1fs", attempt, status, time.time() - t)
        except Exception as e:
            first_line = str(e).splitlines()[0] if str(e) else type(e).__name__
            log.warning("Attempt %d failed after %.1fs: %s", attempt, time.time() - t, first_line)
        if attempt < MAX_LOAD_ATTEMPTS:
            wait_time = 30 * attempt
            log.info("Retrying in %ds", wait_time)
            time.sleep(wait_time)
    return False


def extract_all_pages(page, city_name):
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
                log.warning("DECODE FAILED in %s: %s", city_name, data["decode_error"])
                continue
            data["city_searched"] = city_name
            all_listings.append(data)

        log.info("%s page %d: %d listings (total: %d)",
                 city_name, page_num, len(listings), len(all_listings))

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


def scrape_province(province_value, province_name):
    """Returns (listings, ok). ok=False means the province could not be
    scraped at all (page never loaded, or the dropdowns failed)."""
    province_listings = []
    city_errors = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_default_timeout(DEFAULT_TIMEOUT_MS)
            if BLOCK_HEAVY:
                page.route("**/*", _route)

            if not load_page(page):
                log.error("Could not load page, giving up")
                return [], False

            try:
                page.select_option("#region", "040000000")
                wait_for_dropdown_populated(page, "#province")
                page.select_option("#province", province_value)
                wait_for_dropdown_populated(page, "#city", min_options=2)

                city_options = page.eval_on_selector_all(
                    "#city option",
                    """opts => opts
                        .filter(o => o.value && o.value.trim() !== '' && !o.textContent.toLowerCase().includes('select'))
                        .map(o => ({value: o.value, text: o.textContent.trim()}))""",
                )
            except Exception as e:
                log.error("Could not read city list: %s", str(e).splitlines()[0])
                return [], False

            log.info("Found %d cities", len(city_options))

            for n, city in enumerate(city_options, start=1):
                t = time.time()
                log.info("--- [%d/%d] %s ---", n, len(city_options), city["text"])
                try:
                    page.select_option("#city", city["value"])
                    page.wait_for_timeout(1500)

                    selected_value = page.eval_on_selector("#city", "el => el.value")
                    if selected_value != city["value"]:
                        page.select_option("#city", city["value"])
                        page.wait_for_timeout(1500)

                    page.click("#search-button")
                    settle(page)
                    page.wait_for_timeout(2000)

                    city_listings = extract_all_pages(page, city["text"])

                    for issue in validate_listings(city_listings, city["text"]):
                        log.warning("VALIDATION: %s", issue)

                    log.info("%s: %d listings in %.1fs",
                             city["text"], len(city_listings), time.time() - t)
                    province_listings.extend(city_listings)

                except Exception as e:
                    city_errors += 1
                    first_line = str(e).splitlines()[0] if str(e) else type(e).__name__
                    log.error("Error scraping %s after %.1fs: %s",
                              city["text"], time.time() - t, first_line)

                time.sleep(8)
        finally:
            browser.close()

    if city_errors:
        log.warning("%d of the cities in this province errored", city_errors)
    return province_listings, True


def save_csv(rows, path):
    """Write to a temp file in the same folder, then swap it in, so a crash
    mid-write can never leave a half-written CSV behind."""
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=folder, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def main():
    provinces = [p for p in PROVINCES if not ONLY or p[1] == ONLY]
    if not provinces:
        log.error("ONLY=%s matches no province", ONLY)
        return 1

    gate = threading.Semaphore(WORKERS)
    lock = threading.Lock()
    all_results = []
    failed = []

    def worker(value, name):
        with gate:
            started = time.time()
            try:
                listings, ok = scrape_province(value, name)
            except Exception:
                log.exception("Unhandled error")
                listings, ok = [], False
        with lock:
            all_results.extend(listings)
            if not ok:
                failed.append(name)
        log.info("DONE - %d listings in %.1f min%s", len(listings),
                 (time.time() - started) / 60, "" if ok else " (FAILED)")

    threads = [
        threading.Thread(target=worker, args=(val, name), name=name)
        for val, name in provinces
    ]

    log.info("Starting %d provinces, %d at a time (page load timeout %ds, block heavy=%s)",
             len(threads), WORKERS, PAGE_LOAD_MS // 1000, BLOCK_HEAVY)
    start = time.time()

    for t in threads:
        t.start()
        time.sleep(3)
    for t in threads:
        t.join()

    log.info("All provinces finished in %.1f minutes", (time.time() - start) / 60)
    log.info("Total listings: %d", len(all_results))

    if failed:
        log.error("Provinces that failed: %s. NOT overwriting %s", ", ".join(failed), CSV_PATH)
        return 1
    if len(all_results) < MIN_TOTAL_ROWS:
        log.error("Only %d listings (minimum %d). NOT overwriting %s",
                  len(all_results), MIN_TOTAL_ROWS, CSV_PATH)
        return 1

    save_csv(all_results, CSV_PATH)
    log.info("Saved %d listings to %s", len(all_results), CSV_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
