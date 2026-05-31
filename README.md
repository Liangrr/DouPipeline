# 社交媒体自动发布工具

基于 Playwright 浏览器自动化 + LLM 内容生成的社交媒体自动发布工具，覆盖**抖音**和**小红书**两个平台，实现从 AI 生成文案/图片到自动发布的完整流程。

## 支持平台

| 平台 | 参数 | 链路 |
|------|------|------|
| 抖音 | `--platform douyin` | LLM 生成内容 → 豆包生图 → 抖音发布 |
| 小红书 | `--platform xiaohongshu` | LLM 生成文案 → 小红书发布（或从 JSON 直接发布） |

## 项目结构

```
browser/
├── run.py                        # 统一入口，--platform 选择平台
├── generate.py                   # LLM 内容生成（可独立运行）
├── doubao.py                     # 豆包 AI 生图自动化
├── account_manager.py            # 多账号管理模块
├── douyin/                       # 抖音链路
│   ├── __init__.py
│   └── publisher.py              # 抖音发布（文章/图文）
├── xiaohongshu/                  # 小红书链路
│   ├── __init__.py
│   └── publisher.py              # 小红书发布（长文笔记）
├── accounts/                     # 多账号数据目录
│   ├── legacy/                   # 遗留账号（自动迁移）
│   │   ├── browser_profile/      # 浏览器登录状态
│   │   ├── doubao.json           # 内容配置
│   │   └── doubao_output/        # 生成的图片
│   └── <账号名>/                 # 其他账号
├── logs/                         # 执行日志（JSONL，按日期分文件）
├── doubao_browser_profile/       # 豆包浏览器持久化
└── pyproject.toml                # 项目依赖
```

## 环境准备

```bash
# 1. 安装依赖（使用 uv 包管理器，默认清华源）
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 安装 Playwright 浏览器
uv run playwright install chromium
```

**依赖要求：** Python >= 3.12、playwright、openai

## 使用方法

### 快速开始

```bash
# 查看所有参数
uv run python run.py --help
```

### 多账号管理

支持多账号独立运行，每个账号有独立的浏览器登录状态和配置。

```bash
# 创建新账号
uv run python run.py --platform douyin --account-create my_account

# 列出所有账号
uv run python run.py --platform douyin --account list

# 使用指定账号发布
uv run python run.py --platform douyin --account my_account

# 不指定账号时，默认使用 legacy 账号
uv run python run.py --platform douyin
```

### 抖音链路

抖音链路包含 3 个步骤：**生成内容 → 豆包生成图片 → 抖音发布**

```bash
# 完整执行三步（默认主题"美女"）
uv run python run.py --platform douyin

# 指定主题和类型
uv run python run.py --platform douyin --topic "旅行攻略"
uv run python run.py --platform douyin --type article   # 发布文章（AI面试内容）
uv run python run.py --platform douyin --type image     # 发布图文（默认）

# 指定图片数量
uv run python run.py --platform douyin --count 5

# 使用指定账号
uv run python run.py --platform douyin --type article --topic "Agent记忆系统" --account my_account
```

**分步控制：**

```bash
# 只执行某一步
uv run python run.py --platform douyin --only 1    # 只生成内容
uv run python run.py --platform douyin --only 2    # 只生成图片
uv run python run.py --platform douyin --only 3    # 只发布

# 从某一步开始（跳过前面的步骤）
uv run python run.py --platform douyin --step 2    # 从豆包生图开始
uv run python run.py --platform douyin --step 3    # 直接发布（用已有 doubao.json + 图片）
```

### 小红书链路

小红书链路包含 2 个步骤：**生成文案 → 小红书发布**

```bash
# 自动生成文案并发布（默认主题"宝妈育儿"）
uv run python run.py --platform xiaohongshu

# 指定主题
uv run python run.py --platform xiaohongshu --topic "旅行攻略"

# 使用已有 JSON 文件，跳过生成
uv run python run.py --platform xiaohongshu --input my_note.json
```

**分步控制：**

```bash
uv run python run.py --platform xiaohongshu --only 1    # 只生成文案
uv run python run.py --platform xiaohongshu --only 2    # 只发布
```

