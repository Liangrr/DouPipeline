"""
账号管理模块 - 管理多账号的目录结构和配置
"""
import os
import shutil
from pathlib import Path

# ==================== 配置区 ====================
PROJECT_ROOT = os.path.normpath(os.path.dirname(os.path.abspath(__file__)))
ACCOUNTS_ROOT = os.path.join(PROJECT_ROOT, "accounts")
LEGACY_ACCOUNT_NAME = "legacy"

# 遗留的单账号目录
LEGACY_BROWSER_PROFILE = os.path.join(PROJECT_ROOT, "byte_browser_profile")
LEGACY_DOUBAO_JSON = os.path.join(PROJECT_ROOT, "doubao.json")
LEGACY_DOUBAO_OUTPUT = os.path.join(PROJECT_ROOT, "doubao_output")


def get_account_dir(account_name: str) -> str:
    """获取账号目录的绝对路径"""
    return os.path.join(ACCOUNTS_ROOT, account_name)


def get_account_browser_profile(account_name: str) -> str:
    """获取账号的浏览器 profile 目录"""
    return os.path.join(get_account_dir(account_name), "browser_profile")


def get_account_config_path(account_name: str) -> str:
    """获取账号的配置文件路径（doubao.json）"""
    return os.path.join(get_account_dir(account_name), "doubao.json")


def get_account_output_dir(account_name: str) -> str:
    """获取账号的图片输出目录"""
    return os.path.join(get_account_dir(account_name), "doubao_output")


def get_account_backup_dir(account_name: str) -> str:
    """获取账号的备份目录"""
    return os.path.join(get_account_dir(account_name), "backups")


def list_accounts() -> list:
    """列出所有已创建的账号"""
    if not os.path.exists(ACCOUNTS_ROOT):
        return []

    accounts = []
    for name in os.listdir(ACCOUNTS_ROOT):
        account_path = os.path.join(ACCOUNTS_ROOT, name)
        if os.path.isdir(account_path):
            # 检查是否有浏览器 profile（表示已登录）
            browser_profile = get_account_browser_profile(name)
            has_login = os.path.exists(browser_profile) and len(os.listdir(browser_profile)) > 0
            accounts.append({
                "name": name,
                "path": account_path,
                "has_login": has_login,
            })

    return accounts


def create_account(account_name: str) -> str:
    """创建新账号目录结构"""
    if not account_name:
        raise ValueError("账号名称不能为空")

    # 检查账号名称是否合法（只允许字母、数字、下划线、连字符）
    if not all(c.isalnum() or c in ['_', '-'] for c in account_name):
        raise ValueError("账号名称只能包含字母、数字、下划线和连字符")

    account_dir = get_account_dir(account_name)

    if os.path.exists(account_dir):
        raise FileExistsError(f"账号 '{account_name}' 已存在")

    # 创建账号目录结构
    Path(account_dir).mkdir(parents=True, exist_ok=True)
    Path(get_account_browser_profile(account_name)).mkdir(exist_ok=True)
    Path(get_account_output_dir(account_name)).mkdir(exist_ok=True)

    # 创建空的配置文件
    config_path = get_account_config_path(account_name)
    if not os.path.exists(config_path):
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write('{}')

    print(f"✅ 账号 '{account_name}' 创建成功")
    print(f"   目录: {account_dir}")
    return account_dir


def ensure_account_exists(account_name: str):
    """确保账号存在，不存在则抛出异常"""
    if account_name == LEGACY_ACCOUNT_NAME:
        # legacy 账号特殊处理：如果不存在则自动迁移
        if not os.path.exists(get_account_dir(account_name)):
            migrate_legacy_account()
        return

    account_dir = get_account_dir(account_name)
    if not os.path.exists(account_dir):
        raise FileNotFoundError(
            f"账号 '{account_name}' 不存在\n"
            f"使用以下命令创建: python run.py --platform douyin --account create {account_name}"
        )


