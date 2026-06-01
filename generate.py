import asyncio
import json
import re
import sys
import os
from openai import AsyncOpenAI
from account_manager import PROJECT_ROOT

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass  # python-dotenv 未安装时忽略，依赖系统环境变量

# ==================== 配置区 ====================
API_KEY = os.environ.get("MIMO_API_KEY", "")
BASE_URL = os.environ.get("MIMO_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
MODEL = os.environ.get("MIMO_MODEL", "mimo-v2.5")

if not API_KEY:
    raise EnvironmentError(
        "未设置 MIMO_API_KEY 环境变量。\n"
        "请在 .env 文件或系统环境变量中配置: MIMO_API_KEY=your_key_here"
    )
DEFAULT_SEND_TYPE = "image"
DEFAULT_PROMPT_COUNT = 3

DEFAULT_OUTPUT_PATH = os.path.join(PROJECT_ROOT, "doubao.json")


# ==================== 提示词加载 ====================

PROMPTS_FILE = os.path.join(PROJECT_ROOT, "prompts.json")


def load_prompts_config() -> dict:
    """从 prompts.json 加载所有提示词配置"""
    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


PROMPTS_CONFIG = load_prompts_config()


def build_system_prompt(send_type: str, prompt_count: int) -> str:
    """根据内容类型构建完整的 system prompt（角色 + 指令）"""
    roles = PROMPTS_CONFIG.get("roles", {})
    instructions = PROMPTS_CONFIG.get("system_prompts", {})

    # video 复用 article 的角色
    role_key = send_type if send_type != "video" else "article"
    role = roles.get(role_key, roles.get("article", ""))
    instruction = instructions.get(send_type, instructions.get("article", ""))

    # 替换模板变量（如 {prompt_count}）
    instruction = instruction.format(prompt_count=prompt_count)

    return role + "\n\n" + instruction


def build_user_prompt(topic: str) -> str:
    """构建用户提示词"""
    template = PROMPTS_CONFIG.get("user_prompt_template", "主题：{topic}")
    return template.format(topic=topic)


def _merge_arrays(match: re.Match) -> str:
    """将模型输出的多个独立数组合并为一个数组"""
    key = match.group(1)  # e.g. "prompt"
    # 提取所有数组中的内容（group(2) 是第一个数组，group(3)+ 是后续数组）
    items = []
    full = match.group(0)
    # 用正则提取所有 [...] 中的内容
    for arr_match in re.finditer(r'\[([^\]]*)\]', full):
        content = arr_match.group(1).strip()
        if content:
            items.append(content)
    merged = ", ".join(items)
    return f'{key}: [{merged}]'


def _merge_duplicate_keys(s: str) -> str:
    """合并重复的 JSON 键（如多个 "prompt": "..." 合并为一个数组）"""
    # 匹配 "key": "value" 或 "key": [...] 形式的重复键
    pattern = r'"([\w]+)"\s*:\s*(?:"((?:[^"\\]|\\.)*?)"|\[([^\]]*)\])'
    matches = list(re.finditer(pattern, s))
    if not matches:
        return s

    # 找出重复的键
    key_positions = {}  # key -> list of (start, end, value)
    for m in matches:
        key = m.group(1)
        value = m.group(2) if m.group(2) is not None else m.group(3)
        if key not in key_positions:
            key_positions[key] = []
        key_positions[key].append((m.start(), m.end(), value))

    # 只处理重复的键
    for key, positions in key_positions.items():
        if len(positions) <= 1:
            continue

        # 收集所有值
        values = [p[2] for p in positions]
        # 构建合并后的数组
        merged_items = ", ".join(f'"{v}"' for v in values if v)
        merged = f'"{key}": [{merged_items}]'

        # 从后往前替换，避免位置偏移
        # 先替换第一个位置为合并结果
        first_start, first_end, _ = positions[0]
        s = s[:first_start] + merged + s[first_end:]
        # 删除后续重复项（从后往前）
        # 重新计算位置偏移
        offset = len(merged) - (positions[0][1] - positions[0][0])
        for start, end, _ in positions[1:]:
            adj_start = start + offset
            adj_end = end + offset
            # 删除该键值对及其前面的逗号/换行
            delete_start = adj_start
            # 向前找到逗号或空白
            while delete_start > 0 and s[delete_start - 1] in ' ,\n\r\t':
                delete_start -= 1
            if delete_start > 0 and s[delete_start - 1] == ',':
                delete_start -= 1
            s = s[:delete_start] + s[adj_end:]
            offset -= (adj_end - delete_start)

    return s


def _escape_newlines_in_strings(s: str) -> str:
    """只转义 JSON 字符串值内部的换行符，不影响 JSON 结构换行"""
    def _replace_in_match(m: re.Match) -> str:
        return m.group(0).replace('\n', '\\n').replace('\r', '\\r')
    return re.sub(r'"((?:[^"\\]|\\.)*?)"', _replace_in_match, s)


def fix_json(s: str) -> str:
    """修复 AI 常见的 JSON 格式问题"""
    # 0. 预处理：移除 BOM 和不可见字符
    s = s.strip().lstrip('﻿')

    # 0.0 修复重复键（如多个 "prompt": "..."）→ 合并为一个数组
    s = _merge_duplicate_keys(s)

    # 0.1 修复模型输出多个独立数组的问题：
    #   "prompt": ["a"],
    #   ["b"],
    #   ["c"]
    # → "prompt": ["a", "b", "c"]
    s = re.sub(
        r'("[\w]+")\s*:\s*\[([^\]]*)\],\s*\[([^\]]*)\](?:\s*,\s*\[([^\]]*)\])*',
        lambda m: _merge_arrays(m),
        s
    )

    # 1. 修复单引号键名和字符串值 → 双引号
    #    处理 'key': 'value' → "key": "value"
    s = re.sub(r"(?<=[\[{,:])\s*'([^']*?)'\s*:", r' "\1":', s)  # 键
    s = re.sub(r":\s*'([^']*?)'", r': "\1"', s)                  # 值

    # 2. 去掉尾逗号: }, → }  和  ] → ]
    s = re.sub(r",\s*([\]}])", r"\1", s)

    # 2.1 修复括号不匹配：JSON 对象以 { 开头但以 ] 结尾 → 替换为 }
    stripped = s.rstrip()
    if stripped.endswith(']') and not stripped.endswith(']]'):
        open_braces = stripped.count('{')
        close_braces = stripped.count('}')
        open_brackets = stripped.count('[')
        close_brackets = stripped.count(']')
        # 如果 { 比 } 多，且 ] 比 [ 多，说明 ] 误用了
        if open_braces > close_braces and close_brackets > open_brackets:
            s = stripped[:-1] + '}'

    # 3. 处理 "key": "value" 格式，修复 value 中的未转义引号
    s = re.sub(r'(:\s*")((?:[^"\\]|\\.)*?)(?="\s*[,}\]])', lambda m: m.group(0) if '\\"' not in m.group(0) else m.group(0), s)

    # 4. 修复字符串值内部的换行符（不影响 JSON 结构换行）
    s = _escape_newlines_in_strings(s)

    # 5. 修复截断/未闭合的字符串：如果最后一个字符串值缺少结尾引号，补上并闭合 JSON
    #    匹配 "...prompt": ["... 这种最后一段未闭合的情况
    s = re.sub(r'(:\s*")([^"]*?)$', r'\1\2"}', s)

    # 6. 如果数组未闭合：最后一个元素是完整字符串但缺少 ]}]
    if s.rstrip().endswith('"'):
        # 检查是否缺少闭合的 ]}
        brace_count = s.count('{') - s.count('}')
        bracket_count = s.count('[') - s.count(']')
        s = s.rstrip() + ']' * bracket_count + '}' * brace_count

    # 7. 修复数字格式问题（如：1.2.3 → 1.23）
    s = re.sub(r':\s*(\d+)\.(\d+)\.', r': \1.\2', s)

    # 8. 修复布尔值和 null
    s = re.sub(r':\s*True\b', r': true', s)
    s = re.sub(r':\s*False\b', r': false', s)
    s = re.sub(r':\s*None\b', r': null', s)

    return s


def clean_prompt_for_doubao(prompt: str) -> str:
    """
    清理提示词，使其更适合豆包理解
    1. 移除模糊词汇，替换为具体描述
    2. 简化复杂句式
    3. 确保格式规范
    """
    # 模糊词汇替换为具体描述
    replacements = {
        # 抽象概念 → 具体描述
        "氛围感": "自然",
        "高级感": "优雅",
        "故事感": "温柔",
        "电影感": "专业摄影",
        "松弛感": "轻松自然",

        # 服装相关
        "比基尼": "泳装",
        "泳衣": "夏日服装",
        "露背": "时尚设计",
        "透视": "轻薄",
        "紧身": "合身",

        # 敏感词替换
        "性感": "优雅",
        "魅惑": "迷人",
        "诱惑": "吸引",
        "身材曲线": "身姿",
        "丰满": "匀称",
        "纤细": "修长",
        "胸部": "",
        "胸": "",

        # 简化描述
        "第一人称主观视角": "",
        "电影感旅拍摄影": "专业摄影",
    }

    cleaned = prompt
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)

    # 移除多余的逗号和空格
    cleaned = re.sub(r'，\s*，', '，', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.strip('，。 ')

    # 如果太长（超过450字），适当精简
    if len(cleaned) > 450:
        # 按逗号分割，保留前6个和最后3个描述
        parts = cleaned.split('，')
        if len(parts) > 9:
            cleaned = '，'.join(parts[:6]) + '，' + '，'.join(parts[-3:])

    return cleaned


def validate_prompts(prompts: list) -> list:
    """
    验证并清理提示词列表
    返回清理后的提示词列表
    """
    cleaned_prompts = []
    for i, prompt in enumerate(prompts):
        if not prompt or len(prompt.strip()) < 50:
            print(f"⚠️ 提示词 {i+1} 过短或为空，跳过")
            continue

        cleaned = clean_prompt_for_doubao(prompt)
        if len(cleaned) < 50:
            print(f"⚠️ 提示词 {i+1} 清理后过短，跳过")
            continue

        cleaned_prompts.append(cleaned)

    return cleaned_prompts


async def generate_content(topic: str, send_type: str, prompt_count: int, output_path: str = None) -> dict:
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)

    system_prompt = build_system_prompt(send_type, prompt_count)
    user_prompt = build_user_prompt(topic)

    print(f"🤖 正在调用 {MODEL} 生成内容...")
    print(f"   类型: {send_type} | 主题: {topic}")

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.8,
        max_tokens=8192,
    )

    raw = response.choices[0].message.content.strip()
    print(f"\n📝 原始输出:\n{raw}\n")

    # 检查是否收到 API 拒绝信息
    rejection_keywords = [
        "request was rejected",
        "high risk",
        "rejected",
        "not allowed",
        "violate",
        "inappropriate",
    ]
    raw_lower = raw.lower()
    for keyword in rejection_keywords:
        if keyword.lower() in raw_lower:
            print(f"\n❌ API 返回拒绝信息: {raw}")
            print("\n💡 建议:")
            print("   1. 更换主题，避免敏感内容")
            print("   2. 对于 --type article，尝试更换主题避免敏感内容")
            print("   3. 对于 --type image，主题可能触发了图片安全过滤")
            raise ValueError(f"内容被安全机制拒绝: {raw}")

    # 解析 JSON（处理 ```json ``` 包裹）
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
    result["sendType"] = send_type
    result.setdefault("cover_image", "")
    result.setdefault("prompt", [])

    # 如果 prompt 是字符串而非数组，包装为数组
    if isinstance(result.get("prompt"), str):
        result["prompt"] = [result["prompt"]]

    # content 长度限制：超过 900 字截断到最近的句号/段落
    if send_type != "xiaohongshu" and len(result.get("content", "")) > 900:
        content = result["content"][:900]
        # 尝试在句号处截断
        last_period = max(content.rfind("。"), content.rfind("！"), content.rfind("？"), content.rfind("\n"))
        if last_period > 600:  # 至少保留 600 字
            content = content[:last_period + 1]
        result["content"] = content
    if send_type == "xiaohongshu":
        result.setdefault("tags", [])

    # 清理图片提示词（仅对 image 类型）
    if send_type == "image" and result.get("prompt"):
        print("🧹 清理提示词，优化豆包兼容性...")
        original_count = len(result["prompt"])
        result["prompt"] = validate_prompts(result["prompt"])
        cleaned_count = len(result["prompt"])
        if original_count != cleaned_count:
            print(f"   提示词数量: {original_count} → {cleaned_count}")

    # 如果指定了输出路径，自动保存
    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 已保存到: {output_path}")

    return result


