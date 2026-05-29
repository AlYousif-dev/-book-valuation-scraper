# Book Barcode Alpha — Async ISBN & Book Valuation Pipeline

An asynchronous Python-based MVP for collecting book metadata, expanding ISBN discovery, and estimating used-book market prices from multiple online sources.

This project was built as both:
- a practical resale valuation tool
- and a learning exercise in asynchronous networking, web scraping, caching, anti-bot limitations, and statistical filtering.

## Project Status

The project is currently feature-complete as an MVP.

Development is paused unless migrating to paid infrastructure or commercial APIs. The current implementation intentionally avoids paid proxy networks and enterprise scraping services.

---

# Architecture Overview

The system is split into multiple scraping and processing stages:

text open_lib_scraper.py         │         ▼ Generates isbns_output.txt         │  ┌──────┴──────┐  ▼             ▼ price_scraper.py   scraper.py 

### open_lib_scraper.py
Discovers books and expands ISBN coverage using the OpenLibrary API.

### price_scraper.py
Fetches edition-specific valuations from isbnsearch.org using asynchronous requests and fallback browser automation when needed.

### scraper.py
Parses historical eBay sales data and filters pricing outliers to estimate more reliable market values.

---

# Pipeline Breakdown

## 1. ISBN Discovery & Expansion (open_lib_scraper.py)

This stage:
- queries the OpenLibrary Search API
- resolves works into specific editions
- extracts ISBN-10 and ISBN-13 identifiers
- expands future searches using extracted keywords

### Features
- Asynchronous crawling
- Queue-based keyword expansion
- ISBN extraction and deduplication
- Lightweight tokenizer for recursive discovery

---

## 2. Edition-Specific Pricing (price_scraper.py)

This stage estimates prices using isbnsearch.org.

One of the main motivations for this scraper was improving valuation accuracy compared to broad marketplace title searches.

### Features
- Async requests using aiohttp
- Session retry handling
- Selenium fallback flow for CAPTCHA interruptions
- Edition-level pricing separation

### Why edition-level pricing matters

Marketplace searches often merge:
- hardcover editions
- paperbacks
- teacher editions
- bundles
- international prints

Using ISBN-specific lookups helps isolate pricing to the exact physical edition.

---

## 3. Historical Market Analysis (scraper.py)

This stage scrapes sold eBay listings and computes filtered pricing estimates.

### Features
- curl_cffi browser impersonation
- Historical sold-listing extraction
- Pandas-based statistical filtering
- Mean and median pricing calculations

### Outlier filtering

The scraper applies an Interquartile Range (IQR) filter to remove noisy listings such as:
- abnormal shipping prices
- unrelated bundles
- damaged-item extremes
- incomplete listings

This produces more stable pricing estimates from historical sales data.

---

# Technical Challenges

## Anti-Bot Mitigation

Initial eBay scraping attempts quickly encountered:
- rate limits
- request blocking
- CAPTCHA challenges

To reduce blocking frequency, the scraper:
- staggered request timing
- rotated VPN endpoints
- reduced request concurrency
- used browser impersonation techniques

Under free-tier constraints, stable execution averaged roughly:
- ~25 successful deep parses per VPN cycle
- ~100–130 ISBN valuations per hour

---

# Scaling Considerations

The current implementation intentionally avoids paid scraping infrastructure.

If scaled into a production system, likely upgrades would include:

## Rotating Residential Proxies

Replacing static VPN rotation with rotating residential IP pools would significantly increase throughput and reduce cooldown periods between requests.

Estimated scaling potential:
- ~1–2 second request intervals
- thousands of lookups per hour per worker node

---

## Distributed Task Queues

The current in-memory queue could be replaced with:
- Redis
- RabbitMQ
- Celery workers

This would separate:
- ISBN discovery
- scraping workers
- valuation aggregation

into independent distributed services.

---

## Commercial Data APIs

A production system would likely replace custom scraping with official APIs where possible, such as:
- eBay Developer APIs
- Keepa
- commercial book pricing feeds

This would reduce maintenance overhead caused by frontend layout changes and anti-bot systems.

---

# Tech Stack

## Core Libraries
- Python
- asyncio
- aiohttp
- Selenium
- BeautifulSoup
- pandas
- curl_cffi

## APIs
- OpenLibrary API
- Google Books API

---

# Installation

Install dependencies:

bash pip install -r requirements.txt 

Create a .env file in the project root:

env GOOGLE_BOOKS_API_KEY="your_api_key_here" 

---

# Usage

## 1. Discover ISBNs

bash python open_lib_scraper.py 

Generates:
text isbns_output.txt 

---

## 2. Fetch ISBN-specific pricing

bash python price_scraper.py 

---

## 3. Scrape historical eBay sales

bash python scraper.py 

---

# Lessons Learned

This project became less about book pricing and more about understanding real-world scraping constraints.

Major takeaways included:
- asynchronous networking patterns
- caching and retry design
- anti-bot limitations
- throughput tradeoffs
- statistical data cleanup
- session management
- infrastructure scaling considerations

One of the biggest engineering lessons from the project was recognizing the point where additional scaling would require paid infrastructure rather than better code alone.

---

# Disclaimer

This project was created for educational and research purposes only.

Users are responsible for complying with:
- website Terms of Service
- robots.txt policies
- applicable laws and regulations

The software is provided "as-is" without warranty of any kind.
