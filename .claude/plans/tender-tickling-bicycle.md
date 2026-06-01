# 多账号抖音文章发布方案

## Context

用户需要开辟新账号执行抖音文章发布链路。当前项目只支持单账号（通过 `byte_browser_profile/` 目录存储登录状态）。需要设计一个支持多账号的架构，每个账号独立的浏览器 profile、独立的内容配置，同时保持向后兼容现有单账号使用方式。

## 设计方案

### 核心思路：账号目录隔离

采用**基于账号名称的目录隔离方案**，每个账号对应一个独立的配置目录，包含：
- 浏览器 profile（登录状态）
- 内容配置文件（doubao.json）
- 生成的图片输出目录

### 目录结构设计

```
accounts/
├── account1/                    # 账号1（现有账号迁移）
│   ├── browser_profile/         # 抖音浏览器 profile
│   ├── doubao.json              # 内容配置
│   └── doubao_output/           # 生成的图片
├── account2/                    # 账号2（新账号）
│   ├── browser_profile/
│   ├── doubao.json
│   └── doubao_output/
└── ...
```

### 实现步骤

#### 1. 创建账号管理模块 `account_manager.py`

**文件路径**: `/Users/asuria/Desktop/browser/account_manager.py`

**职责**:
- 管理账号目录的创建、列表、切换
- 提供账号路径解析接口
- 支持账号的增删查操作

**核心函数**:
```python
ACCOUNTS_ROOT = os.path.join(PROJECT_ROOT, "accounts")

def get_account_dir(account_name: str) -> str:
    """获取账号目录路径"""

def list_accounts() -> list:
    """列出所有账号"""

def create_account(account_name: str) -> str:
    """创建新账号目录"""

def ensure_account_exists(account_name: str):
    """确保账号存在，不存在则报错"""

def migrate_legacy_account():
    """迁移现有单账号数据到 accounts/legacy/"""
```

#### 2. 修改 `douyin/publisher.py`

**修改点**:
- `publish()` 函数增加 `account_name` 参数
- 使用 `account_manager.get_account_dir()` 获取账号专属路径
- 读取账号专属的 `doubao.json` 和图片目录
- 使用账号专属的浏览器 profile 目录

**关键变更**:
```python
async def publish(sendType: str = None, title: str = None, content: str = None, account_name: str = "legacy"):
    # 获取账号目录
    account_dir = get_account_dir(account_name)

    # 读取账号专属配置
    config_path = os.path.join(account_dir, "doubao.json")
    output_dir = os.path.join(account_dir, "doubao_output")
    user_data_dir = os.path.join(account_dir, "browser_profile")
```

#### 3. 修改 `run.py`

**修改点**:
- 增加 `--account` 参数支持
- 将 account_name 传递给发布函数
- 支持 `--account list` 列出所有账号
- 支持 `--account create <name>` 创建新账号

**命令行接口**:
```bash
# 列出所有账号
python run.py --platform douyin --account list

# 创建新账号
python run.py --platform douyin --account create my_new_account

# 使用指定账号发布
python run.py --platform douyin --account my_new_account

# 使用默认账号（向后兼容）
python run.py --platform douyin
```

#### 4. 修改 `generate.py` 和 `doubao.py`

**修改点**:
- 支持 `--account` 参数
- 输出到账号专属目录

#### 5. 修改 `scheduler.py`

**修改点**:
- 任务配置支持指定账号
- 支持为不同账号设置不同的调度策略

**配置示例**:
```python
TASKS = [
    # 账号1 每1.5小时发图文
    {"platform": "douyin", "account": "legacy", "schedule": "*/90 * * * *"},
    # 账号2 每2小时发文章
    {"platform": "douyin", "account": "new_account", "schedule": "*/120 * * * *"},
]
```

#### 6. 迁移现有数据

**迁移脚本**: 在首次运行时自动检测并迁移
- 检测 `byte_browser_profile/` 和 `doubao.json` 是否存在
- 如果存在且 `accounts/legacy/` 不存在，自动迁移
- 迁移后保留原目录（不删除），避免影响正在运行的任务

## 验证方案

### 1. 创建新账号
```bash
python run.py --platform douyin --account create test_account
# 验证: 检查 accounts/test_account/ 目录是否创建成功
```

### 2. 登录新账号
```bash
python run.py --platform douyin --account test_account --only 3
# 验证: 浏览器打开，用户扫码登录，登录状态保存到 accounts/test_account/browser_profile/
```

### 3. 完整发布流程
```bash
python run.py --platform douyin --account test_account
# 验证: 完整链路执行，内容发布到新账号
```

### 4. 多账号并发测试
```bash
# 终端1
python run.py --platform douyin --account account1

# 终端2
python run.py --platform douyin --account account2
# 验证: 两个账号独立运行，互不干扰
```

### 5. 向后兼容性
```bash
python run.py --platform douyin
# 验证: 不指定账号时，使用 legacy 账号（原有行为）
```

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `account_manager.py` | 新建 | 账号管理模块 |
| `douyin/publisher.py` | 修改 | 支持多账号 |
| `run.py` | 修改 | 增加 --account 参数 |
| `generate.py` | 修改 | 支持账号目录输出 |
| `doubao.py` | 修改 | 支持账号目录输出 |
| `scheduler.py` | 修改 | 支持多账号调度 |
| `accounts/` | 新建目录 | 账号数据根目录 |

## 注意事项

1. **浏览器并发**: 同一个账号不能同时运行多个发布任务（浏览器 profile 锁冲突）
2. **登录状态**: 每个账号需要独立扫码登录一次
3. **磁盘空间**: 每个账号的浏览器 profile 约 100-200MB
4. **向后兼容**: 不指定 `--account` 时默认使用 `legacy` 账号，保证现有使用方式不受影响
