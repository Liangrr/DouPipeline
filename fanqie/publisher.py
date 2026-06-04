"""
番茄小说自动发布模块

通过 Playwright 浏览器自动化，将小说内容发布到番茄小说创作者后台。
与抖音/小红书发布模块采用相同的架构模式。

使用方法:
    python -m fanqie.publisher --book-dir novels/都市重生 --account legacy
    python -m fanqie.publisher --book-dir novels/都市重生 --only create    # 只创建书籍
    python -m fanqie.publisher --book-dir novels/都市重生 --only publish   # 只发布章节
"""

import os
import json
import sys
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

# 导入账号管理模块
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..')))
from account_manager import (
    PROJECT_ROOT,
    get_account_dir,
    get_account_browser_profile,
    get_account_novels_dir,
    ensure_account_exists,
)

# 导入小说生成模块
from novel_generator import load_architecture, load_chapter, list_chapters

# ==================== 配置区 ====================
WRITER_URL = "https://fanqienovel.com/main/writer/"
CREATE_BOOK_URL = "https://fanqienovel.com/main/writer/create"


def load_publish_state(book_dir: str) -> dict:
    """加载发布状态"""
    state_path = os.path.join(book_dir, "publish_state.json")
    if os.path.exists(state_path):
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"book_id": None, "published_chapters": [], "last_publish_time": None}


def save_publish_state(book_dir: str, state: dict):
    """保存发布状态"""
    state_path = os.path.join(book_dir, "publish_state.json")
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ==================== 登录检测 ====================

