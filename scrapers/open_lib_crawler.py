#!/usr/bin/env python3
"""
ISBN Scraper with reCAPTCHA Handling - Simplified Version
Uses standard selenium instead of undetected_chromedriver
"""

import asyncio
import aiohttp
import os
import json
import re
import random
import time
from bs4 import BeautifulSoup
from aiohttp.client_exceptions import ClientError
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -----------------------------
# CONFIGURATION
# -----------------------------
INPUT_FILE = "isbns_output.txt"
CACHE_FILE = "isbn_price_cache.json"
COOKIE_FILE = "session_cookies.json"
CAPTCHA_COOKIE_FILE = "captcha_solved_cookies.json"

# Timing configuration
DELAY_MIN = 17  # Increased delays
DELAY_MAX = 25
BLOCK_COOLDOWN = 60
MANUAL_CAPTCHA_TIMEOUT = 120
MAX_RETRIES = 3

BASE_URL = "https://isbnsearch.org/isbn/"

# -----------------------------
# CACHE FUNCTIONS
# -----------------------------
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("[WARN] Cache corrupted. Starting fresh.")
            return {}
    return {}

def save_cache(cache):
    temp_file = CACHE_FILE + ".tmp"
    with open(temp_file, "w") as f:
        json.dump(cache, f, indent=2)
    os.replace(temp_file, CACHE_FILE)

def load_captcha_cookies():
    if os.path.exists(CAPTCHA_COOKIE_FILE):
        try:
            with open(CAPTCHA_COOKIE_FILE, "r") as f:
                return json.load(f)
        except:
            return None
    return None

def save_captcha_cookies(cookies):
    with open(CAPTCHA_COOKIE_FILE, "w") as f:
        json.dump(cookies, f, indent=2)

# -----------------------------
# PARSING FUNCTIONS
# -----------------------------
def extract_price(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True).lower()
    
    patterns = [
        r'\$\s*([0-9]+\.[0-9]{2})',
        r'price:\s*\$\s*([0-9]+\.[0-9]{2})',
        r'usd\s*\$\s*([0-9]+\.[0-9]{2})',
    ]
    
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None

def is_blocked(status, html):
    if status in (403, 429, 503):
        return True
    
    html_lower = html.lower()
    blocked_keywords = [
        "captcha", "reCAPTCHA", "verify", "access denied",
        "unusual traffic", "are you a human", "quota exceeded"
    ]
    
    return any(keyword in html_lower for keyword in blocked_keywords)

# -----------------------------
# SIMPLIFIED CAPTCHA HANDLING
# -----------------------------
def solve_captcha_manually(url):
    """
    Launch Chrome browser for manual CAPTCHA solving using standard selenium
    """
    print(f"\n{'='*70}")
    print(f"[CAPTCHA REQUIRED] Please solve manually in the browser window")
    print(f"URL: {url}")
    print(f"Time limit: {MANUAL_CAPTCHA_TIMEOUT} seconds")
    print(f"{'='*70}\n")
    
    driver = None
    try:
        # Configure Chrome options
        chrome_options = Options()
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--start-maximized')
        
        # Add user agent
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Create driver (try different methods)
        try:
            # Method 1: Default
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e1:
            print(f"[INFO] Default Chrome driver failed: {e1}")
            try:
                # Method 2: Specify Chrome path (common on macOS)
                chrome_options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
                driver = webdriver.Chrome(options=chrome_options)
            except Exception as e2:
                print(f"[INFO] Custom Chrome path failed: {e2}")
                # Method 3: Use Service object
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Navigate to URL
        driver.get(url)
        
        # Wait for manual solving
        start_time = time.time()
        solved = False
        
        print("Waiting for CAPTCHA solution", end="")
        
        while time.time() - start_time < MANUAL_CAPTCHA_TIMEOUT:
            # Check if CAPTCHA is resolved
            page_source = driver.page_source.lower()
            
            if not any(keyword in page_source for keyword in 
                      ["captcha", "reCAPTCHA", "verify", "please verify"]):
                solved = True
                print("\n✓ CAPTCHA appears to be solved!")
                break
            
            # Also check if URL changed (redirect after solve)
            current_url = driver.current_url
            if "/isbn/" in current_url or "search" in current_url:
                if not any(keyword in page_source for keyword in ["captcha", "reCAPTCHA"]):
                    solved = True
                    print("\n✓ Redirected - CAPTCHA solved!")
                    break
            
            print(".", end="", flush=True)
            time.sleep(2)
        
        print()  # New line
        
        if solved:
            # Wait a bit for page to stabilize
            time.sleep(3)
            
            # Get cookies
            cookies = driver.get_cookies()
            cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            print(f"[SUCCESS] Got {len(cookies)} cookies from solved session")
            
            # Also save the page source for debugging
            with open("captcha_solved_page.html", "w") as f:
                f.write(driver.page_source)
            
            return cookie_dict
        else:
            print(f"[TIMEOUT] Could not solve CAPTCHA within {MANUAL_CAPTCHA_TIMEOUT} seconds")
            return None
            
    except Exception as e:
        print(f"[ERROR] Browser error: {e}")
        return None
    finally:
        if driver:
            driver.quit()

