# VideoAudit AI 🎥✨

> **智能视频审核专家** - AI-Powered Video Content Analysis & Moderation System

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🌟 简介

**VideoAudit AI** 是一款专业的短视频内容分析与审核系统，专为 TikTok 营销视频打造。通过集成 Google Gemini 多模态 AI，实现从视频批量下载到智能内容审核的全流程自动化。

### 核心能力

| 模块 | 功能 | 技术栈 |
|------|------|--------|
| **视频下载** | 批量下载 TikTok 视频，支持 CSV/TXT/ZIP 输入 | yt-dlp |
| **智能审核** | AI 多维度视频内容分析与标签化 | Google Gemini 2.5 Flash |
| **报告生成** | 自动生成 HTML/JSON 分析报告，含视频预览 | OpenCV, Jinja2 |

---

## ✨ 核心特性

### 1️⃣ 智能视频下载器 (TT_batch_downloader)

- 🚀 **批量下载**: 支持一次性下载数百个视频
- 📁 **灵活输入**: 支持 CSV、TXT、ZIP 压缩包作为 URL 来源
- 🔍 **智能解析**: 自动检测文件编码和分隔符，确保 URL 提取成功
- 📊 **进度追踪**: CSV 文件记录下载进度，自动跳过已下载视频
- 🛡️ **容错机制**: 内置重试逻辑，处理网络波动和平台限制
- 📦 **自动分卷**: 每 100 个视频自动创建新文件夹

### 2️⃣ AI 内容审核系统 (run_video_processing)

- 🤖 **多模态分析**: 利用 Gemini 2.5 Flash 理解视频内容
- 🎯 **四维审核**: 可自定义的审核维度（环境、功能、文案、品牌）
- 📝 **自动标签**: 为每个视频生成结构化审核标签
- 📊 **详细报告**: HTML 可视化报告，支持视频在线预览
- 👤 **多用户隔离**: 支持多用户独立工作空间
- ⚡ **API 重试**: 智能处理 API 限流和错误

---

## 🚀 快速开始

### 环境要求

- Python 3.9+
- Google Cloud 账号（启用 Vertex AI API）
- FFmpeg（可选，用于视频处理）

### 安装

```bash
# 克隆项目
git clone https://github.com/Looperswag/Mkt_AI_debug.git
cd Mkt_AI_debug

# 安装依赖
pip install -r requirements.txt
```

### 配置

设置环境变量（推荐）：

```bash
# Google Cloud 配置
export GOOGLE_KEY_PATH="path/to/your/key.json"
export GEMINI_PROJECT_ID="your-project-id"
export GEMINI_LOCATION="us-central1"
```

或创建 `.env` 文件：

```env
GOOGLE_KEY_PATH=path/to/your/key.json
GEMINI_PROJECT_ID=your-project-id
GEMINI_LOCATION=us-central1
```

### 使用方法

#### 1. 下载 TikTok 视频

创建一个包含 TikTok URL 的 CSV 文件（列名为 `url`）：

```bash
# 下载视频
python -m TT_batch_downloader.main -i urls.csv -o downloaded_videos

# 或使用命令行工具
videoaudit-download -i urls.csv -o downloaded_videos --max-videos 50
```

**支持的输入格式：**

- CSV 文件（包含 `url` 列）
- TXT 文件（每行一个 URL）
- ZIP 文件（包含上述文件）

#### 2. AI 视频审核

```bash
# 运行审核程序
python -m run_video_processing.main

# 或使用命令行工具
videoaudit-process
```

程序将提示输入用户名，然后处理 `user/<username>/original_scene/` 中的所有视频。

---

## 📁 项目结构

```
videoaudit-ai/
├── TT_batch_downloader/          # 视频下载模块
│   ├── main.py                   # CLI 入口，URL 提取器
│   ├── tiktok_data_collector.py  # 下载核心逻辑
│   ├── models.py                 # 数据模型定义
│   └── get_video.py              # 批量下载器（兼容旧版）
│
├── run_video_processing/         # AI 审核模块
│   ├── main.py                   # CLI 入口
│   ├── video_labeler.py          # 视频标注逻辑
│   ├── gemini_utils.py           # Gemini API 集成
│   ├── video_utils.py            # 视频工具函数
│   ├── report_generator.py       # 报告生成器
│   └── config.py                 # 配置管理
│
├── user/                          # 用户数据目录（自动创建）
│   └── <username>/
│       ├── original_scene/       # 待审核视频
│       └── Result_folder_labeled/ # 审核结果
│
├── requirements.txt               # 项目依赖
├── .gitignore                     # Git 忽略规则
├── pyproject.toml                 # 项目配置
└── README.md                      # 本文件
```

---

## 🔧 自定义审核标准

编辑 `run_video_processing/gemini_utils.py` 中的 `DEFAULT_ANALYSIS_PROMPT`：

```python
DEFAULT_ANALYSIS_PROMPT = """
请分析此产品视频，并根据以下标准进行打标。

1. 拍摄环境：[自定义标准]
2. 功能展示：[自定义标准]
3. 文案合规：[自定义标准]
4. 品牌识别：[自定义标准]

请以以下格式输出（使用 "-" 分隔）：
合格/不合格-合格/不合格-合格/不合格-合格/不合格
"""
```

---

## 📊 输出报告

审核完成后，系统将生成：

1. **HTML 报告** (`processing_report.html`)
   - 处理摘要统计
   - 每个视频的详细分析
   - 内嵌视频播放器
   - 响应式设计，支持移动端查看

2. **JSON 摘要** (`processing_summary.json`)
   - 机器可读的结构化数据
   - 便于后续数据处理和集成

---

## 🛠️ 开发

### 代码规范

项目遵循严格的 Python 代码规范：

```bash
# 代码格式化
black .
isort .

# 类型检查
mypy .

# 代码检查
ruff check .
bandit -r .
```

### 运行测试

```bash
# 运行所有测试
pytest

# 带覆盖率报告
pytest --cov=. --cov-report=html
```

---

## ⚠️ 注意事项

### 法律与合规

- 确保您有权下载和使用目标视频内容
- 遵守 TikTok 平台的服务条款和 API 使用规范
- 尊重内容创作者的版权和隐私权

### 技术限制

- **下载限制**: 大量频繁下载可能触发平台限流
- **API 配额**: Gemini API 有调用频率和配额限制
- **文件大小**: 单个视频文件建议不超过 500MB
- **处理时间**: AI 分析每个视频约需 10-30 秒

---

## 🤝 贡献

欢迎贡献！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📝 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 强大的视频下载工具
- [Google Gemini](https://ai.google.dev/) - 多模态 AI 能力
- [OpenCV](https://opencv.org/) - 视频处理

---

## 📮 联系方式

- 问题反馈: [GitHub Issues](https://github.com/Looperswag/Mkt_AI_debug/issues)

---

<div align="center">

**用 AI 赋能视频内容审核** 🎥✨

Made with ❤️ by VideoAudit AI Team

</div>
