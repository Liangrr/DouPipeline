import asyncio
import json
import re
import sys
from openai import AsyncOpenAI

# ==================== 配置区 ====================
API_KEY = "tp-c1g7nehvjiv148ml2rsiv09eanuee3culvm2nkudmr4it3fc"
BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MODEL = "mimo-v2.5"
OUTPUT_PATH = "/Users/asuria/Desktop/browser/doubao.json"
DEFAULT_SEND_TYPE = "image"
DEFAULT_PROMPT_COUNT = 3


# ==================== 角色定义 ====================

ROLE_IMAGE = """你是一位极具天赋、审美顶尖、擅长全域场景的顶级人像艺术摄影师，专精泳装/比基尼主题人像创作，主攻【绝美户外场景+高级泳装女性人像】，拥有十年全球海岛旅拍、高端泳装写真、时尚氛围感大片创作经验。你擅长利用自然光影、户外环境氛围、场景构图，捕捉女性松弛、灵动、阳光、清冷、高级的泳装美感，拒绝流水线网红审美，主打电影感、故事感、时尚高级质感，是专注户外场景泳装人像美学的专属摄影艺术Agent。

角色人设基调：艺术感极强、审美克制高级、细腻温柔、专业度拉满。不浮夸、不低俗，擅长发现普通人的氛围感美感，擅长让人物融入风景，做到景衬人、人点亮景，成片干净通透、极具视觉冲击力。

人物限定：模特必须是肤白貌美的东方女性，拥有白皙细腻的肌肤、精致五官、乌黑长发，身材匀称修长、黄金比例、胸部D-E罩杯，皮肤无纹身，气质清冷高级，具备东方美学特质。"""

ROLE_ARTICLE = """你是一位资深自媒体内容创作者，擅长写爆款情感类文章。风格真实、细腻、有共鸣感，语言口语化、接地气，适合在抖音/头条平台发布。"""

ROLE_VIDEO = ROLE_ARTICLE


def build_system_prompt(send_type: str, prompt_count: int) -> str:
    if send_type == "article":
        return ROLE_ARTICLE + """

请输出以下 JSON 字段，不要输出任何额外文字：
{
  "title": "文章标题，5-10字",
  "subtitle": "副标题，5-10字",
  "summary": "文章摘要，30-80字",
  "content": "文章正文，300-800字，分3-5段，生动有感染力",
  "cover_image": "",
  "sendType": "article",
  "prompt": []
}"""

    elif send_type == "image":
        return ROLE_IMAGE + f"""

请根据用户提供的主题，输出以下 JSON 字段，不要输出任何额外文字。prompt 数组包含 {prompt_count} 条图片提示词，每条100-200字，直接写完整提示词内容，不要加"第1条"、"提示词："等任何前缀或序号，不要用引号包裹提示词描述。
{{
  "title": "文章标题，5-10字",
  "subtitle": "副标题，5-10字",
  "summary": "文章摘要，30-80字",
  "content": "文章正文，300-800字，分3-5段，生动有感染力",
  "cover_image": "",
  "sendType": "image",
  "prompt": ["第一人称主观视角...完整提示词1", "第一人称主观视角...完整提示词2"]
}}

图片提示词创作要求：
- 第一人称主观视角、电影感旅拍摄影
- 每条提示词描述一个不同的户外场景：海岛沙滩、海边礁石、无边泳池、热带雨林、游艇甲板、悬崖海景、椰林海岸、日落海滩等
- 泳装/比基尼主题，比基尼越少越好，露出身体部位超过70%以上，注重服装材质、款式、配饰的细节描写
- 模特面部必须看向镜头，眼神自然有神
- 模特限定：肤白貌美的东方女性，白皙细腻肌肤，精致五官，乌黑长发，清冷高级气质
- 女性人像要有故事感和高级感，捕捉松弛自然的瞬间，拒绝低俗
- 光影是核心：金色夕阳、清澈海水反光、热带阳光、晨间柔光等
- 技术参数统一：超写实、8K、浅景深、50mm镜头、电影级构图、16:9横构图"""

    elif send_type == "video":
        return ROLE_VIDEO + """

请输出以下 JSON 字段，不要输出任何额外文字：
{
  "title": "视频标题，5-10字",
  "subtitle": "副标题，5-10字",
  "summary": "视频简介，30-80字",
  "content": "视频描述/文案，100-300字",
  "cover_image": "",
  "sendType": "video",
  "prompt": [],
  "video_path": ""
}"""

    return ROLE_ARTICLE


def build_user_prompt(topic: str) -> str:
    return f"主题：{topic}"


def fix_json(s: str) -> str:
    """修复 AI 常见的 JSON 格式问题"""
    # 1. 修复单引号键名和字符串值 → 双引号
    #    处理 'key': 'value' → "key": "value"
    s = re.sub(r"(?<=[\[{,:])\s*'([^']*?)'\s*:", r' "\1":', s)  # 键
    s = re.sub(r":\s*'([^']*?)'", r': "\1"', s)                  # 值

    # 2. 去掉尾逗号: }, → }  和  ] → ]
    s = re.sub(r",\s*([\]}])", r"\1", s)

    # 3. 修复截断/未闭合的字符串：如果最后一个字符串值缺少结尾引号，补上并闭合 JSON
    #    匹配 "...prompt": ["... 这种最后一段未闭合的情况
    s = re.sub(r'(:\s*")([^"]*?)$', r'\1\2"}', s)
    #    如果数组未闭合：最后一个元素是完整字符串但缺少 ]}]
    if s.rstrip().endswith('"'):
        # 检查是否缺少闭合的 ]}
        brace_count = s.count('{') - s.count('}')
        bracket_count = s.count('[') - s.count(']')
        s = s.rstrip() + ']' * bracket_count + '}' * brace_count

    return s


async def generate_content(topic: str, send_type: str, prompt_count: int) -> dict:
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
    if send_type == "video":
        result.setdefault("video_path", "")

    return result


async def main():
    topic = '美女'
    send_type = DEFAULT_SEND_TYPE
    prompt_count = DEFAULT_PROMPT_COUNT
    output_path = OUTPUT_PATH

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
        elif args[i] in ("-h", "--help"):
            print("用法: python generate.py [主题] [--type article|image|video] [--count N] [--output PATH]")
            sys.exit(0)
        else:
            topic = (topic + " " + args[i]) if topic else args[i]
            i += 1

    if not topic:
        topic = input("💡 请输入主题: ").strip()

    result = await generate_content(topic, send_type, prompt_count)

    print("\n" + "=" * 50)
    print(f"✅ 标题: {result.get('title', '')}")
    print(f"✅ 副标题: {result.get('subtitle', '')}")
    print(f"✅ 正文: {len(result.get('content', ''))} 字")
    if result.get("prompt"):
        print(f"✅ 图片提示词: {len(result['prompt'])} 条")
        for j, p in enumerate(result["prompt"], 1):
            print(f"   {j}. {p[:60]}...")
    print("=" * 50)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已保存到: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
