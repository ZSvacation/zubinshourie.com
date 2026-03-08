# OpenClaw Overnight Task Plan

## What's Already Running
The Innovation Project ideation sprint (beach belonging security) is already active in your Telegram chat. Let it finish — don't interrupt it with new tasks in the same session.

## What to Send OpenClaw Next

Once the innovation sprint delivers its output, start a **new session** (`/session new`) and paste the prompt below.

---

## PROMPT: Morning Brief + Image Pipeline Setup

**Copy everything below this line and paste as a single message after starting a new session.**

---

You have two jobs tonight. Complete them in order.

## JOB 1: Build the OG Image Scraper

I need a lightweight script that can extract the Open Graph image (`og:image`) from any article URL. This will be used to pull real editorial images into a daily brief website.

Write a Python script called `og_image_scraper.py` that does the following:

1. Takes a list of URLs as input (either as CLI arguments or from a JSON file)
2. For each URL, fetches the page and extracts the `og:image` meta tag content
3. Falls back to `twitter:image` if `og:image` isn't found
4. Falls back to the first large `<img>` on the page (src with width > 400 or class containing "hero"/"featured"/"thumbnail") if neither meta tag exists
5. Outputs a JSON mapping of `{ "url": "original_article_url", "image": "image_url", "title": "og:title or page title" }`
6. Handles errors gracefully — if a URL fails, log it and move on
7. Includes a 5-second timeout per request
8. Uses only `requests` and `beautifulsoup4` (no Selenium or heavy deps)

Requirements:
- Python 3.10+
- Include a requirements.txt with the two dependencies
- Include a `--test` flag that runs against 5 hardcoded news URLs to verify it works
- Print results as formatted JSON to stdout

Test it after writing it. Run it with the `--test` flag and make sure it actually returns real image URLs from real articles. Fix any bugs.

Save the script and send it to me here on Telegram.

## JOB 2: Generate the First Morning Brief

Now use the scraper you just built as part of generating an actual morning brief.

You are building the first edition of a daily morning brief for Zubin Shourie. This is a personal intelligence briefing — not a generic news roundup. It should feel like a sharp, well-edited newsletter written by someone who knows him.

Work through all sections below. Use web search for every section. Write in a direct, concise style. No fluff, no filler, no generic commentary.

**CRITICAL: For every story you include, save the source article URL.** After writing all sections, run the og_image_scraper against every source URL to collect the real editorial images. Include these image URLs in the final output.

### SECTION 1: MARKETS & MONEY
Search for today's market activity and write:
- S&P 500, Nasdaq, Dow — closing prices and daily change
- Top 3 market-moving stories (why did markets move today?)
- 1 interesting stock or ETF worth watching, with a specific reason why
- Bitcoin and Ethereum price + 24h change
- Any notable earnings reports this week

Keep it factual. No vague "markets were mixed" language. Specific numbers and specific reasons.

### SECTION 2: WORLD & POLITICS
Search for the top 3-5 stories in US and global news today. For each:
- What happened (2-3 sentences max)
- Why it matters (1 sentence)

Skip anything that's just noise. Focus on stories that will still matter in a week.

### SECTION 3: SPORTS
Search for scores and headlines from:
- NBA (focus on Lakers, any nationally relevant games)
- NFL (if in season — trades, draft news, free agency)
- Premier League / Champions League (if games played)
- Any other major sporting event happening today

Include actual scores, not just "Team X won." Stats matter.

### SECTION 4: ENTERTAINMENT & CULTURE
Search for 2-3 stories from:
- Music (new releases, tours, industry news)
- Film/TV (trailers, releases, streaming news)
- Cultural moments (viral moments, notable interviews, brand collaborations)

Focus on things a 22-year-old marketing major in Boulder would actually care about.

### SECTION 5: MARKETING & CAREER
Search for 1-2 items from:
- Notable brand campaigns or marketing moves
- Advertising industry news
- Any interesting job market data for marketing roles
- Agency news (mergers, notable hires, campaign wins)

### SECTION 6: THE RABBIT HOLE
Find one genuinely interesting deep-dive topic. Something surprising, counterintuitive, or obscure that connects to business, innovation, or culture. Write a 2-3 paragraph teaser that makes someone want to read more. Examples:
- A failed product that accidentally created a new industry
- An obscure psychological principle that explains consumer behavior
- A business model that shouldn't work but does
- A historical parallel to something happening today

Search broadly. The best rabbit holes come from unexpected places.

### IMAGE COLLECTION STEP
After writing all sections, compile every source article URL you referenced. Run the og_image_scraper.py script against all of them. Collect the results.

### FINAL OUTPUT
Compile everything into a single JSON document with this structure:

```json
{
  "date": "YYYY-MM-DD",
  "generated_at": "ISO timestamp",
  "sections": {
    "markets": {
      "content": "The written brief text for this section",
      "stories": [
        {
          "headline": "Story headline",
          "source_url": "https://...",
          "source_name": "Reuters",
          "image_url": "https://... (from og_image_scraper)",
          "summary": "Brief summary"
        }
      ]
    },
    "world": { ... same structure ... },
    "sports": { ... },
    "entertainment": { ... },
    "marketing": { ... },
    "rabbit_hole": {
      "title": "The teaser headline",
      "content": "The 2-3 paragraph teaser",
      "source_url": "https://...",
      "image_url": "https://..."
    }
  }
}
```

Send me two things on Telegram:
1. The og_image_scraper.py file
2. The full JSON brief as a file called `daily-brief-YYYY-MM-DD.json`

Also send a short readable summary of today's brief as a regular Telegram message (under 1500 words) so I can read it quickly when I wake up. Tone: smart, direct, occasionally witty — like a friend who reads everything and tells you what matters.

If you hit any API rate limits on web search, switch to DuckDuckGo and keep going. Don't stop.

If you have questions, text me — but try to figure it out yourself first.

---

## Notes for Zubin

**What this sets up:** OpenClaw builds the image scraper tool first, then uses it while generating the brief. The JSON output format means when we build the actual site, we just read the JSON and template it into the HTML with real images already embedded. No manual work.

**Publishing pipeline (next step with Claude):**
1. OpenClaw generates `daily-brief-YYYY-MM-DD.json` every morning
2. A build script reads the JSON and renders it into the dashboard.html template
3. Images come from the `image_url` field in each story — real editorial photos from the actual source articles
4. Deploy to Vercel, which auto-rebuilds when new JSON is pushed
5. OpenClaw sends you a Telegram link: "Your brief is ready → yourdomain.com/brief"

**What I (Claude) updated tonight:**
- All three site pages now use the new design system (Cormorant Garamond, Sora, JetBrains Mono, forest green, cream)
- Dashboard and article pages now have clean placeholder cards labeled "Image sourced from article at publish" — these will be replaced by real `og:image` URLs once the pipeline is live
- Homepage still has Unsplash images for portfolio mood (those are fine as-is until you add your own photos)

**Customization after first run:**
- Which stocks/ETFs to track daily
- Which sports teams to prioritize
- More or less of any section
- Tone and length adjustments
