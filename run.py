#!/usr/bin/env python3
"""
统一启动脚本 — 选择平台执行对应链路

抖音链路 (douyin):
    python run.py --platform douyin                         # 默认主题"美女"
    python run.py --platform douyin --topic "旅行攻略"      # 指定主题
    python run.py --platform douyin --type article          # 发布类型: article/image/swimwear
    python run.py --platform douyin --type swimwear --count 6  # 泳装写真
    python run.py --platform douyin --count 3               # 生成图片数量
    python run.py --platform douyin --step 3                # 从发布步骤开始
    python run.py --platform douyin --only 3                # 只发布

小红书链路 (xiaohongshu):
    python run.py --platform xiaohongshu                    # 默认主题"美女"，自动生成文案
    python run.py --platform xiaohongshu --topic "旅行攻略"  # 指定主题
    python run.py --platform xiaohongshu --input xxx.json   # 使用已有 JSON 文件
    python run.py --platform xiaohongshu --only 1           # 只生成文案
    python run.py --platform xiaohongshu --only 2           # 只发布

番茄小说链路 (fanqie):
    python run.py --platform fanqie --topic "都市重生"              # 完整流程：架构→章节→发布
    python run.py --platform fanqie --topic "玄幻修仙" --genre "玄幻" --outlines 10 --chapters 5
    python run.py --platform fanqie --topic "都市重生" --only 1    # 只生成架构
    python run.py --platform fanqie --book-dir novels/都市重生 --only 2  # 生成章节（默认2章）
    python run.py --platform fanqie --book-dir novels/都市重生 --only 2 --chapters 5  # 生成5章
    python run.py --platform fanqie --book-dir novels/都市重生 --only 3  # 发布（默认2章）
    python run.py --platform fanqie --book-dir novels/都市重生 --only 3 --chapters 1  # 发布1章

多账号管理:
    python run.py --platform douyin --account list          # 列出所有账号
    python run.py --platform douyin --account create my_acc # 创建新账号
    python run.py --platform douyin --account my_acc        # 使用指定账号发布
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime

# 导入账号管理模块
from account_manager import (
    PROJECT_ROOT,
    list_accounts,
    create_account,
    print_accounts,
    migrate_legacy_account,
    get_account_config_path,
    get_account_output_dir,
    get_account_browser_profile,
)

LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
XIAOHONGSHU_JSON_PATH = os.path.join(PROJECT_ROOT, "xiaohongshu.json")


def log_execution(step_num: int, step_name: str, success: bool, error_msg: str = "", platform: str = "", account: str = ""):
    """将每步执行结果记录到 logs 目录下，按日期分文件"""
    os.makedirs(LOGS_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(LOGS_DIR, f"{today}.jsonl")
    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "platform": platform,
        "account": account,
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
    account_name = getattr(args, 'account', 'legacy') or 'legacy'

    print("=" * 60)
    print(f"🎬  抖音链路  [账号: {account_name}]")
    print("=" * 60)

    # 获取账号专属路径
    config_path = get_account_config_path(account_name)
    output_dir = get_account_output_dir(account_name)

    start_step = args.step or 1
    only_step = args.only
    content_type = args.type or "image"
    # 文章模式只需 1 张封面图，图文模式默认 3 张
    if content_type == "article":
        count = args.count or 1
    else:
        count = args.count or 3

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
                output_path=config_path,
            )
            print(f"✅ Step 1 完成 -> {config_path}")
            log_execution(1, "generate", success=True, platform="douyin", account=account_name)
        except Exception as e:
            print(f"❌ Step 1 失败: {e}")
            log_execution(1, "generate", success=False, error_msg=str(e), platform="douyin", account=account_name)
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
            from doubao import run_doubao
            await run_doubao(account_name=account_name)
            print("✅ Step 2 完成")
            log_execution(2, "doubao", success=True, platform="douyin", account=account_name)
        except Exception as e:
            print(f"❌ Step 2 失败: {e}")
            log_execution(2, "doubao", success=False, error_msg=str(e), platform="douyin", account=account_name)
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
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            send_type = content_type or config.get("sendType", "image")
            await douyin_publish(
                sendType=send_type,
                title=config.get("title"),
                content=config.get("content"),
                account_name=account_name,
            )
            print("✅ Step 3 完成")
            log_execution(3, "douyin_publish", success=True, platform="douyin", account=account_name)
        except Exception as e:
            print(f"❌ Step 3 失败: {e}")
            log_execution(3, "douyin_publish", success=False, error_msg=str(e), platform="douyin", account=account_name)
            sys.exit(1)
    else:
        print("\n⏭️  Step 3: 跳过")

    print("\n🎉 抖音链路执行完毕！")


# ==================== 小红书链路 ====================

async def run_xiaohongshu_pipeline(args):
    """小红书链路: generate → xiaohongshu.publish"""
    args.topic = args.topic or "宝妈育儿"
    account_name = getattr(args, 'account', 'legacy') or 'legacy'

    print("=" * 60)
    print(f"📕  小红书链路  [账号: {account_name}]")
    print("=" * 60)

    start_step = args.step or 1
    only_step = args.only
    input_file = args.input

    # --- Step 1: 内容生成 ---
    if input_file:
        # 指定了 --input 则跳过生成，直接用指定文件
        if not os.path.isabs(input_file):
            input_file = os.path.join(PROJECT_ROOT, input_file)
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
            log_execution(1, "generate", success=True, platform="xiaohongshu", account=account_name)
            input_file = XIAOHONGSHU_JSON_PATH
        except Exception as e:
            print(f"❌ Step 1 失败: {e}")
            log_execution(1, "generate", success=False, error_msg=str(e), platform="xiaohongshu", account=account_name)
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
            await xhs_publish(input_file, account_name=account_name)
            print("✅ Step 2 完成")
            log_execution(2, "xiaohongshu_publish", success=True, platform="xiaohongshu", account=account_name)
        except Exception as e:
            print(f"❌ Step 2 失败: {e}")
            log_execution(2, "xiaohongshu_publish", success=False, error_msg=str(e), platform="xiaohongshu", account=account_name)
            sys.exit(1)
    else:
        print("\n⏭️  Step 2: 跳过")

    print("\n🎉 小红书链路执行完毕！")


# ==================== 番茄小说链路 ====================

async def run_fanqie_pipeline(args):
    """番茄小说链路: architecture → chapters → publish"""
    args.topic = args.topic or "都市重生"
    account_name = getattr(args, 'account', 'legacy') or 'legacy'

    print("=" * 60)
    print(f"📚  番茄小说链路  [账号: {account_name}]")
    print("=" * 60)

    start_step = args.step or 1
    only_step = args.only
    genre = getattr(args, 'genre', '') or ''
    gender = getattr(args, 'gender', 'male') or 'male'
    outline_count = getattr(args, 'outlines', 10) or 10
    chapter_count = getattr(args, 'chapters', 2) or 2
    book_dir = getattr(args, 'book_dir', None)

    # 确定小说输出目录
    if book_dir:
        if not os.path.isabs(book_dir):
            book_dir = os.path.join(PROJECT_ROOT, book_dir)
    else:
        from account_manager import get_account_novels_dir
        novels_dir = get_account_novels_dir(account_name)
        dir_name = args.topic.replace(" ", "_")[:20]
        book_dir = os.path.join(novels_dir, dir_name)

    # --- Step 1: 生成小说架构（只生成大纲，不生成章节内容）---
    if (start_step <= 1) and (only_step is None or only_step == 1):
        print("\n🚀 Step 1: 生成小说架构 (novel_generator)")
        print("-" * 60)
        try:
            from novel_generator import generate_architecture
            architecture = await generate_architecture(
                topic=args.topic,
                genre=genre,
                gender=gender,
                chapter_count=outline_count,
                output_dir=book_dir,
            )
            print(f"✅ Step 1 完成 -> {book_dir}")
            log_execution(1, "generate_architecture", success=True, platform="fanqie", account=account_name)
        except Exception as e:
            print(f"❌ Step 1 失败: {e}")
            log_execution(1, "generate_architecture", success=False, error_msg=str(e), platform="fanqie", account=account_name)
            sys.exit(1)
        if only_step == 1:
            return
    else:
        print("\n⏭️  Step 1: 跳过")

    # --- Step 2: 生成章节内容（默认2章，可通过 --chapters 指定）---
    if (start_step <= 2) and (only_step is None or only_step == 2):
        print("\n🚀 Step 2: 生成章节内容 (novel_generator)")
        print("-" * 60)
        try:
            from novel_generator import load_architecture, generate_chapters
            architecture = load_architecture(book_dir)
            await generate_chapters(
                architecture=architecture,
                start_chapter=getattr(args, 'start', 1) or 1,
                count=chapter_count,
                output_dir=book_dir,
            )
            print("✅ Step 2 完成")
            log_execution(2, "generate_chapters", success=True, platform="fanqie", account=account_name)
        except Exception as e:
            print(f"❌ Step 2 失败: {e}")
            log_execution(2, "generate_chapters", success=False, error_msg=str(e), platform="fanqie", account=account_name)
            sys.exit(1)
        if only_step == 2:
            return
    else:
        print("\n⏭️  Step 2: 跳过")

    # --- Step 3: 番茄小说发布（默认2章，可通过 --chapters 指定）---
    if (start_step <= 3) and (only_step is None or only_step == 3):
        print("\n🚀 Step 3: 番茄小说发布 (fanqie.publisher)")
        print("-" * 60)
        try:
            from fanqie.publisher import publish as fanqie_publish
            await fanqie_publish(book_dir=book_dir, account_name=account_name, limit=chapter_count)
            print("✅ Step 3 完成")
            log_execution(3, "fanqie_publish", success=True, platform="fanqie", account=account_name)
        except Exception as e:
            print(f"❌ Step 3 失败: {e}")
            log_execution(3, "fanqie_publish", success=False, error_msg=str(e), platform="fanqie", account=account_name)
            sys.exit(1)
    else:
        print("\n⏭️  Step 3: 跳过")

    print("\n🎉 番茄小说链路执行完毕！")


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
    python run.py --platform douyin --type article          # 发布类型: article/image/swimwear
    python run.py --platform douyin --type swimwear --count 6  # 泳装写真，生成6张图
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

  番茄小说链路:
    python run.py --platform fanqie --topic "都市重生"       # 完整流程
    python run.py --platform fanqie --topic "玄幻修仙" --genre "玄幻" --chapters 10
    python run.py --platform fanqie --topic "都市重生" --only 1   # 只生成架构
    python run.py --platform fanqie --book-dir novels/都市重生 --only 2  # 只生成章节
    python run.py --platform fanqie --book-dir novels/都市重生 --only 3  # 只发布

  多账号管理:
    python run.py --platform douyin --account list          # 列出所有账号
    python run.py --platform douyin --account create my_acc # 创建新账号
    python run.py --platform douyin --account my_acc        # 使用指定账号发布
        """,
    )
    parser.add_argument(
        "--platform", "-p",
        required=True,
        choices=["douyin", "xiaohongshu", "fanqie"],
        help="选择平台: douyin (抖音), xiaohongshu (小红书), fanqie (番茄小说)",
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
    parser.add_argument(
        "--account",
        help="账号名称: list=列出所有账号, <名称>=使用指定账号",
    )
    parser.add_argument(
        "--account-create",
        metavar="NAME",
        help="创建新账号",
    )
    # 抖音专用参数
    douyin_group = parser.add_argument_group("抖音参数")
    douyin_group.add_argument(
        "--type", choices=["article", "image", "swimwear"],
        help="[抖音] 发布类型 (article=文章, image=图文, swimwear=泳装写真)",
    )
    douyin_group.add_argument(
        "--count", type=int,
        help="[抖音] 生成图片数量 (默认 图文模式 3 图，文章模式 1 图)",
    )
    # 小红书专用参数
    xhs_group = parser.add_argument_group("小红书参数")
    xhs_group.add_argument(
        "--input", "-i",
        help="[小红书] 指定已有 JSON 文件，跳过文案生成",
    )
    # 番茄小说专用参数
    fanqie_group = parser.add_argument_group("番茄小说参数")
    fanqie_group.add_argument(
        "--genre",
        help="[番茄] 小说分类 (如: 玄幻, 都市, 科幻, 仙侠, 言情)",
    )
    fanqie_group.add_argument(
        "--gender", default="male", choices=["male", "female"],
        help="[番茄] 目标读者 (male=男频, female=女频, 默认: male)",
    )
    fanqie_group.add_argument(
        "--outlines", type=int, default=10,
        help="[番茄] Step1 架构中生成的章节数量 (默认: 10)",
    )
    fanqie_group.add_argument(
        "--chapters", "-c", type=int, default=2,
        help="[番茄] Step2/3 每批次生成/发布章节数量 (默认: 2)",
    )
    fanqie_group.add_argument(
        "--start", type=int, default=1,
        help="[番茄] 从第N章开始生成 (默认: 1)",
    )
    fanqie_group.add_argument(
        "--book-dir",
        help="[番茄] 已有小说目录，用于继续生成或发布",
    )

    args = parser.parse_args()

    # 处理账号管理命令
    if args.account_create:
        # 创建新账号
        try:
            create_account(args.account_create)
        except (ValueError, FileExistsError) as e:
            print(f"❌ {e}")
        return

    if args.account:
        if args.account == "list":
            print_accounts()
            return
        else:
            # 使用指定账号
            print(f"📋 使用账号: {args.account}")

    # 确保 legacy 账号存在（自动迁移）
    migrate_legacy_account()

    if args.platform == "douyin":
        asyncio.run(run_douyin_pipeline(args))
    elif args.platform == "xiaohongshu":
        asyncio.run(run_xiaohongshu_pipeline(args))
    elif args.platform == "fanqie":
        asyncio.run(run_fanqie_pipeline(args))


if __name__ == "__main__":
    main()
