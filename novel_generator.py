"""
小说内容生成模块

两阶段生成：
  Phase 1: generate_architecture() — 生成小说整体架构（书名、简介、世界观、人物、章节大纲）
  Phase 2: generate_chapter()     — 逐章生成小说内容（基于架构 + 前文摘要）
"""

import asyncio
import json
import os
import sys
from openai import AsyncOpenAI

from account_manager import (
    PROJECT_ROOT,
    get_account_novels_dir,
    get_book_dir,
)

# 导入 generate.py 中的 JSON 修复工具
from generate import fix_json

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

# ==================== 配置区 ====================
API_KEY = os.environ.get("MIMO_API_KEY", "")
BASE_URL = os.environ.get("MIMO_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
MODEL = os.environ.get("MIMO_MODEL", "mimo-v2.5")

if not API_KEY:
    raise EnvironmentError(
        "未设置 MIMO_API_KEY 环境变量。\n"
        "请在 .env 文件或系统环境变量中配置: MIMO_API_KEY=your_key_here"
    )

PROMPTS_DIR = os.path.join(PROJECT_ROOT, "prompts")


# ==================== 提示词加载 ====================

def _load_prompt_file(category: str, name: str) -> str:
    """从 prompts/{category}/{name}.md 加载提示词文件"""
    path = os.path.join(PROMPTS_DIR, category, f"{name}.md")
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


# ==================== Phase 1: 生成小说架构 ====================

async def generate_architecture(
    topic: str,
    genre: str = "",
    gender: str = "male",
    chapter_count: int = 10,
    output_dir: str = None,
) -> dict:
    """
    生成小说整体架构

    Args:
        topic: 题材/主题（如"都市重生"、"玄幻修仙"）
        genre: 小说分类（如"都市"、"玄幻"），为空则由 LLM 判断
        gender: 目标读者 male/female
        chapter_count: 计划章节数量
        output_dir: 输出目录，为空则不保存文件

    Returns:
        架构 JSON 字典
    """
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)

    role = _load_prompt_file("roles", "novel")
    instruction = _load_prompt_file("instructions", "novel_architecture")
    instruction = instruction.format(prompt_count=chapter_count)

    system_prompt = role + "\n\n" + instruction

    user_prompt = f"题材：{topic}"
    if genre:
        user_prompt += f"\n分类：{genre}"
    user_prompt += f"\n目标读者：{'男频' if gender == 'male' else '女频'}"
    user_prompt += f"\n计划章节数：{chapter_count}"

    print(f"🤖 正在生成小说架构...")
    print(f"   题材: {topic} | 分类: {genre or '自动'} | {'男频' if gender == 'male' else '女频'} | {chapter_count}章")

    # 根据章节数动态计算 max_tokens（每章约 120 tokens + 结构开销）
    max_tokens = min(max(8192, chapter_count * 150 + 2000), 65536)

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.8,
        max_tokens=max_tokens,
    )

    raw = response.choices[0].message.content.strip()
    print(f"\n📝 原始输出长度: {len(raw)} 字符")

    # 解析 JSON
    json_str = raw
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0].strip()
    elif "```" in json_str:
        json_str = json_str.split("```")[1].split("```")[0].strip()

    try:
        result = json.loads(json_str)
    except json.JSONDecodeError:
        print("⚠️ JSON 解析失败，尝试自动修复...")
        json_str = fix_json(json_str)
        result = json.loads(json_str)

    # 确保必要字段存在
    result.setdefault("book_name", "未命名小说")
    result.setdefault("summary", "")
    result.setdefault("gender", gender)
    result.setdefault("category", genre or "其他")
    result.setdefault("world_setting", "")
    result.setdefault("characters", [])
    result.setdefault("chapters", [])

    print(f"\n📖 小说架构生成完成:")
    print(f"   书名: {result['book_name']}")
    print(f"   分类: {result['category']}")
    print(f"   人物: {len(result['characters'])} 个")
    print(f"   章节: {len(result['chapters'])} 章")

    # 保存到文件
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        arch_path = os.path.join(output_dir, "architecture.json")
        with open(arch_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"   ✅ 已保存到: {arch_path}")

    return result


