# interview-audio-review

从面试录音生成原始文字稿和离线 HTML 逐题复盘。Qwen3-ASR 转写、安装脚本、分析规范、HTML 渲染器及模板均包含在本目录中，不依赖其他转写 skill。

## 环境与转写

本地转写使用 Apple Silicon Mac、Python 3.10+ 和 Qwen3-ASR 0.6B MLX 4-bit。首次安装依赖、下载模型需要联网，转写在本地进行，无语音 API 费用。HTML 本身无需联网。

```bash
bash scripts/setup.sh
~/.cache/interview-audio-review/venv/bin/python scripts/transcribe.py "面试录音.m4a" \
  --language zh --timestamps --output "输出目录/文字稿"
```

独立环境与可选模型缓存位于 `~/.cache/interview-audio-review/`。可通过 `PYTHON_BIN`、`VENV_DIR`、`QWEN_ASR_MODEL` 覆盖配置。音视频由 PyAV 解码，不要求单独安装 ffmpeg。具体参数和局部复核见 [references/transcription.md](references/transcription.md)。

单独转文字时，省略 `--timestamps` 即得到带标点、无时间戳的段落 TXT；生成复盘时保留此参数，让渲染器建立原文锚点。时间来自音频切块，不是逐字对齐；不自动区分说话人。

## 复盘与交付

在 Codex 中提供录音并调用本技能，由代理按 [SKILL.md](SKILL.md) 阅读原文、复核歧义和完成逐题分析。名称沿用用户指定名称或既有文件名偏好。分析 JSON 遵循 [references/analysis-schema.md](references/analysis-schema.md)，然后执行：

```bash
~/.cache/interview-audio-review/venv/bin/python scripts/render_review.py \
  --transcript "输出目录/文字稿.txt" \
  --analysis "工作目录/分析.json" \
  --output "输出目录/面试复盘.html"
```

转写和渲染脚本负责本地处理；问答提取与评价由调用本技能的 Codex 完成，不是脚本自动调用付费分析 API。

每段录音交付 `interview-reviews/YYYY-MM-DD-面试名称/文字稿.txt` 和 `面试复盘.html`。同名目录追加序号，不覆盖历史结果。分析 JSON、复核片段与检查截图留在工作目录。

HTML 右侧完整原文显示为自然段落，默认隐藏时间；同题问答使用相同色系高亮。点击原文可查看左侧问题、回答和分析，导航及证据按钮可反向定位。支持搜索、折叠、文字稿下载和手机布局。

默认略去现场代码实现与候选人反问的分析，相关原文仍保留。说话人和术语不清时标待核，不静默改写原话，不编造成果或推断录用结果。

## 包含的文件

```text
interview-audio-review/
├── SKILL.md
├── README.md
├── scripts/
│   ├── setup.sh
│   ├── transcribe.py
│   └── render_review.py
├── references/
│   ├── transcription.md
│   └── analysis-schema.md
└── assets/review.html
```

移动或分发时保留整个目录。运行环境和模型不打入 skill 包，可由内置安装脚本及模型加载器在新机器上重新建立。
