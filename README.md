# 社交媒体自动发布工具

基于 Playwright 浏览器自动化的社交媒体内容创作 & 发布工具，支持**抖音**和**小红书**两个平台，通过 `--platform` 参数明确区分执行链路。

## 支持平台

| 平台 | 参数 | 链路 |
|------|------|------|
| 抖音 | `--platform douyin` | 生成内容 → 豆包生图 → 抖音发布 |
| 小红书 | `--platform xiaohongshu` | 从 JSON 文件直接发布 |

## 项目结构

```
.
├── run.py                    # 统一入口，--platform 选择平台
├── generate.py               # 共享：调用 LLM 生成内容
├── doubao.py                 # 共享：打开豆包，批量生成图片
├── douyin/                   # 抖音链路
│   ├── __init__.py
│   └── publisher.py          # 抖音发布（文章/图文）
├── xiaohongshu/              # 小红书链路
│   ├── __init__.py
│   └── publisher.py          # 小红书发布（长文笔记）
├── doubao.json               # generate.py 的输出 / doubao.py 的输入
├── doubao_output/            # 豆包生成的图片存放目录
├── logs/                     # 执行日志（按日期记录成功/失败）
├── *_browser_profile/        # 浏览器持久化目录（保存登录状态）
└── pyproject.toml            # 项目依赖配置
```

## 环境准备

```bash
# 1. 安装依赖（默认使用清华源）
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 安装 Playwright 浏览器
uv run playwright install chromium
```

依赖：Python >= 3.12、playwright、openai

## 使用方法

### 抖音链路

抖音链路包含 3 个步骤：**生成内容 → 豆包生成图片 → 抖音发布**

```bash
# 完整执行三步（默认主题"美女"）
uv run python run.py --platform douyin

# 指定主题
uv run python run.py --platform douyin --topic "旅行攻略"

# 指定发布类型
uv run python run.py --platform douyin --type article   # 发布文章
uv run python run.py --platform douyin --type image     # 发布图文（默认）

# 指定图片数量
uv run python run.py --platform douyin --count 5
```

**分步运行：**

```bash
# 只执行某一步
uv run python run.py --platform douyin --only 1    # 只生成内容
uv run python run.py --platform douyin --only 2    # 只生成图片
uv run python run.py --platform douyin --only 3    # 只发布

# 从某一步开始（跳过前面的步骤）
uv run python run.py --platform douyin --step 2    # 从豆包生图开始
uv run python run.py --platform douyin --step 3    # 直接发布（用已有的 doubao.json + 图片）
```

### 小红书链路

小红书链路直接从 JSON 文件读取内容并发布（JSON 需包含 `title` 和 `content` 字段）：

```bash
# 默认读取 redbook.json
uv run python run.py --platform xiaohongshu

# 指定其他 JSON 文件
uv run python run.py --platform xiaohongshu --input everday_hot.json

# 用简写
uv run python run.py -p xiaohongshu -i everday_hot.json
```

**JSON 文件格式：**

```json
{
  "title": "笔记标题",
  "content": "笔记正文内容..."
}
```

### 查看帮助

```bash
uv run python run.py --help
```

## 内容类型（抖音）

| 类型 | 参数 | 说明 |
|------|------|------|
| 图文（默认） | `--type image` | 生成图片 prompt → 豆包生图 → 抖音发布图文 |
| 文章 | `--type article` | 生成文章正文 → 抖音发布文章 |
| 视频 | `--type video` | 待实现 |

## 流程图

```
抖音链路:
  run.py --platform douyin [--topic "主题"]
    │
    ├─ Step 1: generate.py
    │   └─ 调用 LLM API → 生成 JSON → 保存到 doubao.json
    │
    ├─ Step 2: doubao.py
    │   ├─ 打开豆包网页
    │   ├─ 逐条输入 prompt → 等待图片生成
    │   └─ 保存高清图片到 doubao_output/
    │
    └─ Step 3: douyin/publisher.py
        ├─ 打开抖音创作者平台
        ├─ 根据 sendType 选择发布方式
        │   ├─ article → 填写标题/正文 → 发布文章
        │   └─ image   → 上传图片/填写标题 → 发布图文
        └─ 自动选择音乐 + AI 声明 → 发布

小红书链路:
  run.py --platform xiaohongshu [--input redbook.json]
    │
    └─ xiaohongshu/publisher.py
        ├─ 读取 JSON 文件（title + content）
        ├─ 打开小红书创作者平台
        ├─ 写长文 → 填写标题/正文 → 一键排版
        └─ 发布
```

## 注意事项

- **首次运行**需要在弹出的浏览器中手动登录豆包和抖音/小红书，登录状态会保存在 `*_browser_profile/` 目录中，后续运行自动复用
- 豆包生成图片时，输入完 prompt 会等待 3 秒再发送，防止触发人机校验
- 抖音发布时会自动设置「内容由 AI 生成」声明
- 执行日志保存在 `logs/` 目录，按日期记录每步的成功/失败状态
