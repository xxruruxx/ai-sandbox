#!/bin/bash
set -e

cd /home/ubuntu/ai-sandbox/news-rag-agent
source /home/ubuntu/ai-sandbox-env/bin/activate

echo "$(date): Starting daily ingestion" >> /home/ubuntu/ingest_log.txt

python3 src/ingest_current_events.py >> /home/ubuntu/ingest_log.txt 2>&1

echo "$(date): Ingestion complete" >> /home/ubuntu/ingest_log.txt
