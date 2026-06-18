# EPUB Bilingual Translator - 本地 EPUB 双语翻译器

[English README](README.md)

Paperford 是一个本地运行的 EPUB 双语翻译工作台。它把长篇 EPUB 解析成可控的文本块，通过 OpenAI 兼容接口批量翻译，再生成原文与译文交错排版的双语 EPUB。

它的目标不是做“能用就行”的机器直译，而是提供更接近编辑工作流的控制：术语表、翻译档位、风格预设、上下文延续、缓存、失败重试和本地隐私边界。

![Paperford home screen](docs/assets/paperford-home.png)

## 为什么叫 Paperford

Paperford 可以理解为 “paper + ford”：把一本书从原文渡到另一种语言的本地工具。为了让 GitHub 访客一眼看懂用途，本项目现在统一使用更明确的展示名：

**Paperford - Local EPUB Bilingual Translator**

## 核心亮点

- 本地 Web 应用：FastAPI 后端 + React/Vite 前端，一条命令启动。
- EPUB 双语输出：保留原文结构，把译文插入到对应文本块后方。
- OpenAI 兼容接口：支持 OpenAI、DeepSeek、xAI、Gemini 兼容端点和自定义 Base URL。
- 更自然的翻译控制：快速初译、均衡、精修三个档位，内置文学、忠实、网文、非虚构风格。
- 自动术语表：从书稿前段、中段、后段抽样提取人物、地名、组织和专有名词。
- 长段落处理：按 token 估算自动拆分长文本，翻译后合并回原段落。
- 本地缓存：SQLite 缓存相同文本和相同配置，减少重复请求和成本。
- 进度面板：显示速度、预计剩余时间、批次耗时、缓存命中和失败数。
- 隐私边界清晰：EPUB 文件留在本机；API Key 只保存在当前页面内存中。

![Paperford progress and settings](docs/assets/paperford-progress-settings.png)

## 快速开始

```bash
git clone https://github.com/zommmo/epub-bilingual-translator.git
cd epub-bilingual-translator
./run_web.sh
```

启动后打开：

```text
http://127.0.0.1:8000
```

`run_web.sh` 会自动准备 Python 虚拟环境、安装依赖、用 Vite 构建前端，并启动本地 FastAPI 服务。macOS 上如果安装了 Homebrew `node@22`，脚本会优先使用它。

## 手动安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
.venv/bin/python -m uvicorn api_app:app --host 127.0.0.1 --port 8000
```

## 使用流程

1. 在右侧设置区填写 API Key。
2. 选择 Provider，或添加只在当前页面会话中保存的自定义 Provider。
3. 填写模型名称，或点击“获取模型”。
4. 上传 EPUB，可先点击“解析预览”确认抽取结果。
5. 选择翻译档位、风格预设、目标语言、温度、批大小、并发数和最大文本块数。
6. 可选：点击“自动提取术语”，或手动维护全局术语表。
7. 点击“开始翻译”，完成后下载双语 EPUB。
8. 如需强制重新翻译，可在调试区清除翻译缓存。

## 翻译质量控制

Paperford 会把用户风格要求、术语表、上下文片段和输出 JSON 约束分层组织，避免自定义 prompt 破坏结构化输出。

三个翻译档位的定位：

- **快速初译**：更大的处理窗口，更少上下文，适合快速扫书或低成本初稿。
- **均衡**：默认模式，兼顾上下文、速度和译文自然度。
- **精修**：更小窗口并增加润色步骤，适合对文风要求更高的长篇阅读副本。

内置风格预设：

- **文学自然**：保留叙事声音、节奏、意象和对话自然度。
- **忠实克制**：尽量贴近原文信息顺序和细节，不主动扩写。
- **轻小说 / 网文**：更直接、顺畅、节奏感更强。
- **非虚构**：强调术语准确、逻辑清晰和低修辞负担。

## 自动术语表

自动提取术语不会把整本书发给模型，而是从前段、中段和后段抽样约 `18000` 个字符，请模型提取主要人物、地点、阵营、组织和专有名词。

术语表格式：

```text
Alice=爱丽丝
King's Landing=君临城
Silver City=银城
```

术语表会参与缓存 key。修改术语后，Paperford 会生成新的缓存记录，避免复用旧译文。

## 输出和缓存

- 生成的 EPUB 写入 `output/`，也可在页面里直接下载。
- 翻译缓存默认保存在 `translations.sqlite3`。
- 缓存 key 包含文本 hash、模型、prompt 版本、目标语言、温度、Thinking 模式、翻译档位、风格预设、自定义风格和术语表 hash。

## 安全说明

- 上传文件必须是 `.epub`，不能为空，默认最大 100MB。
- 后端限制翻译参数范围：温度 `0-2`，批大小 `1-50`，并发 `1-20`，最大文本块 `0-200000`。
- API Key 只保存在当前页面内存中，刷新页面即丢失。
- 自定义 Provider 的 Base URL 会收到你输入的 API Key，只应填写可信服务商或你自己控制的代理端点。
- Thinking 模式默认关闭；只有确认模型支持时才建议开启。

## 开发验证

```bash
.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests
cd frontend && npm run build
cd frontend && npm audit --audit-level=moderate
```

GitHub Actions 会在 push 和 pull request 时运行后端测试与前端构建；CodeQL 和 Dependabot 用于基础安全扫描和依赖更新提醒。

## 当前限制

- 同一时间只能处理一本 EPUB。
- 自定义 Provider 只保存在当前页面会话中，刷新后会消失。
- 文本抽取目前覆盖 `h1-h6`、`p`、`li` 标签。
- 失败段落可重试；重试前下载的 EPUB 会对失败段落使用 `[未翻译]` 占位。

## License

MIT License
