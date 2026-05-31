#!/bin/bash
SCRIPT_DIR="/Users/asuria/Desktop/browser"
LOG_FILE="/Users/asuria/Desktop/browser/logs/scheduler.log"
PYTHON="uv run python"

while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🔄 定时任务启动" >> "$LOG_FILE"
    caffeinate -i -s "$PYTHON" "$SCRIPT_DIR/scheduler.py" >> "$LOG_FILE" 2>&1
    EXIT_CODE=$?
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  定时任务退出 (code: $EXIT_CODE)，5 秒后重启..." >> "$LOG_FILE"
    sleep 5
done
