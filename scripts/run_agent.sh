#!/bin/bash
# Daily job discovery script for cron
# Example crontab entry (adjust paths for your system):
#   0 8 * * * /path/to/job-application-assistant/scripts/run_agent.sh

set -e

# Resolve project root from this script's location
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Use PYTHON env var if set, otherwise fall back to "python" on PATH
PYTHON="${PYTHON:-python}"

LOG="$PROJECT_DIR/logs/daily_discover.log"

cd "$PROJECT_DIR"

mkdir -p "$PROJECT_DIR/logs"
echo "=== $(date) ===" >> "$LOG"
"$PYTHON" scripts/daily_discover.py >> "$LOG" 2>&1