# ==================== Phase 1.5: 扩展小说架构（追加章节大纲）====================

async def extend_architecture(
    architecture: dict,
    add_count: int = 2,
    output_dir: str = None,
) -> dict:
    """
    在现有架构基础上追加新的章节大纲

    Args:
        architecture: 已有的小说架构字典
        add_count: 要追加的章节数量
        output_dir: 输出目录，为空则不保存文件

    Returns:
        更新后的架构字典
    """
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)

    existing_chapters = architecture.get("chapters", [])
    current_count = len(existing_chapters)
    start_num = current_count + 1
    end_num = current_count + add_count

    # 构建已有章节摘要，让 LLM 了解前情
    existing_outline = []
    for ch in existing_chapters:
        existing_outline.append(f"第{ch['chapter_num']}章 {ch['title']}：{ch['outline']}")
    existing_text = "\n".join(existing_outline)

    user_prompt = f"""【书名】{architecture.get('book_name', '')}
【简介】{architecture.get('summary', '')}
【世界观】{architecture.get('world_setting', '')}

【已有章节大纲】
{existing_text}

请基于以上已有章节，继续生成第{start_num}章到第{end_num}章的大纲，保持剧情连贯性，输出以下 JSON 格式，不要输出任何额外文字：

[
  {{
    "chapter_num": {start_num},
    "title": "章节标题，有吸引力",
    "outline": "本章大纲，100-200字，描述主要事件、冲突和转折"
  }}
]

要求：
- 延续已有章节的剧情线，不要重复已有内容
- 章节之间要有清晰的剧情推进，前后呼应
- 每章大纲要包含：本章主要事件、关键冲突、章末悬念
- 逐步升级冲突和主角实力，节奏紧凑"""

    print(f"🤖 正在扩展架构: 追加第{start_num}~{end_num}章...")

    role = _load_prompt_file("roles", "novel")
    system_prompt = role

    # 根据追加章节数动态计算 max_tokens
    max_tokens = min(max(8192, add_count * 150 + 2000), 65536)

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.8,
        max_tokens=max_tokens,
    )

    raw = response.choices[0].message.content.strip()

    # 解析 JSON
    json_str = raw
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0].strip()
    elif "```" in json_str:
        json_str = json_str.split("```")[1].split("```")[0].strip()

    try:
        new_chapters = json.loads(json_str)
    except json.JSONDecodeError:
        print("⚠️ JSON 解析失败，尝试自动修复...")
        json_str = fix_json(json_str)
        new_chapters = json.loads(json_str)

    # 合并到现有架构
    architecture["chapters"].extend(new_chapters)

    print(f"✅ 架构扩展完成: 现共 {len(architecture['chapters'])} 章")
    for ch in new_chapters:
        print(f"   第{ch['chapter_num']}章: {ch['title']}")

    # 保存
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        arch_path = os.path.join(output_dir, "architecture.json")
        with open(arch_path, "w", encoding="utf-8") as f:
            json.dump(architecture, f, ensure_ascii=False, indent=2)
        print(f"   ✅ 已保存到: {arch_path}")

    return architecture


# ==================== Phase 2: 生成章节内容 ====================

