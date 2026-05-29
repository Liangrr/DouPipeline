import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright

# ==================== 配置区 ====================
MD_FILE_PATH = "/Users/asuria/Desktop/browser/everday_hot.json" 
USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_profile")


def read_json_file(file_path: str) -> dict:
    """读取 JSON 文件，提取 title 和 content"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到文件: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    title = data.get("title", "")
    content = data.get("content", "")

    if not title:
        raise ValueError("未找到 title 字段")
    if not content:
        raise ValueError("未找到 content 字段")

    if len(title) > 20:
        title = title[:20]

    return {"title": title, "content": content}


async def ensure_logged_in(context):
    """检查登录状态，未登录则等待用户手动登录"""
    page = await context.new_page()
    await page.goto("https://creator.xiaohongshu.com/new/home", wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(3000)

    content = await page.content()
    is_logged_in = any(kw in content for kw in ["创作者", "笔记管理", "数据看板", "发布笔记"])

    if is_logged_in:
        print("🎉 已登录！")
        await page.close()
        return

    # 未登录，保持浏览器打开，等待用户手动登录
    print("\n" + "=" * 50)
    print("⚠️  检测到未登录，请在上方浏览器中完成以下操作：")
    print("   1. 用手机小红书 APP 扫码登录")
    print("   2. 登录成功进入创作者中心主页后，回到这里按回车")
    print("=" * 50)
    input("\n✅ 登录完成后按回车继续 >>> ")

    # 验证登录
    await page.reload(wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(2000)
    content = await page.content()
    is_logged_in = any(kw in content for kw in ["创作者", "笔记管理", "数据看板", "发布笔记"])

    if not is_logged_in:
        await page.close()
        raise RuntimeError("❌ 登录失败，请重新运行脚本")

    print("✅ 登录成功！")
    await page.close()


async def publish_note(page, title: str, content: str):
    """执行发布笔记的完整流程"""
    # 步骤1：点击"发布笔记"
    print("📝 步骤1：进入发布页面...")
    await page.click('text=发布笔记')
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1000)

    # 步骤2：点击"写长文"（第6个 .creator-tab）
    print("📝 步骤2：点击写长文...")
    await page.locator('.header-tabs .creator-tab').nth(6).click()
    print("  ✅ 点击成功")
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1000)

    # 步骤3：如果有"新的创作"或"开始创作"按钮，点击它
    for btn_text in ["新的创作", "开始创作"]:
        try:
            btn = page.get_by_text(btn_text, exact=True)
            if await btn.is_visible(timeout=3000):
                print(f"📝 步骤3：点击'{btn_text}'...")
                await btn.click()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1000)
                break
        except Exception:
            pass

    # 步骤4：输入标题
    print(f"📝 步骤4：输入标题: {title}")
    title_input = page.locator('textarea[placeholder*="标题"]').first
    if not await title_input.is_visible(timeout=3000):
        title_input = page.locator('[contenteditable="true"]').first
    await title_input.click()
    await title_input.fill("")
    await title_input.fill(title)

    # 步骤5：输入正文
    print("📝 步骤5：输入正文...")
    editor = page.locator('[contenteditable="true"]').last
    await editor.click()
    await page.keyboard.press("Control+a")
    await page.keyboard.press("Delete")
    await page.keyboard.insert_text(content)
    await page.wait_for_timeout(500)

    # 步骤6：一键排版
    print("📝 步骤6：一键排版...")
    try:
        format_btn = page.get_by_text("一键排版")
        if await format_btn.is_visible(timeout=3000):
            await format_btn.click()
            await page.wait_for_timeout(2000)
            print("  ✅ 排版完成")
    except Exception:
        print("  ⚠️ 未找到一键排版按钮，跳过")

    # 步骤7：下一步
    print("📝 步骤7：点击下一步...")
    next_btn = page.get_by_text("下一步")
    await next_btn.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1000)

    # 步骤8：点击发布（closed shadow root 已被劫持为 open，可直接选择）
    print("📝 步骤8：点击发布...")
    submit_btn = page.get_by_text("发布", exact=True)
    await submit_btn.click()
    print("  ⏳ 等待发布完成（含图片上传）...")
    # 等待"发布成功"或页面跳转，最多等 120 秒
    try:
        await page.get_by_text("发布成功").wait_for(state="visible", timeout=120000)
        print("  ✅ 检测到「发布成功」")
    except Exception:
        # 没有明确提示，等页面跳转（URL 变化）
        current_url = page.url
        try:
            await page.wait_for_url(lambda url: url != current_url, timeout=120000)
        except Exception:
            await page.wait_for_timeout(10000)
        print("  ✅ 页面已跳转，视为发布成功")

    print("✅ 发布完成！")

async def main():
    # 1. 读取 md 文件
    print(f"📖 正在读取文件: {MD_FILE_PATH}")
    article = read_json_file(MD_FILE_PATH)
    print(f"✅ 标题: {article['title']}")
    print(f"✅ 内容长度: {len(article['content'])} 字符")

    # 2. 创建持久化浏览器目录
    Path(USER_DATA_DIR).mkdir(exist_ok=True)
    print(f"📂 浏览器数据目录: {USER_DATA_DIR}")

    # 3. 启动浏览器
    print("\n🌐 正在启动浏览器...")
    p = await async_playwright().start()
    context = await p.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=False,
    )

    # 劫持 attachShadow，将 closed 强制改为 open，使 Playwright 可穿透
    await context.add_init_script("""
        const original = Element.prototype.attachShadow;
        Element.prototype.attachShadow = function(opts) {
            if (opts && opts.mode === 'closed') {
                opts.mode = 'open';
            }
            return original.call(this, opts);
        };
    """)

    try:
        # 4. 检查登录状态
        await ensure_logged_in(context)

        # 5. 打开新页面执行发布
        page = await context.new_page()
        await page.goto("https://creator.xiaohongshu.com/new/home", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # 6. 执行发布
        await publish_note(page, article["title"], article["content"])

        # 7. 发布完成后删除 md 文件
        os.remove(MD_FILE_PATH)
        print(f"🗑️ 已删除: {MD_FILE_PATH}")

        await page.close()
    finally:
        await context.close()
        await p.stop()


if __name__ == "__main__":
    asyncio.run(main())
