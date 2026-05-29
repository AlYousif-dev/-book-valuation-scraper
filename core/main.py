import os
import aiohttp
import json
from dotenv import load_dotenv

load_dotenv()

async def get_book_title(isbn: str, session: aiohttp.ClientSession) -> str:
    """Queries the Google Books API asynchronously."""
    api_key = os.getenv("GOOGLE_BOOKS_API_KEY")
    if not api_key:
        return "NOT_FOUND"

    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}&key={api_key}"
    
    try:
        async with session.get(url) as response:
            data = await response.json()
            if "items" in data and len(data["items"]) > 0:
                return data["items"][0]["volumeInfo"].get("title", "NOT_FOUND")
    except Exception:
        pass
    return "NOT_FOUND"