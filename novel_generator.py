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


# ==================== Phase 1.6: 重新规划大纲（扩展故事架构）====================

async def redesign_architecture(
    architecture: dict,
    total_chapters: int = 100,
    output_dir: str = None,
) -> dict:
    """
    重新规划小说架构，扩展故事线以支持更多章节

    适用场景：原有大纲已写完（如10章就完结），需要扩展到更长篇幅。
    保留已有章节大纲不变，重新规划整体故事走向，生成新的章节大纲。
    自动分批生成，支持任意章节数量。

    Args:
        architecture: 已有的小说架构字典
        total_chapters: 目标总章节数
        output_dir: 输出目录，为空则不保存文件

    Returns:
        更新后的架构字典
    """
    existing_chapters = architecture.get("chapters", [])
    current_count = len(existing_chapters)

    if total_chapters <= current_count:
        print(f"⚠️ 目标章节数({total_chapters})不大于当前章节数({current_count})，无需重新规划")
        return architecture

    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    role = _load_prompt_file("roles", "novel")

    # 每批最多生成 50 章（避免超出 token 限制）
    BATCH_SIZE = 50
    batch_start = current_count + 1
    is_first_batch = True

    print(f"🤖 正在重新规划架构: {current_count}章 → {total_chapters}章 (每批{BATCH_SIZE}章)...")

    while batch_start <= total_chapters:
        batch_end = min(batch_start + BATCH_SIZE - 1, total_chapters)
        batch_count = batch_end - batch_start + 1

        # 构建已有章节摘要（只在第一批传完整摘要，后续批次只传最近 20 章）
        existing_chapters = architecture.get("chapters", [])
        if is_first_batch:
            outline_text = "\n".join(
                f"第{ch['chapter_num']}章 {ch['title']}：{ch['outline']}"
                for ch in existing_chapters
            )
        else:
            recent = existing_chapters[-20:]
            outline_text = "\n".join(
                f"第{ch['chapter_num']}章 {ch['title']}：{ch['outline']}"
                for ch in recent
            )

        if is_first_batch:
            user_prompt = f"""【书名】{architecture.get('book_name', '')}
【当前简介】{architecture.get('summary', '')}
【世界观】{architecture.get('world_setting', '')}
【当前章节数】{current_count} 章
【目标总章节数】{total_chapters} 章

【已有章节大纲】
{outline_text}

=== 问题 ===
以上 {current_count} 章大纲已经把故事写完了，无法继续写下去。

=== 任务 ===
请重新规划小说故事架构，从第{batch_start}章到第{batch_end}章的大纲。

要求：
1. 保留已有 {current_count} 章大纲不变
2. 重新设计更长远的故事主线（更大的敌人、新世界、更深层的阴谋）
3. 自然衔接已有剧情，不能突兀转折
4. 每50-100章设置一个大阶段/大boss
5. 逐步升级冲突和主角实力

输出 JSON 格式：
{{
  "summary": "更新后的简介（体现长篇格局）",
  "new_chapters": [
    {{"chapter_num": {batch_start}, "title": "标题", "outline": "大纲100-200字"}}
  ]
}}"""
        else:
            user_prompt = f"""【书名】{architecture.get('book_name', '')}
【世界观】{architecture.get('world_setting', '')}

【最近章节摘要】
{outline_text}

=== 任务 ===
继续生成第{batch_start}章到第{batch_end}章的大纲（共{batch_count}章）。

要求：
1. 延续已有剧情，保持连贯
2. 每50-100章设置一个大阶段/大boss
3. 逐步升级冲突和主角实力

输出 JSON 格式：
{{
  "new_chapters": [
    {{"chapter_num": {batch_start}, "title": "标题", "outline": "大纲100-200字"}}
  ]
}}"""

        print(f"   📝 生成第{batch_start}~{batch_end}章...")

        max_tokens = min(max(8192, batch_count * 150 + 2000), 65536)

        # 重试机制：最多重试 2 次
        result = None
        for attempt in range(3):
            try:
                response = await client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": role},
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
                    result = json.loads(json_str)
                except json.JSONDecodeError:
                    print(f"   ⚠️ JSON 解析失败，尝试自动修复... (第{attempt+1}次)")
                    json_str = fix_json(json_str)
                    result = json.loads(json_str)

                break  # 成功，跳出重试循环

            except (json.JSONDecodeError, Exception) as e:
                if attempt < 2:
                    print(f"   ⚠️ 批次失败 ({e})，重试中...")
                    await asyncio.sleep(2)
                else:
                    print(f"   ❌ 批次失败，跳过第{batch_start}~{batch_end}章")
                    result = None

        if result is None:
            # 跳过这批，继续下一批
            batch_start = batch_end + 1
            continue

        # 第一批更新简介
        if is_first_batch and result.get("summary"):
            architecture["summary"] = result["summary"]

        # 追加新章节
        new_chapters = result.get("new_chapters", [])
        architecture["chapters"].extend(new_chapters)
        print(f"   ✅ 已生成 {len(new_chapters)} 章")

        # 每批保存一次（防止中途崩溃丢失进度）
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            arch_path = os.path.join(output_dir, "architecture.json")
            with open(arch_path, "w", encoding="utf-8") as f:
                json.dump(architecture, f, ensure_ascii=False, indent=2)

        is_first_batch = False
        batch_start = batch_end + 1

        # 批次间延迟
        if batch_start <= total_chapters:
            await asyncio.sleep(1)

    total_new = len(architecture["chapters"]) - current_count
    print(f"✅ 架构重新规划完成: 现共 {len(architecture['chapters'])} 章 (新增 {total_new} 章)")

    # 保存
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        arch_path = os.path.join(output_dir, "architecture.json")
        with open(arch_path, "w", encoding="utf-8") as f:
            json.dump(architecture, f, ensure_ascii=False, indent=2)
        print(f"   ✅ 已保存到: {arch_path}")

    return architecture


