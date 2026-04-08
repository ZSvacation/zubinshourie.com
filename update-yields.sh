#!/bin/bash
# Fetch Treasury yields from Yahoo Finance and write yields.json to site
# Run nightly via cron: 0 18 * * 1-5 /Users/ZYN/Desktop/site-prototype/update-yields.sh

SITE="/Users/ZYN/Desktop/site-prototype"
OUT="$SITE/yields.json"

fetch_yield() {
  local sym="$1"
  curl -s --max-time 10 \
    "https://query1.finance.yahoo.com/v8/finance/chart/${sym}?interval=1d&range=5d" \
    -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36" \
    -H "Accept: application/json" \
    -H "Referer: https://finance.yahoo.com/"
}

TNX=$(fetch_yield "%5ETNX")
TWO=$(fetch_yield "%5ETWO")  # Try this first for 2Y

python3 - "$TNX" "$TWO" "$OUT" << 'EOF'
import sys, json, datetime

def parse(raw):
    try:
        d = json.loads(raw)
        m = d['chart']['result'][0]['meta']
        price = m.get('regularMarketPrice')
        prev  = m.get('chartPreviousClose') or m.get('previousClose')
        if not price: return None
        change = ((price - prev) / prev * 100) if prev else None
        return {'price': price, 'prev': prev, 'change': change}
    except:
        return None

t10 = parse(sys.argv[1])
t2  = parse(sys.argv[2])

if not t10 and not t2:
    print("No yield data fetched", file=sys.stderr)
    sys.exit(1)

spread = None
if t10 and t2:
    s = t10['price'] - t2['price']
    ps = (t10['prev'] - t2['prev']) if t10['prev'] and t2['prev'] else None
    spread = {'price': s, 'prev': ps, 'change': (s - ps) if ps is not None else None, 'isSpread': True}

out = {
    'updated': datetime.datetime.utcnow().isoformat() + 'Z',
    'TNX': t10,
    'TWO': t2,
    'SPREAD': spread,
}

with open(sys.argv[3], 'w') as f:
    json.dump(out, f, indent=2)

print(f"yields.json updated: 10Y={t10['price'] if t10 else 'n/a'}, 2Y={t2['price'] if t2 else 'n/a'}")
EOF

# Auto-commit and push if git repo
cd "$SITE" && git add yields.json && git commit -m "yields: nightly update $(date +%Y-%m-%d)" && git push origin main 2>/dev/null
