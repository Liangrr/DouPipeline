#!/usr/bin/env python3
"""
豆包(doubao.com)自动登录、批量输入prompt、保存生成图片脚本
使用 Playwright 自动化浏览器（持久化登录状态）
"""

import json
import os
import shutil
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

# 导入账号管理模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from account_manager import (
    get_account_config_path,
    get_account_output_dir,
)

# ====== 配置 ======
DOUBAO_URL = "https://www.doubao.com/chat"
USER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "doubao_browser_profile")
TIMEOUT_IMAGE = 180
MAX_RETRY = 2  # 被拒绝时最多重试次数
REFUSAL_KEYWORDS = [
    "抱歉", "无法生成", "不能生成", "没办法生成", "生成不了",
    "我无法", "我不能", "不可以", "不符合", "违反",
    "sorry", "can't generate", "cannot generate", "unable to",
]

# 全局变量，将在 main() 中设置
ACCOUNT_NAME = "legacy"
PROMPT_FILE = None
OUTPUT_DIR = None


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


def wait_for_input_box(page, timeout=10):
    """轮询等待输入框出现，返回 True 如果找到"""
    input_selectors = [
        'textarea',
        '[contenteditable="true"]',
        'div[role="textbox"]',
        'textarea[placeholder]',
    ]
    start = time.time()
    while time.time() - start < timeout:
        for sel in input_selectors:
            try:
                if page.locator(sel).first.is_visible(timeout=1000):
                    return True
            except Exception:
                continue
        page.wait_for_timeout(1000)
    return False


def ensure_logged_in(page):
    page.goto(DOUBAO_URL, wait_until="domcontentloaded", timeout=60000)

    # 轮询检测登录状态，替代固定 8 秒等待
    if wait_for_input_box(page, timeout=10):
        print("🎉 已登录！（复用上次会话）")
        return

    print("\n" + "=" * 60)
    print("⚠️  检测到未登录，请在上方浏览器中手动登录豆包：")
    print("   登录成功后，回到这里按回车继续")
    print("=" * 60)
    input("\n✅ 登录完成后按回车继续 >>> ")

    page.reload(wait_until="domcontentloaded", timeout=60000)

    if wait_for_input_box(page, timeout=8):
        print("✅ 登录成功！")
        return

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
    # 输入完等待 3 秒再发送，防止触发人机校验
    page.wait_for_timeout(3000)

    print("🚀 发送 prompt...")
    # 先尝试点击发送按钮，比按 Enter 更可靠
    sent = False
    for sel in [
        'button[aria-label="发送"]',
        'button:has-text("发送")',
    ]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1500):
                btn.click()
                print(f"   点击发送按钮: {sel}")
                sent = True
                break
        except Exception:
            continue

    if not sent:
        page.keyboard.press("Enter")

    page.wait_for_timeout(1000)

    return True


