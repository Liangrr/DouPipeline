import asyncio
import json
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright

# 导入账号管理模块
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..')))
from account_manager import (
    PROJECT_ROOT,
    get_account_browser_profile,
    ensure_account_exists,
)

# ==================== 配置区 ====================


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

    # ==================== 步骤1：点击"新创作"按钮 ====================
    # 尝试三种可能的按钮文案，兼容不同版本的小红书页面
    for btn_text in ["新创作", "新的创作", "开始创作"]:
        try:
            # 精确匹配按钮文本
            btn = page.get_by_text(btn_text, exact=True)
            # 等待按钮可见，超时 3 秒
            if await btn.is_visible(timeout=3000):
                print(f"📝 步骤1：点击'{btn_text}'...")
                # 点击按钮
                await btn.click()
                # 等待页面网络请求完成
                await page.wait_for_load_state("networkidle")
                # 额外等待 1 秒，确保页面渲染完成
                await page.wait_for_timeout(1000)
                # 找到并点击后跳出循环
                break
        except Exception:
            # 当前文案未找到，继续尝试下一个
            pass

    # ==================== 步骤2：输入标题 ====================
    print(f"📝 步骤2：输入标题: {title}")
    # 优先定位 textarea 标题输入框（placeholder 包含"标题"）
    title_input = page.locator('textarea[placeholder*="标题"]').first
    # 如果 textarea 不可见，降级到 contenteditable 富文本编辑器
    if not await title_input.is_visible(timeout=3000):
        title_input = page.locator('[contenteditable="true"]').first
    # 点击标题输入框获取焦点
    await title_input.click()
    # 清空已有内容
    await title_input.fill("")
    # 填入标题文本
    await title_input.fill(title)

    # ==================== 步骤3：输入正文 ====================
    print("📝 步骤3：输入正文...")
    # 定位最后一个 contenteditable 元素（正文编辑器）
    editor = page.locator('[contenteditable="true"]').last
    # 点击正文编辑区域获取焦点
    await editor.click()
    # 全选已有内容
    await page.keyboard.press("Control+a")
    # 删除选中内容
    await page.keyboard.press("Delete")
    # 插入正文文本（insert_text 适合富文本编辑器，不会触发换行等问题）
    await page.keyboard.insert_text(content)
    # 等待输入完成
    await page.wait_for_timeout(500)

    # ==================== 步骤4：一键排版 ====================
    print("📝 步骤4：一键排版...")
    try:
        # 定位"一键排版"按钮
        format_btn = page.get_by_text("一键排版")
        # 检查按钮是否可见，超时 3 秒
        if await format_btn.is_visible(timeout=3000):
            # 点击排版按钮
            await format_btn.click()
            # 等待排版动画/处理完成
            await page.wait_for_timeout(2000)
            print("  ✅ 排版完成")
    except Exception:
        # 按钮不存在或不可见，跳过此步骤
        print("  ⚠️ 未找到一键排版按钮，跳过")

    # ==================== 步骤5：点击"下一步" ====================
    print("📝 步骤5：点击下一步...")
    # 定位"下一步"按钮
    next_btn = page.get_by_text("下一步")
    # 点击进入发布设置页
    await next_btn.click()
    # 等待页面加载完成
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1000)

    # ==================== 步骤6：输入标签 ====================
    # 如果传入了标签列表
    if tags:
        print(f"📝 步骤6：输入标签 ({len(tags)} 个)...")
        # 遍历每个标签逐个添加
        for tag in tags:
            try:
                # 定位标签输入框（兼容多种 placeholder 文案）
                tag_input = page.locator('input[placeholder*="话题"], input[placeholder*="标签"], input[placeholder*="添加话题"]').first
                # 检查输入框是否可见
                if await tag_input.is_visible(timeout=3000):
                    # 点击输入框获取焦点
                    await tag_input.click()
                    # 填入标签文字
                    await tag_input.fill(tag)
                    # 等待下拉建议出现
                    await page.wait_for_timeout(1000)
                    # 按回车确认添加标签
                    await page.keyboard.press("Enter")
                    # 等待标签添加动画完成
                    await page.wait_for_timeout(500)
                    print(f"  ✅ 已添加标签: {tag}")
                else:
                    # 输入框不可见，跳过剩余标签
                    print(f"  ⚠️ 未找到标签输入框，跳过标签: {tag}")
                    break
            except Exception as e:
                # 单个标签添加失败，记录错误继续处理下一个
                print(f"  ⚠️ 添加标签 '{tag}' 失败: {e}")
    else:
        # 没有传入标签，跳过此步骤
        print("📝 步骤6：无标签，跳过")

    # ==================== 步骤7：等待图片上传完成 ====================
    print("📝 步骤7：等待图片上传完成...")
    # 最长等待时间：120 秒
    max_wait = 120
    # 记录开始时间
    start_time = asyncio.get_event_loop().time()
    # 轮询检查上传状态
    while True:
        # 计算已等待时间
        elapsed = asyncio.get_event_loop().time() - start_time
        # 超时则跳出循环
        if elapsed > max_wait:
            print("  ⚠️ 等待超时，继续发布")
            break

        # 标记是否有正在上传的元素
        uploading = False
        # 遍历多种上传状态指示器的选择器
        for sel in [
            'text=上传中',           # 文本"上传中"
            'text=上传中...',        # 带省略号的文本
            '[class*="uploading"]',  # CSS class 包含 uploading
            '[class*="progress"]',   # CSS class 包含 progress（进度条）
            '.upload-progress',      # 上传进度条 class
            'text=%',                # 百分比进度文本
        ]:
            try:
                # 取第一个匹配元素
                el = page.locator(sel).first
                # 快速检查是否可见（500ms 超时）
                if await el.is_visible(timeout=500):
                    uploading = True
                    break
            except Exception:
                continue

        # 没有检测到上传中的元素，说明上传完成
        if not uploading:
            print(f"  ✅ 图片上传完成 ({int(elapsed)}s)")
            break

        # 仍在上传中，打印进度并等待 2 秒后再次检查
        print(f"  ⏳ 图片上传中... ({int(elapsed)}s/{max_wait}s)")
        await page.wait_for_timeout(2000)

    # 额外等待 1 秒，确保上传状态完全稳定
    await page.wait_for_timeout(1000)

    # ==================== 步骤8：点击发布 ====================
    print("📝 步骤8：点击发布...")
    # 先等待 2 秒，确保页面状态稳定
    await page.wait_for_timeout(2000)
    # 标记是否成功点击了发布按钮
    published = False
    # 按优先级尝试多种选择器定位发布按钮
    for sel in [
        page.get_by_role("button", name="发布"),                   # 语义化匹配，最可靠
        page.locator('.publish-btn, .submit-btn, [class*="publish"]').first,  # 常见 CSS class
        page.locator('button:has-text("发布"):not(:has-text("笔记"))').first,  # 排除侧边栏的「发布笔记」
        page.locator('button:has-text("立即发布")').first,        # 备选文案
        page.locator('div.btn:has-text("发布")').first,            # div 按钮
    ]:
        try:
            # 检查按钮是否可见
            if await sel.is_visible(timeout=3000):
                # 点击发布按钮
                await sel.click()
                print(f"  ✅ 已点击发布按钮")
                published = True
                break
        except Exception:
            # 当前选择器失败，尝试下一个
            continue

    # 兜底方案：普通 click 不生效时，用 dispatch_event 强制触发点击事件
    if not published:
        print("  ⚠️ 普通点击未生效，尝试 dispatch_event...")
        for sel in [
            page.get_by_role("button", name="发布"),
            page.locator('button:has-text("发布")').last,  # 最后一个，大概率是底部的发布按钮
        ]:
            try:
                if await sel.is_visible(timeout=3000):
                    # 通过 DOM 事件强制触发点击，绕过可能的遮挡
                    await sel.dispatch_event("click")
                    print(f"  ✅ 通过 dispatch_event 点击成功")
                    published = True
                    break
            except Exception:
                continue

    # 所有方式都失败，提示用户手动操作
    if not published:
        print("  ❌ 未找到发布按钮，请手动点击")

    # 等待页面响应
    await page.wait_for_timeout(2000)

    # ==================== 处理确认弹窗 ====================
    # 小红书可能弹出二次确认弹窗，依次尝试常见确认文案
    for confirm_text in ["确认发布", "确认", "确定", "好的"]:
        try:
            # 精确匹配弹窗按钮文本
            confirm_btn = page.get_by_text(confirm_text, exact=True)
            # 检查按钮是否可见
            if await confirm_btn.is_visible(timeout=2000):
                print(f"  📋 检测到确认弹窗，点击「{confirm_text}」...")
                # 点击确认按钮
                await confirm_btn.click()
                await page.wait_for_timeout(1000)
                break
        except Exception:
            # 当前文案未匹配，继续尝试下一个
            continue

    # ==================== 等待发布结果 ====================
    print("  ⏳ 等待发布完成...")
    try:
        # 方式1：等待"发布成功"文本出现，最多等 30 秒
        await page.get_by_text("发布成功").wait_for(state="visible", timeout=30000)
        print("  ✅ 检测到「发布成功」")
    except Exception:
        # 方式2：没有明确提示，检测页面 URL 是否发生变化（跳转 = 发布成功）
        current_url = page.url
        try:
            await page.wait_for_url(lambda url: url != current_url, timeout=30000)
            print("  ✅ 页面已跳转，视为发布成功")
        except Exception:
            # 两种方式都未检测到，提示用户手动确认
            print("  ⚠️ 未检测到成功提示，请手动确认发布结果")

    print("✅ 发布完成！")


