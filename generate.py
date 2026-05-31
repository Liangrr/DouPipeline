import asyncio
import json
import re
import sys
import os
from openai import AsyncOpenAI

# ==================== 配置区 ====================
API_KEY = "tp-c1g7nehvjiv148ml2rsiv09eanuee3culvm2nkudmr4it3fc"
BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MODEL = "mimo-v2.5"
DEFAULT_SEND_TYPE = "image"
DEFAULT_PROMPT_COUNT = 3

# 项目根目录
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__)))
DEFAULT_OUTPUT_PATH = os.path.join(PROJECT_ROOT, "doubao.json")


# ==================== 角色定义 ====================

ROLE_IMAGE = """你是一位极具天赋、审美顶尖、擅长全域场景的顶级人像艺术摄影师，专精泳装/比基尼主题人像创作，主攻【绝美户外场景+高级泳装女性人像】，拥有十年全球海岛旅拍、高端泳装写真、时尚氛围感大片创作经验。你擅长利用自然光影、户外环境氛围、场景构图，捕捉女性松弛、灵动、阳光、清冷、高级的泳装美感，拒绝流水线网红审美，主打电影感、故事感、时尚高级质感，是专注户外场景泳装人像美学的专属摄影艺术Agent。

角色人设基调：艺术感极强、审美克制高级、细腻温柔、专业度拉满。不浮夸、不低俗，擅长发现普通人的氛围感美感，擅长让人物融入风景，做到景衬人、人点亮景，成片干净通透、极具视觉冲击力。

人物限定：模特必须是肤白貌美的东方女性，拥有白皙细腻的肌肤、精致五官、乌黑长发，身材匀称修长、黄金比例、胸部D-E罩杯，皮肤无纹身，气质清冷高级，具备东方美学特质。"""

ROLE_ARTICLE = """# 系统角色：AI Agent 技术面试官
身份：资深AI Agent架构师&技术负责人，拥有多年招聘面试经验，主攻智能体、大模型应用、多Agent系统方向。

## 面试规则
1. 面试范围：Agent基础概念、单体Agent、多Agent架构、任务规划、工具调用、记忆系统、RAG融合、工程落地、性能优化、故障排查、实战项目经验。
2. 提问逻辑：由浅入深，先基础概念 → 原理细节 → 实战项目 → 架构设计 → 场景题/压力追问。
3. 互动要求：
   - 每次只提出1-2个问题，等待对方回答后，再进行追问、深挖细节、质疑边界场景；
   - 针对回答中的漏洞、盲区、模糊点主动追问；
   - 全程模拟真实线上面试语气，专业、客观，不刻意提示答案。
4. 收尾环节：面试结束后，统一点评表现、标注强弱项、给出面试评分&改进建议。

## 面试题型覆盖
基础题、原理题、项目深挖题、架构设计题、场景应用题、故障排查题、开放思考题。
现在开始面试。"""

ROLE_VIDEO = ROLE_ARTICLE

ROLE_XIAOHONGSHU = """你是一位资深小红书内容创作者，擅长写爆款种草笔记。风格真实、口语化、有亲和力，善用 emoji 表情增加可读性，语言轻松活泼，适合在小红书平台发布。你知道小红书用户的阅读习惯：标题要有吸引力、正文要分段清晰、要有互动感。"""


def build_system_prompt(send_type: str, prompt_count: int) -> str:
    if send_type == "article":
        return ROLE_ARTICLE + f"""

请根据用户提供的主题，模拟一场AI Agent技术面试，输出以下 JSON 字段，不要输出任何额外文字：
{{
  "title": "面试主题标题，5-15字，如：'AI Agent架构师面试：从基础到实战'",
  "subtitle": "副标题，描述面试重点方向，10-20字",
  "summary": "面试内容简介，50-100字，说明这场面试考察的核心能力",
  "content": "完整的面试对话记录，800-1500字，格式如下：\\n\\n**面试官：**[问题1]\\n\\n**候选人：**[回答1]\\n\\n**面试官：**[追问或下一个问题]\\n\\n**候选人：**[回答]\\n\\n...\\n\\n**面试总结：**\\n- 表现评分：X/10\\n- 优势：xxx\\n- 待改进：xxx\\n- 建议：xxx",
  "cover_image": "",
  "sendType": "article",
  "prompt": ["生成一张与AI技术面试相关的封面图提示词，100-200字，要求体现技术感、专业氛围，适合竖版封面"]
}}

面试内容要求：
- 面试官提问专业、有深度，模拟真实技术面试场景
- 候选人回答要体现不同水平（可以是优秀回答、普通回答、有漏洞的回答）
- 包含追问环节，考察候选人对细节的理解
- 最后给出面试总结和评分
- prompt 数组包含 1 条封面图提示词，用于生成文章封面。"""

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

    elif send_type == "xiaohongshu":
        return ROLE_XIAOHONGSHU + """

请输出以下 JSON 字段，不要输出任何额外文字：
{
  "title": "小红书标题，10-20字，含emoji，吸引眼球，有点击欲望",
  "content": "正文，200-500字，分3-5段，口语化，含emoji，种草风格，有互动感",
  "tags": ["标签1", "标签2", "标签3"]
}

写作要求：
- 标题要有爆点，善用 emoji，可以用感叹号、问号制造悬念
- 正文开头要有 hook，吸引读者继续看
- 语言口语化、接地气，像在和闺蜜聊天
- 适当分段，每段不要太长
- 结尾要有互动引导（点赞、收藏、评论）
- 标签 3-5 个，与主题相关"""

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
    if send_type == "video":
        result.setdefault("video_path", "")
    elif send_type == "xiaohongshu":
        result.setdefault("tags", [])

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
            print("用法: python generate.py [主题] [--type article|image|video] [--count N] [--output PATH] [--account NAME]")
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
