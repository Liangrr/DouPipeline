#!/usr/bin/env python3
"""
豆包(doubao.com)自动登录、批量输入prompt、保存生成图片脚本
使用 Playwright 自动化浏览器（持久化登录状态）
"""

import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path
from PIL import Image
from playwright.async_api import async_playwright, Page, BrowserContext

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
MIN_IMAGES_REQUIRED = 1  # 最少需要生成的图片数量
DEFAULT_IMAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_cover.jpg")
REFUSAL_KEYWORDS = [
    "抱歉", "无法生成", "不能生成", "没办法生成", "生成不了",
    "我无法", "我不能", "不可以", "不符合", "违反",
    "sorry", "can't generate", "cannot generate", "unable to",
]


def load_prompts(prompt_file: str) -> list:
    with open(prompt_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    prompts = data["prompt"]
    if isinstance(prompts, str):
        prompts = [prompts]
    return prompts


def clear_output_dir(output_dir: str):
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    print(f"🧹 已清空输出目录: {output_dir}")


async def wait_for_input_box(page: Page, timeout: float = 10) -> bool:
    """轮询等待输入框出现"""
    input_selectors = [
        'textarea',
        '[contenteditable="true"]',
        'div[role="textbox"]',
        'textarea[placeholder]',
    ]
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        for sel in input_selectors:
            try:
                if await page.locator(sel).first.is_visible(timeout=1000):
                    return True
            except Exception:
                continue
        await page.wait_for_timeout(1000)
    return False


async def ensure_logged_in(page: Page):
    await page.goto(DOUBAO_URL, wait_until="domcontentloaded", timeout=60000)

    if await wait_for_input_box(page, timeout=10):
        print("🎉 已登录！（复用上次会话）")
        return

    print("\n" + "=" * 60)
    print("⚠️  检测到未登录，请在上方浏览器中手动登录豆包：")
    print("   登录成功后，回到这里按回车继续")
    print("=" * 60)
    input("\n✅ 登录完成后按回车继续 >>> ")

    await page.reload(wait_until="domcontentloaded", timeout=60000)

    if await wait_for_input_box(page, timeout=8):
        print("✅ 登录成功！")
        return

    raise RuntimeError("❌ 登录失败，请重新运行脚本")


async def close_popups(page: Page):
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
            if await btn.is_visible(timeout=1500):
                await btn.click()
                await page.wait_for_timeout(500)
        except Exception:
            continue


async def input_prompt_and_submit(page: Page, prompt: str) -> bool:
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
            if await loc.is_visible(timeout=3000):
                input_box = loc
                print(f"   找到输入框: {sel}")
                break
        except Exception:
            continue

    if not input_box:
        print("❌ 未找到输入框")
        return False

    await input_box.click()
    await page.wait_for_timeout(500)
    await page.keyboard.press("Control+a")
    await page.wait_for_timeout(100)
    await page.keyboard.press("Delete")
    await page.wait_for_timeout(300)

    print(f"   正在键入 prompt（{len(prompt)} 字符）...")
    await page.keyboard.type(prompt, delay=10)
    # 输入完等待 3 秒再发送，防止触发人机校验
    await page.wait_for_timeout(3000)

    print("🚀 发送 prompt...")
    sent = False
    for sel in [
        'button[aria-label="发送"]',
        'button:has-text("发送")',
    ]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1500):
                await btn.click()
                print(f"   点击发送按钮: {sel}")
                sent = True
                break
        except Exception:
            continue

    if not sent:
        await page.keyboard.press("Enter")

    await page.wait_for_timeout(1000)

    return True


