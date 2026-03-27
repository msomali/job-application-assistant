#!/bin/bash
# Daily job discovery script for cron
# Runs at 8 AM daily: 0 8 * * * /Users/msomali/Documents/Devs/ML/job-application-assistant/scripts/run_agent.sh

set -e

PROJECT_DIR="/Users/msomali/Documents/Devs/ML/job-application-assistant"
PYTHON="/opt/miniconda3/envs/dl/bin/python"
LOG="$PROJECT_DIR/logs/daily_discover.log"

cd "$PROJECT_DIR"

echo "=== $(date) ===" >> "$LOG"
"$PYTHON" scripts/daily_discover.py >> "$LOG" 2>&1
