# 抖音自动内容发布工具

基于 Playwright 浏览器自动化的抖音内容创作 & 发布流水线，支持**文章、图文、视频**三种类型，一键完成从内容生成到发布的全流程。

## 它能做什么

```
主题输入 → AI 生成内容 → AI 生成图片 → 自动发布到抖音
```

给定一个主题（如"育儿"），自动完成：

1. **内容生成** — 调用 Kimi 大模型生成标题、正文、图片提示词
2. **图片生成** — 打开豆包，逐条输入提示词，批量生成并保存高清图片
3. **自动发布** — 登录抖音创作者平台，填入标题/正文/图片，自动选择音乐、设置 AI 声明，一键发布

## 项目结构

```
.
├── run.py              # 统一启动入口，编排三步流程
├── generate.py         # 第1步：调用 Kimi 生成内容（标题/正文/prompt）
├── doubao.py           # 第2步：打开豆包，批量生成图片并保存
├── byte.py             # 第3步：登录抖音，自动填写并发布
├── doubao.json         # generate.py 的输出 / doubao.py & byte.py 的输入
├── doubao_output/      # 豆包生成的图片存放目录
├── logs/               # 执行日志（按日期记录成功/失败）
├── *_browser_profile/  # 浏览器持久化目录（保存登录状态，免重复登录）
└── pyproject.toml      # 项目依赖配置
```

## 环境准备

```bash
# 1. 安装依赖
uv sync

# 2. 安装 Playwright 浏览器
uv run playwright install chromium
```

依赖：Python >= 3.12、playwright、openai

## 使用方法

### 一键运行全流程

```bash
# 默认主题"美女"，生成图文
uv run python run.py

# 指定主题
uv run python run.py "育儿干货"

# 指定主题和类型
uv run python run.py "旅行攻略" --type article

# 生成多张图片（默认3条 prompt）
uv run python run.py "风景" --count 5
```

### 分步运行

```bash
# 从第2步开始（跳过内容生成，直接用已有的 doubao.json）
uv run python run.py --step 2

# 只运行某一步
uv run python run.py --only 1    # 只生成内容
uv run python run.py --only 2    # 只生成图片
uv run python run.py --only 3    # 只发布到抖音
```

### 单独运行某个脚本

```bash
uv run python generate.py "主题" --type image --count 3
uv run python doubao.py
uv run python byte.py
```

## 内容类型

| 类型 | 参数 | 说明 |
|------|------|------|
| 图文（默认） | `--type image` | 生成图片 prompt → 豆包生图 → 抖音发布图文 |
| 文章 | `--type article` | 生成文章正文 → 抖音发布文章 |
| 视频 | `--type video` | 生成视频文案（视频发布功能待实现） |

## 注意事项

- **首次运行**需要在弹出的浏览器中手动登录豆包和抖音，登录状态会保存在 `*_browser_profile/` 目录中，后续运行自动复用
- 豆包生成图片时，输入完 prompt 会等待 3 秒再发送，防止触发人机校验
- 抖音发布时会自动设置「内容由 AI 生成」声明
- 执行日志保存在 `logs/` 目录，按日期记录每步的成功/失败状态

## 流程图

```
run.py
  │
  ├─ Step 1: generate.py
  │   └─ 调用 Kimi API → 生成 JSON → 保存到 doubao.json
  │
  ├─ Step 2: doubao.py
  │   ├─ 打开豆包网页
  │   ├─ 逐条输入 prompt → 等待图片生成
  │   └─ 保存高清图片到 doubao_output/
  │
  └─ Step 3: byte.py
      ├─ 打开抖音创作者平台
      ├─ 根据 sendType 选择发布方式
      │   ├─ article → 填写标题/正文 → 发布文章
      │   └─ image   → 上传图片/填写标题 → 发布图文
      └─ 自动选择音乐 + AI 声明 → 发布
```