def migrate_legacy_account():
    """迁移遗留的单账号数据到 accounts/legacy/"""
    legacy_dir = get_account_dir(LEGACY_ACCOUNT_NAME)

    # 如果 legacy 目录已存在，跳过迁移
    if os.path.exists(legacy_dir):
        print(f"ℹ️  legacy 账号目录已存在，跳过迁移")
        return

    # 检查是否有遗留数据需要迁移
    has_legacy_data = (
        os.path.exists(LEGACY_BROWSER_PROFILE) or
        os.path.exists(LEGACY_DOUBAO_JSON) or
        os.path.exists(LEGACY_DOUBAO_OUTPUT)
    )

    if not has_legacy_data:
        # 没有遗留数据，只创建空目录
        create_account(LEGACY_ACCOUNT_NAME)
        print(f"ℹ️  未检测到遗留数据，已创建空的 legacy 账号")
        return

    print(f"🔄 检测到遗留账号数据，正在迁移到 accounts/{LEGACY_ACCOUNT_NAME}/ ...")

    # 创建 legacy 账号目录
    Path(legacy_dir).mkdir(parents=True, exist_ok=True)

    # 迁移浏览器 profile
    if os.path.exists(LEGACY_BROWSER_PROFILE):
        target = get_account_browser_profile(LEGACY_ACCOUNT_NAME)
        if not os.path.exists(target):
            shutil.copytree(LEGACY_BROWSER_PROFILE, target)
            print(f"   ✅ 已迁移浏览器 profile")

    # 迁移配置文件
    if os.path.exists(LEGACY_DOUBAO_JSON):
        target = get_account_config_path(LEGACY_ACCOUNT_NAME)
        if not os.path.exists(target):
            shutil.copy2(LEGACY_DOUBAO_JSON, target)
            print(f"   ✅ 已迁移配置文件")

    # 迁移图片输出目录
    if os.path.exists(LEGACY_DOUBAO_OUTPUT):
        target = get_account_output_dir(LEGACY_ACCOUNT_NAME)
        if not os.path.exists(target):
            shutil.copytree(LEGACY_DOUBAO_OUTPUT, target)
            print(f"   ✅ 已迁移图片输出目录")

    print(f"✅ 遗留数据迁移完成")
    print(f"   注意: 原目录未删除，可手动清理")


def delete_account(account_name: str, confirm: bool = False):
    """删除账号（危险操作）"""
    if account_name == LEGACY_ACCOUNT_NAME:
        raise ValueError("不能删除 legacy 账号")

    account_dir = get_account_dir(account_name)
    if not os.path.exists(account_dir):
        raise FileNotFoundError(f"账号 '{account_name}' 不存在")

    if not confirm:
        print(f"⚠️  即将删除账号 '{account_name}' 的所有数据:")
        print(f"   {account_dir}")
        print(f"   包括: 浏览器登录状态、配置文件、生成的图片")
        answer = input("确认删除? (yes/no): ").strip().lower()
        if answer not in ['yes', 'y']:
            print("❌ 已取消删除")
            return

    shutil.rmtree(account_dir)
    print(f"✅ 账号 '{account_name}' 已删除")


def print_accounts():
    """打印所有账号信息"""
    accounts = list_accounts()

    if not accounts:
        print("📋 当前没有账号")
        print(f"   使用以下命令创建: python run.py --platform douyin --account create <名称>")
        return

    print(f"📋 当前共有 {len(accounts)} 个账号:")
    print()
    for acc in accounts:
        login_status = "✅ 已登录" if acc["has_login"] else "❌ 未登录"
        print(f"   • {acc['name']}  [{login_status}]")
        print(f"     路径: {acc['path']}")
    print()


if __name__ == "__main__":
    # 测试用
    print("=== 账号管理测试 ===")
    print()
    print_accounts()

    # 测试创建账号
    # create_account("test_account")
    # print_accounts()

    # 测试迁移
    # migrate_legacy_account()
    # print_accounts()
