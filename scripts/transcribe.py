#!/usr/bin/env python3
"""Local Qwen3-ASR transcription on Apple Silicon; plain paragraphs by default."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import sys
import time

MODEL_ID = "mlx-community/Qwen3-ASR-0.6B-4bit"
MODEL_CACHE = Path.home() / ".cache/interview-audio-review/models/Qwen3-ASR-0.6B-4bit"
SAMPLE_RATE = 16000


def fmt_clock(seconds):
    h, rem = divmod(int(round(seconds)), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def join_text(left, right):
    if left and right and left[-1].isascii() and right[0].isascii():
        if left[-1].isalnum() and right[0].isalnum():
            return left + " " + right
    return left + right


def paragraphs(segments, target=180):
    """Only insert whitespace; never correct, paraphrase or infer speakers."""
    text = ""
    for seg in segments:
        text = join_text(text, re.sub(r"\s+", " ", seg["text"]).strip())
    result, current = [], ""
    for sentence in re.split(r"(?<=[。！？!?])", text):
        current += sentence
        if len(current) >= target:
            result.append(current.strip())
            current = ""
    if current.strip():
        result.append(current.strip())
    return "\n\n".join(result) + ("\n" if result else "")


def decode_audio(path):
    import av
    import numpy as np

    frames = []
    with av.open(str(path)) as container:
        resampler = av.AudioResampler(format="fltp", layout="mono", rate=SAMPLE_RATE)
        for frame in container.decode(audio=0):
            for converted in resampler.resample(frame):
                frames.append(converted.to_ndarray().reshape(-1))
        for converted in resampler.resample(None):
            frames.append(converted.to_ndarray().reshape(-1))
    if not frames:
        raise ValueError("音频没有可解码的声音轨道")
    return np.concatenate(frames).astype(np.float32, copy=False)


def audio_chunks(audio, seconds):
    """Cover every sample once; prefer a quiet boundary in the last five seconds."""
    import numpy as np

    start, limit = 0, int(seconds * SAMPLE_RATE)
    frame_size = SAMPLE_RATE // 10
    while start < len(audio):
        end = min(start + limit, len(audio))
        if end < len(audio):
            search_start = max(start + limit // 2, end - 5 * SAMPLE_RATE)
            region = audio[search_start:end]
            count = len(region) // frame_size
            if count:
                energy = np.mean(region[:count * frame_size].reshape(count, frame_size) ** 2, axis=1)
                end = search_start + int(np.argmin(energy)) * frame_size + frame_size // 2
        yield start, end, audio[start:end]
        start = end


def main():
    parser = argparse.ArgumentParser(description="Qwen3-ASR 本地转写：默认带标点、无时间戳的段落文字")
    parser.add_argument("audio", type=Path, help="m4a/mp3/wav/mp4/flac 等音视频文件")
    parser.add_argument("--model", default=None, help="MLX Qwen3-ASR 模型目录或 Hugging Face ID")
    parser.add_argument("--language", default=None, help="zh/en/Chinese/English 等；默认自动检测")
    parser.add_argument("--format", choices=["txt"], default="txt", help="输出 TXT；不生成未经强制对齐的 SRT")
    parser.add_argument("--output", type=Path, help="输出前缀，不含扩展名；默认与音频同目录同名")
    parser.add_argument("--timestamps", action="store_true", help="显式改为带音频块起止时间的 TXT（非逐字对齐）")
    parser.add_argument("--metadata", action="store_true", help="额外保存 .json，包含原始块文字和粗粒度定位信息")
    parser.add_argument("--metrics-output", type=Path, help="将各阶段实测耗时保存到指定 JSON（建议放工作目录）")
    parser.add_argument("--hotword", action="append", default=[], help="可重复传入术语提示，不包含推荐答案")
    parser.add_argument("--chunk-seconds", type=float, default=25.0, help="每块最长秒数，默认 25，范围 5–30")
    parser.add_argument("--max-tokens", type=int, default=1024, help="每个音频块的 token 上限")
    parser.add_argument("--start", type=float, default=0.0, help="只转写指定起点之后的录音，单位秒")
    parser.add_argument("--duration", type=float, help="只转写指定长度，单位秒；默认直到录音末尾")
    args = parser.parse_args()
    if not args.audio.is_file():
        parser.error(f"找不到音频：{args.audio}")
    if not 5 <= args.chunk_seconds <= 30:
        parser.error("--chunk-seconds 必须在 5–30 秒之间")
    if args.start < 0 or (args.duration is not None and args.duration <= 0) or args.max_tokens <= 0:
        parser.error("起点须非负，时长与 token 上限须为正数")
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        parser.error("本脚本使用 MLX，需要 Apple Silicon Mac；其他硬件需采用 Qwen3-ASR 官方运行时")
    try:
        import numpy as np
        from mlx_audio.stt import load
    except ImportError as exc:
        parser.exit(1, f"缺少运行依赖：{exc}。请先运行 scripts/setup.sh，并使用其打印的 Python 路径。\n")

    started = time.perf_counter()
    audio = decode_audio(args.audio)
    decoded = time.perf_counter()
    original_duration = len(audio) / SAMPLE_RATE
    first = int(args.start * SAMPLE_RATE)
    last = len(audio) if args.duration is None else min(len(audio), first + int(args.duration * SAMPLE_RATE))
    audio = audio[first:last]
    if not len(audio):
        parser.error("指定范围没有音频")
    chosen_model = args.model or os.environ.get("QWEN_ASR_MODEL") or (str(MODEL_CACHE) if (MODEL_CACHE / "config.json").exists() else MODEL_ID)
    language = {"zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean", "yue": "Cantonese"}.get(args.language, args.language)
    if language in ("auto", ""):
        language = None
    print(f"加载 Qwen3-ASR：{chosen_model}", flush=True)
    model = load(chosen_model)
    loaded = time.perf_counter()
    segments = []
    for i, (start, end, samples) in enumerate(audio_chunks(audio, args.chunk_seconds), 1):
        # Skip digital silence only; do not pretend this energy check is speaker detection.
        if np.max(np.abs(samples)) < 1e-5:
            text, detected_language = "", None
        else:
            result = model.generate(samples, language=language, max_tokens=args.max_tokens,
                                    temperature=0.0, hotwords=args.hotword or None, verbose=False)
            if result.generation_tokens >= args.max_tokens:
                raise RuntimeError("模型达到 token 上限，已停止以避免静默截断；请提高 --max-tokens 后重试")
            text, detected_language = result.text.strip(), result.language
        segments.append({"id": i, "start": args.start + start / SAMPLE_RATE,
                         "end": args.start + end / SAMPLE_RATE,
                         "text": text, "language": detected_language})
        print(f"已处理 {fmt_clock(args.start + end / SAMPLE_RATE)}，第 {i} 块", flush=True)

    recognized = time.perf_counter()
    base = args.output or args.audio.with_suffix("")
    base.parent.mkdir(parents=True, exist_ok=True)
    txt_path = Path(str(base) + ".txt")
    if args.timestamps:
        content = "\n".join(f'[{fmt_clock(s["start"])} -> {fmt_clock(s["end"])}] {s["text"]}'
                            for s in segments if s["text"]) + "\n"
    else:
        content = paragraphs(segments)
    txt_path.write_text(content, encoding="utf-8")
    if args.metadata:
        metadata = {"engine": "Qwen3-ASR / mlx-audio", "model": chosen_model,
                    "audio": str(args.audio.resolve()), "audio_duration": original_duration,
                    "range_start": args.start, "range_end": args.start + len(audio) / SAMPLE_RATE,
                    "time_precision": "audio_chunk_boundaries_not_word_alignment",
                    "paragraphs": "punctuation_and_length_not_semantic_or_speaker_segmentation",
                    "hotwords": args.hotword, "segments": segments}
        Path(str(base) + ".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finished = time.perf_counter()
    if args.metrics_output:
        metrics = {"decode_seconds": round(decoded - started, 4), "load_seconds": round(loaded - decoded, 4),
                   "recognize_seconds": round(recognized - loaded, 4), "write_seconds": round(finished - recognized, 4),
                   "total_seconds": round(finished - started, 4), "audio_seconds": len(audio) / SAMPLE_RATE,
                   "segment_count": len(segments)}
        args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
        args.metrics_output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {txt_path}，耗时 {finished - started:.1f} 秒", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as exc:
        sys.exit(f"转写失败：{exc}")