# ==================== Phase 1.7: 补全缺失章节大纲 ====================

async def fill_missing_outlines(
    architecture: dict,
    output_dir: str = None,
) -> dict:
    """
    检测并补全缺失的章节大纲

    适用场景：分批生成时中途崩溃，导致部分章节丢失（如1-100有，100-200丢失，200-300有）。
    自动检测缺失的章节范围，只补生成缺失部分。

    Args:
        architecture: 已有的小说架构字典
        output_dir: 输出目录，为空则不保存文件

    Returns:
        更新后的架构字典
    """
    chapters = architecture.get("chapters", [])
    if not chapters:
        print("⚠️ 没有已有章节，无法补全")
        return architecture

    # 找出已有的章节号
    existing_nums = {ch["chapter_num"] for ch in chapters}
    max_chapter = max(existing_nums)

    # 找出缺失的章节号
    missing = sorted(set(range(1, max_chapter + 1)) - existing_nums)

    if not missing:
        print(f"✅ 没有缺失章节（共 {max_chapter} 章完整）")
        return architecture

    # 按连续范围分组
    gaps = []
    start = missing[0]
    end = missing[0]
    for num in missing[1:]:
        if num == end + 1:
            end = num
        else:
            gaps.append((start, end))
            start = num
            end = num
    gaps.append((start, end))

    total_missing = len(missing)
    print(f"🔍 检测到 {total_missing} 章缺失（{len(gaps)} 个区间）:")
    for s, e in gaps:
        print(f"   第{s}~{e}章 ({e - s + 1}章)")

    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    role = _load_prompt_file("roles", "novel")

    # 构建已有章节摘要（按区间前后取上下文）
    for gap_start, gap_end in gaps:
        gap_count = gap_end - gap_start + 1
        print(f"\n🤖 补全第{gap_start}~{gap_end}章...")

        # 取缺口前后的章节作为上下文
        before = [ch for ch in chapters if ch["chapter_num"] < gap_start]
        after = [ch for ch in chapters if ch["chapter_num"] > gap_end]
        context_before = before[-10:] if len(before) > 10 else before
        context_after = after[:5] if len(after) > 5 else after

        context_text = ""
        if context_before:
            context_text += "【前文大纲】\n"
            for ch in context_before:
                context_text += f"第{ch['chapter_num']}章 {ch['title']}：{ch['outline']}\n"

        if context_after:
            context_text += "\n【后文大纲】\n"
            for ch in context_after:
                context_text += f"第{ch['chapter_num']}章 {ch['title']}：{ch['outline']}\n"

        # 分批补全（每批最多50章）
        BATCH_SIZE = 50
        batch_start = gap_start

        while batch_start <= gap_end:
            batch_end = min(batch_start + BATCH_SIZE - 1, gap_end)
            batch_count = batch_end - batch_start + 1

            user_prompt = f"""【书名】{architecture.get('book_name', '')}
【世界观】{architecture.get('world_setting', '')}

{context_text}
=== 任务 ===
补全第{batch_start}章到第{batch_end}章的大纲（共{batch_count}章）。
这些章节位于已有剧情之间，需要自然衔接前后内容。

输出 JSON 格式：
{{
  "new_chapters": [
    {{"chapter_num": {batch_start}, "title": "标题", "outline": "大纲100-200字"}}
  ]
}}"""

            print(f"   📝 补全第{batch_start}~{batch_end}章...")

            max_tokens = min(max(8192, batch_count * 150 + 2000), 65536)

            # 重试机制
            result = None
            for attempt in range(3):
                try:
                    response = await client.chat.completions.create(
                        model=MODEL,
                        messages=[
                            {"role": "system", "content": role},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.8,
                        max_tokens=max_tokens,
                    )

                    raw = response.choices[0].message.content.strip()

                    json_str = raw
                    if "```json" in json_str:
                        json_str = json_str.split("```json")[1].split("```")[0].strip()
                    elif "```" in json_str:
                        json_str = json_str.split("```")[1].split("```")[0].strip()

                    try:
                        result = json.loads(json_str)
                    except json.JSONDecodeError:
                        json_str = fix_json(json_str)
                        result = json.loads(json_str)

                    break

                except Exception as e:
                    if attempt < 2:
                        print(f"   ⚠️ 失败 ({e})，重试中...")
                        await asyncio.sleep(2)
                    else:
                        print(f"   ❌ 补全失败，跳过第{batch_start}~{batch_end}章")

            if result:
                new_chapters = result.get("new_chapters", [])
                architecture["chapters"].extend(new_chapters)
                architecture["chapters"].sort(key=lambda c: c.get("chapter_num", 0))
                print(f"   ✅ 已补全 {len(new_chapters)} 章")

                # 每批保存
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                    arch_path = os.path.join(output_dir, "architecture.json")
                    with open(arch_path, "w", encoding="utf-8") as f:
                        json.dump(architecture, f, ensure_ascii=False, indent=2)

            batch_start = batch_end + 1
            if batch_start <= gap_end:
                await asyncio.sleep(1)

    final_count = len(architecture.get("chapters", []))
    print(f"\n✅ 补全完成: 现共 {final_count} 章")

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
    parser.add_argument("--only", type=int, choices=[1, 2, 3, 4, 5], help="只执行某步 (1=架构, 2=章节, 3=扩展架构, 4=重新规划大纲, 5=补全缺失大纲)")
    parser.add_argument("--start", type=int, default=1, help="从第N章开始生成 (仅 step 2)")
    parser.add_argument("--book-dir", help="已有小说目录 (用于继续生成章节)")
    parser.add_argument("--add", type=int, default=2, help="追加章节数量 (配合 --only 3 使用，默认2章)")
    parser.add_argument("--total", type=int, default=100, help="目标总章节数 (配合 --only 4 使用，默认100)")

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

    # Step 4: 重新规划大纲（故事写完了，扩展到更长篇幅）
    if args.only == 4:
        architecture = await redesign_architecture(
            architecture=architecture,
            total_chapters=args.total,
            output_dir=book_dir,
        )
        return

    # Step 5: 补全缺失章节大纲
    if args.only == 5:
        architecture = await fill_missing_outlines(
            architecture=architecture,
            output_dir=book_dir,
        )
        return

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
