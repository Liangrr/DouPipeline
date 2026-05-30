import asyncio
import json
import os
import glob
from pathlib import Path
from playwright.async_api import async_playwright

# ==================== 配置区 ====================
JSON_FILE_PATH = "/Users/asuria/Desktop/browser/byte.json"
USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "byte_browser_profile")
UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"
OUTPUT_DIR = "/Users/asuria/Desktop/browser/doubao_output"


def read_json_file(file_path: str) -> dict:
    """读取 JSON 文件，提取 title、subtitle、summary、content"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到文件: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    title = data.get("title", "")
    subtitle = data.get("subtitle", "")
    summary = data.get("summary", "")
    content = data.get("content", "")

    if not title:
        raise ValueError("未找到 title 字段")

    return {"title": title, "subtitle": subtitle, "summary": summary, "content": content}


def get_output_images() -> list:
    """获取 doubao_output 目录下所有图片文件"""
    if not os.path.exists(OUTPUT_DIR):
        raise FileNotFoundError(f"找不到输出目录: {OUTPUT_DIR}")

    images = []
    for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.gif", "*.bmp"]:
        images.extend(glob.glob(os.path.join(OUTPUT_DIR, ext)))
        images.extend(glob.glob(os.path.join(OUTPUT_DIR, ext.upper())))

    images = sorted(set(images))

    if not images:
        raise FileNotFoundError(f"目录 {OUTPUT_DIR} 中没有找到图片文件")

    print(f"📷 找到 {len(images)} 张图片:")
    for img in images:
        print(f"   - {img}")

    return images


async def ensure_logged_in(page):
    """检查登录状态，未登录则等待用户手动登录"""
    await page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(3000)

    page_text = await page.content()
    is_logged_in = any(kw in page_text for kw in ["发布作品", "内容管理", "数据中心", "发布图文", "发布文章"])

    if is_logged_in:
        print("🎉 已登录！")
        return

    print("\n" + "=" * 50)
    print("⚠️  检测到未登录，请在上方浏览器中完成以下操作：")
    print("   1. 用抖音 APP 扫码登录")
    print("   2. 登录成功后，回到这里按回车")
    print("=" * 50)
    input("\n✅ 登录完成后按回车继续 >>> ")

    await page.reload(wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(3000)
    page_text = await page.content()
    is_logged_in = any(kw in page_text for kw in ["发布作品", "内容管理", "数据中心", "发布图文", "发布文章"])

    if not is_logged_in:
        raise RuntimeError("❌ 登录失败，请重新运行脚本")

    print("✅ 登录成功！")


async def publish_image_post(page, title: str, subtitle: str, summary: str, content: str, images: list):
    """执行发布图文的完整流程（基于实际页面布局）"""

    # 步骤1：点击"发布图文"
    print("📝 步骤1：点击「发布图文」...")
    try:
        btn = page.get_by_text("发布图文")
        await btn.wait_for(state="visible", timeout=10000)
        await btn.click()
        print("  ✅ 点击成功")
    except Exception:
        await page.click('text=发布图文')
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(3000)

    # 步骤2：点击"上传图文"，上传所有图片
    print("📝 步骤2：点击「上传图文」并上传图片...")
    try:
        btn = page.get_by_text("上传图文")
        await btn.wait_for(state="visible", timeout=10000)
        async with page.expect_file_chooser(timeout=10000) as fc_info:
            await btn.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(images)
        print(f"  ✅ 已上传 {len(images)} 张图片")
    except Exception as e:
        print(f"  ⚠️ 上传图文按钮点击失败: {e}")
        # 备用：查找"点击上传"区域
        try:
            upload_area = page.get_by_text("点击上传")
            async with page.expect_file_chooser(timeout=5000) as fc_info:
                await upload_area.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(images)
            print(f"  ✅ 通过「点击上传」上传了 {len(images)} 张图片")
        except Exception as e2:
            print(f"  ❌ 图片上传失败: {e2}")

    # 等待上传完成和页面加载"编辑图文"区域
    await page.wait_for_timeout(5000)

    # 步骤3：填充标题（输入框 placeholder: "请输入图文标题（选填）最多30字"）
    if title:
        # 截取前30个字符（抖音限制最多30字）
        title_to_fill = title[:30]
        print(f"📝 步骤3：填充标题: {title_to_fill}")
        try:
            title_input = page.locator('input[placeholder*="图文标题"]').first
            await title_input.wait_for(state="visible", timeout=10000)
            await title_input.click()
            await title_input.fill("")
            await title_input.fill(title_to_fill)
            print("  ✅ 标题已填入")
        except Exception:
            print("  ⚠️ 未找到标题输入框，尝试备用方式")
            try:
                title_input = page.locator('input[placeholder*="标题"]').first
                await title_input.wait_for(state="visible", timeout=5000)
                await title_input.click()
                await title_input.fill("")
                await title_input.fill(title_to_fill)
                print("  ✅ 标题已通过备用方式填入")
            except Exception:
                print("  ❌ 标题填入失败")

    await page.wait_for_timeout(1000)

    # 步骤4：填充描述（contenteditable 编辑器区域）
    # 优先使用 content，如果没有则用 subtitle 或 summary
    text_to_fill = content if content else (subtitle or summary)
    if text_to_fill:
        print(f"📝 步骤4：填充描述...")
        try:
            # 查找描述区域的 contenteditable 编辑器
            # 先尝试通过 placeholder 找到对应的编辑区域
            editor = None
            editors = page.locator('[contenteditable="true"]')
            count = await editors.count()

            for i in range(count):
                ed = editors.nth(i)
                if await ed.is_visible(timeout=1000):
                    bbox = await ed.bounding_box()
                    # 选择较大的编辑区域作为描述输入框
                    if bbox and bbox["width"] > 200 and bbox["height"] > 80:
                        editor = ed
                        break

            if editor:
                await editor.click()
                await page.keyboard.press("Control+a")
                await page.keyboard.press("Delete")
                await page.keyboard.insert_text(text_to_fill)
                await page.wait_for_timeout(500)
                print("  ✅ 描述已填入")
            else:
                print("  ⚠️ 未找到描述编辑区域")
        except Exception as e:
            print(f"  ❌ 描述填入失败: {e}")

    await page.wait_for_timeout(2000)

    # 步骤5：点击发布
    print("📝 步骤5：点击「发布」...")
    published = False

    # 根据截图，发布按钮在右上角，绿色按钮
    for text in ["发布", "发表", "立即发布"]:
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
        # 备用选择器
        try:
            btn = page.locator('button:has-text("发布")').first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                print("  ✅ 已通过选择器点击发布")
                published = True
        except Exception:
            pass

    if not published:
        print("  ⚠️ 未找到发布按钮，请手动点击")
    else:
        # 等待发布完成
        print("  ⏳ 等待发布完成...")
        try:
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
    print(f"✅ 副标题: {article['subtitle'] or '未配置'}")
    print(f"✅ 摘要: {article['summary'] or '未配置'}")
    print(f"✅ 正文长度: {len(article['content'])} 字符")

    # 2. 获取输出图片
    images = get_output_images()

    # 3. 创建持久化浏览器目录
    Path(USER_DATA_DIR).mkdir(exist_ok=True)
    print(f"📂 浏览器数据目录: {USER_DATA_DIR}")

    # 4. 启动浏览器
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
        # 5. 检查登录状态
        await ensure_logged_in(page)

        # 6. 执行发布图文流程
        await publish_image_post(
            page,
            article["title"],
            article["subtitle"],
            article["summary"],
            article["content"],
            images,
        )

    finally:
        await page.close()
        await context.close()
        await p.stop()


if __name__ == "__main__":
    asyncio.run(main())
