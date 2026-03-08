#!/usr/bin/env python3
"""
build_brief.py
Reads a daily-brief-YYYY-MM-DD.json and renders it into dashboard.html.

Usage:
  python build_brief.py daily-brief-2026-03-06.json
  python build_brief.py daily-brief-2026-03-06.json --output dashboard.html
  python build_brief.py daily-brief-2026-03-06.json --output dist/index.html
"""

import sys
import json
import argparse
from datetime import datetime
from pathlib import Path


# ─── Helpers ────────────────────────────────────────────────────────────────

def fmt_date(iso_str: str) -> str:
    """2026-03-06 → Thursday, March 6, 2026"""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%A, %B %-d, %Y")
    except Exception:
        return iso_str


def fmt_change(val: float | str) -> tuple[str, str]:
    """Returns (formatted_string, css_class)"""
    try:
        v = float(str(val).replace("%", "").replace("+", "").strip())
        cls = "up" if v >= 0 else "down"
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.2f}%", cls
    except Exception:
        return str(val), "neutral"


def img_tag(url: str | None, alt: str = "", cls: str = "") -> str:
    """Returns an <img> tag or a placeholder div if no image."""
    if url:
        return f'<img src="{url}" alt="{alt}" loading="lazy">'
    placeholder = (
        '<div class="img-placeholder">'
        '<span>Image sourced from article at publish</span>'
        '</div>'
    )
    return placeholder


def safe(d: dict, *keys, default=""):
    """Safe nested dict access."""
    v = d
    for k in keys:
        if not isinstance(v, dict):
            return default
        v = v.get(k, default)
    return v if v is not None else default


# ─── Section Renderers ───────────────────────────────────────────────────────

def render_ticker(markets: dict) -> str:
    items = safe(markets, "ticker", default=[])
    if not items:
        return ""
    html = ""
    for item in items:
        change_str, cls = fmt_change(safe(item, "change"))
        html += f"""
    <div class="ticker-item">
      <span class="symbol">{safe(item, 'symbol')}</span>
      <span class="price">{safe(item, 'price')}</span>
      <span class="change {cls}">{change_str}</span>
    </div>"""
    return html


def render_markets(markets: dict) -> str:
    cards = safe(markets, "cards", default=[])
    cards_html = ""
    for c in cards:
        val_str, cls = fmt_change(safe(c, "change"))
        cards_html += f"""
        <div class="market-card">
          <div class="name">{safe(c, 'name')}</div>
          <div class="value">{safe(c, 'value')}</div>
          <div class="delta {cls}">{val_str}</div>
        </div>"""

    stories_html = ""
    for s in safe(markets, "stories", default=[]):
        stories_html += f"""
        <div class="market-story">
          <div class="story-source">{safe(s, 'source_name')}</div>
          <div class="story-headline"><a href="{safe(s, 'source_url')}" target="_blank">{safe(s, 'headline')}</a></div>
          <div class="story-summary">{safe(s, 'summary')}</div>
        </div>"""

    return f"""
    <div class="markets-row">{cards_html}
    </div>
    <p class="market-note">{safe(markets, 'content')}</p>
    {f'<div class="market-stories">{stories_html}</div>' if stories_html else ""}
    """


def render_top_stories(world: dict) -> str:
    stories = safe(world, "stories", default=[])
    if not stories:
        return f'<p class="market-note">{safe(world, "content")}</p>'

    lead = stories[0]
    lead_img = img_tag(safe(lead, "image_url"), safe(lead, "headline"))
    lead_html = f"""
      <div class="story-lead">
        <div class="story-lead-img">{lead_img}</div>
        <h3>{safe(lead, 'headline')}</h3>
        <p>{safe(lead, 'summary')}</p>
        <a href="{safe(lead, 'source_url')}" target="_blank" class="read-more">Read more →</a>
      </div>"""

    sidebar_html = ""
    for s in stories[1:4]:
        sidebar_html += f"""
        <a href="{safe(s, 'source_url')}" target="_blank" class="story-small">
          <div class="source">{safe(s, 'source_name')}</div>
          <h4>{safe(s, 'headline')}</h4>
          <p>{safe(s, 'summary')}</p>
        </a>"""

    return f"""
    <div class="stories-grid">
      {lead_html}
      <div class="story-sidebar">{sidebar_html}
      </div>
    </div>"""


