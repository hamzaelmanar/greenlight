"""
fetch_offer.py
Usage: python ingestion/fetch_offer.py <url>
Fetches a job offer URL and saves the cleaned text to offers/<slug>.txt
"""

import sys
import re
import hashlib
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OFFERS_DIR = Path(__file__).parent.parent / "offers"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove script / style noise
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    # Collapse whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def slug(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:10]


def save(url: str, text: str) -> Path:
    OFFERS_DIR.mkdir(exist_ok=True)
    path = OFFERS_DIR / f"{slug(url)}.txt"
    path.write_text(text, encoding="utf-8")
    return path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingestion/fetch_offer.py <url>")
        sys.exit(1)

    url = sys.argv[1]
    print(f"Fetching: {url}")
    text = fetch(url)
    path = save(url, text)
    print(f"Saved {len(text)} chars → {path}")