**JSON 文件格式：**

```json
{
  "title": "笔记标题（10-20字，含emoji）",
  "content": "正文内容（200-500字，口语化）",
  "tags": ["标签1", "标签2", "标签3"],
  "sendType": "xiaohongshu"
}
```

## 内容类型（抖音）

| 类型 | 参数 | 说明 |
|------|------|------|
| 图文（默认） | `--type image` | 生成图片 prompt → 豆包生图 → 抖音发布图文 |
| 文章 | `--type article` | 生成 AI Agent 技术面试文章 → 抖音发布文章 |
| 视频 | `--type video` | 待实现 |

## 独立运行各模块

除通过 `run.py` 统一调度外，各模块也可独立运行：

```bash
# generate.py — LLM 内容生成
uv run python generate.py "旅行攻略" --type image --count 5 --output doubao.json
uv run python generate.py "Agent工具调用" --type article --account my_account

# doubao.py — 豆包生图（读取 doubao.json）
uv run python doubao.py
uv run python doubao.py --account my_account

# douyin/publisher.py — 抖音发布
uv run python -m douyin.publisher --type article --account my_account

# xiaohongshu/publisher.py — 小红书发布
uv run python -m xiaohongshu.publisher --input my_note.json
```

## 运行流程

```
抖音链路 (3步):
  run.py --platform douyin [--topic "主题"] [--type article|image] [--count N] [--account NAME]
    │
    ├─ Step 1: generate.py
    │   └─ 调用 mimo-v2.5 LLM → 生成标题/摘要/正文/图片 prompt → 保存到账号目录
    │
    ├─ Step 2: doubao.py
    │   ├─ 打开豆包网页 (持久化浏览器)
    │   ├─ 逐条输入 prompt → 等待图片生成（最多 180s）
    │   ├─ 拒绝检测 + 最多重试 2 次
    │   └─ 拦截高清图片响应 → 保存到账号目录
    │
    └─ Step 3: douyin/publisher.py
        ├─ 打开抖音创作者平台 (持久化浏览器)
        ├─ 根据 sendType 选择发布方式
        │   ├─ article → AI Agent 技术面试文章 → 填写标题/摘要/正文 → 上传封面 → 发布
        │   └─ image   → 上传图片 → 填写标题/描述 → 发布图文
        └─ 自动选择音乐 + 设置「内容由 AI 生成」声明 → 发布

小红书链路 (2步):
  run.py --platform xiaohongshu [--topic "主题"] [--input xxx.json]
    │
    ├─ Step 1: generate.py
    │   └─ 调用 LLM → 生成 emoji 风格标题 + 口语化正文 + 标签 → 保存 xiaohongshu.json
    │
    └─ Step 2: xiaohongshu/publisher.py
        ├─ 读取 JSON（title + content + tags）
        ├─ 打开小红书创作者平台 (持久化浏览器)
        ├─ 写长文 → 填写标题/正文 → 一键排版 → 添加标签
        └─ 等待图片上传完成 → 发布
```

## 日志

每次执行会自动记录日志到 `logs/YYYY-MM-DD.jsonl`，格式：

```json
{
  "time": "2025-01-01 12:00:00",
  "platform": "douyin",
  "account": "legacy",
  "step": 1,
  "step_name": "generate",
  "status": "success"
}
```

## 注意事项

- **首次运行**需手动登录：弹出浏览器后扫码登录豆包/抖音/小红书，登录状态保存在账号目录的 `browser_profile/` 中，后续自动复用
- **多账号隔离**：每个账号独立的浏览器 profile、配置文件和生成的图片，互不干扰
- 豆包生图时，输入 prompt 后等待 3 秒再发送，防止触发人机校验
- 抖音发布自动设置「内容由 AI 生成」声明
- 豆包生图支持拒绝检测：若 AI 拒绝生成会自动重试（最多 2 次）
- LLM 输出 JSON 时若有格式问题，`generate.py` 内置 `fix_json()` 自动修复
- 遗留数据会自动迁移到 `accounts/legacy/` 目录
