# Project Context for OpenClaw

## Who This Is For
Zubin Shourie — senior marketing major at CU Boulder, graduating Spring 2026. Based in Boulder. Interested in marketing, brand strategy, sports/music/entertainment industries. Career targets: NYC, LA, Denver. Agency-side work preferred.

## What This Project Is
A personal website with two sides:
1. **Public portfolio** (index.html) — showcases marketing projects, photography, personal brand
2. **Private daily brief** (dashboard.html + article.html) — AI-generated morning intelligence briefing covering markets, news, sports, entertainment, marketing industry, and a daily "rabbit hole" deep-dive

OpenClaw generates the brief content daily and publishes it to the site. Telegram sends a notification link when it's ready.

## Design System
- **Inspiration**: Aimé Leon Dore website, vacation.inc, henry.codes, poolsuite.net
- **Vibe**: Warm, nostalgic, editorial. Like a well-designed independent magazine. NOT generic startup/tech aesthetic.
- **Fonts**: Cormorant Garamond (serif headlines), Sora (sans-serif body), JetBrains Mono (monospace labels/tags)
- **Colors**: Forest green (#3D5A47) accent, cream (#F4F1EB) background, tan (#E8E0D4), warm white (#FAF8F5), warm gray (#8A8478), forest light (#5A7A63), forest dark (#2B3E30)
- **Images**: Nostalgic film-style filter (saturate 0.85, contrast 1.05). No generic stock photos — editorial images should come from actual source articles via og:image scraping.
- **Tone**: Smart, direct, occasionally witty. Like a sharp friend who reads everything and tells you what matters. No fluff, no filler, no buzzwords.

## File Structure
- `index.html` — Portfolio homepage (hero, about, work grid, featured strip, photography grid, contact)
- `dashboard.html` — Morning brief page (masthead, ticker, top stories, markets, sports, entertainment, rabbit hole)
- `article.html` — Full-length article template (reading progress bar, drop cap, pull quotes, takeaway box, related articles)
- `CONTEXT.md` — This file

## Current State
All three pages are styled HTML prototypes with placeholder content. The design system is consistent across pages. Dashboard and article pages have placeholder image cards labeled "Image sourced from article at publish" — these get replaced by real og:image URLs when the content pipeline is live.

Homepage has Unsplash mood images for portfolio cards and photography grid — these are temporary until Zubin adds his own photos (he shoots Fujifilm X-T5).

## What Needs to Happen Next
See `openclaw-overnight-plan.md` (should be alongside this folder on the Desktop) for tonight's tasks. The two immediate jobs are:
1. Build `og_image_scraper.py` — extracts real editorial images from article URLs via og:image meta tags
2. Generate the first morning brief as structured JSON with real image URLs from source articles

## Tech Stack (Planned)
- Static site generator: Astro
- Styling: Tailwind CSS
- Hosting: Vercel (auto-rebuild on new content)
- Content pipeline: OpenClaw generates JSON daily → build script templates it into HTML → Vercel deploys
- Notifications: Telegram link when new brief is published

## OpenClaw Config
- Primary model: anthropic/claude-sonnet-4-6
- Fallback: groq/llama-3.1-8b-instant
- Web search: Gemini provider (500 free searches/day, falls back to DuckDuckGo if rate limited)
- Tools profile: full
- Gateway: localhost:18789, token auth
