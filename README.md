# Book Barcode Alpha: Async ISBN & Price Intelligence Pipeline

An asynchronous, modular Web Scraping MVP designed to crawl book metadata, expand discovery keywords, and extract programmatic pricing valuations across multiple web surfaces. Built as a practical architectural exploration into asynchronous networking, anti-bot mitigation, and transaction data filtering.

> **Project Status:** This repository serves as a functional MVP and a deep architectural learning exercise. Active feature development is paused unless transitioning to premium enterprise-tier upstream APIs.

---

## 🛠️ Core Architecture & Pipeline

The system consists of three distinct scraping files, transitioning from broad item discovery to precise, target-surface valuation indexing.


[ open_lib_scraper.py ] ──(Keyword Expansion)──► [ Generation of isbns_output.txt ]
│
┌─────────────────┴─────────────────┐
▼                                   ▼
[ price_scraper.py ]                  [ scraper.py ]
• Async Browser-Engine             • Mimicked TLS Fingerprints
• Real-time Spot Valuations       • IQR Statistical Modeling

### 1. Data Harvesting & Discovery (`open_lib_scraper.py`)
* **Mechanism:** Implements an asynchronous queue (`collections.deque`) populated by an automated **Query Expansion Engine**.
* **Pipeline:** Scrapes the OpenLibrary Search API, resolves abstract work objects down to explicit editions (`/editions.json`), extracts valid ISBN-10/13 codes, and runs an abstract tokenizer to strip stopwords and feed new keyword hooks back into the crawler queue.

### 2. High-Fidelity Valuation Layer (`price_scraper.py`)
* **Mechanism:** Dual-layer fallback client leveraging `aiohttp` for speed paired with automated orchestration loops using `Selenium` to handle interactive reCAPTCHA state flags.
* **Edition Control:** Isolates pricing points corresponding precisely to the specific print edition via `isbnsearch.org`, binding valuation tracking directly to individual physical manifestations of a book layout.

### 3. Market Distribution Parser (`scraper.py`)
* **Mechanism:** Uses `curl_cffi` to impersonate explicit browser TLS fingerprints (`chrome120`), bypassing structural edge-blocks on eBay.
* **Statistical Sanitization:** Pulls raw historical transactions, builds a `pandas.DataFrame`, and runs an **Interquartile Range (IQR)** outlier filtration algorithm to eliminate extreme noise (e.g., promotional shipping costs or unrelated product bundles), calculating reliable mean and median market clearing indices.
* **API Integration:** Leverages the Google Books API asynchronously (`main.py`) to resolve raw ISBN inputs into clean book titles before launching target marketplace queries.

---

## 🧠 Technical Challenges & Engineering Revelations

### 🧱 Mitigation of Anti-Scraping Protocols (eBay Phase)
Early iterations faced immediate network containment and interactive verification walls from eBay's edge defenses. 
* **The In-House Hack:** Leveraged a local Surfshark VPN infrastructure running automated IP rotation cycles on a 5-minute interval anchor. 
* **The Math:** Restructuring execution timings around a strict ~12-second per-request stagger window yielded roughly 25 successful deep-page parses per cycle. The script extracts comprehensive target histories, applies statistical normalization, and serializes state pools directly to disk without triggering alerts.

### 🏎️ Throughput Scaling & Pivot Economics (IsbnSearch Phase)
Transitioning to direct platform scraping presented an alternative bottleneck: safe, linear execution ceilings allowed a reliable throughput of ~130 prices per hour utilizing zero-cost local computation vectors.
* **The Edition Factor:** Crucially, this pivot resolved a key limitation of the eBay layout: high-level title queries often merged wildly disparate book variations. `isbnsearch.org` isolates exact, distinct edition-based valuations.

---

## 🚀 Scalability Blueprint (Next-Gen Production Upgrades)

If transitioned to a commercial, enterprise production pipeline, the architecture is intentionally designed to scale via the following infrastructure injections:

1. **Residential Proxy Fabric API:** Swapping the static local client pool for a back-connect residential proxy rotating gateway. Injecting randomized proxy endpoints per request would lower target safety windows down to 1–2 second intervals.
   $$\text{Estimated Throughput} = \frac{3600\text{ seconds}}{1.5\text{s average latency}} \approx 2,400\text{ items / hour / node}$$
2. **Distributed Queue Topology:** Moving the local memory `deque` queue abstraction layer to a dedicated Redis or RabbitMQ managed instance to decouple the OpenLibrary harvest layer entirely from the downstream pricing execution workers.
3. **Upstream Commercial APIs:** Swapping custom BeautifulSoup DOM manipulation structures for direct premium data feeds (e.g., official Keepa or eBay Developer access portals) to shift structural maintenance overhead off the system core.

---

## 🔧 Installation & Execution

1. Clone the environment and configure dependencies:
   ```bash
   pip install -r requirements.txt

	1.	Establish your credential environment inside a root .env file:
GOOGLE_BOOKS_API_KEY="your_actual_api_key_here"

	2.	Execute the data pipeline segments directly from the root directory:
python open_lib_scraper.py       # Harvest targets and expand keywords
python price_scraper.py          # Evaluate pricing via IsbnSearch
python scraper.py                # Evaluate historical sales via eBay

⚖️ Disclaimer
This project is strictly for educational and research purposes. It was developed as an MVP to explore asynchronous networking architectures, anti-bot mitigation patterns, and statistical data sanitization.
The author assumes no responsibility for how third parties utilize this software. Users are entirely responsible for complying with the Terms of Service (ToS), robots.txt directives, and local legal regulations of any target websites they interact with. The code is provided "as-is" without warranty of any kind.# -book-valuation-scraper