# -----------------------------
# SCRAPING FUNCTION
# -----------------------------
async def fetch_isbn(isbn, session, cache, captcha_solved=False):
    url = BASE_URL + isbn
    
    attempts = cache.get(isbn, {}).get("attempts", 0) + 1
    cache[isbn] = {"attempts": attempts, "status": "PENDING"}
    
    try:
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        async with session.get(url, timeout=30) as resp:
            html = await resp.text()
            
            if is_blocked(resp.status, html):
                if not captcha_solved:
                    return "CAPTCHA"
                else:
                    return "BLOCKED"
            
            price = extract_price(html)
            
            if price is None:
                cache[isbn] = {
                    "price": None, 
                    "status": "NOT_FOUND", 
                    "attempts": attempts,
                    "timestamp": time.time()
                }
                print(f"[NOT FOUND] {isbn}")
            else:
                cache[isbn] = {
                    "price": price, 
                    "status": "OK", 
                    "attempts": attempts,
                    "timestamp": time.time()
                }
                print(f"[OK] {isbn} -> ${price:.2f}")
            
            return "SUCCESS"
            
    except asyncio.TimeoutError:
        print(f"[TIMEOUT] {isbn}")
        if attempts >= MAX_RETRIES:
            cache[isbn] = {"price": None, "status": "FAILED", "attempts": attempts}
        return "ERROR"
    except Exception as e:
        print(f"[ERROR] {isbn}: {e}")
        if attempts >= MAX_RETRIES:
            cache[isbn] = {"price": None, "status": "FAILED", "attempts": attempts}
        return "ERROR"

# -----------------------------
# SESSION WARM-UP
# -----------------------------
async def warm_up_session(session):
    print("[WARMUP] Building session...")
    await session.get(BASE_URL)
    await asyncio.sleep(random.uniform(3, 5))
    await session.get(f"{BASE_URL}search?q=9780439023528")
    await asyncio.sleep(random.uniform(2, 4))
    print("[WARMUP] Complete")

# -----------------------------
# MAIN FUNCTION
# -----------------------------
async def main():
    if not os.path.exists(INPUT_FILE):
        print(f"[ERROR] Missing {INPUT_FILE}")
        return
    
    with open(INPUT_FILE, "r") as f:
        isbns = [line.strip() for line in f if line.strip()]
    
    print(f"[INFO] Loaded {len(isbns)} ISBNs")
    
    cache = load_cache()
    captcha_cookies = load_captcha_cookies()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        if captcha_cookies:
            print("[INFO] Loading saved CAPTCHA cookies")
            for name, value in captcha_cookies.items():
                session.cookie_jar.update_cookies({name: value})
        else:
            print("[INFO] Starting fresh session")
            await warm_up_session(session)
        
        captcha_solved_for_session = bool(captcha_cookies)
        consecutive_blocks = 0
        
        for idx, isbn in enumerate(isbns, 1):
            status = cache.get(isbn, {}).get("status")
            if status in ("OK", "NOT_FOUND", "FAILED"):
                print(f"[SKIP] {idx}/{len(isbns)} {isbn} ({status})")
                continue
            
            print(f"\n[{idx}/{len(isbns)}] Processing {isbn}...")
            
            result = await fetch_isbn(isbn, session, cache, captcha_solved_for_session)
            
            if result == "CAPTCHA":
                print(f"\n{'!'*70}")
                print("CAPTCHA DETECTED! Opening browser for manual solve...")
                print(f"{'!'*70}")
                
                cookies = solve_captcha_manually(BASE_URL)
                
                if cookies:
                    session.cookie_jar.clear()
                    for name, value in cookies.items():
                        session.cookie_jar.update_cookies({name: value})
                    
                    save_captcha_cookies(cookies)
                    captcha_solved_for_session = True
                    consecutive_blocks = 0
                    
                    print("[INFO] Retrying with new session...")
                    result = await fetch_isbn(isbn, session, cache, True)
                    
                    if result == "SUCCESS":
                        save_cache(cache)
                        continue
                
                consecutive_blocks += 1
                
                if consecutive_blocks >= 3:
                    print(f"[COOLDOWN] Multiple blocks. Cooling down for {BLOCK_COOLDOWN}s...")
                    await asyncio.sleep(BLOCK_COOLDOWN)
                    consecutive_blocks = 0
            
            elif result == "SUCCESS":
                consecutive_blocks = 0
                save_cache(cache)
            
            elif result == "BLOCKED":
                await asyncio.sleep(BLOCK_COOLDOWN)
                consecutive_blocks += 1
            
            if idx < len(isbns) and result != "CAPTCHA":
                delay = random.uniform(DELAY_MIN, DELAY_MAX)
                print(f"[DELAY] Waiting {delay:.1f} seconds...")
                await asyncio.sleep(delay)
    
    save_cache(cache)
    
    # Summary
    print("\n" + "="*70)
    print("COMPLETE")
    print("="*70)
    ok_count = sum(1 for v in cache.values() if v.get("status") == "OK")
    print(f"✅ Prices found: {ok_count}/{len(isbns)}")
    print(f"📁 Results: {CACHE_FILE}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[STOPPED] Cache saved")