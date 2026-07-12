from playwright.sync_api import sync_playwright
import time

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

    # scroll directly to the region dropdown element
    page.locator("#region").scroll_into_view_if_needed()
    page.select_option("#region", "040000000")
    page.wait_for_timeout(3000)  # give province dropdown time to populate

    province_html = page.eval_on_selector("#province", "el => el.outerHTML")
    print(province_html)

    page.screenshot(path="test_screenshot.png", full_page=True)

    # keep browser open a moment so you can manually look around if needed
    print("Done. Closing in 10 seconds...")
    time.sleep(10)
    browser.close()