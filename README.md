# 社交媒体自动发布工具 / Social Media Auto Publisher

> 基于 LLM + 浏览器自动化，一键生成内容并发布到抖音、小红书。
>
> An AI-powered tool that generates content via LLM and auto-publishes to Douyin (TikTok China) and Xiaohongshu (RED) using browser automation.

---

## 目录 / Table of Contents

- [快速上手 / Quick Start](#快速上手--quick-start)
- [支持平台 / Supported Platforms](#支持平台--supported-platforms)
- [安装 / Installation](#安装--installation)
- [使用教程 / Usage Tutorial](#使用教程--usage-tutorial)
- [进阶用法 / Advanced Usage](#进阶用法--advanced-usage)
- [项目结构 / Project Structure](#项目结构--project-structure)
- [常见问题 / FAQ](#常见问题--faq)

---

## 快速上手 / Quick Start

只需要 3 步即可发布你的第一条内容 / Just 3 steps to publish your first post:

```bash
# 1. 安装依赖 / Install dependencies
uv sync && uv run playwright install chromium

# 2. 发布到抖音（首次需扫码登录）/ Publish to Douyin (scan QR on first run)
uv run python run.py --platform douyin

# 3. 发布到小红书 / Publish to Xiaohongshu
uv run python run.py --platform xiaohongshu
```

就这么简单！工具会自动：AI 生成文案 → AI 生成图片 → 浏览器自动发布。
That's it! The tool automatically: generates copy via AI → generates images via AI → publishes via browser.

---

## 支持平台 / Supported Platforms

| 平台 / Platform | 命令 / Command | 工作流 / Workflow |
|------|------|------|
| 抖音 / Douyin | `--platform douyin` | LLM 生成内容 → 豆包生图 → 抖音发布 |
| 小红书 / Xiaohongshu | `--platform xiaohongshu` | LLM 生成文案 → 小红书发布 |

---

## 安装 / Installation

### 环境要求 / Prerequisites

- **Python >= 3.12**
- **uv** 包管理器（[安装 uv](https://docs.astral.sh/uv/getting-started/installation/)）

### 安装步骤 / Setup

```bash
# 克隆项目 / Clone the repo
git clone <repo-url> && cd browser

# 安装依赖 / Install dependencies
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 安装 Playwright 浏览器 / Install Playwright browser
uv run playwright install chromium
```

---

## 使用教程 / Usage Tutorial

### 第一次使用 / First Time Use

> **重要：** 首次运行会弹出浏览器窗口，需要你**手动扫码登录**对应平台。登录状态会保存在本地，后续自动复用。
>
> **Important:** The first run will open a browser window. You need to **scan the QR code** to log in. Login state is saved locally for future use.

```bash
# 抖音首次登录 / First login for Douyin
uv run python run.py --platform douyin --only 1   # 只运行第一步，触发登录 / Only run step 1 to trigger login
```

登录完成后，浏览器会关闭，之后再运行完整流程即可。
After login, the browser closes. You can then run the full pipeline.

---

### 发布到抖音 / Publish to Douyin

抖音链路包含 **3 个步骤**，工具会自动依次执行：
The Douyin pipeline has **3 steps**, executed automatically in sequence:

```
Step 1: AI 生成文案和图片描述
Step 2: 豆包 AI 生成图片
Step 3: 自动发布到抖音
```

#### 基础用法 / Basic Usage

```bash
# 使用默认主题"美女"发布图文 / Publish images with default topic
uv run python run.py --platform douyin

# 指定主题 / Specify a topic
uv run python run.py --platform douyin --topic "旅行攻略"
uv run python run.py --platform douyin --topic "Travel tips"

# 指定图片数量 / Specify image count
uv run python run.py --platform douyin --count 5
```

#### 内容类型 / Content Types

```bash
# 发布图文（默认）/ Publish images (default)
uv run python run.py --platform douyin --type image

# 发布文章 / Publish article
uv run python run.py --platform douyin --type article --topic "AI面试题"

# 发布泳装写真 / Publish swimwear photos
uv run python run.py --platform douyin --type swimwear --count 6
```

| 类型 / Type | 参数 / Flag | 说明 / Description |
|------|------|------|
| 图文 / Image | `--type image` | 生成图片 → 发布图文相册 / Generate images → publish photo album |
| 文章 / Article | `--type article` | 生成技术文章 → 发布长文 / Generate tech article → publish long-form |
| 泳装 / Swimwear | `--type swimwear` | 生成泳装写真 → 发布图文 / Generate swimwear photos → publish |

#### 分步控制 / Step Control

如果某一步失败了，可以从失败的步骤重新开始，不用从头来：
If a step fails, you can restart from that step without repeating everything:

```bash
# 只执行某一步 / Run only one step
uv run python run.py --platform douyin --only 1    # 只生成内容 / Only generate
uv run python run.py --platform douyin --only 2    # 只生成图片 / Only generate images
uv run python run.py --platform douyin --only 3    # 只发布 / Only publish

# 从某一步开始 / Start from a step
uv run python run.py --platform douyin --step 2    # 跳过生成，从生图开始 / Skip to image gen
uv run python run.py --platform douyin --step 3    # 跳到发布（用已有内容）/ Skip to publish
```

---

### 发布到小红书 / Publish to Xiaohongshu

小红书链路包含 **2 个步骤**：
The Xiaohongshu pipeline has **2 steps**:

```
Step 1: AI 生成文案
Step 2: 自动发布到小红书
```

#### 基础用法 / Basic Usage

```bash
# 自动生成文案并发布 / Auto-generate and publish
uv run python run.py --platform xiaohongshu

# 指定主题 / Specify a topic
uv run python run.py --platform xiaohongshu --topic "旅行攻略"
uv run python run.py --platform xiaohongshu --topic "Skincare tips"
```

#### 使用已有内容 / Use Existing Content

如果你已经写好了文案，可以直接用 JSON 文件发布，跳过 AI 生成：
If you already have content, publish directly from a JSON file:

```bash
uv run python run.py --platform xiaohongshu --input my_note.json
```

JSON 文件格式 / JSON format:
```json
{
  "title": "笔记标题（10-20字，含emoji）",
  "content": "正文内容（200-500字，口语化）",
  "tags": ["标签1", "标签2", "标签3"],
  "sendType": "xiaohongshu"
}
```

#### 分步控制 / Step Control

```bash
uv run python run.py --platform xiaohongshu --only 1    # 只生成文案 / Only generate
uv run python run.py --platform xiaohongshu --only 2    # 只发布 / Only publish
```

---

### 多账号管理 / Multi-Account Management

支持多个账号独立运行，每个账号有独立的登录状态和配置：
Supports multiple isolated accounts, each with its own login state and config:

```bash
# 创建新账号 / Create a new account
uv run python run.py --platform douyin --account create my_account

# 列出所有账号 / List all accounts
uv run python run.py --platform douyin --account list

# 使用指定账号发布 / Publish with a specific account
uv run python run.py --platform douyin --account my_account

# 不指定账号时，默认使用 legacy 账号 / Defaults to "legacy" if not specified
uv run python run.py --platform douyin
```

---

## 进阶用法 / Advanced Usage

### 单独运行各模块 / Run Modules Independently

每个模块都可以脱离 `run.py` 独立使用：
Each module can be used independently without `run.py`:

```bash
# 只调用 LLM 生成内容 / Generate content with LLM only
uv run python generate.py "旅行攻略" --type image --count 5 --output doubao.json

# 只运行豆包生图 / Run Doubao image generation only
uv run python doubao.py --account my_account

# 只运行抖音发布 / Run Douyin publishing only
uv run python -m douyin.publisher --type article --account my_account

# 只运行小红书发布 / Run Xiaohongshu publishing only
uv run python -m xiaohongshu.publisher --input my_note.json
```

### 查看所有参数 / View All Options

```bash
uv run python run.py --help
```

### 查看日志 / View Logs

每次执行会自动记录日志到 `logs/YYYY-MM-DD.jsonl`：
Execution logs are saved to `logs/YYYY-MM-DD.jsonl`:

```bash
# 查看今天的日志 / View today's logs
cat logs/$(date +%Y-%m-%d).jsonl
```

---

## 项目结构 / Project Structure

```
browser/
├── run.py                        # 统一入口 / Unified entry point
├── generate.py                   # LLM 内容生成 / LLM content generation
├── doubao.py                     # 豆包 AI 生图 / Doubao AI image generation
├── account_manager.py            # 多账号管理 / Multi-account management
├── douyin/                       # 抖音模块 / Douyin module
│   └── publisher.py              # 抖音发布 / Douyin publisher
├── xiaohongshu/                  # 小红书模块 / Xiaohongshu module
│   └── publisher.py              # 小红书发布 / Xiaohongshu publisher
├── accounts/                     # 账号数据 / Account data
│   ├── legacy/                   # 默认账号 / Default account
│   └── <账号名>/                 # 其他账号 / Other accounts
├── logs/                         # 执行日志 / Execution logs
└── pyproject.toml                # 项目配置 / Project config
```

---

## 常见问题 / FAQ

### Q: 首次运行浏览器弹出来但什么都没发生？
### Q: Browser opens on first run but nothing happens?

**A:** 这是在等你扫码登录。用手机打开对应平台 App，扫描浏览器中的二维码即可。
**A:** It's waiting for you to scan the QR code. Open the corresponding platform app on your phone and scan the code in the browser.

### Q: 豆包生图时报错"拒绝生成"？
### Q: Doubao reports "refused to generate"?

**A:** 工具会自动检测拒绝并重试（最多 2 次）。如果仍然失败，可能是 prompt 中包含敏感词，工具会自动清洗后重试。
**A:** The tool auto-detects refusals and retries (up to 2 times). If it still fails, the prompt may contain sensitive words — the tool will auto-clean and retry.

### Q: 多个账号之间会互相影响吗？
### Q: Will multiple accounts affect each other?

**A:** 不会。每个账号有独立的浏览器 profile、配置文件和图片目录，完全隔离。
**A:** No. Each account has its own browser profile, config, and image directory — completely isolated.

### Q: 登录状态过期了怎么办？
### Q: What if my login session expires?

**A:** 删除对应账号目录下的 `browser_profile/` 文件夹，重新运行即可触发重新登录。
**A:** Delete the `browser_profile/` folder under the account directory, then run again to trigger re-login.

### Q: 支持哪些平台？
### Q: Which platforms are supported?

**A:** 目前支持抖音和小红书。
**A:** Currently Douyin and Xiaohongshu.

### Q: LLM 生成的 JSON 格式有问题？
### Q: LLM-generated JSON has format issues?

**A:** 工具内置了 `fix_json()` 自动修复常见格式问题（单引号、尾逗号、未闭合字符串等）。
**A:** The tool has a built-in `fix_json()` that auto-repairs common format issues (single quotes, trailing commas, unclosed strings, etc.).

---

## 注意事项 / Notes

- 首次运行需扫码登录，登录状态自动保存 / Scan QR on first run; login state is saved automatically
- 豆包生图有 3 秒防抖延迟 / Doubao image gen has a 3-second anti-bot delay
- 抖音发布自动标注「内容由 AI 生成」/ Douyin auto-adds "AI-generated content" declaration
- 图片 prompt 自动清洗敏感词汇 / Image prompts are auto-cleaned of sensitive words