async def check_refusal(page: Page) -> bool:
    """检查豆包最新回复是否包含拒绝话术"""
    try:
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
                count = await msgs.count()
                if count > 0:
                    last_msg = msgs.nth(count - 1)
                    text = await last_msg.inner_text(timeout=3000)
                    if text and len(text) > 5:
                        all_text = text
                        break
            except Exception:
                continue

        if not all_text:
            try:
                all_text = await page.locator('body').inner_text(timeout=5000)
            except Exception:
                return False

        text_lower = all_text.lower()
        for kw in REFUSAL_KEYWORDS:
            if kw.lower() in text_lower:
                print(f"🚫 检测到拒绝关键词: 「{kw}」")
                idx = text_lower.find(kw.lower())
                start = max(0, idx - 30)
                end = min(len(all_text), idx + len(kw) + 30)
                context = all_text[start:end].replace("\n", " ")
                print(f"   上下文: ...{context}...")
                return True

    except Exception as e:
        print(f"   检测拒绝时异常: {e}")

    return False


async def find_new_image(page: Page, old_srcs: set) -> str | None:
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
            count = await images.count()
            for i in range(count):
                img = images.nth(i)
                src = await img.get_attribute("src") or ""
                if src and src.startswith("http") and len(src) > 20 and src not in old_srcs:
                    try:
                        bbox = await img.bounding_box()
                        if bbox and bbox["width"] > 150 and bbox["height"] > 150:
                            return src
                    except Exception:
                        continue
        except Exception:
            continue
    return None


def remove_watermark(image_path: str) -> bool:
    """裁切图片左上角水印区域"""
    try:
        img = Image.open(image_path)
        w, h = img.size
        crop_w = int(w * 0.12)
        crop_h = int(h * 0.06)
        cropped = img.crop((crop_w, crop_h, w, h))
        cropped.save(image_path, quality=95)
        print(f"   ✂️ 已裁切左上角水印 ({crop_w}×{crop_h}px)")
        return True
    except Exception as e:
        print(f"   ⚠️ 去水印失败: {e}")
        return False


async def wait_for_image_and_save(page: Page, index: int, output_dir: str) -> bool:
    """等待图片完全生成，点击预览获取高清图并保存"""
    print(f"⏳ 等待图片生成（超时 {TIMEOUT_IMAGE} 秒）...")

    # 记录已有的图片
    old_srcs = set()
    for sel in ['img[src*="byteimg"]', 'img[src*="tos-cn"]', 'img[src*="doubao"]']:
        try:
            imgs = page.locator(sel)
            for i in range(await imgs.count()):
                s = await imgs.nth(i).get_attribute("src") or ""
                if s:
                    old_srcs.add(s)
        except Exception:
            pass

    start = time.monotonic()
    found_image = None

    while time.monotonic() - start < TIMEOUT_IMAGE:
        await page.wait_for_timeout(2000)
        src = await find_new_image(page, old_srcs)
        if src:
            found_image = src
            print(f"🔍 检测到新图片: {src[:80]}...")
            break
        elapsed = int(time.monotonic() - start)
        if elapsed > 0 and elapsed % 15 == 0:
            print(f"   等待生成中... ({elapsed}s/{TIMEOUT_IMAGE}s)")

    if not found_image:
        print("❌ 未检测到生成的图片")
        return False

    print("   确认图片生成完毕...")
    await page.wait_for_timeout(2000)

    # ========== 点击图片打开预览，拦截高清原图响应 ==========
    print("🔍 点击图片打开预览...")
    output_path = os.path.join(output_dir, f"output{index}.jpg")
    saved = False

    try:
        captured_images = []

        async def on_response(response):
            url = response.url
            ct = response.headers.get("content-type", "")
            if "image" in ct and "rc_gen_image" in url and url.startswith("http"):
                try:
                    body = await response.body()
                    if len(body) > 5000:
                        captured_images.append({"url": url, "body": body, "size": len(body)})
                except Exception:
                    pass

        page.on("response", on_response)

        img_el = page.locator(f'img[src="{found_image}"]').first
        await img_el.click()

        print("   等待预览弹窗...")
        await page.wait_for_timeout(2000)

        for sel in [
            'button:has-text("查看原图")',
            'button:has-text("原图")',
            'a:has-text("查看原图")',
            'span:has-text("查看原图")',
            'text=查看原图',
        ]:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=1500):
                    print(f"   点击「查看原图」...")
                    await btn.click()
                    await page.wait_for_timeout(3000)
                    break
            except Exception:
                continue

        print("   等待高清图加载...")
        await page.wait_for_timeout(4000)

        page.remove_listener("response", on_response)

        if captured_images:
            captured_images.sort(key=lambda x: x["size"], reverse=True)
            best = captured_images[0]
            print(f"   拦截到 {len(captured_images)} 张图，最大: {best['size']/1024:.0f}KB")
            with open(output_path, "wb") as f:
                f.write(best["body"])
            saved = True
            print(f"✅ 高清图已保存！ ({os.path.getsize(output_path) / 1024:.1f} KB)")
            remove_watermark(output_path)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(1000)

    except Exception as e:
        print(f"   预览流程异常: {e}")
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
        except Exception:
            pass

    # 兜底：直接下载原始缩略图
    if not saved:
        print("   回退：下载原始图片...")
        try:
            resp = await page.request.get(found_image)
            if resp.ok:
                with open(output_path, "wb") as f:
                    f.write(await resp.body())
                saved = True
                print(f"✅ 图片已保存！ ({os.path.getsize(output_path) / 1024:.1f} KB)")
                remove_watermark(output_path)
        except Exception as e:
            print(f"   下载异常: {e}")

    if saved:
        print(f"📁 路径: {output_path}")
        return True
    return False


