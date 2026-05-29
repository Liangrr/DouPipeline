import asyncio
import os
from browser_use import Agent
from browser_use.llm.openai.chat import ChatOpenAI

# ==================== 配置区 ====================
os.environ["OPENAI_API_KEY"] = "tp-c1g7nehvjiv148ml2rsiv09eanuee3culvm2nkudmr4it3fc"
BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"

# 在这里填入你的本地 md 文件路径
MD_FILE_PATH = "/Users/asuria/Desktop/ai_shell_content/每日热搜文案-2026-05-29.md"


def read_md_file(file_path: str) -> dict:
    """读取 md 文件，提取标题和正文内容"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到文件: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 提取标题：取第一个 # 开头的行，去掉 # 符号
    title = ""
    body_lines = content.split("\n")
    for i, line in enumerate(body_lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            title = stripped.lstrip("# ").strip()
            # 标题行之后的内容作为正文
            body_lines = body_lines[i + 1 :]
            break

    # 如果没有找到 # 标题，取第一行非空内容作为标题
    if not title:
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped:
                title = stripped[:30]  # 截取前30个字符
                break

    body = "\n".join(body_lines).strip()
    # 小红书标题最长20个字，截取一下
    if len(title) > 20:
        title = title[:20]

    return {"title": title, "content": body}


async def main():
    # 1. 读取本地 md 文件
    print(f"📖 正在读取文件: {MD_FILE_PATH}")
    article = read_md_file(MD_FILE_PATH)
    print(f"✅ 标题: {article['title']}")
    print(f"✅ 内容长度: {len(article['content'])} 字符")

    # 2. 初始化大模型
    llm = ChatOpenAI(model="mimo-v2.5", base_url=BASE_URL)

    # 3. 构建任务描述（把标题和内容直接塞给 agent）
    task = f"""
请严格按照以下步骤操作小红书创作者平台：

第1步：打开浏览器，访问 https://creator.xiaohongshu.com/new/home
第2步：等页面加载完成后，在页面上找到"发布笔记"的区域或菜单，点击进入
第3步：找到"写长文"按钮，点击它
第4步：如果看到"新的创作"或类似按钮，点击它开始新的长文创作

第5步：在标题输入框中填入以下标题文字：
{article['title']}

第6步：在正文/内容编辑区域中，填入以下文章内容：
{article['content']}

第7步：找到"一键排版"按钮，点击它进行排版
第8步：排版完成后，找到"下一步"按钮，点击它
第9步：最后找到"发布"按钮，点击它完成发布

注意事项：
- 每一步都要等页面加载完成后再操作
- 如果遇到弹窗或确认框，点击确认/确定
- 如果某一步操作失败，尝试重试一次
- 登录可能需要你手动扫码确认
- 如果遇到任何验证环节，请暂停等待用户操作
"""

    # 4. 创建 Agent 并执行
    agent = Agent(
        task=task,
        llm=llm,
        save_conversation_path="conversation_log",  # 保存对话日志方便调试
    )

    print("\n🚀 开始自动化发布流程...")
    print("⚠️  如果需要登录或验证，请在浏览器中手动操作\n")
    result = await agent.run()
    print("\n📋 执行结果:")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
