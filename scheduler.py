#!/usr/bin/env python3
"""
定时执行脚本 — 按 cron 风格定时运行抖音和小红书发布链路

用法:
  python scheduler.py

  # 修改下方 SCHEDULES 列表自定义定时规则
"""

import subprocess
import sys
import os
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

# ==================== 定时配置 ====================
# 格式: (minute, hour, platform, extra_args)
#
#   minute / hour 支持三种格式:
#     具体数字  → 精确匹配，如 9 表示第 9 分钟 / 第 9 小时
#     "*"      → 每个都执行，如 hour="*" 表示每小时
#     "*/N"    → 每隔 N 执行，如 hour="*/2" 表示每 2 小时
#
# 示例:
#   (0,  9,     "douyin",      ["--type", "article"])  → 每天 9:00  发布抖音文章
#   (0,  "*/4", "douyin",      ["--type", "image"])     → 每 4 小时  发布抖音图文
#   (30, "*/2", "xiaohongshu", [])                       → 每 2 小时的 30 分  发布小红书
#   (0,  "*",   "douyin",      ["--type", "article"])   → 每小时整点  发布抖音文章

SCHEDULES = [
    # (minute, hour, platform, extra_args)
    # (0,  9,     "douyin",      ["--type", "article"]),    # 每天 9:00
    # (30, 9,     "xiaohongshu", []),                        # 每天 9:30
    (0,  "*/1.5", "douyin",      ["--type", "image"]),    # 每 4 小时
    (0,  "*/1", "xiaohongshu", []),                     # 每 2 小时
]


def match_time(pattern, value) -> bool:
    """判断当前时间值是否匹配 cron 模式"""
    if isinstance(pattern, int):
        return value == pattern
    if pattern == "*":
        return True
    if pattern.startswith("*/"):
        n = int(pattern[2:])
        return n > 0 and value % n == 0
    return False


def task_key(minute, hour, platform, extra_args) -> str:
    """生成任务去重 key，避免同一周期内重复执行"""
    now = datetime.now()

    # 按小时去重: hour 是 "*/N" 或 "*"
    if isinstance(hour, str):
        if isinstance(minute, int):
            # 每 N 小时的第 X 分钟 → key 按小时
            return f"{platform}:{extra_args}:{now.strftime('%Y-%m-%d-%H')}"
        else:
            # 每 N 分钟 + 每 N 小时 → key 按小时
            return f"{platform}:{extra_args}:{now.strftime('%Y-%m-%d-%H')}"

    # 按天去重: hour 是固定数字
    if isinstance(minute, str):
        return f"{platform}:{extra_args}:{now.strftime('%Y-%m-%d-%H')}"
    else:
        return f"{platform}:{extra_args}:{now.strftime('%Y-%m-%d')}"


def format_pattern(pattern) -> str:
    """格式化时间模式用于显示"""
    if isinstance(pattern, int):
        return f"{pattern:02d}"
    return pattern


def run_task(platform: str, extra_args: list):
    """执行一次发布任务，失败不影响调度器继续运行"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cmd = [PYTHON, os.path.join(BASE_DIR, "run.py"), "--platform", platform] + extra_args

    print(f"\n{'=' * 60}")
    print(f"⏰ [{now}] 执行: {' '.join(cmd)}")
    print(f"{'=' * 60}")

    try:
        result = subprocess.run(cmd, cwd=BASE_DIR)

        if result.returncode == 0:
            print(f"\n[{now}] ✅ 成功")
        else:
            print(f"\n[{now}] ❌ 失败 (退出码: {result.returncode})")

    except Exception as e:
        print(f"\n[{now}] ❌ 异常: {e}")

    # 无论成功失败，都返回继续调度（不抛异常）


def main():
    print("🕐 定时调度器已启动")
    print(f"📋 已配置 {len(SCHEDULES)} 个定时任务:")
    for minute, hour, platform, args in SCHEDULES:
        args_str = " ".join(args) if args else "(默认参数)"
        print(f"   ⏰ {format_pattern(hour)}:{format_pattern(minute)} → {platform} {args_str}")
    print()

    # 记录已执行的任务 key，避免同一周期重复执行
    executed = set()

    try:
        while True:
            now = datetime.now()

            for minute, hour, platform, extra_args in SCHEDULES:
                if match_time(minute, now.minute) and match_time(hour, now.hour):
                    key = task_key(minute, hour, platform, str(extra_args))
                    if key not in executed:
                        executed.add(key)
                        run_task(platform, extra_args)

            # 定期清理过期 key（保留当天的）
            if len(executed) > 100:
                today = datetime.now().strftime("%Y-%m-%d")
                executed = {k for k in executed if today in k}

            time.sleep(30)  # 每 30 秒检查一次

    except KeyboardInterrupt:
        print("\n👋 调度器已停止")


if __name__ == "__main__":
    main()
