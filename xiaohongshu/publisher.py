import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright

# ==================== 配置区 ====================
# 此文件从项目根目录的 run.py 调用，所有相对路径基于项目根目录
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
USER_DATA_DIR = os.path.join(PROJECT_ROOT, "browser_profile")


def read_json_file(file_path: str) -> dict:
    """读取 JSON 文件，提取 title、content 和 tags"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到文件: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    title = data.get("title", "")
    content = data.get("content", "")
    tags = data.get("tags", [])

    if not title:
        raise ValueError("未找到 title 字段")
    if not content:
        raise ValueError("未找到 content 字段")

    if len(title) > 20:
        title = title[:20]

    return {"title": title, "content": content, "tags": tags}


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


async def publish_note(page, title: str, content: str, tags: list = None):
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

    # 步骤8：输入标签
    if tags:
        print(f"📝 步骤8：输入标签 ({len(tags)} 个)...")
        for tag in tags:
            try:
                # 小红书发布页的话题/标签输入框
                tag_input = page.locator('input[placeholder*="话题"], input[placeholder*="标签"], input[placeholder*="添加话题"]').first
                if await tag_input.is_visible(timeout=3000):
                    await tag_input.click()
                    await tag_input.fill(tag)
                    await page.wait_for_timeout(1000)
                    # 按回车或点击下拉选项添加标签
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(500)
                    print(f"  ✅ 已添加标签: {tag}")
                else:
                    print(f"  ⚠️ 未找到标签输入框，跳过标签: {tag}")
                    break
            except Exception as e:
                print(f"  ⚠️ 添加标签 '{tag}' 失败: {e}")
    else:
        print("📝 步骤8：无标签，跳过")

    # 步骤9：等待图片上传完成
    print("📝 步骤9：等待图片上传完成...")
    max_wait = 120  # 最长等待 120 秒
    start_time = asyncio.get_event_loop().time()
    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > max_wait:
            print("  ⚠️ 等待超时，继续发布")
            break

        # 检查是否存在上传中的指示器
        uploading = False
        for sel in [
            'text=上传中',
            'text=上传中...',
            '[class*="uploading"]',
            '[class*="progress"]',
            '.upload-progress',
            'text=%',  # 百分比进度
        ]:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=500):
                    uploading = True
                    break
            except Exception:
                continue

        if not uploading:
            print(f"  ✅ 图片上传完成 ({int(elapsed)}s)")
            break

        print(f"  ⏳ 图片上传中... ({int(elapsed)}s/{max_wait}s)")
        await page.wait_for_timeout(2000)

    await page.wait_for_timeout(1000)

    # 步骤10：点击发布
    print("📝 步骤10：点击发布...")
    await page.wait_for_timeout(2000)
    # 尝试多种选择器定位发布按钮（按优先级排列，避开侧边栏的「发布笔记」）
    published = False
    for sel in [
        page.get_by_role("button", name="发布"),                   # 语义化匹配，最可靠
        page.locator('.publish-btn, .submit-btn, [class*="publish"]').first,  # 常见 CSS class
        page.locator('button:has-text("发布"):not(:has-text("笔记"))').first,  # 排除「发布笔记」
        page.locator('button:has-text("立即发布")').first,
        page.locator('div.btn:has-text("发布")').first,
    ]:
        try:
            if await sel.is_visible(timeout=3000):
                await sel.click()
                print(f"  ✅ 已点击发布按钮")
                published = True
                break
        except Exception:
            continue

    # 兜底：普通 click 不生效时，用 dispatch_event 强制触发
    if not published:
        print("  ⚠️ 普通点击未生效，尝试 dispatch_event...")
        for sel in [
            page.get_by_role("button", name="发布"),
            page.locator('button:has-text("发布")').last,  # 最后一个，大概率是底部的发布按钮
        ]:
            try:
                if await sel.is_visible(timeout=3000):
                    await sel.dispatch_event("click")
                    print(f"  ✅ 通过 dispatch_event 点击成功")
                    published = True
                    break
            except Exception:
                continue

    if not published:
        print("  ❌ 未找到发布按钮，请手动点击")

    await page.wait_for_timeout(2000)

    # 处理可能的确认弹窗
    for confirm_text in ["确认发布", "确认", "确定", "好的"]:
        try:
            confirm_btn = page.get_by_text(confirm_text, exact=True)
            if await confirm_btn.is_visible(timeout=2000):
                print(f"  📋 检测到确认弹窗，点击「{confirm_text}」...")
                await confirm_btn.click()
                await page.wait_for_timeout(1000)
                break
        except Exception:
            continue

    print("  ⏳ 等待发布完成...")
    # 等待"发布成功"提示或页面跳转，最多等 30 秒
    try:
        await page.get_by_text("发布成功").wait_for(state="visible", timeout=30000)
        print("  ✅ 检测到「发布成功」")
    except Exception:
        # 没有明确提示，等页面跳转（URL 变化）
        current_url = page.url
        try:
            await page.wait_for_url(lambda url: url != current_url, timeout=30000)
            print("  ✅ 页面已跳转，视为发布成功")
        except Exception:
            print("  ⚠️ 未检测到成功提示，请手动确认发布结果")

    print("✅ 发布完成！")


async def publish(file_path: str):
    """主函数：读取 JSON 文件并发布到小红书"""
    # 1. 读取 JSON 文件
    print(f"📖 正在读取文件: {file_path}")
    article = read_json_file(file_path)
    print(f"✅ 标题: {article['title']}")
    print(f"✅ 内容长度: {len(article['content'])} 字符")
    if article.get("tags"):
        print(f"✅ 标签: {', '.join(article['tags'])}")

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
        await publish_note(page, article["title"], article["content"], article.get("tags"))

        await page.close()
    finally:
        await context.close()
        await p.stop()


async def main():
    """入口函数"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="输入 JSON 文件路径")
    args = parser.parse_args()
    await publish(args.input)


if __name__ == "__main__":
    asyncio.run(main())
