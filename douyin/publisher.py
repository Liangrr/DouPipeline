import os
import json
import glob
from pathlib import Path
import asyncio
from playwright.async_api import async_playwright

# ==================== 配置区 ====================
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "doubao_output")
TYPE_MAP = {
    "article": "文章",
    "image": "图文",
    "video": "视频",
}


def read_config():
    """
    读取配置文件
    {
        "sendType": "image",
        "title": "标题",
        "subtitle": "副标题",
        "summary": "摘要",
        "content": "内容"
    }
    """
    config_path = os.path.join(PROJECT_ROOT, "doubao.json")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config


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
    """检查登录状态，未登录则等待用户手动登录（抖音 APP 扫码）"""
    await page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)

    # 轮询检测登录状态，替代固定等待
    for _ in range(6):
        await page.wait_for_timeout(1000)
        page_text = await page.content()
        if any(kw in page_text for kw in ["发布作品", "内容管理", "数据中心", "发布文章", "发布图文"]):
            print("🎉 已登录！")
            return

    page_text = await page.content()
    is_logged_in = any(kw in page_text for kw in ["发布作品", "内容管理", "数据中心", "发布文章", "发布图文"])

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
    await page.wait_for_timeout(2000)
    page_text = await page.content()
    is_logged_in = any(kw in page_text for kw in ["发布作品", "内容管理", "数据中心", "发布文章", "发布图文"])

    if not is_logged_in:
        raise RuntimeError("❌ 登录失败，请重新运行脚本")

    print("✅ 登录成功！")


# ==================== 类型1：发布文章 ====================

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
        await page.click('text=发布文章')
    await page.wait_for_load_state("domcontentloaded")

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

    # 步骤6：选择音乐（选择音乐 → 收藏 → 悬停第一条 → 点击使用）
    print("📝 步骤6：选择音乐...")
    try:
        print("  🎵 点击「选择音乐」...")
        music_btn = page.get_by_text("选择音乐", exact=False).last
        await music_btn.wait_for(state="visible", timeout=10000)
        await music_btn.click()
        print("  ✅ 已点击「选择音乐」，等待弹窗加载...")

        await page.wait_for_timeout(3000)
        fav_btn = page.get_by_text("收藏", exact=True).first
        await fav_btn.wait_for(state="visible", timeout=10000)
        await fav_btn.click()
        print("  ✅ 已点击「收藏」，等待列表加载...")

        await page.wait_for_timeout(3000)
        use_span = page.locator('span:text("使用")').first
        await use_span.wait_for(state="attached", timeout=10000)
        await use_span.dispatch_event("click")
        print("  ✅ 已点击「使用」，弹窗关闭")

        await page.wait_for_timeout(2000)
        print("  ✅ 音乐选择完成")
    except Exception as e:
        print(f"  ⚠️ 选择音乐失败: {e}")

    await page.wait_for_timeout(1500)

    # 步骤7：自主声明（点击请选择自主声明 → 弹窗中选内容由AI生成 → 确定）
    print("📝 步骤7：设置自主声明...")
    try:
        declare_btn = page.get_by_text("请选择自主声明", exact=False).first
        await declare_btn.wait_for(state="visible", timeout=10000)
        await declare_btn.click()
        print("  ✅ 已点击「请选择自主声明」，等待弹窗加载...")

        await page.wait_for_timeout(3000)

        ai_options = page.get_by_text("内容由AI生成", exact=False)
        ai_count = await ai_options.count()
        print(f"  🔍 找到 {ai_count} 个「内容由AI生成」元素")
        for i in range(ai_count):
            item = ai_options.nth(i)
            try:
                text = await item.text_content()
                visible = await item.is_visible(timeout=1000)
                tag = await item.evaluate("el => el.tagName")
                print(f"     [{i}] 标签: {tag} | 文本: 「{text}」 | 可见: {visible}")
            except Exception:
                print(f"     [{i}] 无法获取信息")

        ai_option = page.get_by_text("内容由AI生成", exact=False).first
        await ai_option.wait_for(state="attached", timeout=10000)
        await ai_option.dispatch_event("click")
        print("  ✅ 已选择「内容由AI生成」")
        await page.wait_for_timeout(1000)

        confirm_btn = page.get_by_text("确定", exact=True).first
        await confirm_btn.wait_for(state="attached", timeout=5000)
        await confirm_btn.dispatch_event("click")
        print("  ✅ 已点击「确定」，弹窗关闭")
        await page.wait_for_timeout(1000)
        print("  ✅ 自主声明设置完成")
    except Exception as e:
        print(f"  ⚠️ 自主声明设置失败: {e}")

    await page.wait_for_timeout(1000)

    # 步骤8：上传封面图片
    if cover_image:
        if not os.path.exists(cover_image):
            print(f"⚠️ 封面图片不存在: {cover_image}，跳过")
        else:
            print(f"📝 步骤8：上传封面图片: {cover_image}")
            uploaded = False

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
        print("📝 步骤8：未配置封面图片，跳过")

    # 步骤9：等待截图/裁剪弹窗 → 点击确定
    print("📝 步骤9：等待截图弹窗，点击「确定」...")
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

    await page.wait_for_timeout(1500)

    # 步骤10：点击发布按钮
    print("📝 步骤10：点击「发布」...")
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


