#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  install-automation.sh
#  Run this ONCE to install the daily automation LaunchAgent.
#
#  What it does:
#   • Installs com.zubinshourie.morning-run.plist into ~/Library/LaunchAgents
#   • Loads it so it activates immediately (fires next at 8:00 AM)
#   • Removes the old brief-push plist if it exists
#   • Makes morning-run.sh executable
#
#  Usage:
#    cd ~/Desktop/site-prototype
#    bash install-automation.sh
# ─────────────────────────────────────────────────────────────

SITE_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
PLIST_NAME="com.zubinshourie.morning-run"
PLIST_SRC="$SITE_DIR/${PLIST_NAME}.plist"
PLIST_DST="$LAUNCH_DIR/${PLIST_NAME}.plist"

echo ""
echo "▸ Installing zubinshourie.com morning automation"
echo ""

# Make script executable
chmod +x "$SITE_DIR/morning-run.sh"
echo "  ✓ morning-run.sh is executable"

# Create LaunchAgents dir if needed
mkdir -p "$LAUNCH_DIR"

# Remove old push-only plist if installed
OLD_PLIST="$LAUNCH_DIR/com.zubinshourie.daily-brief-push.plist"
if [ -f "$OLD_PLIST" ]; then
  launchctl unload "$OLD_PLIST" 2>/dev/null
  rm "$OLD_PLIST"
  echo "  ✓ Removed old daily-brief-push agent"
fi

# Copy new plist
cp "$PLIST_SRC" "$PLIST_DST"
echo "  ✓ Plist copied to $PLIST_DST"

# Unload if already loaded (for clean reinstall)
launchctl unload "$PLIST_DST" 2>/dev/null

# Load the agent
launchctl load "$PLIST_DST"
if [ $? -eq 0 ]; then
  echo "  ✓ LaunchAgent loaded — will fire every morning at 8:00 AM"
else
  echo "  ✗ Load failed — try: launchctl load $PLIST_DST"
  exit 1
fi

echo ""
echo "────────────────────────────────────────"
echo "  All set. Here's the full daily schedule:"
echo ""
echo "  7:09 AM  Cowork runs — generates brief, commits to git"
echo "  8:00 AM  LaunchAgent runs — updates yields.json, pushes to GitHub"
echo "           → Netlify/Vercel auto-deploys the live site"
echo ""
echo "  Log file:  ~/Desktop/morning-run.log"
echo "────────────────────────────────────────"
echo ""
echo "  To test right now (without waiting for 8 AM):"
echo "  bash ~/Desktop/site-prototype/morning-run.sh"
echo ""
