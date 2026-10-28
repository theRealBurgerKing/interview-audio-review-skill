#!/usr/bin/env python3
"""Validate evidence/turn links and render a self-contained interview review."""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

LINE = re.compile(r'^\[(\d{2}:\d{2}:\d{2}) -> (\d{2}:\d{2}:\d{2})\] (.*)$')
ROLES = {'interviewer': '提问', 'candidate': '回答', 'context': '说明', 'uncertain': '说话人待核'}


def seconds(clock):
    if not isinstance(clock, str) or not re.fullmatch(r'\d{2}:\d{2}:\d{2}', clock):
        raise ValueError(f'Invalid timestamp: {clock!r}')
    h, m, s = map(int, clock.split(':'))
    if m > 59 or s > 59:
        raise ValueError(f'Invalid timestamp: {clock}')
    return h * 3600 + m * 60 + s


def normalized(text):
    return re.sub(r'\s+', '', text)


def prepare(raw, data):
    for key in ('title', 'date', 'audio'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f'Missing {key}')
    if not isinstance(data.get('summary'), list) or not data['summary']:
        raise ValueError('Missing summary')
    lines, segments = [], []
    for line_no, line in enumerate(raw.splitlines(), 1):
        match = LINE.fullmatch(line)
        item = {'id': f'l{line_no}', 'raw': line}
        if match:
            start, end, text = match.groups()
            item.update(start=start, end=end, text=text, seconds=seconds(start), q=None, role=None)
            segments.append(item)
        lines.append(item)
    if not segments:
        raise ValueError('Transcript has no timestamped segments')
    questions = data.get('questions', [])
    if not questions:
        raise ValueError('No questions')
    previous = -1
    for n, q in enumerate(questions, 1):
        if q.get('id') != f'q{n}':
            raise ValueError('Question IDs must be sequential q1, q2, ...')
        for key in ('title', 'question', 'evaluation', 'speech'):
            if not isinstance(q.get(key), str) or not q[key].strip():
                raise ValueError(f'{q["id"]}: missing {key}')
        if not q.get('answer') or not all(isinstance(x, str) and x.strip() for x in q['answer']):
            raise ValueError(f'{q["id"]}: missing answer bullets')
        if not q.get('steps') or not all(x.get('title') and x.get('body') for x in q['steps']):
            raise ValueError(f'{q["id"]}: missing answer steps')
        attached = []
        for span in q.get('ranges', []):
            a, b = seconds(span['start']), seconds(span['end'])
            if a >= b or span['role'] not in ROLES:
                raise ValueError(f'{q["id"]}: invalid range/role')
            matched = [s for s in segments if a <= s['seconds'] < b]
            if not matched:
                raise ValueError(f'{q["id"]}: empty range {span}')
            for seg in matched:
                if seg['q'] is not None:
                    raise ValueError(f'{seg["id"]}: overlapping ranges ({seg["q"]}, {q["id"]})')
                seg['q'], seg['role'] = q['id'], span['role']
                attached.append(seg)
        if not attached:
            raise ValueError(f'{q["id"]}: no transcript links')
        attached.sort(key=lambda x: int(x['id'][1:]))
        first = attached[0]['seconds']
        if first < previous:
            raise ValueError('Questions are not chronological')
        previous = first
        q['segment_ids'] = [x['id'] for x in attached]
        q['start'], q['end'] = attached[0]['start'], attached[-1]['end']
        q['number'] = n
        q['hue'] = (185 + (n - 1) * 137.508) % 360
        for ev in q.get('evidence', []):
            t = seconds(ev['time'])
            near = [s for s in attached if s['seconds'] <= t <= seconds(s['end'])]
            if not near:
                raise ValueError(f'{q["id"]}: evidence time outside associated transcript: {ev["time"]}')
            needle = normalized(ev['quote'])
            # Restrict each quote to a contiguous run of the same speaker.
            runs = []
            for seg in attached:
                if not runs or seg['role'] != runs[-1][-1]['role'] or int(seg['id'][1:]) != int(runs[-1][-1]['id'][1:]) + 1:
                    runs.append([])
                runs[-1].append(seg)
            anchor = None
            for run in runs:
                lengths = [len(normalized(s['text'])) for s in run]
                combined = ''.join(normalized(s['text']) for s in run)
                offset = combined.find(needle) if needle else -1
                while offset >= 0:
                    position, covered = 0, []
                    for seg, length in zip(run, lengths):
                        if position < offset + len(needle) and position + length > offset:
                            covered.append(seg)
                        position += length
                    if covered and any(seg in near for seg in covered):
                        anchor = covered[0]['id']
                        break
                    offset = combined.find(needle, offset + 1)
                if anchor:
                    break
            if not anchor:
                raise ValueError(f'{q["id"]}: quote not found in associated speaker turn: {ev["quote"]}')
            ev['segment_id'] = anchor
        for source in q.get('sources', []):
            if urlparse(source['url']).scheme not in ('http', 'https'):
                raise ValueError('Only http(s) evidence source URLs are allowed')
    data['segment_count'] = len(segments)
    data['associated_count'] = sum(s['q'] is not None for s in segments)
    data['duration'] = re.search(r'音频时长: ([\d.]+) 秒', raw).group(1) if '音频时长:' in raw else ''
    return lines, data


