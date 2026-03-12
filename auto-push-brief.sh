#!/bin/bash
# Daily Brief Auto-Push
# Runs at 8 AM via Launch Agent — pushes any pending commits to GitHub so Netlify auto-deploys.

SITE_DIR="$HOME/Desktop/site-prototype"
LOG="$HOME/Desktop/brief-push.log"

echo "$(date): Auto-push triggered" >> "$LOG"

cd "$SITE_DIR" || { echo "$(date): ERROR - could not cd to $SITE_DIR" >> "$LOG"; exit 1; }

# Check if there are commits ahead of origin
AHEAD=$(git rev-list origin/main..HEAD --count 2>/dev/null)

if [ "$AHEAD" = "0" ] || [ -z "$AHEAD" ]; then
  echo "$(date): Nothing to push (up to date with origin)" >> "$LOG"
  exit 0
fi

echo "$(date): Pushing $AHEAD commit(s) to origin/main..." >> "$LOG"
git push origin main >> "$LOG" 2>&1

if [ $? -eq 0 ]; then
  echo "$(date): Push successful — Netlify deploying" >> "$LOG"
else
  echo "$(date): ERROR - push failed (check SSH keys / network)" >> "$LOG"
fi
