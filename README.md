# 🤖 社交媒体 AI 自动发布工具

> **一句话介绍：** 运行一条命令，AI 自动帮你写文案、生成图片、发布到抖音/小红书。
>
> 整个过程全自动：**AI 写文案 → AI 生图 → 浏览器自动操作发布**，你只需要喝杯咖啡等着就行 ☕

---

## ⚡ 快速配置（拿到项目后第一件事）

### 1. 复制配置文件模板

```bash
cp .env.example .env
```

### 2. 编辑 `.env`，填写你的 API 密钥

```env
# ========== 必须修改（不改跑不起来！）==========

# 你的大模型 API 密钥（去对应平台申请，下面有获取方法）
MIMO_API_KEY=把这里换成你的密钥

# ========== 以下一般不用改（想换模型时再改）==========

# 大模型 API 地址（默认是小米 MiMo）
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1

# 使用的模型名称
MIMO_MODEL=mimo-v2.5
```

### 3. API 密钥怎么获取？

| 模型平台 | 官网 | 获取密钥 |
|---------|------|---------|
| **小米 MiMo**（默认） | [token-plan-cn.xiaomimimo.com](https://token-plan-cn.xiaomimimo.com) | 注册后在控制台获取 API Key |
| **DeepSeek** | [platform.deepseek.com](https://platform.deepseek.com) | 注册后在 API Keys 页面创建 |
| **通义千问** | [dashscope.aliyun.com](https://dashscope.aliyun.com) | 注册后在 API-KEY 管理页面创建 |
| **其他兼容 OpenAI 接口的模型** | 对应平台 | 对应平台获取 |

> 💡 **只要兼容 OpenAI 接口的模型都能用！** 修改 `MIMO_BASE_URL` 和 `MIMO_MODEL` 即可。
>
> 例如换成 DeepSeek：
> ```env
> MIMO_API_KEY=sk-xxxxxxxxxxxxxxxx
> MIMO_BASE_URL=https://api.deepseek.com/v1
> MIMO_MODEL=deepseek-chat
> ```

### 4. 还有哪些可以改？

| 配置文件 | 改什么 | 什么时候需要改 |
|---------|--------|--------------|
| `.env` | 大模型 API 地址、密钥、模型名 | **必须改！** 不改跑不起来 |
| `prompts.json` | AI 的角色设定和写作风格 | 想让 AI 写不同风格时改 |
| `run.py` 中的默认主题 | `美女`（抖音）、`宝妈育儿`（小红书） | 想换默认主题时改 |

> ⚠️ **`.env` 包含你的密钥，绝对不要分享给别人或提交到 git！**

---

## 📖 目录

- [快速配置（拿到项目后第一件事）](#-快速配置拿到项目后第一件事)
- [这个工具能干什么？](#-这个工具能干什么)
- [运行效果预览](#-运行效果预览)
- [环境准备（必看！）](#-环境准备必看)
- [安装步骤（手把手教）](#-安装步骤手把手教)
- [配置 API 密钥（必须！）](#-配置-api-密钥必须)
- [第一次运行（含扫码登录）](#-第一次运行含扫码登录)
- [日常使用命令大全](#-日常使用命令大全)
- [多账号管理](#-多账号管理)
- [项目文件说明](#-项目文件说明)
- [常见问题 FAQ](#-常见问题-faq)
- [工作原理（技术细节）](#-工作原理技术细节)

---

## 🎯 这个工具能干什么？

### 抖音发布（3 步全自动）

```
你输入一个主题（比如"旅行攻略"）
    ↓
Step 1: AI 自动生成标题、正文、图片描述（调用 LLM）
    ↓
Step 2: AI 自动生成配图（调用豆包 AI 画图）
    ↓
Step 3: 浏览器自动打开抖音创作者平台，自动填写、自动发布
    ↓
✅ 发布完成！
```

### 小红书发布（2 步全自动）

```
你输入一个主题（比如"宝妈育儿"）
    ↓
Step 1: AI 自动生成标题、正文、标签（调用 LLM）
    ↓
Step 2: 浏览器自动打开小红书创作者中心，自动填写、自动发布
    ↓
✅ 发布完成！
```

---

## 🖼 运行效果预览

运行后你会看到类似这样的输出：

```
============================================================
🎬  抖音链路  [账号: legacy]
============================================================

🚀 Step 1: 内容生成 (generate)
------------------------------------------------------------
🤖 正在调用 mimo-v2.5 生成内容...
   类型: image | 主题: 旅行攻略
✅ Step 1 完成 -> accounts/legacy/doubao.json

🚀 Step 2: 豆包图片生成 (doubao)
------------------------------------------------------------
🤖 豆包批量提问 & 保存图片  [账号: legacy]
📋 共 8 条 prompt
✅ 高清图已保存！

🚀 Step 3: 抖音发布 (douyin.publisher)
------------------------------------------------------------
🎉 已登录！
📝 步骤1：点击「发布图文」...
✅ 发布完成！

🎉 抖音链路执行完毕！
```

---

## 🛠 环境准备（必看！）

在安装之前，请确保你的电脑满足以下条件：

### 1. 操作系统

- ✅ **macOS**（推荐）
- ✅ **Windows**（需要 WSL 或原生支持）
- ✅ **Linux**

### 2. 安装 Python 3.12+

打开终端（Mac 按 `Command + 空格`，输入 `Terminal`；Windows 打开 PowerShell），输入：

```bash
python3 --version
```

如果显示 `Python 3.12.x` 或更高版本，就 OK 了 ✅

**如果没有安装 Python 或版本太低：**

- **Mac 用户：** 推荐用 Homebrew 安装：
  ```bash
  brew install python@3.12
  ```
- **Windows 用户：** 去 [python.org](https://www.python.org/downloads/) 下载安装包
- **Linux 用户：**
  ```bash
  sudo apt install python3.12  # Ubuntu/Debian
  sudo dnf install python3.12  # Fedora
  ```

### 3. 安装 uv（Python 包管理工具）

**uv 是什么？** 它是一个超快的 Python 包管理工具，类似 pip 但快 10-100 倍。

```bash
# Mac / Linux 一行搞定
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows（PowerShell）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

安装后验证：

```bash
uv --version
```

看到版本号就说明安装成功了 ✅

> 💡 **如果你不想用 uv**，也可以用 pip：`pip install -r requirements.txt`，但推荐用 uv。

### 4. 网络要求

- 需要能访问 **豆包 AI**（doubao.com）—— 用于 AI 生成图片
- 需要能访问 **抖音创作者平台**（creator.douyin.com）—— 用于发布
- 需要能访问 **小红书创作者中心**（creator.xiaohongshu.com）—— 用于发布
- 需要能访问 **LLM API**（默认是小米 MiMo 接口）—— 用于 AI 生成文案

---

## 📦 安装步骤（手把手教）

### 第 1 步：下载项目

打开终端，进入你想放项目的目录，然后克隆：

```bash
# 进入桌面（或其他你想放的位置）
cd ~/Desktop

# 克隆项目（把 <repo-url> 换成实际的仓库地址）
git clone <repo-url> browser

# 进入项目目录
cd browser
```

> 💡 如果你已经有项目文件了，直接 `cd` 进去就行。

### 第 2 步：安装 Python 依赖

```bash
# 使用国内镜像源加速下载（推荐国内用户）
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 如果你在国内且网络好，也可以直接：
# uv sync
```

这个命令会自动安装所有需要的 Python 库，包括：
- `openai` — 调用 AI 大模型
- `playwright` — 浏览器自动化
- `pillow` — 图片处理
- `python-dotenv` — 读取配置文件

### 第 3 步：安装浏览器

```bash
uv run playwright install chromium
```

这会下载一个 Chromium 浏览器（约 150MB），用于自动化操作抖音和小红书网站。

> ⚠️ **这一步很重要！** 如果不安装浏览器，后面运行会报错。

### 第 4 步：验证安装

```bash
# 检查是否能正常运行
uv run python run.py --help
```

如果看到帮助信息，说明安装成功 ✅

---

## 🔑 配置 API 密钥（必须！）

这个工具需要调用 AI 大模型来生成内容，所以你需要配置一个 API 密钥。

### 第 1 步：创建 .env 文件

项目根目录下有一个 `.env.example` 文件，复制一份：

```bash
cp .env.example .env
```

### 第 2 步：编辑 .env 文件

用任意文本编辑器打开 `.env` 文件：

```bash
# Mac
open -e .env

# Windows
notepad .env

# Linux
nano .env
```

把里面的内容改成你自己的：

```env
# LLM API 配置
MIMO_API_KEY=你的API密钥粘贴到这里
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.5
```

### 各字段说明

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `MIMO_API_KEY` | **你的 API 密钥**（必填！） | 无，必须填写 |
| `MIMO_BASE_URL` | API 接口地址 | `https://token-plan-cn.xiaomimimo.com/v1` |
| `MIMO_MODEL` | 使用的模型名称 | `mimo-v2.5` |

> ⚠️ **重要：** `.env` 文件包含你的密钥，**不要分享给别人**，也**不要提交到 git**（已在 .gitignore 中排除）。

> 💡 **默认使用小米 MiMo 模型。** 如果你想用其他兼容 OpenAI 接口的模型（如 DeepSeek、通义千问等），修改 `MIMO_BASE_URL` 和 `MIMO_MODEL` 即可。

---

## 🚀 第一次运行（含扫码登录）

### 重要提示

> **首次运行会弹出浏览器窗口，需要你手动扫码登录！**
>
> 这是正常的 —— 工具需要登录你的抖音/小红书账号才能发布内容。登录一次后，登录状态会保存在本地，以后就不用再登了。

### 第一次发布到抖音

```bash
# 只运行第一步（触发登录，不实际发布）
uv run python run.py --platform douyin --only 1
```

运行后会：
1. 弹出一个浏览器窗口
2. 自动打开抖音创作者平台
3. **等你扫码登录** —— 用手机抖音 APP 扫描浏览器上的二维码
4. 登录成功后，回到终端按回车继续

登录成功后，浏览器会关闭。**以后再运行就不需要扫码了**（除非登录过期）。

### 第一次发布到小红书

```bash
# 只运行第一步（触发登录，不实际发布）
uv run python run.py --platform xiaohongshu --only 1
```

同样会弹出浏览器，用手机小红书 APP 扫码登录。

### 登录完成后，正式发布

```bash
# 发布到抖音
uv run python run.py --platform douyin

# 发布到小红书
uv run python run.py --platform xiaohongshu
```

就这么简单！🎉

---

## 📋 日常使用命令大全

### 抖音发布

```bash
# ========== 基础用法 ==========

# 使用默认主题"美女"发布图文（默认 8 张图）
uv run python run.py --platform douyin

# 指定主题
uv run python run.py --platform douyin --topic "旅行攻略"
uv run python run.py --platform douyin --topic "美食推荐"
uv run python run.py --platform douyin --topic "AI面试题"

# ========== 内容类型 ==========

# 发布图文相册（默认类型）
uv run python run.py --platform douyin --type image

# 发布文章（长文 + 封面图）
uv run python run.py --platform douyin --type article --topic "AI Agent面试"

# 发布泳装写真
uv run python run.py --platform douyin --type swimwear --count 6

# ========== 控制图片数量 ==========

# 生成 5 张图
uv run python run.py --platform douyin --count 5

# ========== 分步执行（调试用）==========

# 只执行第 1 步：AI 生成内容（不生图不发布）
uv run python run.py --platform douyin --only 1

# 只执行第 2 步：豆包生成图片（需要先执行过第 1 步）
uv run python run.py --platform douyin --only 2

# 只执行第 3 步：发布到抖音（需要先执行过第 1、2 步）
uv run python run.py --platform douyin --only 3

# 从第 2 步开始（跳过第 1 步，用已有的内容）
uv run python run.py --platform douyin --step 2

# 从第 3 步开始（跳过前两步，用已有的图片和内容）
uv run python run.py --platform douyin --step 3
```

### 小红书发布

```bash
# ========== 基础用法 ==========

# 使用默认主题"宝妈育儿"自动生成文案并发布
uv run python run.py --platform xiaohongshu

# 指定主题
uv run python run.py --platform xiaohongshu --topic "护肤心得"
uv run python run.py --platform xiaohongshu --topic "减肥食谱"

# ========== 使用已有的文案 ==========

# 用自己写好的 JSON 文件发布（跳过 AI 生成）
uv run python run.py --platform xiaohongshu --input my_note.json

# ========== 分步执行 ==========

# 只生成文案（不发布）
uv run python run.py --platform xiaohongshu --only 1

# 只发布（用已有的文案）
uv run python run.py --platform xiaohongshu --only 2
```

### 查看帮助

```bash
# 查看所有可用参数
uv run python run.py --help
```

### 参数速查表

| 参数 | 说明 | 示例 |
|------|------|------|
| `--platform` / `-p` | 选择平台（必填） | `--platform douyin` |
| `--topic` | 内容主题 | `--topic "旅行攻略"` |
| `--type` | 内容类型（仅抖音） | `--type article` |
| `--count` | 图片数量（仅抖音） | `--count 5` |
| `--input` / `-i` | 已有 JSON 文件（仅小红书） | `--input note.json` |
| `--only` | 只执行第 N 步 | `--only 1` |
| `--step` | 从第 N 步开始 | `--step 2` |
| `--account` | 指定账号 | `--account my_acc` |

### 内容类型说明（仅抖音）

| 类型 | 参数 | 说明 |
|------|------|------|
| 图文 | `--type image` | AI 生成多张图片，发布为图文相册（默认） |
| 文章 | `--type article` | AI 生成长文 + 1 张封面图，发布为文章 |
| 泳装 | `--type swimwear` | AI 生成泳装写真图片，发布为图文相册 |

---

## 👥 多账号管理

如果你想管理多个抖音/小红书账号（比如一个号发美食，一个号发旅行），可以用多账号功能。

### 创建新账号

```bash
# 创建一个叫 "food" 的账号
uv run python run.py --platform douyin --account create food

# 创建一个叫 "travel" 的账号
uv run python run.py --platform douyin --account create travel
```

### 查看所有账号

```bash
uv run python run.py --platform douyin --account list
```

输出示例：

```
📋 当前共有 3 个账号:

   • legacy  [✅ 已登录]
     路径: /xxx/browser/accounts/legacy
   • food  [❌ 未登录]
     路径: /xxx/browser/accounts/food
   • travel  [❌ 未登录]
     路径: /xxx/browser/accounts/travel
```

### 使用指定账号发布

```bash
# 用 "food" 账号发布
uv run python run.py --platform douyin --account food --topic "美食推荐"

# 用 "travel" 账号发布
uv run python run.py --platform douyin --account travel --topic "旅行攻略"

# 不指定账号时，默认使用 "legacy" 账号
uv run python run.py --platform douyin
```

### 账号数据隔离

每个账号的数据完全独立，互不影响：

```
accounts/
├── legacy/                 # 默认账号
│   ├── browser_profile/    # 浏览器登录状态
│   ├── doubao.json         # AI 生成的内容配置
│   └── doubao_output/      # AI 生成的图片
├── food/                   # 美食账号
│   ├── browser_profile/
│   ├── doubao.json
│   └── doubao_output/
└── travel/                 # 旅行账号
    ├── browser_profile/
    ├── doubao.json
    └── doubao_output/
```

---

## 📁 项目文件说明

```
browser/
├── run.py                  # 🚀 主入口脚本（你平时就运行这个）
├── generate.py             # 🤖 AI 内容生成模块（调用 LLM 生成文案和图片描述）
├── doubao.py               # 🎨 豆包 AI 生图模块（自动操作豆包网站生成图片）
├── account_manager.py      # 👤 账号管理模块（管理多个账号的目录和配置）
├── prompts.json            # 📝 AI 提示词配置（定义了 AI 的角色和生成规则）
│
├── douyin/                 # 📱 抖音发布模块
│   ├── __init__.py
│   └── publisher.py        #    抖音自动发布（操作浏览器完成发布）
│
├── xiaohongshu/            # 📕 小红书发布模块
│   ├── __init__.py
│   └── publisher.py        #    小红书自动发布（操作浏览器完成发布）
│
├── accounts/               # 💾 账号数据目录（每个账号独立）
│   ├── legacy/             #    默认账号
│   │   ├── browser_profile/ #      浏览器登录状态
│   │   ├── doubao.json     #      AI 生成的内容
│   │   └── doubao_output/  #      AI 生成的图片
│   └── <其他账号>/         #    其他账号（结构同上）
│
├── logs/                   # 📊 运行日志（按日期记录）
│
├── .env                    # 🔑 API 密钥配置（不要分享！）
├── .env.example            #    配置文件模板
├── pyproject.toml          # 📦 项目依赖配置
├── uv.lock                 #    依赖版本锁定文件
└── .gitignore              #    Git 忽略规则
```

### 各文件的作用

| 文件 | 作用 | 你需要修改吗？ |
|------|------|--------------|
| `run.py` | 主入口，统一调度所有功能 | ❌ 不需要 |
| `generate.py` | 调用 LLM 生成文案 | ❌ 不需要 |
| `doubao.py` | 调用豆包 AI 生成图片 | ❌ 不需要 |
| `doubayin/publisher.py` | 自动发布到抖音 | ❌ 不需要 |
| `xiaohongshu/publisher.py` | 自动发布到小红书 | ❌ 不需要 |
| `account_manager.py` | 管理多账号 | ❌ 不需要 |
| `prompts.json` | AI 的角色和提示词 | 🔧 可选：想自定义 AI 风格时修改 |
| `.env` | API 密钥 | ✅ **必须配置！** |
| `accounts/` | 账号数据 | ❌ 自动生成，不要手动改 |

---

## ❓ 常见问题 FAQ

### 安装相关

#### Q: `uv sync` 报错怎么办？

**A:** 试试以下方法：
```bash
# 1. 确认 uv 已安装
uv --version

# 2. 如果没有 uv，先安装
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. 用国内镜像重试
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

#### Q: `playwright install chromium` 报错？

**A:** 试试：
```bash
# 确保 uv 已正确安装 playwright
uv run playwright install chromium

# 如果还是失败，尝试手动安装
uv pip install playwright
uv run playwright install chromium
```

#### Q: 运行时报 `ModuleNotFoundError`？

**A:** 确保你用的是 `uv run python` 而不是直接 `python`：
```bash
# ❌ 错误
python run.py --platform douyin

# ✅ 正确
uv run python run.py --platform douyin
```

### 登录相关

#### Q: 浏览器弹出来了，但什么都没发生？

**A:** 这是在等你扫码登录！
1. 用手机打开对应的 APP（抖音/小红书）
2. 扫描浏览器上的二维码
3. 登录成功后，回到终端按回车继续

#### Q: 登录状态过期了怎么办？

**A:** 删除对应账号的浏览器缓存，重新登录：
```bash
# 删除 legacy 账号的登录状态
rm -rf accounts/legacy/browser_profile/

# 重新运行，会触发重新登录
uv run python run.py --platform douyin --only 1
```

#### Q: 多个账号之间会互相影响吗？

**A:** 不会！每个账号有完全独立的浏览器 profile、配置文件和图片目录，完全隔离。

### 运行相关

#### Q: 豆包生图时报错"拒绝生成"？

**A:** 工具会自动检测拒绝并重试（最多 2 次）。如果仍然失败：
- 可能是主题包含敏感词
- 工具会自动清洗敏感词后重试
- 尝试换个主题

#### Q: LLM 生成的 JSON 格式有问题？

**A:** 工具内置了 `fix_json()` 自动修复常见格式问题（单引号、尾逗号、未闭合字符串等），一般不需要担心。

#### Q: 某一步失败了，怎么从那一步重新开始？

**A:** 用 `--only` 或 `--step` 参数：
```bash
# 比如第 2 步失败了，只重新执行第 2 步
uv run python run.py --platform douyin --only 2

# 或者从第 2 步开始
uv run python run.py --platform douyin --step 2
```

#### Q: 怎么查看运行日志？

**A:** 日志保存在 `logs/` 目录下，按日期分文件：
```bash
# 查看今天的日志
cat logs/$(date +%Y-%m-%d).jsonl
```

#### Q: 我想自定义 AI 的写作风格怎么办？

**A:** 编辑 `prompts.json` 文件。里面定义了 AI 的角色设定（`roles`）和生成指令（`system_prompts`），你可以根据需要修改。

---

## 🔧 工作原理（技术细节）

> 💡 这部分是给想了解技术细节的同学看的，普通用户可以跳过。

### 整体架构

```
用户输入主题
    ↓
┌─────────────────────────────────────────┐
│  run.py（统一入口）                       │
│  解析命令行参数，调度对应链路              │
└───────────┬─────────────────────────────┘
            ↓
┌─────────────────────────────────────────┐
│  generate.py（LLM 内容生成）              │
│  调用 MiMo 大模型，生成：                 │
│  - 标题、副标题、正文                     │
│  - 图片描述提示词（prompt）               │
│  输出: doubao.json                        │
└───────────┬─────────────────────────────┘
            ↓
┌─────────────────────────────────────────┐
│  doubao.py（豆包 AI 生图）               │
│  自动操作豆包网站：                       │
│  - 逐条输入 prompt                        │
│  - 等待图片生成                           │
│  - 下载高清图片（自动去水印）              │
│  输出: doubao_output/*.jpg                │
└───────────┬─────────────────────────────┘
            ↓
┌─────────────────────────────────────────┐
│  douyin/publisher.py 或                   │
│  xiaohongshu/publisher.py                 │
│  自动操作浏览器：                          │
│  - 打开创作者平台                          │
│  - 上传图片/填写内容                       │
│  - 点击发布                               │
└─────────────────────────────────────────┘
```

### 技术栈

- **Python 3.12+** — 主语言
- **OpenAI SDK** — 调用 LLM API（兼容 OpenAI 接口的任何模型）
- **Playwright** — 浏览器自动化（控制 Chromium 浏览器）
- **Pillow** — 图片处理（裁切水印等）
- **python-dotenv** — 环境变量管理

### 数据流

```
prompts.json（提示词模板）
    + 用户输入的主题
    ↓
generate.py → doubao.json（AI 生成的文案 + 图片描述）
    ↓
doubao.py → doubao_output/（AI 生成的图片）
    ↓
publisher.py → 自动发布到平台
```

---

## 📌 注意事项

1. **首次运行必须扫码登录** — 登录状态会保存在本地，后续自动复用
2. **豆包生图有 3 秒延迟** — 这是防触发人机校验，属于正常行为
3. **抖音发布自动标注「内容由 AI 生成」** — 符合平台规定
4. **图片 prompt 自动清洗敏感词汇** — 避免被豆包拒绝生成
5. **`.env` 文件不要分享** — 包含你的 API 密钥
6. **`accounts/` 目录不要删除** — 包含登录状态和生成的内容

---

## 🆘 获取帮助

如果遇到问题：

1. 先看上面的 [常见问题 FAQ](#-常见问题-faq)
2. 运行 `uv run python run.py --help` 查看所有参数
3. 查看 `logs/` 目录下的运行日志定位问题
4. 删除 `accounts/<账号名>/browser_profile/` 重新登录

---

> 🎉 **恭喜你看到这里！** 现在你已经知道怎么使用这个工具了。快去试试吧：
>
> ```bash
> uv run python run.py --platform douyin --topic "今天天气真好"
> ```