def render_sports(sports: dict) -> str:
    scores = safe(sports, "scores", default=[])
    scores_html = ""
    for g in scores:
        scores_html += f"""
        <div class="score-card">
          <div>
            <div class="teams"><strong>{safe(g, 'winner')}</strong> vs {safe(g, 'loser')}</div>
            <div class="status">Final</div>
          </div>
          <div class="result">{safe(g, 'score')}</div>
        </div>"""

    upcoming = safe(sports, "upcoming", default=[])
    upcoming_html = ""
    if upcoming:
        items = "".join(f'<div class="upcoming-item">{u}</div>' for u in upcoming)
        upcoming_html = f'<div class="upcoming"><div class="upcoming-label">Coming Up</div>{items}</div>'

    note = safe(sports, "content")
    note_html = f'<p class="market-note" style="margin-top:1rem">{note}</p>' if note else ""

    return f"""
    <div class="scores-row">{scores_html}
    </div>{upcoming_html}{note_html}"""


def render_entertainment(ent: dict) -> str:
    stories = safe(ent, "stories", default=[])
    cards_html = ""
    for s in stories[:3]:
        img = img_tag(safe(s, "image_url"), safe(s, "headline"))
        cards_html += f"""
        <a href="{safe(s, 'source_url')}" target="_blank" class="ent-card">
          <div class="ent-image">{img}</div>
          <div class="ent-type">{safe(s, 'category', default='Culture')}</div>
          <h4>{safe(s, 'headline')}</h4>
        </a>"""

    return f'<div class="ent-grid">{cards_html}</div>'


def render_marketing(mkt: dict) -> str:
    stories = safe(mkt, "stories", default=[])
    items_html = ""
    for s in stories:
        img_html = ""
        if safe(s, "image_url"):
            img_html = f'<div class="mkt-img">{img_tag(safe(s, "image_url"), safe(s, "headline"))}</div>'
        items_html += f"""
      <div class="mkt-item">
        {img_html}
        <div class="mkt-text">
          <div class="story-source">{safe(s, 'source_name')}</div>
          <div class="story-headline"><a href="{safe(s, 'source_url')}" target="_blank">{safe(s, 'headline')}</a></div>
          <div class="story-summary">{safe(s, 'summary')}</div>
        </div>
      </div>"""

    note = safe(mkt, "content")
    note_html = f'<p class="market-note">{note}</p>' if note else ""

    return f"""
    {note_html}
    <div class="mkt-stories">{items_html}
    </div>"""


def render_rabbit_hole(rh: dict) -> str:
    img_html = ""
    if safe(rh, "image_url"):
        img_html = f'<div class="rh-image">{img_tag(safe(rh, "image_url"), safe(rh, "title"))}</div>'
    return f"""
    <div class="rabbit-hole">
      <div class="rh-label">Today's Rabbit Hole</div>
      {img_html}
      <h3>{safe(rh, 'title')}</h3>
      <p>{safe(rh, 'content')}</p>
      <a href="{safe(rh, 'source_url')}" target="_blank" class="read-full">Read the full story →</a>
    </div>"""


# ─── Main Template ────────────────────────────────────────────────────────────

