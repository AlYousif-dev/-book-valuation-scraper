import os
import json
import re
import pandas as pd
import asyncio
import aiohttp
import random
import time

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from main import get_book_title


# -----------------------------
# CONFIG
# -----------------------------
CACHE_FILE = "/Users/alyousif/Desktop/Personal/Book-Barcode-Alpha/book_cache.json"
ISBN_FILE = "isbns.txt"

CONCURRENCY_LIMIT = 1
MIN_DELAY = 1.2

last_request_time = 0
request_lock = asyncio.Lock()

# consecutive NOT_FOUND counter
not_found_count = 0
request_count = 0 

# -----------------------------
# CACHE
# -----------------------------
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache_data):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache_data, f, indent=4)


# -----------------------------
# PRICE EXTRACTION
# -----------------------------
def extract_prices(soup):

    prices = []

    items = soup.select(".s-item, .s-card")

    for item in items:

        text = item.get_text(" ", strip=True).lower()

        # Skip noisy listings
        skip_words = [
            "shipping",
            "best offer",
            "shop on ebay",
            "similar sponsored",
            "results matching fewer words"
        ]

        if any(word in text for word in skip_words):
            continue

        # Multiple fallback selectors
        price_elem = (
            item.select_one(".s-item__price") or
            item.select_one(".s-card__price") or
            item.select_one("[data-testid='price']")
        )

        if not price_elem:
            continue

        price_text = price_elem.get_text(" ", strip=True)

        # Skip ranges
        if " to " in price_text.lower():
            continue

        match = re.search(r"\$([0-9,.]+)", price_text)

        if not match:
            continue

        try:
            price = float(match.group(1).replace(",", ""))

            # realistic used book range
            if 0.5 <= price <= 500:
                prices.append(price)

        except Exception:
            continue

    return prices


# -----------------------------
# SCRAPER
# -----------------------------
async def scrape_isbn(
    isbn,
    ebay_session,
    google_session,
    cache,
    semaphore,
    file_lock
):

    global last_request_time
    global not_found_count

    isbn = isbn.strip()

    if not isbn:
        return

    # skip already cached
    if isbn in cache:
        print(f"Skipping cached ISBN: {isbn}")
        return

    async with semaphore:

        try:

            print(f"\nProcessing: {isbn}")

            # -----------------------------
            # GOOGLE BOOKS
            # -----------------------------
            title = await get_book_title(isbn, google_session)

            if title == "NOT_FOUND":
                search_query = isbn
            else:
                search_query = f"{title} book"

            print(f"Search Query: {search_query}")

            # -----------------------------
            # RATE LIMIT
            # -----------------------------
            async with request_lock:

                now = time.time()

                wait_time = MIN_DELAY - (now - last_request_time)

                if wait_time > 0:

                    await asyncio.sleep(
                        wait_time + random.uniform(0.3, 1.3)
                    )

                last_request_time = time.time()

            # -----------------------------
            # HEADERS
            # -----------------------------
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.ebay.com/"
            }

            params = {
                "_nkw": search_query,
                "LH_Sold": "1",
                "LH_Complete": "1",
                "_ipg": "250",
                "_sop": "13",
                "rt": "nc"
            }

            # -----------------------------
            # REQUEST
            # -----------------------------
            resp = await ebay_session.get(
                "https://www.ebay.com/sch/i.html",
                params=params,
                headers=headers,
                timeout=30
            )

            # human-ish cooldown
            await asyncio.sleep(random.uniform(0.4,1.2 ))

            html = resp.text.lower()

            # -----------------------------
            # BLOCK DETECTION
            # -----------------------------
            blocked_words = [
                "captcha",
                "robot check",
                "verify yourself",
                "access denied"
            ]

            if any(word in html for word in blocked_words):

                print(f"BLOCKED by eBay: {isbn}")

                cache[isbn] = "BLOCKED"

                async with file_lock:
                    save_cache(cache)

                return

            # -----------------------------
            # PARSE
            # -----------------------------
            soup = BeautifulSoup(resp.text, "html.parser")

            prices = extract_prices(soup)

            print(f"Prices found: {len(prices)}")

            # -----------------------------
            # ANALYSIS
            # -----------------------------
            if prices:

                # successful scrape resets counter
                not_found_count = 0

                print("NOT_FOUND streak reset to 0")

                df = pd.DataFrame(prices, columns=["Price"])

                # IQR outlier removal
                q1 = df["Price"].quantile(0.25)
                q3 = df["Price"].quantile(0.75)

                iqr = q3 - q1

                filtered = df[
                    (df["Price"] >= q1 - 1.5 * iqr) &
                    (df["Price"] <= q3 + 1.5 * iqr)
                ]

                if len(filtered) == 0:
                    filtered = df

                cache[isbn] = {
                    "title": title,
                    "avg": round(filtered["Price"].mean(), 2),
                    "median": round(filtered["Price"].median(), 2),
                    "min": round(filtered["Price"].min(), 2),
                    "max": round(filtered["Price"].max(), 2),
                    "count": int(len(filtered)),
                    "updated": time.strftime("%Y-%m-%d")
                }

                print(
                    f"Saved: {isbn} | "
                    f"Median: ${cache[isbn]['median']}"
                )

            else:

                print(f"No prices found: {isbn}")

                not_found_count += 1

                print(
                    f"NOT_FOUND streak: "
                    f"{not_found_count}"
                )

                cache[isbn] = "NOT_FOUND"

                # -----------------------------
                # BACKOFF SYSTEM
                # -----------------------------
                if not_found_count >= 3:

                    sleep_time = 180  # 3 minutes

                    print(
                        f"\nToo many NOT_FOUND results "
                        f"({not_found_count} in a row). "
                        f"Sleeping for {sleep_time} seconds...\n"
                    )

                    await asyncio.sleep(sleep_time)

                    # reset after cooldown
                    not_found_count = 0

                    print(
                        "Cooldown finished. "
                        "NOT_FOUND streak reset."
                    )

            # -----------------------------
            # SAVE CACHE
            # -----------------------------
            async with file_lock:
                save_cache(cache)

            print(f"Finished: {isbn}")

        except Exception as e:

            print(f"Error processing {isbn}: {e}")

            cache[isbn] = f"ERROR: {str(e)}"

            async with file_lock:
                save_cache(cache)


# -----------------------------
# MAIN
# -----------------------------
async def main():

    if not os.path.exists(ISBN_FILE):
        print("isbns.txt not found")
        return

    with open(ISBN_FILE, "r") as f:

        isbn_list = [
            line.strip()
            for line in f
            if line.strip()
        ]

    print(f"Loaded {len(isbn_list)} ISBNs")

    cache = load_cache()

    print(f"Loaded {len(cache)} cached entries")

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    file_lock = asyncio.Lock()

    async with AsyncSession(
        impersonate="chrome120"
    ) as ebay_session:

        async with aiohttp.ClientSession() as google_session:

            # warmup request
            await ebay_session.get("https://www.ebay.com")

            await asyncio.sleep(2)

            for isbn in isbn_list:

                await scrape_isbn(
                    isbn,
                    ebay_session,
                    google_session,
                    cache,
                    semaphore,
                    file_lock
                )


# -----------------------------
# START
# -----------------------------
if __name__ == "__main__":
    asyncio.run(main())