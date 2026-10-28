# interview-audio-review

从面试录音生成原始转写稿和离线 HTML 逐题复盘。Qwen3-ASR 转写、安装脚本、分析规范、HTML 渲染器及模板均包含在本目录中，不依赖其他转写 skill。

## 环境与转写

本地转写使用 Apple Silicon Mac、Python 3.10+ 和 Qwen3-ASR 0.6B MLX 4-bit。首次安装依赖、下载模型需要联网，转写在本地进行，无语音 API 费用。HTML 本身无需联网。

```bash
bash scripts/setup.sh
~/.cache/interview-audio-review/venv/bin/python scripts/transcribe.py "面试录音.m4a" \
  --language zh --timestamps --output "输出目录/转写稿"
```

独立环境与可选模型缓存位于 `~/.cache/interview-audio-review/`。可通过 `PYTHON_BIN`、`VENV_DIR`、`QWEN_ASR_MODEL` 覆盖配置。音视频由 PyAV 解码，不要求单独安装 ffmpeg。具体参数和局部复核见 [references/transcription.md](references/transcription.md)。

单独转文字时，省略 `--timestamps` 即得到带标点、无时间戳的段落 TXT；生成复盘时保留此参数，让渲染器建立原文锚点。时间来自音频切块，不是逐字对齐；不自动区分说话人。

## 复盘与交付

在 Codex 中提供录音并调用本技能，由代理按 [SKILL.md](SKILL.md) 阅读原文、复核歧义和完成逐题分析。名称沿用用户指定名称或既有文件名偏好。分析 JSON 遵循 [references/analysis-schema.md](references/analysis-schema.md)，然后执行：

```bash
~/.cache/interview-audio-review/venv/bin/python scripts/render_review.py \
  --transcript "输出目录/转写稿.txt" \
  --analysis "工作目录/分析.json" \
  --output "输出目录/面试复盘报告.html"
```

转写和渲染脚本负责本地处理；问答提取与评价由调用本技能的 Codex 完成，不是脚本自动调用付费分析 API。

默认报告保存到 `~/Documents/面试录音分析/YYYY-MM-DD-面试名称/`，包含原始录音（例如 `小米四面.m4a`）、`转写稿.txt` 和 `面试复盘报告.html`。原始录音按原文件名与扩展名复制，保留源文件和原始内容。用户显式指定输出目录时优先使用指定目录。同名目录追加序号，不覆盖历史结果。分析 JSON、复核片段与检查截图留在工作目录。

HTML 右侧完整原文显示为自然段落，默认隐藏时间；同题问答使用相同色系高亮。点击原文可查看左侧问题、回答和分析，最左侧纵向目录显示面试名称和各题标题，当前项显示为蓝色；点击目录可反向定位。窄屏可展开目录。每题使用“问题”“我的回复”“评价”和始终展开的推荐答法，不显示证据区块或片段计数。支持搜索和手机布局。转写稿作为独立文件交付。

默认略去现场代码实现与候选人反问的分析，相关原文仍保留。说话人和术语不清时标待核，不静默改写原话，不编造成果或推断录用结果。

## 固定处理与验收流程

新增 `scripts/prepare_analysis.py` 生成带编号阅读稿和分析草稿；由 Codex 直接填写分析 JSON，再由渲染器统一验证原文与证据。浏览器使用 `scripts/check_review.cjs`，默认抽查典型题与通用功能，必要时 `--full`。

默认一次全量转写，仅对影响结论的歧义局部重转；不再为每份录音临时编写分析生成或验收脚本。各阶段保存实测耗时，分析耗时以包含等待的墙钟时间记录，不冒充模型纯计算时间。具体命令见 [references/fast-workflow.md](references/fast-workflow.md)。

## 包含的文件

```text
interview-audio-review/
├── SKILL.md
├── README.md
├── scripts/
│   ├── setup.sh
│   ├── transcribe.py
│   ├── prepare_analysis.py
│   ├── render_review.py
│   └── check_review.cjs
├── references/
│   ├── transcription.md
│   ├── analysis-schema.md
│   └── fast-workflow.md
└── assets/review.html
```

移动或分发时保留整个目录。运行环境和模型不打入 skill 包，可由内置安装脚本及模型加载器在新机器上重新建立。