def build_html(brief: dict) -> str:
    date_str = safe(brief, "date")
    display_date = fmt_date(date_str)
    gen_time = safe(brief, "generated_at", default="")
    try:
        gen_dt = datetime.fromisoformat(gen_time)
        gen_display = gen_dt.strftime("%-I:%M %p MT")
    except Exception:
        gen_display = gen_time

    sections = safe(brief, "sections", default={})
    markets  = safe(sections, "markets",       default={})
    world    = safe(sections, "world",          default={})
    sports   = safe(sections, "sports",         default={})
    ent      = safe(sections, "entertainment",  default={})
    mkt      = safe(sections, "marketing",      default={})
    rh       = safe(sections, "rabbit_hole",    default={})

    ticker_html       = render_ticker(markets)
    markets_html      = render_markets(markets)
    top_stories_html  = render_top_stories(world)
    sports_html       = render_sports(sports)
    ent_html          = render_entertainment(ent)
    marketing_html    = render_marketing(mkt)
    rabbit_hole_html  = render_rabbit_hole(rh)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>The Daily Brief &mdash; {display_date}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Sora:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&family=Lora:ital,wght@0,400;0,600;1,400&display=swap');

    :root {{
      --cream: #F4F1EB;
      --warm-white: #FAF8F5;
      --tan: #E5DDD0;
      --sand: #D4C9B8;
      --charcoal: #2A2A2A;
      --soft-black: #1A1A1A;
      --forest: #3D5A47;
      --forest-light: #4A6B55;
      --forest-dark: #2E4536;
      --warm-gray: #8C8578;
      --faded-coral: #D4A08F;
      --market-green: #4A6B55;
      --market-red: #B8524D;
    }}

    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Sora', -apple-system, sans-serif; background: var(--cream); color: var(--charcoal); -webkit-font-smoothing: antialiased; }}

    .dash-nav {{ padding: 1.5rem 3rem; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--tan); max-width: 1000px; margin: 0 auto; }}
    .dash-nav .back {{ font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--warm-gray); text-decoration: none; }}
    .dash-nav .date {{ font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--warm-gray); }}

    .brief-header {{ max-width: 1000px; margin: 0 auto; padding: 4rem 3rem 3rem; border-bottom: 2px solid var(--soft-black); }}
    .brief-header .masthead {{ font-family: 'Cormorant Garamond', serif; font-size: 3.5rem; color: var(--soft-black); letter-spacing: -0.03em; margin-bottom: 0.5rem; }}
    .brief-header .edition {{ font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.15em; color: var(--warm-gray); }}
    .brief-header .greeting {{ font-family: 'Lora', serif; font-style: italic; font-size: 1.1rem; color: var(--warm-gray); margin-top: 1.5rem; }}

    .ticker {{ max-width: 1000px; margin: 0 auto; padding: 1.25rem 3rem; display: flex; gap: 2.5rem; border-bottom: 1px solid var(--tan); overflow-x: auto; }}
    .ticker-item {{ display: flex; flex-direction: column; min-width: fit-content; }}
    .ticker-item .symbol {{ font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; font-weight: 700; letter-spacing: 0.05em; color: var(--charcoal); }}
    .ticker-item .price {{ font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: var(--charcoal); }}
    .ticker-item .change {{ font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; }}
    .ticker-item .change.up {{ color: var(--market-green); }}
    .ticker-item .change.down {{ color: var(--market-red); }}

    .brief-content {{ max-width: 1000px; margin: 0 auto; padding: 0 3rem; }}
    .brief-section {{ padding: 2.5rem 0; border-bottom: 1px solid var(--tan); }}
    .brief-section:last-child {{ border-bottom: none; }}

    .section-label {{ font-family: 'JetBrains Mono', monospace; font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.2em; color: var(--forest); margin-bottom: 1.5rem; display: flex; align-items: center; gap: 0.75rem; }}
    .section-label::after {{ content: ''; flex: 1; height: 1px; background: var(--tan); }}

    .stories-grid {{ display: grid; grid-template-columns: 1.2fr 1fr; gap: 2.5rem; }}
    .story-lead {{ border-right: 1px solid var(--tan); padding-right: 2.5rem; }}
    .story-lead-img {{ width: 100%; aspect-ratio: 16/9; overflow: hidden; border-radius: 3px; margin-bottom: 1rem; }}
    .story-lead-img img {{ width: 100%; height: 100%; object-fit: cover; filter: saturate(0.85) contrast(1.05); }}
    .story-lead h3 {{ font-family: 'Cormorant Garamond', serif; font-size: 1.75rem; line-height: 1.2; color: var(--soft-black); margin-bottom: 1rem; letter-spacing: -0.02em; }}
    .story-lead p {{ font-size: 0.95rem; font-weight: 300; line-height: 1.7; color: var(--charcoal); margin-bottom: 1rem; }}
    .story-lead .read-more {{ font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--forest); text-decoration: none; }}
    .story-sidebar {{ display: flex; flex-direction: column; gap: 1.5rem; }}
    .story-small {{ padding-bottom: 1.5rem; border-bottom: 1px solid var(--tan); text-decoration: none; color: inherit; display: block; }}
    .story-small:last-child {{ border-bottom: none; }}
    .story-small .source {{ font-family: 'JetBrains Mono', monospace; font-size: 0.55rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--warm-gray); margin-bottom: 0.4rem; }}
    .story-small h4 {{ font-family: 'Cormorant Garamond', serif; font-size: 1.1rem; line-height: 1.3; color: var(--soft-black); margin-bottom: 0.4rem; letter-spacing: -0.01em; }}
    .story-small p {{ font-size: 0.8rem; font-weight: 300; color: var(--warm-gray); line-height: 1.5; }}

    .markets-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }}
    .market-card {{ background: var(--warm-white); border: 1px solid var(--tan); border-radius: 4px; padding: 1.25rem; }}
    .market-card .name {{ font-family: 'JetBrains Mono', monospace; font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--warm-gray); margin-bottom: 0.5rem; }}
    .market-card .value {{ font-family: 'Cormorant Garamond', serif; font-size: 1.5rem; color: var(--soft-black); margin-bottom: 0.25rem; }}
    .market-card .delta {{ font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; }}
    .market-card .delta.up {{ color: var(--market-green); }}
    .market-card .delta.down {{ color: var(--market-red); }}
    .market-note {{ font-size: 0.85rem; font-weight: 300; color: var(--charcoal); line-height: 1.7; }}
    .market-stories {{ margin-top: 1.5rem; display: flex; flex-direction: column; gap: 1rem; }}
    .market-story {{ padding-bottom: 1rem; border-bottom: 1px solid var(--tan); }}
    .market-story:last-child {{ border-bottom: none; }}
    .story-source {{ font-family: 'JetBrains Mono', monospace; font-size: 0.55rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--warm-gray); margin-bottom: 0.25rem; }}
    .story-headline a {{ font-family: 'Cormorant Garamond', serif; font-size: 1rem; color: var(--soft-black); text-decoration: none; line-height: 1.3; }}
    .story-headline a:hover {{ color: var(--forest); }}
    .story-summary {{ font-size: 0.8rem; font-weight: 300; color: var(--warm-gray); line-height: 1.5; margin-top: 0.25rem; }}

    .scores-row {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin-bottom: 1.5rem; }}
    .score-card {{ background: var(--warm-white); border: 1px solid var(--tan); border-radius: 4px; padding: 1.25rem; display: flex; justify-content: space-between; align-items: center; }}
    .score-card .teams {{ font-size: 0.9rem; color: var(--charcoal); }}
    .score-card .teams strong {{ font-weight: 600; }}
    .score-card .result {{ font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 700; color: var(--soft-black); }}
    .score-card .status {{ font-family: 'JetBrains Mono', monospace; font-size: 0.55rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--warm-gray); }}
    .upcoming {{ margin-top: 1rem; }}
    .upcoming-label {{ font-family: 'JetBrains Mono', monospace; font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--warm-gray); margin-bottom: 0.75rem; }}
    .upcoming-item {{ font-size: 0.85rem; font-weight: 300; color: var(--charcoal); padding: 0.5rem 0; border-bottom: 1px solid rgba(212,197,173,0.5); }}

    .ent-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; }}
    .ent-card {{ text-decoration: none; color: inherit; }}
    .ent-card .ent-image {{ width: 100%; aspect-ratio: 16/10; background: var(--tan); border-radius: 3px; margin-bottom: 0.75rem; overflow: hidden; position: relative; }}
    .ent-card .ent-image img {{ width: 100%; height: 100%; object-fit: cover; filter: saturate(0.85) contrast(1.05); }}
    .ent-card .ent-type {{ font-family: 'JetBrains Mono', monospace; font-size: 0.55rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--forest); margin-bottom: 0.35rem; }}
    .ent-card h4 {{ font-family: 'Cormorant Garamond', serif; font-size: 1rem; color: var(--soft-black); line-height: 1.3; }}

    .mkt-stories {{ display: flex; flex-direction: column; gap: 1.25rem; margin-top: 1rem; }}
    .mkt-item {{ display: flex; gap: 1.25rem; align-items: flex-start; }}
    .mkt-img {{ width: 120px; flex-shrink: 0; aspect-ratio: 16/9; overflow: hidden; border-radius: 3px; }}
    .mkt-img img {{ width: 100%; height: 100%; object-fit: cover; filter: saturate(0.85) contrast(1.05); }}
    .mkt-text {{ flex: 1; }}

    .rabbit-hole {{ background: var(--forest-dark); border-radius: 6px; padding: 2.5rem; color: var(--cream); }}
    .rh-label {{ font-family: 'JetBrains Mono', monospace; font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.2em; color: var(--forest-light); margin-bottom: 1.25rem; }}
    .rh-image {{ width: 100%; aspect-ratio: 16/7; overflow: hidden; border-radius: 4px; margin-bottom: 1.5rem; }}
    .rh-image img {{ width: 100%; height: 100%; object-fit: cover; filter: saturate(0.7) contrast(1.1); }}
    .rabbit-hole h3 {{ font-family: 'Cormorant Garamond', serif; font-size: 1.75rem; line-height: 1.25; margin-bottom: 1rem; letter-spacing: -0.02em; }}
    .rabbit-hole p {{ font-size: 0.9rem; font-weight: 300; line-height: 1.8; color: var(--sand); margin-bottom: 1.5rem; }}
    .rabbit-hole .read-full {{ font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--forest-light); text-decoration: none; border-bottom: 1px solid var(--faded-coral); padding-bottom: 0.2rem; }}

    .img-placeholder {{ width: 100%; height: 100%; background: var(--tan); display: flex; align-items: center; justify-content: center; }}
    .img-placeholder span {{ font-family: 'JetBrains Mono', monospace; font-size: 0.5rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--warm-gray); text-align: center; padding: 1rem; }}

    .brief-footer {{ max-width: 1000px; margin: 0 auto; padding: 2rem 3rem; text-align: center; border-top: 2px solid var(--soft-black); }}
    .brief-footer p {{ font-family: 'JetBrains Mono', monospace; font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.15em; color: var(--warm-gray); }}
    .brief-footer a {{ color: var(--warm-gray); }}

    @media (max-width: 768px) {{
      .dash-nav, .brief-header, .brief-content, .brief-footer {{ padding-left: 1.5rem; padding-right: 1.5rem; }}
      .brief-header .masthead {{ font-size: 2.5rem; }}
      .stories-grid {{ grid-template-columns: 1fr; }}
      .story-lead {{ border-right: none; padding-right: 0; border-bottom: 1px solid var(--tan); padding-bottom: 2rem; }}
      .markets-row {{ grid-template-columns: repeat(2, 1fr); }}
      .scores-row {{ grid-template-columns: 1fr; }}
      .ent-grid {{ grid-template-columns: 1fr; }}
      .ticker {{ padding: 1rem 1.5rem; }}
    }}
  </style>
