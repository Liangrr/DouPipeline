#!/usr/bin/env python3
"""
豆包(doubao.com)自动登录、批量输入prompt、保存生成图片脚本
使用 Playwright 自动化浏览器（持久化登录状态）
"""

import json
import os
import shutil
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

# ====== 配置 ======
DOUBAO_URL = "https://www.doubao.com/chat"
PROMPT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "doubao.json")
USER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "doubao_browser_profile")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "doubao_output")
TIMEOUT_IMAGE = 180


def load_prompts():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    prompts = data["prompt"]
    if isinstance(prompts, str):
        prompts = [prompts]
    return prompts


def clear_output_dir():
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"🧹 已清空输出目录: {OUTPUT_DIR}")


def ensure_logged_in(page):
    page.goto(DOUBAO_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)

    input_selectors = [
        'textarea',
        '[contenteditable="true"]',
        'div[role="textbox"]',
        'textarea[placeholder]',
    ]

    for sel in input_selectors:
        try:
            if page.locator(sel).first.is_visible(timeout=3000):
                print("🎉 已登录！（复用上次会话）")
                return
        except Exception:
            continue

    print("\n" + "=" * 60)
    print("⚠️  检测到未登录，请在上方浏览器中手动登录豆包：")
    print("   登录成功后，回到这里按回车继续")
    print("=" * 60)
    input("\n✅ 登录完成后按回车继续 >>> ")

    page.reload(wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)

    for sel in input_selectors:
        try:
            if page.locator(sel).first.is_visible(timeout=3000):
                print("✅ 登录成功！")
                return
        except Exception:
            continue

    raise RuntimeError("❌ 登录失败，请重新运行脚本")


def close_popups(page):
    for sel in [
        'button:has-text("关闭")',
        'button:has-text("跳过")',
        'button:has-text("我知道了")',
        'button:has-text("开始使用")',
        '[aria-label="Close"]',
        '[aria-label="关闭"]',
    ]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1500):
                btn.click()
                page.wait_for_timeout(500)
        except Exception:
            continue


def input_prompt_and_submit(page, prompt):
    print(f"📝 正在输入 prompt...")

    input_selectors = [
        'textarea',
        '[contenteditable="true"]',
        'div[role="textbox"]',
        'textarea[placeholder]',
    ]

    input_box = None
    for sel in input_selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=3000):
                input_box = loc
                print(f"   找到输入框: {sel}")
                break
        except Exception:
            continue

    if not input_box:
        print("❌ 未找到输入框")
        return False

    input_box.click()
    page.wait_for_timeout(500)
    page.keyboard.press("Control+a")
    page.wait_for_timeout(100)
    page.keyboard.press("Delete")
    page.wait_for_timeout(300)

    print(f"   正在键入 prompt（{len(prompt)} 字符）...")
    page.keyboard.type(prompt, delay=10)
    page.wait_for_timeout(1000)

    print("   等待 3 秒后发送...")
    page.wait_for_timeout(3000)

    print("🚀 发送 prompt...")
    page.keyboard.press("Enter")
    page.wait_for_timeout(3000)

    for sel in [
        'button[aria-label="发送"]',
        'button:has-text("发送")',
    ]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                btn.click()
                print(f"   点击发送按钮: {sel}")
                break
        except Exception:
            continue

    return True


def find_new_image(page, old_srcs):
    """查找新出现的大尺寸图片"""
    image_selectors = [
        'img[src*="tos-cn"]',
        'img[src*="byteimg"]',
        'img[src*="doubao"]',
        'img[src*="bytedance"]',
    ]

    for sel in image_selectors:
        try:
            images = page.locator(sel)
            count = images.count()
            for i in range(count):
                img = images.nth(i)
                src = img.get_attribute("src") or ""
                if src and src.startswith("http") and len(src) > 20 and src not in old_srcs:
                    try:
                        bbox = img.bounding_box()
                        if bbox and bbox["width"] > 150 and bbox["height"] > 150:
                            return src
                    except Exception:
                        continue
        except Exception:
            continue
    return None