async def publish(file_path: str, account_name: str = "legacy"):
    """主函数：读取 JSON 文件并发布到小红书"""
    # 确保账号存在
    ensure_account_exists(account_name)

    # 1. 读取 JSON 文件
    print(f"📖 正在读取文件: {file_path}")
    article = read_json_file(file_path)
    print(f"✅ 标题: {article['title']}")
    print(f"✅ 内容长度: {len(article['content'])} 字符")
    if article.get("tags"):
        print(f"✅ 标签: {', '.join(article['tags'])}")

    # 2. 账号专属浏览器目录
    user_data_dir = get_account_browser_profile(account_name)
    Path(user_data_dir).mkdir(exist_ok=True)
    print(f"📂 浏览器数据目录: {user_data_dir}")

    # 3. 启动浏览器
    print("\n🌐 正在启动浏览器...")
    p = await async_playwright().start()
    # 解释：使用 launch_persistent_context 启动持久化上下文，保持登录状态；headless=False 以便用户扫码登录
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

    try:
        # 4. 检查登录状态
        await ensure_logged_in(context)

        # 5. 打开新页面执行发布
        page = await context.new_page()
        await page.goto("https://creator.xiaohongshu.com/publish/publish?from=menu&target=article", wait_until="networkidle", timeout=30000)
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
    parser.add_argument("--account", default="legacy", help="账号名称 (默认: legacy)")
    args = parser.parse_args()
    await publish(args.input, account_name=args.account)


if __name__ == "__main__":
    asyncio.run(main())
