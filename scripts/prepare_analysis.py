#!/usr/bin/env python3
"""Prepare an indexed reading copy and a draft for direct JSON authoring."""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from render_review import LINE, seconds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transcript', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--title', required=True)
    parser.add_argument('--audio', required=True)
    parser.add_argument('--date', default=date.today().isoformat())
    args = parser.parse_args()
    started = time.perf_counter()
    raw = args.transcript.read_text(encoding='utf-8')
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    segments = []
    for n, line in enumerate(raw.splitlines(), 1):
        match = LINE.fullmatch(line)
        if match:
            start, end, text = match.groups()
            if seconds(end) < seconds(start) or (segments and seconds(start) < seconds(segments[-1]['start'])):
                parser.error(f'Invalid or nonchronological segment on line {n}')
            segments.append({'id': f'l{n}', 'start': start, 'end': end, 'text': text})
    if not segments:
        parser.error('Transcript has no timestamped segments')
    args.work_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.work_dir / '准备记录.json'
    draft = args.work_dir / '分析.json'
    previous = None
    if draft.exists():
        if not manifest_path.exists():
            parser.error('Analysis already exists without a preparation record; choose another work directory')
        previous = json.loads(manifest_path.read_text(encoding='utf-8'))
        if previous['transcript_sha256'] != digest:
            parser.error('Transcript changed; use another work directory to avoid stale evidence')
        if (previous['title'], previous['audio'], previous['date']) != (args.title, args.audio, args.date):
            parser.error('Report metadata changed; use another work directory')
    else:
        draft.write_text(json.dumps({'title': args.title, 'date': args.date, 'audio': args.audio,
                                    'summary': [], 'questions': []}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    reading = args.work_dir / '阅读稿.txt'
    reading.write_text('\n'.join(f'[{s["id"]} | {s["start"]} -> {s["end"]}] {s["text"]}'
                                 for s in segments) + '\n', encoding='utf-8')
    manifest = {'transcript': str(args.transcript.resolve()), 'transcript_sha256': digest,
                'title': args.title, 'audio': args.audio, 'date': args.date,
                'segment_count': len(segments),
                'analysis_started_at': previous['analysis_started_at'] if previous else datetime.now(timezone.utc).isoformat(),
                'prepare_seconds': round(time.perf_counter() - started, 4)}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Prepared {len(segments)} source segments: {reading}')
    print(f'Author the analysis directly in: {draft}')


if __name__ == '__main__':
    main()
