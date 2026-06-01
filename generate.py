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
DEFAULT_PROMPT_COUNT = 9

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


def fix_json(s: str) -> str:
    """修复 AI 常见的 JSON 格式问题"""
    # 0. 预处理：移除 BOM 和不可见字符
    s = s.strip().lstrip('﻿')

    # 1. 修复单引号键名和字符串值 → 双引号
    #    处理 'key': 'value' → "key": "value"
    s = re.sub(r"(?<=[\[{,:])\s*'([^']*?)'\s*:", r' "\1":', s)  # 键
    s = re.sub(r":\s*'([^']*?)'", r': "\1"', s)                  # 值

    # 2. 去掉尾逗号: }, → }  和  ] → ]
    s = re.sub(r",\s*([\]}])", r"\1", s)

    # 3. 处理 "key": "value" 格式，修复 value 中的未转义引号
    s = re.sub(r'(:\s*")((?:[^"\\]|\\.)*?)(?="\s*[,}\]])', lambda m: m.group(0) if '\\"' not in m.group(0) else m.group(0), s)

    # 4. 修复字符串中的换行符
    s = s.replace('\r\n', '\\n').replace('\n', '\\n').replace('\r', '\\r')

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
            print("   2. 对于 --type article，尝试更技术性的主题，如: 'Agent工具调用'、'RAG检索增强'")
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
