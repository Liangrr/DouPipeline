#!/usr/bin/env python3
"""
统一启动脚本 — 选择平台执行对应链路

抖音链路 (douyin):
    python run.py --platform douyin                         # 默认主题"美女"
    python run.py --platform douyin --topic "旅行攻略"      # 指定主题
    python run.py --platform douyin --type article          # 发布类型: article/image
    python run.py --platform douyin --count 3               # 生成图片数量
    python run.py --platform douyin --step 3                # 从发布步骤开始
    python run.py --platform douyin --only 3                # 只发布

小红书链路 (xiaohongshu):
    python run.py --platform xiaohongshu                    # 默认主题"美女"，自动生成文案
    python run.py --platform xiaohongshu --topic "旅行攻略"  # 指定主题
    python run.py --platform xiaohongshu --input xxx.json   # 使用已有 JSON 文件
    python run.py --platform xiaohongshu --only 1           # 只生成文案
    python run.py --platform xiaohongshu --only 2           # 只发布
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "logs")
CONFIG_PATH = os.path.join(BASE_DIR, "doubao.json")
XIAOHONGSHU_JSON_PATH = os.path.join(BASE_DIR, "xiaohongshu.json")


def log_execution(step_num: int, step_name: str, success: bool, error_msg: str = "", platform: str = ""):
    """将每步执行结果记录到 logs 目录下，按日期分文件"""
    os.makedirs(LOGS_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(LOGS_DIR, f"{today}.jsonl")
    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "platform": platform,
        "step": step_num,
        "step_name": step_name,
        "status": "success" if success else "fail",
    }
    if error_msg:
        record["error"] = error_msg
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ==================== 抖音链路 ====================

async def run_douyin_pipeline(args):
    """抖音链路: generate → doubao → douyin.publish"""
    args.topic = args.topic or "美女"
    print("=" * 60)
    print("🎬  抖音链路")
    print("=" * 60)

    start_step = args.step or 1
    only_step = args.only
    content_type = args.type or "image"
    count = args.count or 5

    # --- Step 1: 内容生成 ---
    if (start_step <= 1) and (only_step is None or only_step == 1):
        print("\n🚀 Step 1: 内容生成 (generate)")
        print("-" * 60)
        try:
            from generate import generate_content
            config = await generate_content(
                topic=args.topic,
                send_type=content_type,
                prompt_count=count,
            )
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"✅ Step 1 完成 -> {CONFIG_PATH}")
            log_execution(1, "generate", success=True, platform="douyin")
        except Exception as e:
            print(f"❌ Step 1 失败: {e}")
            log_execution(1, "generate", success=False, error_msg=str(e), platform="douyin")
            sys.exit(1)
        if only_step == 1:
            return
    else:
        print("\n⏭️  Step 1: 跳过")

    # --- Step 2: 豆包图片生成 ---
    if (start_step <= 2) and (only_step is None or only_step == 2):
        print("\n🚀 Step 2: 豆包图片生成 (doubao)")
        print("-" * 60)
        try:
            doubao_script = os.path.join(BASE_DIR, "doubao.py")
            result = subprocess.run(
                [sys.executable, doubao_script],
                cwd=BASE_DIR,
            )
            if result.returncode != 0:
                raise RuntimeError(f"退出码: {result.returncode}")
            print("✅ Step 2 完成")
            log_execution(2, "doubao", success=True, platform="douyin")
        except Exception as e:
            print(f"❌ Step 2 失败: {e}")
            log_execution(2, "doubao", success=False, error_msg=str(e), platform="douyin")
            sys.exit(1)
        if only_step == 2:
            return
    else:
        print("\n⏭️  Step 2: 跳过")

    # --- Step 3: 抖音发布 ---
    if (start_step <= 3) and (only_step is None or only_step == 3):
        print("\n🚀 Step 3: 抖音发布 (douyin.publisher)")
        print("-" * 60)
        try:
            from douyin.publisher import publish as douyin_publish
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
            send_type = content_type or config.get("sendType", "image")
            await douyin_publish(
                sendType=send_type,
                title=config.get("title"),
                content=config.get("content"),
            )
            print("✅ Step 3 完成")
            log_execution(3, "douyin_publish", success=True, platform="douyin")
        except Exception as e:
            print(f"❌ Step 3 失败: {e}")
            log_execution(3, "douyin_publish", success=False, error_msg=str(e), platform="douyin")
            sys.exit(1)
    else:
        print("\n⏭️  Step 3: 跳过")

    print("\n🎉 抖音链路执行完毕！")


# ==================== 小红书链路 ====================

async def run_xiaohongshu_pipeline(args):
    """小红书链路: generate → xiaohongshu.publish"""
    args.topic = args.topic or "宝妈育儿"
    print("=" * 60)
    print("📕  小红书链路")
    print("=" * 60)

    start_step = args.step or 1
    only_step = args.only
    input_file = args.input

    # --- Step 1: 内容生成 ---
    if input_file:
        # 指定了 --input 则跳过生成，直接用指定文件
        if not os.path.isabs(input_file):
            input_file = os.path.join(BASE_DIR, input_file)
        if not os.path.exists(input_file):
            print(f"❌ 文件不存在: {input_file}")
            sys.exit(1)
        print(f"\n⏭️  Step 1: 使用指定文件 -> {input_file}")
    elif (start_step <= 1) and (only_step is None or only_step == 1):
        print("\n🚀 Step 1: 小红书文案生成 (generate)")
        print("-" * 60)
        try:
            from generate import generate_content
            config = await generate_content(
                topic=args.topic,
                send_type="xiaohongshu",
                prompt_count=0,
            )
            with open(XIAOHONGSHU_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"✅ Step 1 完成 -> {XIAOHONGSHU_JSON_PATH}")
            log_execution(1, "generate", success=True, platform="xiaohongshu")
            input_file = XIAOHONGSHU_JSON_PATH
        except Exception as e:
            print(f"❌ Step 1 失败: {e}")
            log_execution(1, "generate", success=False, error_msg=str(e), platform="xiaohongshu")
            sys.exit(1)
        if only_step == 1:
            return
    else:
        print("\n⏭️  Step 1: 跳过，使用已有文案")
        input_file = XIAOHONGSHU_JSON_PATH

    # --- Step 2: 小红书发布 ---
    if (start_step <= 2) and (only_step is None or only_step == 2):
        print(f"\n🚀 Step 2: 小红书发布 (xiaohongshu.publisher)")
        print(f"   输入文件: {input_file}")
        print("-" * 60)
        try:
            from xiaohongshu.publisher import publish as xhs_publish
            await xhs_publish(input_file)
            print("✅ Step 2 完成")
            log_execution(2, "xiaohongshu_publish", success=True, platform="xiaohongshu")
        except Exception as e:
            print(f"❌ Step 2 失败: {e}")
            log_execution(2, "xiaohongshu_publish", success=False, error_msg=str(e), platform="xiaohongshu")
            sys.exit(1)
    else:
        print("\n⏭️  Step 2: 跳过")

    print("\n🎉 小红书链路执行完毕！")


# ==================== 统一入口 ====================

def main():
    parser = argparse.ArgumentParser(
        description="社交媒体自动发布工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  抖音链路:
    python run.py --platform douyin                         # 默认主题"美女"
    python run.py --platform douyin --topic "旅行攻略"      # 指定主题
    python run.py --platform douyin --type article          # 发布类型: article/image
    python run.py --platform douyin --count 3               # 生成图片数量
    python run.py --platform douyin --only 1                # 只生成内容
    python run.py --platform douyin --only 3                # 只发布
    python run.py --platform douyin --step 3                # 从发布步骤开始

  小红书链路:
    python run.py --platform xiaohongshu                    # 默认主题，自动生成文案
    python run.py --platform xiaohongshu --topic "旅行攻略"  # 指定主题
    python run.py --platform xiaohongshu --input xxx.json   # 使用已有 JSON 文件
    python run.py --platform xiaohongshu --only 1           # 只生成文案
    python run.py --platform xiaohongshu --only 2           # 只发布
        """,
    )
    parser.add_argument(
        "--platform", "-p",
        required=True,
        choices=["douyin", "xiaohongshu"],
        help="选择平台: douyin (抖音) 或 xiaohongshu (小红书)",
    )
    # 通用参数
    parser.add_argument(
        "--topic",
        help="内容主题 (抖音默认: 美女, 小红书默认: 宝妈育儿)",
    )
    parser.add_argument(
        "--step", type=int,
        help="从第 N 步开始",
    )
    parser.add_argument(
        "--only", type=int,
        help="只执行第 N 步",
    )
    # 抖音专用参数
    douyin_group = parser.add_argument_group("抖音参数")
    douyin_group.add_argument(
        "--type", choices=["article", "image", "video"],
        help="[抖音] 发布类型 (article=文章, image=图文)",
    )
    douyin_group.add_argument(
        "--count", type=int,
        help="[抖音] 生成图片数量 (默认 5)",
    )
    # 小红书专用参数
    xhs_group = parser.add_argument_group("小红书参数")
    xhs_group.add_argument(
        "--input", "-i",
        help="[小红书] 指定已有 JSON 文件，跳过文案生成",
    )

    args = parser.parse_args()

    if args.platform == "douyin":
        asyncio.run(run_douyin_pipeline(args))
    elif args.platform == "xiaohongshu":
        asyncio.run(run_xiaohongshu_pipeline(args))


if __name__ == "__main__":
    main()
