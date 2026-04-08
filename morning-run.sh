#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  morning-run.sh — Daily automation for zubinshourie.com
#  Runs at 8:00 AM via LaunchAgent (com.zubinshourie.morning-run.plist)
#
#  Steps:
#   1. Update yields.json (Treasury rates from Yahoo Finance)
#   2. Push any pending commits from the Cowork daily brief task
# ─────────────────────────────────────────────────────────────

SITE_DIR="$HOME/Desktop/site-prototype"
LOG="$HOME/Desktop/morning-run.log"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

echo "" >> "$LOG"
echo "═══════════════════════════════════" >> "$LOG"
echo "$TIMESTAMP  morning-run starting" >> "$LOG"
echo "═══════════════════════════════════" >> "$LOG"

cd "$SITE_DIR" || {
  echo "$TIMESTAMP  ERROR: cannot cd to $SITE_DIR" >> "$LOG"
  exit 1
}

# ── Step 1: Update yields.json ────────────────────────────────
echo "$TIMESTAMP  [yields] Fetching Treasury rates..." >> "$LOG"

fetch_yield() {
  curl -s --max-time 12 \
    "https://query1.finance.yahoo.com/v8/finance/chart/${1}?interval=1d&range=5d" \
    -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
    -H "Accept: application/json" \
    -H "Referer: https://finance.yahoo.com/"
}

TNX=$(fetch_yield "%5ETNX")
TWO=$(fetch_yield "%5ETWO")

python3 - "$TNX" "$TWO" "$SITE_DIR/yields.json" << 'PYEOF'
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
    print("[yields] No data from Yahoo — skipping update", flush=True)
    sys.exit(0)

spread = None
if t10 and t2:
    s  = t10['price'] - t2['price']
    ps = (t10['prev'] - t2['prev']) if (t10.get('prev') and t2.get('prev')) else None
    spread = {'price': s, 'prev': ps, 'change': (s - ps) if ps is not None else None, 'isSpread': True}

out = {
    'updated': datetime.datetime.utcnow().isoformat() + 'Z',
    'TNX': t10,
    'TWO': t2,
    'SPREAD': spread,
}

with open(sys.argv[3], 'w') as f:
    json.dump(out, f, indent=2)

t10v = t10['price'] if t10 else 'n/a'
t2v  = t2['price']  if t2  else 'n/a'
print(f"[yields] Updated — 10Y={t10v}  2Y={t2v}", flush=True)
PYEOF

YIELDS_EXIT=$?
if [ $YIELDS_EXIT -eq 0 ]; then
  echo "$TIMESTAMP  [yields] OK" >> "$LOG"
else
  echo "$TIMESTAMP  [yields] Skipped or errored (exit $YIELDS_EXIT)" >> "$LOG"
fi

# ── Step 2: Commit yields.json if changed ─────────────────────
if git diff --quiet yields.json 2>/dev/null; then
  echo "$TIMESTAMP  [yields] No change to commit" >> "$LOG"
else
  git add yields.json
  git commit -m "yields: $(date +%Y-%m-%d) morning update" >> "$LOG" 2>&1
  echo "$TIMESTAMP  [yields] Committed" >> "$LOG"
fi

# ── Step 3: Push any pending commits (brief + yields) ─────────
AHEAD=$(git rev-list origin/main..HEAD --count 2>/dev/null)

if [ -z "$AHEAD" ] || [ "$AHEAD" = "0" ]; then
  echo "$TIMESTAMP  [push]   Nothing to push — already in sync with origin" >> "$LOG"
  exit 0
fi

echo "$TIMESTAMP  [push]   Pushing $AHEAD commit(s) to origin/main..." >> "$LOG"
git push origin main >> "$LOG" 2>&1

if [ $? -eq 0 ]; then
  echo "$TIMESTAMP  [push]   ✓ Pushed — Netlify/Vercel deploying now" >> "$LOG"
else
  echo "$TIMESTAMP  [push]   ✗ Push failed — check SSH keys or network" >> "$LOG"
  echo "$TIMESTAMP           Run: git -C $SITE_DIR push origin main" >> "$LOG"
fi
