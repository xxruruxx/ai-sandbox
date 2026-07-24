#!/bin/bash
set -e

cd /home/ubuntu/ai-sandbox/playwright-scraper
source /home/ubuntu/ai-sandbox-env/bin/activate

echo "$(date): Starting scraper run" >> /home/ubuntu/scraper_log.txt

python3 scrape_listings_parallel.py >> /home/ubuntu/scraper_log.txt 2>&1
date -u +"%Y-%m-%d %H:%M UTC" > /home/ubuntu/ai-sandbox/playwright-scraper/last_updated.txt

cd /home/ubuntu/ai-sandbox
git add playwright-scraper/calabarzon_all_listings.csv
git commit -m "chore: automated scraper update $(date +%Y-%m-%d)" || echo "No changes to commit"
git push

echo "$(date): Scraper run complete" >> /home/ubuntu/scraper_log.txt