async def ensure_logged_in(page):
    """检查登录状态，未登录则等待用户手动登录"""
    await page.goto(WRITER_URL, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(3000)

    # 轮询检测登录状态
    for _ in range(6):
        await page.wait_for_timeout(1000)
        page_text = await page.content()
        if any(kw in page_text for kw in ["作家专区", "作品管理", "我的作品", "创建作品", "写新章节"]):
            print("🎉 已登录番茄小说创作者后台！")
            return

    # 再次检查
    page_text = await page.content()
    is_logged_in = any(kw in page_text for kw in ["作家专区", "作品管理", "我的作品", "创建作品", "写新章节"])

    if is_logged_in:
        print("🎉 已登录番茄小说创作者后台！")
        return

    # 未登录 → 等待用户手动登录
    print("\n" + "=" * 50)
    print("⚠️  检测到未登录，请在上方浏览器中完成以下操作：")
    print("   1. 登录番茄小说创作者后台")
    print("   2. 支持手机号、抖音账号等方式登录")
    print("   3. 登录成功后，回到这里按回车")
    print("=" * 50)
    input("\n✅ 登录完成后按回车继续 >>> ")

    # 验证登录
    await page.reload(wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(3000)
    page_text = await page.content()
    is_logged_in = any(kw in page_text for kw in ["作家专区", "作品管理", "我的作品", "创建作品", "写新章节"])

    if not is_logged_in:
        raise RuntimeError("❌ 登录失败，请重新运行脚本")

    print("✅ 登录成功！")


# ==================== 创建新书 ====================

async def create_book(page, architecture: dict) -> str:
    """
    创建新小说

    Args:
        page: Playwright page 对象
        architecture: 小说架构字典

    Returns:
        创建成功后的页面 URL（含 book_id）
    """
    book_name = architecture.get("book_name", "未命名小说")
    summary = architecture.get("summary", "")
    category = architecture.get("category", "")
    gender = architecture.get("gender", "male")

    print(f"\n📚 创建新书: {book_name}")
    print(f"   分类: {category} | {'男频' if gender == 'male' else '女频'}")

    # 导航到创建页面
    await page.goto(CREATE_BOOK_URL, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(3000)

    # 步骤1：填写书名
    print("  📝 填写书名...")
    try:
        name_input = page.locator('input[placeholder*="书名"], input[placeholder*="作品名"], input[placeholder*="标题"]').first
        await name_input.wait_for(state="visible", timeout=10000)
        await name_input.click()
        await name_input.fill("")
        await name_input.fill(book_name)
        print(f"    ✅ 书名已填入: {book_name}")
    except Exception as e:
        print(f"    ⚠️ 书名填写失败: {e}")

    await page.wait_for_timeout(1000)

    # 步骤2：选择分类
    if category:
        print(f"  📝 选择分类: {category}")
        try:
            # 尝试点击分类选择器
            category_trigger = page.locator('text=请选择分类, text=选择分类, [class*="category"]').first
            if await category_trigger.is_visible(timeout=3000):
                await category_trigger.click()
                await page.wait_for_timeout(2000)

                # 在下拉列表中查找匹配的分类
                category_option = page.get_by_text(category, exact=False).first
                if await category_option.is_visible(timeout=3000):
                    await category_option.click()
                    print(f"    ✅ 分类已选择: {category}")
                else:
                    print(f"    ⚠️ 未找到分类: {category}")
            else:
                print("    ⚠️ 未找到分类选择器")
        except Exception as e:
            print(f"    ⚠️ 分类选择失败: {e}")

    await page.wait_for_timeout(1000)

    # 步骤3：填写简介
    if summary:
        print("  📝 填写简介...")
        try:
            summary_input = page.locator(
                'textarea[placeholder*="简介"], textarea[placeholder*="简介"], '
                'textarea[placeholder*="描述"], [contenteditable="true"]'
            ).first
            if await summary_input.is_visible(timeout=5000):
                await summary_input.click()
                await summary_input.fill("")
                await summary_input.fill(summary[:500])  # 限制长度
                print(f"    ✅ 简介已填入 ({len(summary)} 字)")
            else:
                print("    ⚠️ 未找到简介输入框")
        except Exception as e:
            print(f"    ⚠️ 简介填写失败: {e}")

    await page.wait_for_timeout(1000)

    # 步骤4：选择目标读者（男频/女频）
    print(f"  📝 选择目标读者: {'男频' if gender == 'male' else '女频'}")
    try:
        gender_text = "男频" if gender == "male" else "女频"
        gender_btn = page.get_by_text(gender_text, exact=False).first
        if await gender_btn.is_visible(timeout=3000):
            await gender_btn.click()
            print(f"    ✅ 已选择: {gender_text}")
        else:
            # 可能是 男/女 选项
            gender_short = "男" if gender == "male" else "女"
            gender_btn = page.get_by_text(gender_short, exact=True).first
            if await gender_btn.is_visible(timeout=3000):
                await gender_btn.click()
                print(f"    ✅ 已选择: {gender_short}")
    except Exception as e:
        print(f"    ⚠️ 读者选择失败: {e}")

    await page.wait_for_timeout(1000)

    # 步骤5：点击创建/确认按钮
    print("  📝 点击创建...")
    created = False
    for btn_text in ["创建", "创建作品", "确认", "确定", "提交", "开始创作"]:
        try:
            btn = page.get_by_text(btn_text, exact=True).first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                print(f"    ✅ 已点击「{btn_text}」")
                created = True
                break
        except Exception:
            pass

    if not created:
        # 尝试 button 选择器
        try:
            btn = page.locator('button:has-text("创建"), button:has-text("确认"), button:has-text("提交")').first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                print("    ✅ 已通过选择器点击创建")
                created = True
        except Exception:
            pass

    if not created:
        print("    ⚠️ 未找到创建按钮，请手动点击")

    # 等待创建完成
    await page.wait_for_timeout(5000)

    # 检查是否创建成功（页面应该跳转到作品管理或章节管理页面）
    current_url = page.url
    print(f"  📍 当前页面: {current_url}")

    print("✅ 书籍创建完成！")
    return current_url


# ==================== 发布章节 ====================

async def publish_chapter(page, chapter: dict, architecture: dict):
    """
    发布单个章节

    Args:
        page: Playwright page 对象
        chapter: 章节字典 {chapter_num, title, content}
        architecture: 小说架构字典
    """
    chapter_num = chapter.get("chapter_num", 0)
    title = chapter.get("title", f"第{chapter_num}章")
    content = chapter.get("content", "")

    print(f"\n📝 发布第 {chapter_num} 章: {title}")
    print(f"   内容长度: {len(content)} 字")

    # 步骤1：点击"写新章节"或"新建章节"
    print("  📝 点击「写新章节」...")
    clicked = False
    for btn_text in ["写新章节", "新建章节", "新增章节", "添加章节", "创建章节"]:
        try:
            btn = page.get_by_text(btn_text, exact=False).first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                print(f"    ✅ 已点击「{btn_text}」")
                clicked = True
                break
        except Exception:
            pass

    if not clicked:
        # 尝试通过链接或按钮选择器
        try:
            btn = page.locator('a:has-text("章节"), button:has-text("章节"), [class*="chapter"] button').first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                print("    ✅ 已通过选择器点击")
                clicked = True
        except Exception:
            pass

    if not clicked:
        print("    ⚠️ 未找到新建章节按钮，请手动操作")
        input("    操作完成后按回车继续 >>> ")

    await page.wait_for_timeout(3000)

    # 步骤2：填写章节标题
    print(f"  📝 填写标题: {title}")
    try:
        title_input = page.locator(
            'input[placeholder*="标题"], input[placeholder*="章节"], '
            'textarea[placeholder*="标题"], textarea[placeholder*="章节"]'
        ).first
        if await title_input.is_visible(timeout=5000):
            await title_input.click()
            await title_input.fill("")
            await title_input.fill(title)
            print("    ✅ 标题已填入")
        else:
            print("    ⚠️ 未找到标题输入框")
    except Exception as e:
        print(f"    ⚠️ 标题填写失败: {e}")

    await page.wait_for_timeout(1000)

    # 步骤3：填写章节正文
    print("  📝 填写正文...")
    try:
        # 尝试多种编辑器选择器
        editor = None
        selectors = [
            '[contenteditable="true"]',
            'textarea[placeholder*="正文"], textarea[placeholder*="内容"]',
            '.ql-editor',  # Quill 编辑器
            '.ProseMirror',  # ProseMirror 编辑器
            '[class*="editor"] [contenteditable]',
            '[class*="content"] textarea',
        ]

        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    editor = el
                    break
            except Exception:
                continue

        if editor:
            await editor.click()
            await page.keyboard.press("Control+a")
            await page.keyboard.press("Delete")
            await page.keyboard.insert_text(content)
            await page.wait_for_timeout(500)
            print(f"    ✅ 正文已填入 ({len(content)} 字)")
        else:
            print("    ⚠️ 未找到正文编辑器，请手动输入")
            input("    操作完成后按回车继续 >>> ")
    except Exception as e:
        print(f"    ⚠️ 正文填写失败: {e}")

    await page.wait_for_timeout(2000)

    # 步骤4：点击发布/存为草稿
    print("  📝 点击发布...")
    published = False
    for btn_text in ["发布", "发布章节", "发表", "立即发布", "提交发布"]:
        try:
            btn = page.get_by_text(btn_text, exact=True).first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                print(f"    ✅ 已点击「{btn_text}」")
                published = True
                break
        except Exception:
            pass

    if not published:
        try:
            btn = page.locator('button:has-text("发布"), button:has-text("发表"), button:has-text("提交")').first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                print("    ✅ 已通过选择器点击发布")
                published = True
        except Exception:
            pass

    if not published:
        print("    ⚠️ 未找到发布按钮，请手动点击")
        input("    操作完成后按回车继续 >>> ")

    # 处理确认弹窗
    await page.wait_for_timeout(2000)
    for confirm_text in ["确认发布", "确认", "确定", "好的"]:
        try:
            confirm_btn = page.get_by_text(confirm_text, exact=True).first
            if await confirm_btn.is_visible(timeout=2000):
                await confirm_btn.click()
                print(f"    ✅ 已确认「{confirm_text}」")
                break
        except Exception:
            pass

    # 等待发布结果
    await page.wait_for_timeout(3000)
    print(f"  ✅ 第 {chapter_num} 章发布完成！")


# ==================== 主入口 ====================

async def publish(book_dir: str, account_name: str = "legacy", only: str = None):
    """
    主入口：将小说发布到番茄小说

    Args:
        book_dir: 小说数据目录（包含 architecture.json 和 chapter_*.json）
        account_name: 账号名称
        only: 只执行某个操作 ("create" = 只创建书籍, "publish" = 只发布章节)
    """
    # 确保账号存在
    ensure_account_exists(account_name)

    # 加载小说架构
    architecture = load_architecture(book_dir)
    book_name = architecture.get("book_name", "未命名小说")
    print(f"📖 小说: {book_name}")

    # 加载已有的章节
    chapter_nums = list_chapters(book_dir)
    if not chapter_nums:
        print("❌ 没有找到已生成的章节，请先运行内容生成")
        return

    print(f"📚 已生成 {len(chapter_nums)} 章: 第{chapter_nums[0]}章 ~ 第{chapter_nums[-1]}章")

    # 加载发布状态
    state = load_publish_state(book_dir)

    # 过滤出未发布的章节
    if only != "create":
        unpublished = [n for n in chapter_nums if n not in state.get("published_chapters", [])]
        if not unpublished:
            print("✅ 所有章节已发布，无需操作")
            return
        print(f"📤 待发布 {len(unpublished)} 章: 第{unpublished[0]}章 ~ 第{unpublished[-1]}章")

    # 浏览器数据目录（复用账号的 browser_profile）
    user_data_dir = get_account_browser_profile(account_name)
    Path(user_data_dir).mkdir(exist_ok=True)
    print(f"📂 浏览器数据目录: {user_data_dir}")

    # 启动浏览器
    print("\n🌐 正在启动浏览器...")
    p = await async_playwright().start()
    context = await p.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=False,
    )

    # 劫持 attachShadow
    await context.add_init_script("""
        const original = Element.prototype.attachShadow;
        Element.prototype.attachShadow = function(opts) {
            if (opts && opts.mode === 'closed') {
                opts.mode = 'open';
            }
            return original.call(this, opts);
        };
    """)

    # 反 webdriver 检测
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)

    page = await context.new_page()

    try:
        # 登录检测
        await ensure_logged_in(page)

        # 创建书籍
        if only != "publish":
            if state.get("book_id"):
                print(f"\n📚 书籍已创建 (ID: {state['book_id']})，跳过创建步骤")
            else:
                await create_book(page, architecture)
                # 保存当前 URL 作为 book_id 标识
                state["book_id"] = page.url
                save_publish_state(book_dir, state)

        if only == "create":
            print("\n✅ 书籍创建完成！")
            return

        # 发布章节
        for chapter_num in unpublished:
            chapter = load_chapter(book_dir, chapter_num)
            await publish_chapter(page, chapter, architecture)

            # 更新发布状态
            state["published_chapters"].append(chapter_num)
            state["published_chapters"].sort()
            from datetime import datetime
            state["last_publish_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_publish_state(book_dir, state)

            # 章节间延迟，避免触发风控
            if chapter_num != unpublished[-1]:
                print("  ⏳ 等待 5 秒后发布下一章...")
                await page.wait_for_timeout(5000)

        print(f"\n🎉 全部 {len(unpublished)} 章发布完成！")

    finally:
        await page.close()
        await context.close()
        await p.stop()


# ==================== CLI 入口 ====================

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="番茄小说自动发布工具")
    parser.add_argument("--book-dir", required=True, help="小说数据目录")
    parser.add_argument("--account", default="legacy", help="账号名称 (默认: legacy)")
    parser.add_argument("--only", choices=["create", "publish"], help="只执行某步 (create=创建书籍, publish=发布章节)")
    args = parser.parse_args()

    book_dir = args.book_dir
    if not os.path.isabs(book_dir):
        book_dir = os.path.join(PROJECT_ROOT, book_dir)

    await publish(book_dir, account_name=args.account, only=args.only)


if __name__ == "__main__":
    asyncio.run(main())
