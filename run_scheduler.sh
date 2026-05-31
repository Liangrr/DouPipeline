#!/bin/bash
#
# 定时任务守护脚本
# 用法:
#   ./run_scheduler.sh start        # 启动（后台运行，自动重启）
#   ./run_scheduler.sh stop         # 停止
#   ./run_scheduler.sh status       # 查看状态
#   ./run_scheduler.sh logs         # 查看日志
#   ./run_scheduler.sh foreground   # 前台运行（调试用，Ctrl+C 停止）

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.scheduler.pid"
DAEMON_PID_FILE="$SCRIPT_DIR/.scheduler_daemon.pid"
LOG_FILE="$SCRIPT_DIR/logs/scheduler.log"
PYTHON="uv run python"

mkdir -p "$SCRIPT_DIR/logs"

# 守护循环脚本（写入临时文件，避免引号问题）
DAEMON_SCRIPT="$SCRIPT_DIR/.scheduler_daemon.sh"

cat > "$DAEMON_SCRIPT" << 'DAEMON_EOF'
#!/bin/bash
SCRIPT_DIR="__SCRIPT_DIR__"
LOG_FILE="__LOG_FILE__"
PYTHON="__PYTHON__"

while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🔄 定时任务启动" >> "$LOG_FILE"
    caffeinate -i -s "$PYTHON" "$SCRIPT_DIR/scheduler.py" >> "$LOG_FILE" 2>&1
    EXIT_CODE=$?
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  定时任务退出 (code: $EXIT_CODE)，5 秒后重启..." >> "$LOG_FILE"
    sleep 5
done
DAEMON_EOF

# 替换占位符
sed -i '' "s|__SCRIPT_DIR__|$SCRIPT_DIR|g" "$DAEMON_SCRIPT"
sed -i '' "s|__LOG_FILE__|$LOG_FILE|g" "$DAEMON_SCRIPT"
sed -i '' "s|__PYTHON__|$PYTHON|g" "$DAEMON_SCRIPT"
chmod +x "$DAEMON_SCRIPT"

start_scheduler() {
    if [ -f "$DAEMON_PID_FILE" ] && kill -0 "$(cat "$DAEMON_PID_FILE")" 2>/dev/null; then
        echo "⚠️  定时任务已在运行 (PID: $(cat "$DAEMON_PID_FILE"))"
        echo "   停止请执行: ./run_scheduler.sh stop"
        exit 1
    fi

    echo "🚀 启动定时任务（后台守护模式）..."
    echo "   日志: $LOG_FILE"
    echo "   停止: ./run_scheduler.sh stop"

    nohup "$DAEMON_SCRIPT" >> "$LOG_FILE" 2>&1 &
    DAEMON_PID=$!
    echo "$DAEMON_PID" > "$DAEMON_PID_FILE"

    sleep 1

    if kill -0 "$DAEMON_PID" 2>/dev/null; then
        echo "✅ 已启动 (PID: $DAEMON_PID)"
    else
        echo "❌ 启动失败，查看日志: $LOG_FILE"
        rm -f "$DAEMON_PID_FILE"
        exit 1
    fi
}

stop_scheduler() {
    if [ ! -f "$DAEMON_PID_FILE" ]; then
        echo "⚠️  未找到 PID 文件，可能没有在运行"
        pkill -f "scheduler.py" 2>/dev/null && echo "✅ 已清理残留进程"
        rm -f "$DAEMON_SCRIPT" 2>/dev/null
        return
    fi

    DAEMON_PID=$(cat "$DAEMON_PID_FILE")
    echo "🛑 正在停止定时任务..."

    # 杀掉守护进程和它的所有子进程（caffeinate + python）
    if kill -0 "$DAEMON_PID" 2>/dev/null; then
        # 先杀子进程
        pkill -P "$DAEMON_PID" 2>/dev/null
        sleep 1
        # 再杀守护进程
        kill "$DAEMON_PID" 2>/dev/null
        sleep 1
        # 强制清理
        kill -9 "$DAEMON_PID" 2>/dev/null
    fi

    # 清理残留
    pkill -f "scheduler.py" 2>/dev/null
    pkill -f "caffeinate.*scheduler" 2>/dev/null

    rm -f "$DAEMON_PID_FILE"
    echo "✅ 已停止"
}

status_scheduler() {
    if [ -f "$DAEMON_PID_FILE" ] && kill -0 "$(cat "$DAEMON_PID_FILE")" 2>/dev/null; then
        PID=$(cat "$DAEMON_PID_FILE")
        echo "✅ 定时任务运行中 (PID: $PID)"
        echo ""
        echo "最近日志:"
        tail -5 "$LOG_FILE" 2>/dev/null || echo "  (无日志)"
    else
        echo "❌ 定时任务未运行"
        rm -f "$DAEMON_PID_FILE"
    fi
}

logs_scheduler() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo "⚠️  日志文件不存在"
    fi
}

foreground_scheduler() {
    echo "🖥️  前台模式（Ctrl+C 停止）..."
    trap 'echo -e "\n👋 已停止"; exit 0' INT TERM
    caffeinate -i -s $PYTHON "$SCRIPT_DIR/scheduler.py"
}

case "$1" in
    start)
        start_scheduler
        ;;
    stop)
        stop_scheduler
        ;;
    status)
        status_scheduler
        ;;
    logs)
        logs_scheduler
        ;;
    foreground)
        foreground_scheduler
        ;;
    restart)
        stop_scheduler
        sleep 1
        start_scheduler
        ;;
    *)
        echo "用法: ./run_scheduler.sh {start|stop|restart|status|logs|foreground}"
        echo ""
        echo "  start        后台启动（自动重启 + 防休眠）"
        echo "  stop         停止"
        echo "  restart      重启"
        echo "  status       查看状态"
        echo "  logs         实时查看日志"
        echo "  foreground   前台运行（调试用）"
        ;;
esac
