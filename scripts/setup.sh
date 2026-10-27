#!/usr/bin/env bash
# Qwen3-ASR MLX runtime, isolated from any existing Whisper installation.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$HOME/.cache/interview-audio-review/venv}"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo "当前脚本需要 Apple Silicon Mac（MLX）。其他硬件请使用 Qwen3-ASR 官方运行时。" >&2
  exit 1
fi
TASK_PYTHON="${PYTHON_BIN:-}"
if [[ -z "$TASK_PYTHON" ]]; then
  for candidate in python3.12 python3.11 python3.10 python3 "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' 2>/dev/null; then
      TASK_PYTHON="$candidate"
      break
    fi
  done
fi
if [[ -z "$TASK_PYTHON" ]] || ! "$TASK_PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
  echo "需要 Python 3.10+，可设置 PYTHON_BIN=/绝对路径/python3。" >&2
  exit 1
fi
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$TASK_PYTHON" -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install 'mlx-audio==0.6.2' 'av>=14,<18'
echo "环境就绪；首次转写会下载模型，之后复用本地缓存。"
printf '运行：\n  %q %q "录音.m4a" --language zh\n' "$VENV_DIR/bin/python" "$SKILL_DIR/scripts/transcribe.py"