async def main():
    topic = '美女'
    send_type = DEFAULT_SEND_TYPE
    prompt_count = DEFAULT_PROMPT_COUNT
    output_path = None
    account_name = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--type" and i + 1 < len(args):
            send_type = args[i + 1]
            i += 2
        elif args[i] == "--count" and i + 1 < len(args):
            prompt_count = int(args[i + 1])
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output_path = args[i + 1]
            i += 2
        elif args[i] == "--account" and i + 1 < len(args):
            account_name = args[i + 1]
            i += 2
        elif args[i] in ("-h", "--help"):
            print("用法: python generate.py [主题] [--type article|image|swimwear] [--count N] [--output PATH] [--account NAME]")
            sys.exit(0)
        else:
            topic = (topic + " " + args[i]) if topic else args[i]
            i += 1

    if not topic:
        topic = input("💡 请输入主题: ").strip()

    # 如果指定了账号但没有指定输出路径，使用账号专属路径
    if account_name and not output_path:
        from account_manager import get_account_config_path
        output_path = get_account_config_path(account_name)
    elif not output_path:
        output_path = DEFAULT_OUTPUT_PATH

    result = await generate_content(topic, send_type, prompt_count, output_path)

    print("\n" + "=" * 50)
    print(f"✅ 标题: {result.get('title', '')}")
    print(f"✅ 副标题: {result.get('subtitle', '')}")
    print(f"✅ 正文: {len(result.get('content', ''))} 字")
    if result.get("prompt"):
        print(f"✅ 图片提示词: {len(result['prompt'])} 条")
        for j, p in enumerate(result["prompt"], 1):
            print(f"   {j}. {p[:60]}...")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