def check_refusal(page):
    """检查豆包最新回复是否包含拒绝话术"""
    try:
        # 获取所有消息气泡（通常 AI 回复有特定 class 或 role）
        # 豆包的消息容器可能的选择器
        message_selectors = [
            '[data-testid="chat-message-content"]',
            '.message-content',
            '[class*="message"]',
            '[class*="reply"]',
            '[class*="response"]',
        ]

        all_text = ""
        for sel in message_selectors:
            try:
                msgs = page.locator(sel)
                count = msgs.count()
                if count > 0:
                    # 只看最后一条消息
                    last_msg = msgs.nth(count - 1)
                    text = last_msg.inner_text(timeout=3000)
                    if text and len(text) > 5:
                        all_text = text
                        break
            except Exception:
                continue

        if not all_text:
            # 兜底：获取页面最后出现的文本块
            try:
                # 获取所有可见文本节点
                all_text = page.locator('body').inner_text(timeout=5000)
            except Exception:
                return False

        # 检查拒绝关键词
        text_lower = all_text.lower()
        for kw in REFUSAL_KEYWORDS:
            if kw.lower() in text_lower:
                print(f"🚫 检测到拒绝关键词: 「{kw}」")
                # 截取相关上下文
                idx = text_lower.find(kw.lower())
                start = max(0, idx - 30)
                end = min(len(all_text), idx + len(kw) + 30)
                context = all_text[start:end].replace("\n", " ")
                print(f"   上下文: ...{context}...")
                return True

    except Exception as e:
        print(f"   检测拒绝时异常: {e}")

    return False


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

    # 等待新图片出现（轮询间隔从 3s 缩短到 2s）
    while time.time() - start < TIMEOUT_IMAGE:
        page.wait_for_timeout(2000)
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

    # 等图片 src 稳定（从 2 次×3s 缩短到 1 次×2s）
    print("   确认图片生成完毕...")
    page.wait_for_timeout(2000)

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
        page.wait_for_timeout(2000)

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
                if btn.is_visible(timeout=1500):
                    print(f"   点击「查看原图」...")
                    btn.click()
                    page.wait_for_timeout(3000)
                    break
            except Exception:
                continue

        # 等待高清图加载完成
        print("   等待高清图加载...")
        page.wait_for_timeout(4000)

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
        page.wait_for_timeout(1000)

    except Exception as e:
        print(f"   预览流程异常: {e}")
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
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
    global ACCOUNT_NAME, PROMPT_FILE, OUTPUT_DIR

    # 解析命令行参数
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--account" and i + 1 < len(args):
            ACCOUNT_NAME = args[i + 1]
            i += 2
        elif args[i] in ("-h", "--help"):
            print("用法: python doubao.py [--account NAME]")
            sys.exit(0)
        else:
            i += 1

    # 设置账号专属路径
    PROMPT_FILE = get_account_config_path(ACCOUNT_NAME)
    OUTPUT_DIR = get_account_output_dir(ACCOUNT_NAME)

    print("=" * 60)
    print(f"🤖 豆包批量提问 & 保存图片  [账号: {ACCOUNT_NAME}]")
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

            success_count = 0
            skip_count = 0
            for i, prompt in enumerate(prompts, start=1):
                print(f"\n{'=' * 60}")
                print(f"📌 [{i}/{total}] Prompt: {prompt[:60]}...")
                print(f"{'=' * 60}")

                if i > 1:
                    page.goto(DOUBAO_URL, wait_until="domcontentloaded", timeout=60000)
                    wait_for_input_box(page, timeout=8)

                # --- 重试逻辑 ---
                retry_suffixes = [
                    "",
                    "",
                ]
                current_prompt = prompt
                saved = False

                for attempt in range(MAX_RETRY + 1):
                    if attempt > 0:
                        suffix = retry_suffixes[(attempt - 1) % len(retry_suffixes)]
                        current_prompt = prompt + suffix
                        print(f"\n🔄 第 {attempt} 次重试: {current_prompt[:60]}...")
                        # 开一个新对话
                        page.goto(DOUBAO_URL, wait_until="domcontentloaded", timeout=60000)
                        wait_for_input_box(page, timeout=8)

                    if not input_prompt_and_submit(page, current_prompt):
                        print(f"❌ [{i}] 提交 prompt 失败")
                        break

                    # 等待豆包回复（轮询检查，替代固定 12 秒）
                    print("   等待豆包回复...")
                    refused = False
                    for poll_i in range(3):  # 最多 3 次 × 4 秒 = 12 秒
                        page.wait_for_timeout(4000)
                        if check_refusal(page):
                            refused = True
                            break
                        # 如果图片已经出现了，说明没有拒绝
                        old_srcs_check = set()
                        if find_new_image(page, old_srcs_check):
                            print(f"   已检测到图片，跳过剩余检查")
                            break
                        print(f"   等待中... ({(poll_i + 1) * 4}s/12s)")

                    if refused:
                        print(f"⚠️ [{i}] 豆包拒绝生成 (attempt {attempt + 1}/{MAX_RETRY + 1})")
                        if attempt < MAX_RETRY:
                            print("   将尝试换一种描述方式重试...")
                            continue
                        else:
                            print(f"⏭️ [{i}] 重试 {MAX_RETRY} 次仍被拒绝，跳过此 prompt")
                            skip_count += 1
                            break

                    # 没被拒绝，等待图片生成
                    if wait_for_image_and_save(page, i):
                        success_count += 1
                        saved = True
                        break
                    else:
                        print(f"⚠️ [{i}] 图片生成超时 (attempt {attempt + 1}/{MAX_RETRY + 1})")
                        if attempt < MAX_RETRY:
                            print("   将重试...")
                            continue

                if not saved and not skip_count:
                    print(f"❌ [{i}] 图片生成/保存失败（已重试）")

            print(f"\n{'=' * 60}")
            print(f"✨ 全部完成！成功: {success_count}/{total}", end="")
            if skip_count:
                print(f"，跳过: {skip_count}")
            else:
                print()
            print(f"{'=' * 60}")

        finally:
            try:
                page.wait_for_timeout(1000)
                page.close()
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