</head>
<body>

  <div class="dash-nav">
    <a href="index.html" class="back">&larr; Back to site</a>
    <span class="date">{display_date}</span>
  </div>

  <header class="brief-header">
    <div class="masthead">The Daily Brief</div>
    <div class="edition">Morning Edition &middot; {display_date}</div>
    <p class="greeting">Good morning, Zubin. Here's what matters today.</p>
  </header>

  <div class="ticker">{ticker_html}
  </div>

  <div class="brief-content">

    <div class="brief-section">
      <div class="section-label">Top Stories</div>
      {top_stories_html}
    </div>

    <div class="brief-section">
      <div class="section-label">Markets</div>
      {markets_html}
    </div>

    <div class="brief-section">
      <div class="section-label">Sports</div>
      {sports_html}
    </div>

    <div class="brief-section">
      <div class="section-label">Culture &amp; Entertainment</div>
      {ent_html}
    </div>

    <div class="brief-section">
      <div class="section-label">Marketing &amp; Career</div>
      {marketing_html}
    </div>

    <div class="brief-section">
      {rabbit_hole_html}
    </div>

  </div>

  <div class="brief-footer">
    <p>Generated at {gen_display} &middot; Powered by your OpenClaw agent &middot; <a href="index.html">Back to site</a></p>
  </div>

</body>
</html>"""


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build dashboard HTML from daily brief JSON")
    parser.add_argument("json_file", help="Path to daily-brief-YYYY-MM-DD.json")
    parser.add_argument("--output", "-o", default="dashboard.html", help="Output HTML file (default: dashboard.html)")
    args = parser.parse_args()

    json_path = Path(args.json_file)
    if not json_path.exists():
        print(f"[ERROR] File not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    with open(json_path) as f:
        brief = json.load(f)

    html = build_html(brief)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"[OK] Built → {out_path}")


if __name__ == "__main__":
    main()
