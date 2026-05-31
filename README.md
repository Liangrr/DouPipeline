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
├── scheduler.py                  # 定时执行脚本
├── run_scheduler.sh              # 定时任务守护脚本（防休眠+自动重启）
├── generate.py                   # LLM 内容生成（可独立运行）
├── doubao.py                     # 豆包 AI 生图自动化
├── douyin/                       # 抖音链路
│   ├── __init__.py
│   └── publisher.py              # 抖音发布（文章/图文）
├── xiaohongshu/                  # 小红书链路
│   ├── __init__.py
│   └── publisher.py              # 小红书发布（长文笔记）
├── doubao.json                   # generate.py 输出 → doubao.py / douyin.publisher 输入
├── xiaohongshu.json              # 小红书文案数据
├── doubao_output/                # 豆包生成的图片
├── logs/                         # 执行日志（JSONL，按日期分文件）
├── byte_browser_profile/         # 抖音浏览器持久化（登录状态）
├── doubao_browser_profile/       # 豆包浏览器持久化
├── browser_profile/              # 小红书浏览器持久化
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

### 抖音链路

抖音链路包含 3 个步骤：**生成内容 → 豆包生成图片 → 抖音发布**

```bash
# 完整执行三步（默认主题"美女"）
uv run python run.py --platform douyin

# 指定主题和类型
uv run python run.py --platform douyin --topic "旅行攻略"
uv run python run.py --platform douyin --type article   # 发布文章
uv run python run.py --platform douyin --type image     # 发布图文（默认）
python run.py --platform douyin --type article --topic "agent记忆系统" --account asuria

uv run python run.py --platform douyin --type article --account asuria
uv run python run.py --platform douyin --type article --account asuria --topic "agent记忆系统" --only 3

# 指定图片数量
uv run python run.py --platform douyin --count 5
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
| 文章 | `--type article` | 生成文章正文 → 抖音发布文章 |
| 视频 | `--type video` | 待实现 |

## 独立运行各模块

除通过 `run.py` 统一调度外，各模块也可独立运行：

```bash
# generate.py — LLM 内容生成
uv run python generate.py "旅行攻略" --type image --count 5 --output doubao.json

# doubao.py — 豆包生图（读取 doubao.json）
uv run python doubao.py

# douyin/publisher.py — 抖音发布
uv run python -m douyin.publisher --type article

# xiaohongshu/publisher.py — 小红书发布
uv run python -m xiaohongshu.publisher --input my_note.json
```

## 运行流程

```
抖音链路 (3步):
  run.py --platform douyin [--topic "主题"] [--type article|image] [--count N]
    │
    ├─ Step 1: generate.py
    │   └─ 调用 mimo-v2.5 LLM → 生成标题/摘要/正文/图片 prompt → 保存 doubao.json
    │
    ├─ Step 2: doubao.py
    │   ├─ 打开豆包网页 (持久化浏览器)
    │   ├─ 逐条输入 prompt → 等待图片生成（最多 180s）
    │   ├─ 拒绝检测 + 最多重试 2 次
    │   └─ 拦截高清图片响应 → 保存到 doubao_output/
    │
    └─ Step 3: douyin/publisher.py
        ├─ 打开抖音创作者平台 (持久化浏览器)
        ├─ 根据 sendType 选择发布方式
        │   ├─ article → 填写标题/摘要/正文 → 上传封面 → 发布文章
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
  "step": 1,
  "step_name": "generate",
  "status": "success"
}
```

## 定时执行

通过 `scheduler.py` 定时自动执行发布任务。

### 修改定时规则

编辑 [scheduler.py:28-36](scheduler.py#L28-L36) 的 `SCHEDULES` 列表，格式为 `(minute, hour, platform, extra_args)`：

`minute` 和 `hour` 支持三种写法：

| 写法 | 含义 | 示例 |
|------|------|------|
| 具体数字 | 精确匹配 | `hour=9` → 第 9 小时 |
| `"*"` | 每个都执行 | `hour="*"` → 每小时 |
| `"*/N"` | 每隔 N 执行 | `hour="*/2"` → 每 2 小时 |

```python
SCHEDULES = [
    # (minute, hour, platform, extra_args)

    # 每天固定时间
    (0,  9,     "douyin",      ["--type", "article"]),    # 每天 9:00
    (30, 9,     "xiaohongshu", []),                        # 每天 9:30

    # 每隔 N 小时
    (0,  "*/4", "douyin",      ["--type", "image"]),      # 每 4 小时
    (0,  "*/2", "xiaohongshu", []),                        # 每 2 小时

    # 每小时
    (0,  "*",   "douyin",      ["--type", "image"]),      # 每小时整点
]
```

**常用配置示例：**

| 需求 | 配置 |
|------|------|
| 每天 9:00 抖音发文章 | `(0, 9, "douyin", ["--type", "article"])` |
| 每 4 小时 抖音发图文 | `(0, "*/4", "douyin", ["--type", "image"])` |
| 每 2 小时的 30 分 小红书 | `(30, "*/2", "xiaohongshu", [])` |
| 每小时整点 抖音发文章 | `(0, "*", "douyin", ["--type", "article"])` |
| 注释掉（暂停） | 在行首加 `#`，如 `# (0, "*/4", "douyin", [])` |

### 执行

**快速调试（前台运行）：**

```bash
uv run python scheduler.py
```

按 `Ctrl+C` 停止。

**生产环境（后台守护）：**

通过 [run_scheduler.sh](run_scheduler.sh) 启动，支持防休眠、自动重启、后台运行：

```bash
# 启动（后台守护，关屏合盖不停，异常自动重启）
./run_scheduler.sh start

# 停止
./run_scheduler.sh stop

# 重启
./run_scheduler.sh restart

# 查看运行状态
./run_scheduler.sh status

# 实时查看日志
./run_scheduler.sh logs

# 前台运行（调试用，Ctrl+C 停止）
./run_scheduler.sh foreground
```

| 功能 | 说明 |
|------|------|
| 防休眠 | `caffeinate -i -s` 关屏合盖系统不休眠 |
| 自动重启 | scheduler.py 异常退出后 5 秒自动重启 |
| 后台运行 | `nohup` 守护，关闭终端不影响 |
| 日志记录 | `logs/scheduler.log` |

### 修改检查频次

默认每 **30 秒**检查一次时间。修改 [scheduler.py:103](scheduler.py#L103)：

```python
time.sleep(30)  # 改成你需要的秒数，如 60
```

## 注意事项

- **首次运行**需手动登录：弹出浏览器后扫码登录豆包/抖音/小红书，登录状态保存在 `*_browser_profile/` 目录中，后续自动复用
- 豆包生图时，输入 prompt 后等待 3 秒再发送，防止触发人机校验
- 抖音发布自动设置「内容由 AI 生成」声明
- 豆包生图支持拒绝检测：若 AI 拒绝生成会自动重试（最多 2 次）
- LLM 输出 JSON 时若有格式问题，`generate.py` 内置 `fix_json()` 自动修复
