#!/usr/bin/env python3
"""
og_image_scraper.py
Extracts og:image, twitter:image, or first large img from article URLs.
Usage:
  python og_image_scraper.py https://url1.com https://url2.com
  python og_image_scraper.py --json urls.json
  python og_image_scraper.py --test
"""

import sys
import json
import argparse
import requests
from bs4 import BeautifulSoup

TIMEOUT = 5
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

TEST_URLS = [
    "https://www.bbc.com/news",
    "https://techcrunch.com",
    "https://www.theverge.com",
    "https://www.reuters.com",
    "https://www.nytimes.com",
]


def scrape_url(url: str) -> dict:
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # og:title or page title
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"] if og_title and og_title.get("content") else None
        if not title:
            tag = soup.find("title")
            title = tag.get_text(strip=True) if tag else ""

        # og:image
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return {"url": url, "image": og_image["content"], "title": title}

        # twitter:image fallback
        tw_image = soup.find("meta", attrs={"name": "twitter:image"})
        if tw_image and tw_image.get("content"):
            return {"url": url, "image": tw_image["content"], "title": title}

        # first large <img> fallback
        for img in soup.find_all("img", src=True):
            src = img.get("src", "")
            cls = " ".join(img.get("class", []))
            width = img.get("width")
            if any(k in cls.lower() for k in ["hero", "featured", "thumbnail"]):
                return {"url": url, "image": src, "title": title}
            try:
                if width and int(width) > 400:
                    return {"url": url, "image": src, "title": title}
            except (ValueError, TypeError):
                pass

        return {"url": url, "image": None, "title": title}

    except Exception as e:
        print(f"[ERROR] {url}: {e}", file=sys.stderr)
        return {"url": url, "image": None, "title": None, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Extract og:image from URLs")
    parser.add_argument("urls", nargs="*", help="URLs to scrape")
    parser.add_argument("--json", dest="json_file", help="JSON file with list of URLs")
    parser.add_argument("--test", action="store_true", help="Run against 5 test URLs")
    args = parser.parse_args()

    if args.test:
        urls = TEST_URLS
    elif args.json_file:
        with open(args.json_file) as f:
            urls = json.load(f)
    else:
        urls = args.urls

    if not urls:
        parser.print_help()
        sys.exit(1)

    results = [scrape_url(u) for u in urls]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
