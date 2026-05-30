import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright

# ==================== 配置区 ====================
JSON_FILE_PATH = "/Users/asuria/Desktop/browser/byte.json"
USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "byte_browser_profile")
UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"


def read_json_file(file_path: str) -> dict:
    """读取 JSON 文件，提取 title、summary、content、cover_image"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到文件: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    title = data.get("title", "")
    summary = data.get("summary", "")
    content = data.get("content", "")
    cover_image = data.get("cover_image", "")

    if not title:
        raise ValueError("未找到 title 字段")
    if not content:
        raise ValueError("未找到 content 字段")

    return {"title": title, "summary": summary, "content": content, "cover_image": cover_image}


async def ensure_logged_in(page):
    """检查登录状态，未登录则等待用户手动登录（抖音 APP 扫码）"""
    await page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(3000)

    page_text = await page.content()
    # 登录后页面会出现这些元素
    is_logged_in = any(kw in page_text for kw in ["发布作品", "内容管理", "数据中心", "发布文章"])

    if is_logged_in:
        print("🎉 已登录！")
        return

    # 未登录 → 等待用户手动扫码登录
    print("\n" + "=" * 50)
    print("⚠️  检测到未登录，请在上方浏览器中完成以下操作：")
    print("   1. 用抖音 APP 扫码登录")
    print("   2. 登录成功后，回到这里按回车")
    print("=" * 50)
    input("\n✅ 登录完成后按回车继续 >>> ")

    # 验证登录
    await page.reload(wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(3000)
    page_text = await page.content()
    is_logged_in = any(kw in page_text for kw in ["发布作品", "内容管理", "数据中心", "发布文章"])

    if not is_logged_in:
        raise RuntimeError("❌ 登录失败，请重新运行脚本")

    print("✅ 登录成功！")


async def publish_article(page, title: str, summary: str, content: str, cover_image: str = ""):
    """执行发布文章的完整流程"""
    # 步骤1：点击"发布文章"
    print("📝 步骤1：点击「发布文章」...")
    try:
        btn = page.get_by_text("发布文章")
        await btn.wait_for(state="visible", timeout=10000)
        await btn.click()
        print("  ✅ 点击成功")
    except Exception:
        # 备用：尝试其他选择器
        await page.click('text=发布文章')
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(3000)

    # 步骤2：点击"我要发文"
    print("📝 步骤2：点击「我要发文」...")
    try:
        btn = page.get_by_text("我要发文")
        await btn.wait_for(state="visible", timeout=10000)
        await btn.click()
        print("  ✅ 点击成功")
    except Exception:
        await page.click('text=我要发文')
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(3000)

    # 步骤3：填充文章标题
    print(f"📝 步骤3：填充文章标题: {title}")
    title_input = page.locator('textarea[placeholder*="标题"], input[placeholder*="标题"]').first
    await title_input.wait_for(state="visible", timeout=10000)
    await title_input.click()
    await title_input.fill("")
    await title_input.fill(title)
    print("  ✅ 标题已填入")

    # 步骤4：填充文章摘要
    if summary:
        print(f"📝 步骤4：填充文章摘要: {summary}")
        try:
            summary_input = page.locator('textarea[placeholder*="摘要"], input[placeholder*="摘要"]').first
            if await summary_input.is_visible(timeout=5000):
                await summary_input.click()
                await summary_input.fill("")
                await summary_input.fill(summary)
                print("  ✅ 摘要已填入")
        except Exception:
            print("  ⚠️ 未找到摘要输入框，跳过")
    else:
        print("📝 步骤4：摘要为空，跳过")

    # 步骤5：填充文章正文
    print("📝 步骤5：填充文章正文...")
    editor = page.locator('[contenteditable="true"]').first
    await editor.wait_for(state="visible", timeout=10000)
    await editor.click()
    await page.keyboard.press("Control+a")
    await page.keyboard.press("Delete")
    await page.keyboard.insert_text(content)
    await page.wait_for_timeout(500)
    print("  ✅ 正文已填入")

    # 步骤6：上传封面图片
    if cover_image:
        if not os.path.exists(cover_image):
            print(f"⚠️ 封面图片不存在: {cover_image}，跳过")
        else:
            print(f"📝 步骤6：上传封面图片: {cover_image}")
            uploaded = False

            # 点击上传按钮，拦截文件选择对话框
            for selector in ["上传封面", "上传图片", "上传", "点击上传", "选择封面"]:
                try:
                    btn = page.get_by_text(selector, exact=False).first
                    if await btn.is_visible(timeout=2000):
                        async with page.expect_file_chooser(timeout=5000) as fc_info:
                            await btn.click()
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(cover_image)
                        print(f"  ✅ 通过「{selector}」上传成功")
                        uploaded = True
                        break
                except Exception:
                    pass

            if not uploaded:
                print("  ⚠️ 封面上传失败，请手动上传")
            else:
                print("  ✅ 封面上传完成")
    else:
        print("📝 步骤6：未配置封面图片，跳过")

    # 步骤7：等待截图/裁剪弹窗 → 点击确定
    print("📝 步骤7：等待截图弹窗，点击「确定」...")
    await page.wait_for_timeout(2000)
    confirmed = False
    for text in ["确定", "确认", "完成", "OK"]:
        try:
            btn = page.get_by_text(text, exact=True).first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                print(f"  ✅ 已点击「{text}」")
                confirmed = True
                break
        except Exception:
            pass

    if not confirmed:
        # 备用：在弹窗/遮罩层中查找按钮
        try:
            btn = page.locator('.ant-btn-primary, .el-button--primary, [class*="modal"] button, [class*="dialog"] button').first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                print("  ✅ 已点击弹窗主按钮")
                confirmed = True
        except Exception:
            pass

    if not confirmed:
        print("  ⚠️ 未找到确定按钮，请手动点击")

    await page.wait_for_timeout(3000)

    # 步骤8：点击发布按钮
    print("📝 步骤8：点击「发布」...")
    published = False
    for text in ["发布", "发表", "提交发布"]:
        try:
            btn = page.get_by_text(text, exact=True).first
            if await btn.is_visible(timeout=5000):
                await btn.click()
                print(f"  ✅ 已点击「{text}」")
                published = True
                break
        except Exception:
            pass

    if not published:
        print("  ⚠️ 未找到发布按钮，请手动点击")
    else:
        # 步骤9：等待发布完成
        print("  ⏳ 等待发布完成...")
        try:
            # 等待"发布成功"提示或页面跳转
            await page.get_by_text("发布成功").wait_for(state="visible", timeout=60000)
            print("  ✅ 检测到「发布成功」")
        except Exception:
            current_url = page.url
            try:
                await page.wait_for_url(lambda url: url != current_url, timeout=60000)
                print("  ✅ 页面已跳转，发布完成")
            except Exception:
                await page.wait_for_timeout(10000)
                print("  ✅ 等待结束，视为发布完成")

    print("✅ 全部流程执行完毕！")


async def main():
    # 1. 读取 JSON 文件
    print(f"📖 正在读取文件: {JSON_FILE_PATH}")
    article = read_json_file(JSON_FILE_PATH)
    print(f"✅ 标题: {article['title']}")
    print(f"✅ 摘要: {article['summary']}")
    print(f"✅ 正文长度: {len(article['content'])} 字符")
    print(f"✅ 封面: {article['cover_image'] or '未配置'}")

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

    page = await context.new_page()

    try:
        # 4. 检查登录状态（持久化浏览器自动保存 cookie，下次免登录）
        await ensure_logged_in(page)

        # 5. 执行发布文章流程
        await publish_article(page, article["title"], article["summary"], article["content"], article["cover_image"])

    finally:
        await page.close()
        await context.close()
        await p.stop()


if __name__ == "__main__":
    asyncio.run(main())