# ==================== 类型2：发布图文 ====================

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
    await page.wait_for_timeout(1500)

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
    await page.wait_for_timeout(3000)

    # 步骤3：填充标题（输入框 placeholder: "请输入图文标题（选填）最多30字"）
    if title:
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

    # 步骤4：填充描述（contenteditable 编辑器区域）
    text_to_fill = content if content else (subtitle or summary)
    if text_to_fill:
        print(f"📝 步骤4：填充描述...")
        try:
            editor = None
            editors = page.locator('[contenteditable="true"]')
            count = await editors.count()

            for i in range(count):
                ed = editors.nth(i)
                if await ed.is_visible(timeout=1000):
                    bbox = await ed.bounding_box()
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

    await page.wait_for_timeout(1000)

    # 步骤5：选择音乐（选择音乐 → 收藏 → 悬停第一条 → 点击使用）
    print("📝 步骤5：选择音乐...")
    try:
        print("  🎵 点击「选择音乐」...")
        music_btn = page.get_by_text("选择音乐", exact=False).last
        await music_btn.wait_for(state="visible", timeout=10000)
        await music_btn.click()
        print("  ✅ 已点击「选择音乐」，等待弹窗加载...")

        await page.wait_for_timeout(3000)
        fav_btn = page.get_by_text("收藏", exact=True).first
        await fav_btn.wait_for(state="visible", timeout=10000)
        await fav_btn.click()
        print("  ✅ 已点击「收藏」，等待列表加载...")

        await page.wait_for_timeout(3000)
        use_span = page.locator('span:text("使用")').first
        await use_span.wait_for(state="attached", timeout=10000)
        await use_span.dispatch_event("click")
        print("  ✅ 已点击「使用」，弹窗关闭")

        await page.wait_for_timeout(2000)
        print("  ✅ 音乐选择完成")
    except Exception as e:
        print(f"  ⚠️ 选择音乐失败: {e}")

    await page.wait_for_timeout(1500)

    # 步骤6：自主声明（点击请选择自主声明 → 弹窗中选内容由AI生成 → 确定）
    print("📝 步骤6：设置自主声明...")
    try:
        declare_btn = page.get_by_text("请选择自主声明", exact=False).first
        await declare_btn.wait_for(state="visible", timeout=10000)
        await declare_btn.click()
        print("  ✅ 已点击「请选择自主声明」，等待弹窗加载...")

        await page.wait_for_timeout(3000)

        ai_options = page.get_by_text("内容由AI生成", exact=False)
        ai_count = await ai_options.count()
        print(f"  🔍 找到 {ai_count} 个「内容由AI生成」元素")
        for i in range(ai_count):
            item = ai_options.nth(i)
            try:
                text = await item.text_content()
                visible = await item.is_visible(timeout=1000)
                tag = await item.evaluate("el => el.tagName")
                print(f"     [{i}] 标签: {tag} | 文本: 「{text}」 | 可见: {visible}")
            except Exception:
                print(f"     [{i}] 无法获取信息")

        ai_option = page.get_by_text("内容由AI生成", exact=False).first
        await ai_option.wait_for(state="attached", timeout=10000)
        await ai_option.dispatch_event("click")
        print("  ✅ 已选择「内容由AI生成」")
        await page.wait_for_timeout(1000)

        confirm_btn = page.get_by_text("确定", exact=True).first
        await confirm_btn.wait_for(state="attached", timeout=5000)
        await confirm_btn.dispatch_event("click")
        print("  ✅ 已点击「确定」，弹窗关闭")
        await page.wait_for_timeout(1000)
        print("  ✅ 自主声明设置完成")
    except Exception as e:
        print(f"  ⚠️ 自主声明设置失败: {e}")

    await page.wait_for_timeout(1000)

    # 步骤7：点击发布
    print("📝 步骤7：点击「发布」...")
    published = False

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
                await page.wait_for_timeout(500)
                print("  ✅ 等待结束，视为发布完成")

    print("✅ 全部流程执行完毕！")


# ==================== 类型3：发布视频（待实现） ====================

async def publish_video(page, title: str, summary: str, content: str, video_path: str = ""):
    """执行发布视频的完整流程（待实现）"""
    print("📝 发布视频功能待实现...")
    print("⚠️ 视频发布功能尚未实现，跳过")


# ==================== 入口 ====================

async def publish(sendType: str = None, title: str = None, content: str = None):
    """主入口：根据 sendType 执行对应的发布流程"""
    config = read_config()

    if not sendType:
        sendType = config.get("sendType", "article")
    if not title:
        title = config.get("title", "默认标题")
    if not content:
        content = config.get("content", "默认内容")
    subtitle = config.get("subtitle", "")
    summary = config.get("summary", "")
    cover_image = config.get("cover_image", "")

    print(f"📋 发布类型: {TYPE_MAP.get(sendType, '未知')}")
    print(f"📋 标题: {title}")
    print(f"📋 内容长度: {len(content)} 字符")

    # 用户数据目录
    user_data_dir = os.path.join(PROJECT_ROOT, "byte_browser_profile")
    Path(user_data_dir).mkdir(exist_ok=True)
    print(f"📂 浏览器数据目录: {user_data_dir}")

    # 启动浏览器
    print("\n🌐 正在启动浏览器...")
    p = await async_playwright().start()
    context = await p.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
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
        await ensure_logged_in(page)

        if sendType == "article":
            print(f"\n🚀 开始发布文章...")
            await publish_article(page, title, summary, content, cover_image)

        elif sendType == "image":
            print(f"\n🚀 开始发布图文...")
            images = get_output_images()
            await publish_image_post(page, title, subtitle, summary, content, images)

        elif sendType == "video":
            print(f"\n🚀 开始发布视频...")
            video_path = config.get("video_path", "")
            await publish_video(page, title, summary, content, video_path)

        else:
            print(f"❌ 不支持的发送类型: {sendType}")

        print("✅ 发布完成！")
    finally:
        await page.close()
        await context.close()
        await p.stop()


async def main():
    """独立运行入口"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["article", "image", "video"], help="发布类型")
    args = parser.parse_args()
    await publish(sendType=args.type)


if __name__ == "__main__":
    asyncio.run(main())