async def generate_chapter(
    architecture: dict,
    chapter_num: int,
    previous_summary: str = "",
    output_dir: str = None,
) -> dict:
    """
    生成单个章节内容

    Args:
        architecture: 小说架构字典
        chapter_num: 章节编号（从1开始）
        previous_summary: 前一章的内容摘要，用于保持连贯性
        output_dir: 输出目录，为空则不保存文件

    Returns:
        章节 JSON 字典
    """
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)

    role = _load_prompt_file("roles", "novel")
    instruction = _load_prompt_file("instructions", "novel_chapter")
    instruction = instruction.format(prompt_count=chapter_num)

    system_prompt = role + "\n\n" + instruction

    # 找到当前章节的大纲
    chapter_outline = None
    for ch in architecture.get("chapters", []):
        if ch.get("chapter_num") == chapter_num:
            chapter_outline = ch
            break

    if not chapter_outline:
        raise ValueError(f"未找到第 {chapter_num} 章的大纲")

    # 构建用户提示词
    user_parts = [
        f"【书名】{architecture.get('book_name', '')}",
        f"【简介】{architecture.get('summary', '')}",
        f"【世界观】{architecture.get('world_setting', '')}",
    ]

    # 人物信息
    characters = architecture.get("characters", [])
    if characters:
        char_lines = []
        for c in characters:
            char_lines.append(f"- {c.get('name', '')}（{c.get('role', '')}）：{c.get('description', '')}")
        user_parts.append("【主要人物】\n" + "\n".join(char_lines))

    # 当前章节大纲
    user_parts.append(f"【当前章节】第{chapter_num}章 {chapter_outline.get('title', '')}")
    user_parts.append(f"【章节大纲】{chapter_outline.get('outline', '')}")

    # 前文摘要
    if previous_summary:
        user_parts.append(f"【前文摘要】{previous_summary}")
    else:
        user_parts.append("【前文摘要】这是第一章，无前文")

    user_prompt = "\n\n".join(user_parts)

    print(f"🤖 正在生成第 {chapter_num} 章...")
    print(f"   标题: {chapter_outline.get('title', '')}")

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.85,
        max_tokens=8192,
    )

    raw = response.choices[0].message.content.strip()
    print(f"   原始输出长度: {len(raw)} 字符")

    # 解析 JSON
    json_str = raw
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0].strip()
    elif "```" in json_str:
        json_str = json_str.split("```")[1].split("```")[0].strip()

    try:
        result = json.loads(json_str)
    except json.JSONDecodeError:
        print("   ⚠️ JSON 解析失败，尝试自动修复...")
        json_str = fix_json(json_str)
        result = json.loads(json_str)

    # 确保必要字段
    result.setdefault("chapter_num", chapter_num)
    result.setdefault("title", f"第{chapter_num}章 {chapter_outline.get('title', '')}")
    result.setdefault("content", "")
    result.setdefault("summary_for_next", "")

    content_len = len(result.get("content", ""))
    print(f"   ✅ 第 {chapter_num} 章生成完成 ({content_len} 字)")

    # 保存到文件
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        chapter_path = os.path.join(output_dir, f"chapter_{chapter_num}.json")
        with open(chapter_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"   ✅ 已保存到: {chapter_path}")

    return result


async def generate_chapters(
    architecture: dict,
    start_chapter: int = 1,
    count: int = None,
    output_dir: str = None,
) -> list:
    """
    批量生成多个章节（顺序执行，保持连贯性）

    Args:
        architecture: 小说架构字典
        start_chapter: 起始章节编号
        count: 生成章节数量，None 则生成架构中所有章节
        output_dir: 输出目录

    Returns:
        章节字典列表
    """
    total_chapters = len(architecture.get("chapters", []))
    if count is None:
        count = total_chapters - start_chapter + 1

    end_chapter = min(start_chapter + count - 1, total_chapters)

    print(f"\n📚 开始批量生成章节: 第{start_chapter}章 ~ 第{end_chapter}章 (共{end_chapter - start_chapter + 1}章)")

    chapters = []
    previous_summary = ""

    # 如果不是从第1章开始，尝试加载前一章的摘要
    if start_chapter > 1 and output_dir:
        prev_path = os.path.join(output_dir, f"chapter_{start_chapter - 1}.json")
        if os.path.exists(prev_path):
            with open(prev_path, "r", encoding="utf-8") as f:
                prev_chapter = json.load(f)
            previous_summary = prev_chapter.get("summary_for_next", "")
            print(f"   📎 已加载第{start_chapter - 1}章摘要，保持连贯性")

    for chapter_num in range(start_chapter, end_chapter + 1):
        chapter = await generate_chapter(
            architecture=architecture,
            chapter_num=chapter_num,
            previous_summary=previous_summary,
            output_dir=output_dir,
        )
        chapters.append(chapter)
        previous_summary = chapter.get("summary_for_next", "")

        # 章节间短暂延迟，避免 API 限流
        if chapter_num < end_chapter:
            await asyncio.sleep(1)

    print(f"\n✅ 批量生成完成: {len(chapters)} 章")
    return chapters


