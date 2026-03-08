# Content Pipeline

## How It Works

```
OpenClaw generates JSON  →  og_image_scraper fetches images  →  build_brief.py renders HTML  →  Vercel deploys
```

## Daily Brief Pipeline

### Step 1 — Generate the brief JSON
OpenClaw runs every morning at 7AM MT and produces:
```
daily-brief-YYYY-MM-DD.json
```
JSON structure:
```json
{
  "date": "2026-03-07",
  "generated_at": "2026-03-07T07:00:00-07:00",
  "sections": {
    "markets": {
      "content": "Written summary...",
      "ticker": [{ "symbol": "S&P", "price": "5,842", "change": "+0.43%" }],
      "cards": [{ "name": "S&P 500", "value": "5,842", "change": "+0.43%" }],
      "stories": [{ "headline": "...", "source_url": "...", "source_name": "...", "image_url": "...", "summary": "..." }]
    },
    "world": { "content": "...", "stories": [...] },
    "sports": {
      "content": "...",
      "scores": [{ "winner": "Celtics", "loser": "Mavs", "score": "112-98" }],
      "upcoming": ["Champions League QF: Arsenal vs Bayern — 3PM ET"]
    },
    "entertainment": { "content": "...", "stories": [...] },
    "marketing": { "content": "...", "stories": [...] },
    "rabbit_hole": {
      "title": "The headline",
      "content": "2-3 paragraph teaser...",
      "source_url": "https://...",
      "image_url": "https://..."
    }
  }
}
```

### Step 2 — Scrape images (if needed)
The og_image_scraper is run *during* brief generation — image_url fields in the JSON already contain real editorial images.

To run manually:
```bash
python og_image_scraper.py https://article-url.com https://another.com
# or
python og_image_scraper.py --json urls.json
# or test with 5 hardcoded news sites
python og_image_scraper.py --test
```

### Step 3 — Build the HTML dashboard
```bash
# From the site-prototype directory:
python build_brief.py daily-brief-2026-03-07.json
# → writes dashboard.html

# Custom output path (for Vercel dist):
python build_brief.py daily-brief-2026-03-07.json --output dist/dashboard.html
```

### Step 4 — Deploy to Vercel
Push to Git → Vercel auto-rebuilds.

Full automation (to be set up):
```bash
# This will live in a cron script:
python build_brief.py daily-brief-$(date +%F).json --output dashboard.html
git add dashboard.html daily-brief-$(date +%F).json
git commit -m "Brief: $(date +%F)"
git push
# Vercel builds and deploys automatically
```

## File Structure
```
site-prototype/
├── index.html          ← Portfolio homepage (static)
├── dashboard.html      ← Daily brief (rebuilt daily by pipeline)
├── article.html        ← Article template
├── build_brief.py      ← JSON → HTML renderer
├── og_image_scraper.py ← Fetches og:image from article URLs
├── PIPELINE.md         ← This file
└── img/
    └── photos/         ← Your photography (Fujifilm X-T5)
```
