# 本地 Qwen3-ASR 转写

使用本技能的 `scripts/setup.sh` 和 `scripts/transcribe.py`。当前实现需要 Apple Silicon Mac、Python 3.10+，默认模型为 `mlx-community/Qwen3-ASR-0.6B-4bit`。其他硬件未适配。

## 环境

首次执行 `bash scripts/setup.sh`，默认环境为 `~/.cache/interview-audio-review/venv`；用 `PYTHON_BIN`、`VENV_DIR` 分别指定 Python 和环境位置。安装依赖和首次下载模型需要联网，转写在本机进行。

脚本优先使用 `--model`，其次是 `QWEN_ASR_MODEL`，再检查 `~/.cache/interview-audio-review/models/Qwen3-ASR-0.6B-4bit`，最后使用默认模型仓库及 Hugging Face 缓存。自定义模型须为 MLX 格式，不能直接使用 PyTorch 权重。

## 命令

在本技能目录执行，复盘转写的完整命令见 [SKILL.md](../SKILL.md#执行命令)。局部复核示例：

```bash
~/.cache/interview-audio-review/venv/bin/python scripts/transcribe.py "录音.m4a" \
  --language zh --start 340 --duration 45 --metadata --output "工作目录/局部复核"
```

`--output` 是不含扩展名的路径前缀；必须显式指定，避免默认写到音频旁。PyAV 解码 m4a、mp3、wav、mp4、flac 等音视频，无需 ffmpeg 命令。

## 输出与特殊参数

- 默认 TXT 为带标点、无时间戳的段落文字；复盘需加 `--timestamps`，每行为 `[HH:MM:SS -> HH:MM:SS] 原文`。格式调整仅处理空白，不润色或纠字。
- `--metadata` 保存含片段原文、起止秒数及模型配置的 JSON，用于复核；渲染器读取带时间锚点的 TXT。
- `--metrics-output` 保存各阶段计时；`--language zh` 指定中文，省略时自动识别。
- `--hotword` 可重复传入已知术语，仅用词表，不提示期望答案；需检查误识别。
- `--chunk-seconds` 默认 25，范围 5–30 秒，优先在末尾较安静处切分。达到 `--max-tokens` 上限会停止，需提高上限后重试，不静默截断。

其他参数见 `transcribe.py --help`。尚未实现完整 VAD、说话人分离或强制对齐，不生成 SRT。环境首次安装或报错时先用短片段验证，环境正常则直接全量转写。