def transcript_groups(segments, data):
    """Apply semantic turn starts without changing source text or block times."""
    turns = data.get('transcript_turns')
    if turns is not None:
        if not isinstance(turns, list) or not turns:
            raise ValueError('transcript_turns must be a nonempty list')
        indices = {seg['id']: i for i, seg in enumerate(segments)}
        question_ids = {q['id'] for q in data['questions']}
        starts = []
        for turn in turns:
            if turn.get('segment_id') not in indices:
                raise ValueError('Turn start references an unknown source segment')
            if turn.get('role') not in ROLES or not isinstance(turn.get('mixed', False), bool):
                raise ValueError('Invalid transcript turn role/mixed flag')
            if turn.get('question_id') is not None and turn['question_id'] not in question_ids:
                raise ValueError('Transcript turn references an unknown question')
            index = indices[turn['segment_id']]
            text = segments[index]['text']
            marker = turn.get('starts_with')
            offset = 0
            if marker is not None:
                if not isinstance(marker, str) or not marker or text.count(marker) != 1:
                    raise ValueError('Turn starts_with must match exactly once in its source segment')
                offset = text.index(marker)
            point = (index, offset)
            if starts and point <= starts[-1][0]:
                raise ValueError('Transcript turn starts must be strictly chronological')
            starts.append((point, turn))
        if starts[0][0] != (0, 0):
            raise ValueError('Transcript turns must cover the beginning of the original text')
        groups, part_counts = [], {}
        for n, ((start_index, start_offset), turn) in enumerate(starts):
            end_index, end_offset = starts[n + 1][0] if n + 1 < len(starts) else (len(segments), 0)
            group = []
            for i in range(start_index, min(end_index + 1, len(segments))):
                if i == end_index and end_offset == 0:
                    break
                seg = segments[i]
                left = start_offset if i == start_index else 0
                right = end_offset if i == end_index else len(seg['text'])
                if seg['q'] != turn.get('question_id'):
                    raise ValueError(f'{seg["id"]}: transcript turn crosses a question association')
                part_counts[seg['id']] = part_counts.get(seg['id'], 0) + 1
                part = part_counts[seg['id']]
                group.append({**seg, 'source_id': seg['id'],
                              'id': seg['id'] if part == 1 else f'{seg["id"]}-part{part}',
                              'text': seg['text'][left:right], 'role': turn['role'],
                              'mixed': turn.get('mixed', False)})
            if not group:
                raise ValueError('Empty transcript turn')
            groups.append(group)
        return groups
    # Older analyses still merge continuous same-question/same-role speech.
    groups = []
    for item in segments:
        prior = groups[-1][-1] if groups else None
        boundary = prior is None or item['q'] != prior['q'] or item['role'] != prior['role']
        if boundary:
            groups.append([])
        groups[-1].append(item)
    return groups


