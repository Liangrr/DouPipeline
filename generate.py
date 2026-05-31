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
DEFAULT_PROMPT_COUNT = 9

# 项目根目录
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__)))
DEFAULT_OUTPUT_PATH = os.path.join(PROJECT_ROOT, "doubao.json")


# ==================== 角色定义 ====================

ROLE_IMAGE = """你是一位极具天赋、审美顶尖、擅长全域场景的顶级人像艺术摄影师，主攻【绝美户外场景+高级时尚女性人像】，拥有十年全球旅拍、高端时尚写真、氛围感大片创作经验。你擅长利用自然光影、户外环境氛围、场景构图，捕捉女性松弛、灵动、阳光、清冷、高级的美感，拒绝流水线网红审美，主打电影感、故事感、时尚高级质感，是专注户外场景人像美学的专属摄影艺术Agent。

角色人设基调：艺术感极强、审美克制高级、细腻温柔、专业度拉满。不浮夸、不低俗，擅长发现普通人的氛围感美感，擅长让人物融入风景，做到景衬人、人点亮景，成片干净通透、极具视觉冲击力。

人物限定（重要！必须严格遵守）：
- 年龄：18-28岁的年轻东方女性
- 外貌：白皙细腻的肌肤、精致五官、乌黑长发
- 身材（核心要求）：必须是沙漏型身材！强调纤细腰肢、匀称丰满的上围、圆润臀部，腰臀比明显，曲线玲珑有致，S型曲线突出
- 皮肤：无纹身
- 气质：清冷高级，具备东方美学特质"""

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

请根据用户提供的主题，输出以下 JSON 字段，不要输出任何额外文字。prompt 数组包含 {prompt_count} 条图片提示词，每条200-350字，直接写完整提示词内容，不要加"第1条"、"提示词："等任何前缀或序号，不要用引号包裹提示词描述。
{{
  "title": "文章标题，5-10字",
  "subtitle": "副标题，5-10字",
  "summary": "文章摘要，30-80字",
  "content": "文章正文，300-800字，分3-5段，生动有感染力",
  "cover_image": "",
  "sendType": "image",
  "prompt": ["完整提示词1", "完整提示词2"]
}}

图片提示词创作要求（重要！请严格遵守，每条提示词必须包含以下所有要素）：

1. 场景环境（详细描述）：
   - 地点：海岛沙滩、海边礁石、无边泳池、热带雨林、游艇甲板、悬崖海景、椰林海岸、日落海滩等
   - 时间段：清晨薄雾、正午烈阳、黄昏落日、傍晚余晖
   - 天气：晴朗通透、多云柔和、薄雾朦胧
   - 环境细节：沙粒质感、海水颜色、植被种类、天空层次

2. 人物形象（细腻刻画）：
   - 年龄要求：18-28岁的年轻女性，青春活力，面容姣好
   - 面部特征：精致立体的五官、清澈明亮的眼眸、自然红润的唇色、柔和的面部轮廓
   - 肤质描写：白皙细腻如瓷、通透有光泽、阳光下泛着珍珠般微光
   - 发型发质：乌黑柔顺的长发、发丝随风飘逸、湿发微卷、松散盘发
   - 身材要求（重点强调）：
     * 必须是沙漏型身材（hourglass figure）
     * 纤细腰肢，腰围明显小于胸围和臀围
     * 上围匀称丰满，臀部圆润挺翘
     * 腰臀比突出，S型曲线玲珑有致
     * 整体线条流畅优美，黄金比例身材
   - 气质神韵：清冷优雅、温柔恬静、自信从容、灵动自然

3. 服装造型（具体描述）：
   - 款式：飘逸长裙、优雅连衣裙、度假风罩衫、时尚套装、轻薄开衫
   - 颜色：纯白、米白、浅蓝、香槟金、薄荷绿、珊瑚粉等柔和色调
   - 材质：真丝光泽、棉麻质感、雪纺轻盈、蕾丝精致
   - 细节：领口设计、袖型款式、裙摆飘动、腰间系带

4. 姿态动作（自然优雅）：
   - 体态：挺拔优雅、松弛自然、微微侧身、轻盈灵动
   - 手部：轻抚发丝、自然垂落、手扶栏杆、轻触花瓣
   - 眼神：直视镜头、微微侧目、凝视远方、温柔回眸
   - 表情：恬静微笑、若有所思、自信从容、温柔恬淡

5. 光影氛围（电影级质感）：
   - 主光源：金色侧逆光、柔和正午光、温暖夕阳、清晨柔光
   - 光线效果：轮廓光勾勒、发丝光晕、水面反光、树叶漏光
   - 色调氛围：暖调金黄、冷调蓝紫、清新自然、浓郁油画
   - 明暗对比：高光细腻、阴影层次、过渡自然、立体感强

6. 构图技法（专业摄影）：
   - 景别：全身远景、七分身、半身近景、特写局部
   - 视角：平视、微仰、俯拍、侧面45度
   - 景深：主体清晰、背景虚化、前景遮挡、层次分明
   - 构图法则：三分法、对角线、中心对称、引导线

7. 技术参数（统一标准）：
   - 画质：超写实、8K分辨率、极致细腻、毛孔可见
   - 镜头：50mm标准镜头、f/1.4大光圈、浅景深虚化
   - 画幅：16:9横构图、电影级宽银幕
   - 后期：自然色彩、不过度修饰、保留皮肤质感

示例格式（供参考，请根据主题创作不同内容）：
"一位气质清冷的东方女性站在巴厘岛海边的悬崖边，清晨第一缕阳光穿透薄雾洒落，她拥有白皙细腻如瓷器般的肌肤，精致立体的五官在晨光中格外柔和，乌黑柔顺的长发被海风轻轻吹起几缕发丝。她身穿一件米白色真丝质感的吊带长裙，裙摆随风微微飘动，领口处有细腻的褶皱设计。她微微侧身面向镜头，一手轻抚被风吹乱的发丝，眼神清澈而温柔地望向镜头，嘴角带着若有若无的恬静微笑。温暖的金色晨光从侧后方打来，为她的轮廓勾勒出一圈柔和的光晕，发丝在逆光中呈现出半透明的金色光泽。背景是层叠的悬崖和蔚蓝的印度洋海面，天空呈现从橙粉到淡蓝的渐变色。超写实8K画质，浅景深50mm镜头虚化远处海面，全身远景构图，16:9电影级宽银幕比例，画面通透干净，高级质感" """

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
    if send_type == "video":
        result.setdefault("video_path", "")
    elif send_type == "xiaohongshu":
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