def simplify_prompt(prompt: str) -> str:
    """简化 prompt，移除可能触发拒绝的敏感词"""
    replacements = {
        "比基尼": "泳装",
        "泳衣": "夏日服装",
        "露背": "时尚设计",
        "性感": "优雅",
        "身材": "气质",
        "曲线": "身姿",
        "胸部": "",
        "丰满": "匀称",
        "纤细": "修长",
    }

    simplified = prompt
    for old, new in replacements.items():
        simplified = simplified.replace(old, new)

    if len(simplified) > 300:
        parts = simplified.split("，")
        if len(parts) > 6:
            simplified = "，".join(parts[:4]) + "，" + "，".join(parts[-2:])

    return simplified


def use_default_image(output_dir: str, index: int) -> bool:
    """使用默认图片作为兜底"""
    output_path = os.path.join(output_dir, f"output{index}.jpg")

    if os.path.exists(DEFAULT_IMAGE_PATH):
        shutil.copy2(DEFAULT_IMAGE_PATH, output_path)
        print(f"📌 使用默认图片: {DEFAULT_IMAGE_PATH}")
        return True

    print(f"⚠️ 默认图片不存在，跳过: {index}")
    return False


def check_and_fill_images(output_dir: str, total_prompts: int, success_count: int):
    """检查图片数量，不足时使用默认图片填充"""
    if success_count < MIN_IMAGES_REQUIRED:
        print(f"\n⚠️ 图片数量不足: {success_count}/{MIN_IMAGES_REQUIRED}")
        print("   尝试使用默认图片填充...")

        for i in range(1, total_prompts + 1):
            output_path = os.path.join(output_dir, f"output{i}.jpg")
            if not os.path.exists(output_path):
                use_default_image(output_dir, i)


def save_failed_prompts(output_dir: str, failed_prompts: list):
    """保存失败的 prompt 信息"""
    if not failed_prompts:
        return

    failed_file = os.path.join(output_dir, "failed_prompts.json")
    with open(failed_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(failed_prompts),
            "prompts": failed_prompts
        }, f, ensure_ascii=False, indent=2)
    print(f"📝 失败的 prompt 已保存到: {failed_file}")