def wait_for_image_and_save(page, index):
    """等待图片完全生成，点击预览获取高清图并保存"""
    print(f"⏳ 等待图片生成（超时 {TIMEOUT_IMAGE} 秒）...")

    # 记录已有的图片
    old_srcs = set()
    for sel in ['img[src*="byteimg"]', 'img[src*="tos-cn"]', 'img[src*="doubao"]']:
        try:
            imgs = page.locator(sel)
            for i in range(imgs.count()):
                s = imgs.nth(i).get_attribute("src") or ""
                if s:
                    old_srcs.add(s)
        except Exception:
            pass

    start = time.time()
    found_image = None

    # 等待新图片出现
    while time.time() - start < TIMEOUT_IMAGE:
        page.wait_for_timeout(3000)
        src = find_new_image(page, old_srcs)
        if src:
            found_image = src
            print(f"🔍 检测到新图片: {src[:80]}...")
            break
        elapsed = int(time.time() - start)
        if elapsed > 0 and elapsed % 15 == 0:
            print(f"   等待生成中... ({elapsed}s/{TIMEOUT_IMAGE}s)")

    if not found_image:
        print("❌ 未检测到生成的图片")
        return False

    # 等图片 src 稳定
    print("   确认图片生成完毕...")
    stable_count = 0
    last_src = found_image
    while stable_count < 2:
        page.wait_for_timeout(3000)
        src = find_new_image(page, old_srcs)
        current_src = src or last_src
        if current_src == last_src:
            stable_count += 1
        else:
            stable_count = 0
            last_src = current_src
            found_image = current_src
            print(f"   图片仍在更新，继续等待...")

    page.wait_for_timeout(3000)

    # ========== 点击图片打开预览，拦截高清原图响应 ==========
    print("🔍 点击图片打开预览...")
    output_path = os.path.join(OUTPUT_DIR, f"output{index}.jpg")
    saved = False

    try:
        # 收集点击后新加载的图片响应
        captured_images = []

        def on_response(response):
            url = response.url
            ct = response.headers.get("content-type", "")
            if "image" in ct and "rc_gen_image" in url and url.startswith("http"):
                try:
                    body = response.body()
                    if len(body) > 5000:
                        captured_images.append({"url": url, "body": body, "size": len(body)})
                except Exception:
                    pass

        page.on("response", on_response)

        # 点击当前生成的图
        img_el = page.locator(f'img[src="{found_image}"]').first
        img_el.click()

        # 等待预览弹窗出现
        print("   等待预览弹窗...")
        page.wait_for_timeout(5000)

        # 尝试点击"查看原图"或类似按钮
        for sel in [
            'button:has-text("查看原图")',
            'button:has-text("原图")',
            'a:has-text("查看原图")',
            'span:has-text("查看原图")',
            'text=查看原图',
        ]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    print(f"   点击「查看原图」...")
                    btn.click()
                    page.wait_for_timeout(5000)
                    break
            except Exception:
                continue

        # 等待高清图加载完成
        print("   等待高清图加载...")
        page.wait_for_timeout(8000)

        page.remove_listener("response", on_response)

        if captured_images:
            # 按大小排序，取最大的（最清晰）
            captured_images.sort(key=lambda x: x["size"], reverse=True)
            best = captured_images[0]
            print(f"   拦截到 {len(captured_images)} 张图，最大: {best['size']/1024:.0f}KB")
            with open(output_path, "wb") as f:
                f.write(best["body"])
            saved = True
            print(f"✅ 高清图已保存！ ({os.path.getsize(output_path) / 1024:.1f} KB)")

        # 关闭预览
        page.keyboard.press("Escape")
        page.wait_for_timeout(2000)

    except Exception as e:
        print(f"   预览流程异常: {e}")
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(1000)
        except Exception:
            pass

    # 兜底：直接下载原始缩略图
    if not saved:
        print("   回退：下载原始图片...")
        try:
            resp = page.request.get(found_image)
            if resp.ok:
                with open(output_path, "wb") as f:
                    f.write(resp.body())
                saved = True
                print(f"✅ 图片已保存！ ({os.path.getsize(output_path) / 1024:.1f} KB)")
        except Exception as e:
            print(f"   下载异常: {e}")

    if saved:
        print(f"📁 路径: {output_path}")
        return True
    return False


def main():
    print("=" * 60)
    print("🤖 豆包批量提问 & 保存图片")
    print("=" * 60)

    prompts = load_prompts()
    total = len(prompts)
    print(f"📋 共 {total} 条 prompt")

    clear_output_dir()

    Path(USER_DATA_DIR).mkdir(exist_ok=True)
    print(f"📂 浏览器数据目录: {USER_DATA_DIR}")

    with sync_playwright() as p:
        print("🌐 启动浏览器（持久化模式）...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        page = context.new_page()

        try:
            ensure_logged_in(page)
            close_popups(page)
            page.wait_for_timeout(1000)

            success_count = 0
            for i, prompt in enumerate(prompts, start=1):
                print(f"\n{'=' * 60}")
                print(f"📌 [{i}/{total}] Prompt: {prompt[:60]}...")
                print(f"{'=' * 60}")

                if i > 1:
                    page.goto(DOUBAO_URL, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(5000)

                if input_prompt_and_submit(page, prompt):
                    if wait_for_image_and_save(page, i):
                        success_count += 1
                    else:
                        print(f"❌ [{i}] 图片生成/保存失败")
                else:
                    print(f"❌ [{i}] 提交 prompt 失败")

            print(f"\n{'=' * 60}")
            print(f"✨ 全部完成！成功: {success_count}/{total}")
            print(f"{'=' * 60}")

        finally:
            try:
                page.wait_for_timeout(5000)
                page.close()
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
