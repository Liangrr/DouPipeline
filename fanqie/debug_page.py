#!/usr/bin/env python3
"""
调试脚本：分析番茄小说创建章节页面的结构
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..')))

from playwright.async_api import async_playwright
from account_manager import get_account_browser_profile

BOOK_MANAGE_URL = "https://fanqienovel.com/main/writer/book-manage"


async def main():
    user_data_dir = get_account_browser_profile("legacy")
    print(f"📂 浏览器数据目录: {user_data_dir}")

    p = await async_playwright().start()
    context = await p.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=False,
    )

    # 反 webdriver 检测
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)

    page = await context.new_page()

    # 打开书籍管理页面
    print(f"🌐 打开: {BOOK_MANAGE_URL}")
    await page.goto(BOOK_MANAGE_URL, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(5000)

    # 截图保存
    screenshot_path = os.path.join(os.path.dirname(__file__), "debug_manage.png")
    await page.screenshot(path=screenshot_path, full_page=True)
    print(f"📸 截图已保存: {screenshot_path}")

    # 获取页面所有按钮和链接
    print("\n📋 页面中的按钮和链接:")
    buttons = await page.locator('button, a, [role="button"]').all()
    for btn in buttons:
        text = await btn.inner_text()
        if text.strip():
            print(f"  - {text.strip()[:50]}")

    # 点击"创建章节"
    print("\n🔍 尝试点击「创建章节」...")
    for btn_text in ["创建章节", "新建章节", "写新章节"]:
        try:
            btn = page.get_by_text(btn_text, exact=False).first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                print(f"  ✅ 已点击「{btn_text}」")
                break
        except Exception:
            pass

    # 等待新页面加载
    await page.wait_for_timeout(8000)

    # 获取所有页面
    pages = context.pages
    print(f"\n📑 打开的页面数量: {len(pages)}")

    # 找到新打开的页面
    target_page = None
    for p_page in pages:
        url = p_page.url
        print(f"  - {url}")
        if "chapter" in url.lower() or "write" in url.lower() or "editor" in url.lower():
            target_page = p_page

    if not target_page and len(pages) > 1:
        target_page = pages[-1]  # 使用最后一个页面

    if target_page:
        print(f"\n📝 使用页面: {target_page.url}")
        await target_page.bring_to_front()
        await target_page.wait_for_timeout(3000)

        # 截图
        screenshot_path2 = os.path.join(os.path.dirname(__file__), "debug_editor.png")
        await target_page.screenshot(path=screenshot_path2, full_page=True)
        print(f"📸 截图已保存: {screenshot_path2}")

        # 获取所有输入框
        print("\n📋 页面中的输入框:")
        inputs = await target_page.locator('input, textarea, [contenteditable="true"]').all()
        for inp in inputs:
            tag = await inp.evaluate('el => el.tagName')
            placeholder = await inp.get_attribute('placeholder') or ''
            input_type = await inp.get_attribute('type') or ''
            class_name = await inp.get_attribute('class') or ''
            visible = await inp.is_visible()
            print(f"  - <{tag}> placeholder='{placeholder}' type='{input_type}' class='{class_name[:50]}' visible={visible}")

        # 获取所有按钮
        print("\n📋 页面中的按钮:")
        buttons2 = await target_page.locator('button, [role="button"]').all()
        for btn in buttons2:
            text = await btn.inner_text()
            visible = await btn.is_visible()
            if text.strip() and visible:
                print(f"  - {text.strip()[:50]}")

    print("\n✅ 调试完成，请查看截图了解页面结构")
    input("\n按回车关闭浏览器...")

    await page.close()
    await context.close()
    await p.stop()


if __name__ == "__main__":
    asyncio.run(main())