# ==================== 工具函数 ====================

def load_architecture(book_dir: str) -> dict:
    """从目录加载小说架构"""
    arch_path = os.path.join(book_dir, "architecture.json")
    if not os.path.exists(arch_path):
        raise FileNotFoundError(f"找不到架构文件: {arch_path}")
    with open(arch_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_chapter(book_dir: str, chapter_num: int) -> dict:
    """从目录加载指定章节"""
    chapter_path = os.path.join(book_dir, f"chapter_{chapter_num}.json")
    if not os.path.exists(chapter_path):
        raise FileNotFoundError(f"找不到章节文件: {chapter_path}")
    with open(chapter_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_chapters(book_dir: str) -> list:
    """列出目录中已生成的所有章节"""
    chapters = []
    if not os.path.exists(book_dir):
        return chapters
    for f in sorted(os.listdir(book_dir)):
        if f.startswith("chapter_") and f.endswith(".json"):
            try:
                num = int(f.replace("chapter_", "").replace(".json", ""))
                chapters.append(num)
            except ValueError:
                pass
    return chapters


# ==================== CLI 入口 ====================

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="小说内容生成工具")
    parser.add_argument("--topic", "-t", required=True, help="题材/主题")
    parser.add_argument("--genre", "-g", default="", help="小说分类 (如: 玄幻, 都市)")
    parser.add_argument("--gender", default="male", choices=["male", "female"], help="目标读者")
    parser.add_argument("--chapters", "-c", type=int, default=10, help="章节数量 (默认: 10)")
    parser.add_argument("--output", "-o", help="输出目录")
    parser.add_argument("--account", default="legacy", help="账号名称")
    parser.add_argument("--only", type=int, choices=[1, 2, 3], help="只执行某步 (1=架构, 2=章节, 3=扩展架构+生成新章节)")
    parser.add_argument("--start", type=int, default=1, help="从第N章开始生成 (仅 step 2)")
    parser.add_argument("--book-dir", help="已有小说目录 (用于继续生成章节)")
    parser.add_argument("--add", type=int, default=2, help="追加章节数量 (配合 --only 3 使用，默认2章)")

    args = parser.parse_args()

    # 确定输出目录
    if args.book_dir:
        book_dir = args.book_dir
        if not os.path.isabs(book_dir):
            book_dir = os.path.join(PROJECT_ROOT, book_dir)
    elif args.output:
        book_dir = args.output
    else:
        from account_manager import get_account_novels_dir
        novels_dir = get_account_novels_dir(args.account)
        # 用主题作为目录名（简化处理）
        dir_name = args.topic.replace(" ", "_")[:20]
        book_dir = os.path.join(novels_dir, dir_name)

    # Step 1: 生成架构
    if args.only is None or args.only == 1:
        architecture = await generate_architecture(
            topic=args.topic,
            genre=args.genre,
            gender=args.gender,
            chapter_count=args.chapters,
            output_dir=book_dir,
        )
        if args.only == 1:
            return
    else:
        # 加载已有架构
        architecture = load_architecture(book_dir)
        print(f"📖 已加载架构: {architecture.get('book_name', '')}")

    # Step 3: 扩展架构 + 生成新章节
    if args.only == 3:
        old_count = len(architecture.get("chapters", []))
        architecture = await extend_architecture(
            architecture=architecture,
            add_count=args.add,
            output_dir=book_dir,
        )
        await generate_chapters(
            architecture=architecture,
            start_chapter=old_count + 1,
            count=args.add,
            output_dir=book_dir,
        )
        return

    # Step 2: 生成章节
    if args.only is None or args.only == 2:
        await generate_chapters(
            architecture=architecture,
            start_chapter=args.start,
            count=args.chapters if args.only == 2 else None,
            output_dir=book_dir,
        )


if __name__ == "__main__":
    asyncio.run(main())