def render(raw, data):
    lines, data = prepare(raw, data)
    questions = {q['id']: q for q in data['questions']}
    groups = transcript_groups([line for line in lines if 'seconds' in line], data)
    data['paragraph_count'] = len(groups)
    rows = []
    for group in groups:
        item = group[0]
        qid = item['q'] or ''
        if qid:
            q = questions[qid]
            tone = 'dark' if item['role'] == 'interviewer' else 'light'
            attrs = f'data-q="{qid}" data-role="{item["role"]}" data-tone="{tone}" tabindex="0" role="button" aria-label="查看第 {q["number"]} 题分析，{item["start"]}"'
            label = f'<span class="turn-label">Q{q["number"]}{ROLES[item["role"]]}</span>'
        else:
            attrs = 'data-q=""'
            label = '<span class="turn-label unassigned">未纳入分析</span>'
        fragments = []
        previous_text = ''
        for seg in group:
            # Only add a space where two Latin/number tokens meet.
            if re.search(r'[A-Za-z0-9]$', previous_text) and re.match(r'[A-Za-z0-9]', seg['text']):
                fragments.append(' ')
            source_id = seg.get('source_id', seg['id'])
            fragments.append(f'<span id="{seg["id"]}" data-source-id="{source_id}" class="source-fragment"><span class="fragment-time">[{seg["start"]} → {seg["end"]}] </span><span class="fragment-text">{html.escape(seg["text"])}</span></span>')
            previous_text = seg['text']
        body = ''.join(fragments)
        rows.append(f'<div id="p-{item["id"]}" class="segment {"linked" if qid else ""}" {attrs}>{label}<p class="paragraph-body">{body}</p></div>')
    template = (Path(__file__).resolve().parent.parent / 'assets' / 'review.html').read_text(encoding='utf-8')
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    raw_payload = json.dumps(raw, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    replacements = {
        '@@PAGE_TITLE@@': html.escape(data['title'] + '｜面试复盘'),
        '@@RAW_ROWS@@': '\n'.join(rows),
        '@@DATA@@': payload,
        '@@RAW_DATA@@': raw_payload,
    }
    return re.sub(r'@@(?:PAGE_TITLE|RAW_ROWS|DATA|RAW_DATA)@@', lambda m: replacements[m.group()], template)


def recording_metadata(data, audio_path):
    """Read container metadata only; never infer recording time from file copies."""
    recorded_at = data.get('recorded_at')
    duration = data.get('duration_seconds')
    if audio_path.is_file() and (not recorded_at or duration is None):
        try:
            import av
        except ImportError:
            av = None
        if av is not None:
            try:
                with av.open(str(audio_path)) as container:
                    recorded_at = recorded_at or container.metadata.get('creation_time')
                    if duration is None and container.duration is not None:
                        duration = container.duration / av.time_base
            except (OSError, ValueError):
                pass
    if recorded_at:
        try:
            timestamp = datetime.fromisoformat(recorded_at.replace('Z', '+00:00'))
            if timestamp.utcoffset() is None:
                raise ValueError('Timezone required')
        except (ValueError, AttributeError) as error:
            raise ValueError('recorded_at must be an ISO datetime with timezone') from error
        local = timestamp.astimezone()
        offset = local.strftime('%z')
        data['recorded_at'] = timestamp.isoformat()
        data['recorded_at_display'] = local.strftime('%Y-%m-%d %H:%M') + f' (UTC{offset[:3]}:{offset[3:]})'
    if duration is not None:
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not 0 < duration < float('inf'):
            raise ValueError('duration_seconds must be a positive finite number')
        data['duration_seconds'] = duration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transcript', type=Path, required=True)
    parser.add_argument('--analysis', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stats-output', type=Path, help='Save validation/render timing and counts')
    parser.add_argument('--preparation', type=Path, help='Verify prepared input hash and record analysis elapsed wall time')
    args = parser.parse_args()
    started = time.perf_counter()
    raw = args.transcript.read_text(encoding='utf-8')
    data = json.loads(args.analysis.read_text(encoding='utf-8'))
    preparation = None
    if args.preparation:
        preparation = json.loads(args.preparation.read_text(encoding='utf-8'))
        if hashlib.sha256(raw.encode('utf-8')).hexdigest() != preparation['transcript_sha256']:
            parser.error('Transcript changed since preparation; review the new input before rendering')
    data['storage_path'] = str(args.output.resolve().parent)
    audio_path = Path(data.get('audio', ''))
    if not audio_path.is_absolute():
        audio_path = args.output.resolve().parent / audio_path
    recording_metadata(data, audio_path)
    result = render(raw, data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding='utf-8')
    if args.stats_output:
        stats = {'validation_render_seconds': round(time.perf_counter() - started, 4),
                 'question_count': len(data['questions']), 'segment_count': data['segment_count'],
                 'evidence_count': sum(len(q.get('evidence', [])) for q in data['questions'])}
        if preparation:
            stats['analysis_elapsed_wall_seconds_including_pauses'] = round(
                (datetime.now(timezone.utc) - datetime.fromisoformat(preparation['analysis_started_at'])).total_seconds(), 2)
        args.stats_output.parent.mkdir(parents=True, exist_ok=True)
        args.stats_output.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Rendered {len(data["questions"])} questions / {data["segment_count"]} original segments: {args.output}')


if __name__ == '__main__':
    main()
