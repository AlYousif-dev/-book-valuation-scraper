import asyncio
import aiohttp
import json
import os
import random
import re
import time
from collections import deque
from urllib.parse import quote

# -----------------------------
# CONFIG
# -----------------------------
CACHE_FILE = "isbn_expanding_cache.json"
OUTPUT_FILE = "isbns_output.txt"

CONCURRENCY = 8
REQUEST_TIMEOUT = 20
AUTO_SAVE_THRESHOLD = 50

SEED_QUERIES = [
    "science", "history", "finance", "psychology",
    "business", "fiction", "technology", "philosophy",
    "self help", "economics", "programming", "math",
    "biology", "physics", "chemistry", "romance"
]

SEARCH_URL = "https://openlibrary.org/search.json"
BASE_URL = "https://openlibrary.org"

# -----------------------------
# CACHE
# -----------------------------
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
    else:
        cache = {}

    if "titles" not in cache:
        cache["titles"] = {}
    if "queries_done" not in cache:
        cache["queries_done"] = []
    if "new_since_save" not in cache:
        cache["new_since_save"] = 0

    return cache


def save_cache(cache):
    safe = {
        "titles": {
            t: {
                "isbns": list(v["isbns"]),
                "query": v["query"],
                "timestamp": v["timestamp"]
            }
            for t, v in cache["titles"].items()
        },
        "queries_done": cache["queries_done"],
        "new_since_save": cache["new_since_save"]
    }

    with open(CACHE_FILE, "w") as f:
        json.dump(safe, f, indent=2)


def save_output(cache):
    with open(OUTPUT_FILE, "w") as f:
        for t in cache["titles"].values():
            for isbn in t["isbns"]:
                f.write(isbn + "\n")


# -----------------------------
# SIMPLE KEYWORD EXTRACTOR
# -----------------------------
STOPWORDS = {
    "the", "a", "an", "and", "of", "for", "in", "on",
    "to", "with", "guide", "introduction", "edition"
}

def extract_keywords(title):
    words = re.findall(r"[a-zA-Z]{3,}", title.lower())
    return [
        w for w in words
        if w not in STOPWORDS
    ][:5]


# -----------------------------
# FETCH EDITIONS
# -----------------------------
async def fetch_editions(work_key, session):
    url = f"{BASE_URL}{work_key}/editions.json"

    try:
        async with session.get(url, timeout=REQUEST_TIMEOUT) as r:
            if r.status != 200:
                return []
            data = await r.json()
            return data.get("entries", [])
    except:
        return []


# -----------------------------
# QUERY PROCESS
# -----------------------------
async def process_query(query, session, sem, cache, query_queue, seen_queries):

    async with sem:

        if query in seen_queries:
            return

        seen_queries.add(query)

        url = f"{SEARCH_URL}?q={quote(query)}&limit=20"

        try:
            async with session.get(url, timeout=REQUEST_TIMEOUT) as r:

                if r.status != 200:
                    return

                data = await r.json()

                docs = data.get("docs", [])

                for book in docs:

                    title = book.get("title")
                    work_key = book.get("key")

                    if not title or not work_key:
                        continue

                    # -----------------------------
                    # STORE TITLE
                    # -----------------------------
                    if title not in cache["titles"]:
                        cache["titles"][title] = {
                            "isbns": set(),
                            "query": query,
                            "timestamp": time.strftime("%Y-%m-%d")
                        }

                    # -----------------------------
                    # FETCH EDITIONS
                    # -----------------------------
                    editions = await fetch_editions(work_key, session)

                    for e in editions:
                        isbns = set()
                        isbns.update(e.get("isbn_10", []))
                        isbns.update(e.get("isbn_13", []))

                        for isbn in isbns:
                            if isbn not in cache["titles"][title]["isbns"]:
                                cache["titles"][title]["isbns"].add(isbn)
                                cache["new_since_save"] += 1

                    # -----------------------------
                    # 🔥 QUERY EXPANSION ENGINE
                    # -----------------------------
                    keywords = extract_keywords(title)

                    for kw in keywords:
                        if kw not in seen_queries:
                            query_queue.append(kw)

                print(f"[{query}] processed")

        except Exception as e:
            print(f"[{query}] error: {e}")


# -----------------------------
# MAIN LOOP (SELF EXPANDING)
# -----------------------------
async def main():

    cache = load_cache()

    print(f"Loaded titles: {len(cache['titles'])}")

    sem = asyncio.Semaphore(CONCURRENCY)

    query_queue = deque(SEED_QUERIES)
    seen_queries = set(cache["queries_done"])

    headers = {"User-Agent": "Mozilla/5.0 (ISBN-Crawler/2.0)"}

    async with aiohttp.ClientSession(headers=headers) as session:

        while query_queue:

            query = query_queue.popleft()

            await process_query(
                query,
                session,
                sem,
                cache,
                query_queue,
                seen_queries
            )

            cache["queries_done"].append(query)

            # -----------------------------
            # AUTO SAVE
            # -----------------------------
            if cache["new_since_save"] >= AUTO_SAVE_THRESHOLD:
                print("\nAuto-saving...\n")
                save_cache(cache)
                save_output(cache)
                cache["new_since_save"] = 0

            await asyncio.sleep(random.uniform(0.5, 2.0))

    print("Crawler finished queue (will likely never fully finish in expansion mode)")


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    asyncio.run(main())