async def run_doubao(account_name: str = "legacy"):
    """主执行函数：登录豆包，批量生成图片"""
    prompt_file = get_account_config_path(account_name)
    output_dir = get_account_output_dir(account_name)

    print("=" * 60)
    print(f"🤖 豆包批量提问 & 保存图片  [账号: {account_name}]")
    print("=" * 60)

    prompts = load_prompts(prompt_file)
    total = len(prompts)
    print(f"📋 共 {total} 条 prompt")

    clear_output_dir(output_dir)

    Path(USER_DATA_DIR).mkdir(exist_ok=True)
    print(f"📂 浏览器数据目录: {USER_DATA_DIR}")

    async with async_playwright() as p:
        print("🌐 启动浏览器（持久化模式）...")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        page = await context.new_page()

        try:
            await ensure_logged_in(page)
            await close_popups(page)

            success_count = 0
            skip_count = 0
            failed_prompts = []

            for i, prompt in enumerate(prompts, start=1):
                print(f"\n{'=' * 60}")
                print(f"📌 [{i}/{total}] Prompt: {prompt[:60]}...")
                print(f"{'=' * 60}")

                if i > 1:
                    await page.goto(DOUBAO_URL, wait_until="domcontentloaded", timeout=60000)
                    await wait_for_input_box(page, timeout=8)

                # --- 重试逻辑 ---
                current_prompt = prompt
                saved = False

                for attempt in range(MAX_RETRY + 1):
                    if attempt > 0:
                        current_prompt = simplify_prompt(prompt)
                        print(f"\n🔄 第 {attempt} 次重试（简化 prompt）: {current_prompt[:60]}...")
                        await page.goto(DOUBAO_URL, wait_until="domcontentloaded", timeout=60000)
                        await wait_for_input_box(page, timeout=8)

                    if not await input_prompt_and_submit(page, current_prompt):
                        print(f"❌ [{i}] 提交 prompt 失败")
                        break

                    # 等待豆包回复
                    print("   等待豆包回复...")
                    refused = False
                    for poll_i in range(3):
                        await page.wait_for_timeout(4000)
                        if await check_refusal(page):
                            refused = True
                            break
                        old_srcs_check = set()
                        if await find_new_image(page, old_srcs_check):
                            print(f"   已检测到图片，跳过剩余检查")
                            break
                        print(f"   等待中... ({(poll_i + 1) * 4}s/12s)")

                    if refused:
                        print(f"⚠️ [{i}] 豆包拒绝生成 (attempt {attempt + 1}/{MAX_RETRY + 1})")
                        if attempt < MAX_RETRY:
                            print("   将尝试简化 prompt 重试...")
                            continue
                        else:
                            print(f"⏭️ [{i}] 重试 {MAX_RETRY} 次仍被拒绝，跳过此 prompt")
                            failed_prompts.append({"index": i, "prompt": prompt, "reason": "rejected"})
                            skip_count += 1
                            break

                    if await wait_for_image_and_save(page, i, output_dir):
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
                    failed_prompts.append({"index": i, "prompt": prompt, "reason": "timeout"})

            check_and_fill_images(output_dir, total, success_count)
            save_failed_prompts(output_dir, failed_prompts)

            print(f"\n{'=' * 60}")
            print(f"✨ 全部完成！成功: {success_count}/{total}", end="")
            if skip_count:
                print(f"，跳过: {skip_count}")
            else:
                print()
            if failed_prompts:
                print(f"⚠️ {len(failed_prompts)} 条 prompt 失败，已保存到 failed_prompts.json")
            print(f"{'=' * 60}")

        finally:
            try:
                await page.wait_for_timeout(1000)
                await page.close()
            except Exception:
                pass
            try:
                await context.close()
            except Exception:
                pass


async def main():
    """独立运行入口"""
    args = sys.argv[1:]
    account_name = "legacy"
    i = 0
    while i < len(args):
        if args[i] == "--account" and i + 1 < len(args):
            account_name = args[i + 1]
            i += 2
        elif args[i] in ("-h", "--help"):
            print("用法: python doubao.py [--account NAME]")
            sys.exit(0)
        else:
            i += 1

    await run_doubao(account_name)


if __name__ == "__main__":
    asyncio.run(main())
