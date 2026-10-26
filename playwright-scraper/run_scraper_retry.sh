#!/bin/bash
# Retry wrapper: runs the scraper only if today's run hasn't already succeeded.
STAMP="${STAMP:-/home/ubuntu/ai-sandbox/playwright-scraper/last_updated.txt}"
TODAY=$(date -u +%F)
if [ -f "$STAMP" ] && [ "$(cut -c1-10 "$STAMP")" = "$TODAY" ]; then
  echo "$(date): Retry skipped, already updated today ($TODAY)" >> /home/ubuntu/scraper_log.txt
  exit 0
fi
echo "$(date): Retry starting, no successful update yet today" >> /home/ubuntu/scraper_log.txt
exec /home/ubuntu/ai-sandbox/playwright-scraper/run_scraper.sh
