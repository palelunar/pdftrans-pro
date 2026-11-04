#!/usr/bin/env python3
"""PDF translation: create one JSONL plan, fill dst, then rebuild.

  python pdftrans.py paper.pdf --plan
  python pdftrans.py paper.pdf translated.pdf
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

import pymupdf

# palelunar / hasheng


def norm(text):
    for old, new in {'ﬀ': 'ff', 'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬃ': 'ffi', 'ﬄ': 'ffl'}.items():
        text = text.replace(old, new)
    return re.sub(r'\s+', '', text)


def fingerprint(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def blocks(page):
    result = []
    for block in page.get_text('dict')['blocks']:
        if block['type'] != 0:
            continue
        spans = [sp for line in block['lines'] for sp in line['spans']]
        if spans:
            result.append({'rect': block['bbox'], 'size': max(sp['size'] for sp in spans),
                           'text': '\n'.join(''.join(sp['text'] for sp in line['spans'])
                                            for line in block['lines']), 'spans': spans})
    return result


def plan_path(source, supplied=None):
    return Path(supplied) if supplied else Path(str(Path(source).resolve()) + '.pdftrans') / 'plan.jsonl'


def load_plan(path, source):
    rows, seen = [], set()
    for line, text in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
        if not text.strip():
            continue
        try:
            row = json.loads(text)
            if row.get('meta'):
                if row.get('source_sha256') and row['source_sha256'] != fingerprint(source):
                    raise ValueError('计划属于另一份 PDF；请使用该文件对应的计划')
                continue
            kind = row.get('type', 'SPAN' if 's' in row else 'PARA')
            if kind not in ('PARA', 'SPAN', 'RECT') or not isinstance(row.get('dst', ''), str):
                raise ValueError('检查 type 和 dst 字段')
            key = (row['p'], kind, row.get('b'), row.get('s'), tuple(row.get('rect', [])))
            if key in seen:
                raise ValueError('同一条目重复，请只保留一份')
            seen.add(key)
            rows.append(dict(row, type=kind))
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ValueError('%s:%d: %s' % (path, line, exc)) from exc
    return rows


def create_plan(source, doc, path):
    if path.exists():
        rows = load_plan(path, source)
        print('已有计划，保留 %d 条内容: %s' % (len(rows), path))
        return
    extracted = [blocks(page) for page in doc]
    sizes = sorted(b['size'] for page in extracted for b in page)
    if not sizes:
        raise ValueError('未提取到文本；扫描件请先 OCR')
    body = sizes[len(sizes) // 2]
    rows = [{'meta': 1, 'source_sha256': fingerprint(source)}]
    for p, page in enumerate(extracted, 1):
        for b, block in enumerate(page):
            row = {'p': p, 'b': b, 'type': 'PARA', 'src': block['text'], 'dst': ''}
            if block['size'] >= body * 1.2 and len(block['text']) < 120:
                row['style'] = 'title' if p == 1 and block['size'] >= body * 1.5 else 'heading'
            rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
    print('已生成 %d 条整块原文: %s' % (len(rows) - 1, path))


def active(row):
    return bool(row.get('dst', '').strip()) and row.get('status') != 'skip'


def locate(page, row, extracted):
    """Return the original rectangle, font size and baseline for a translation."""
    kind = row['type']
    if kind == 'RECT':
        rect = pymupdf.Rect(row['rect'])
        nearby = [sp for b in extracted for sp in b['spans']
                  if (rect & pymupdf.Rect(sp['bbox'])).get_area() > 1]
        size = float(row.get('size', max((sp['size'] for sp in nearby), default=10)))
        origin = (rect.x0, nearby[0]['origin'][1] if nearby else rect.y1 - size * 0.2)
    else:
        index = row['b']
        if type(index) is not int or not 0 <= index < len(extracted):
            raise ValueError('块编号超出范围')
        block = extracted[index]
        if kind == 'SPAN':
            index = row['s']
            if type(index) is not int or not 0 <= index < len(block['spans']):
                raise ValueError('span 编号超出范围')
            sp = block['spans'][index]
            rect, size, origin, text = pymupdf.Rect(sp['bbox']), sp['size'], sp['origin'], sp['text']
        else:
            rect, size, origin, text = pymupdf.Rect(block['rect']), block['size'], block['spans'][0]['origin'], block['text']
        if row.get('src') and norm(row['src']) != norm(text):
            raise ValueError('src 与所选原文不一致')
        size = float(row.get('size', size))
    if rect.is_empty or rect.is_infinite or not page.rect.contains(rect) or not 0 < size <= 200:
        raise ValueError('区域或字号无效')
    return rect, size, origin


def fit(page, row, rect, size, origin, fonts):
    heading = row.get('style', 'body') != 'body'
    path = os.environ.get('PDFTRANS_SIMHEI' if heading else 'PDFTRANS_SIMSUN',
                          r'C:\Windows\Fonts\simhei.ttf' if heading else r'C:\Windows\Fonts\simsun.ttc')
    if path not in fonts:
        fonts[path] = pymupdf.Font(fontfile=path)
    font, text = fonts[path], row['dst']
    align = 1 if row.get('style') in ('title', 'headc') else 0
    one_line = row['type'] == 'SPAN' or (row['type'] == 'RECT' and rect.height < size * 1.6)

    def attempt(candidate):
        writer = pymupdf.TextWriter(page.rect)
        try:
            if one_line:
                width = font.text_length(text, fontsize=candidate)
                if '\n' in text or width > rect.width + 0.5:
                    return None
                writer.append((rect.x0, origin[1]), text, font=font, fontsize=candidate)
            else:
                writer.fill_textbox(rect, text, font=font, fontsize=candidate,
                                    lineheight=1.1, align=align, warn=False)
            return writer
        except ValueError:
            return None

    writer = attempt(size)
    if writer is not None:
        return writer
    low, high = size * 0.55, size
    writer = attempt(low)
    if writer is None:
        raise ValueError('译文放不下；本条保留原文，请缩短表达或调整区域')
    for _ in range(5):
        middle = (low + high) / 2
        candidate = attempt(middle)
        if candidate is None:
            high = middle
        else:
            low, writer = middle, candidate
    return writer


def rebuild(source, output, doc, rows, overlay=False):
    output = Path(output).resolve()
    if output == Path(source).resolve() or (output.exists() and os.path.samefile(source, output)):
        raise ValueError('输出不能覆盖原 PDF')
    groups, issues, fonts, written = {}, [], {}, 0
    for index, row in enumerate(rows, 1):
        if not active(row):
            continue
        p = row.get('p')
        if type(p) is not int or not 1 <= p <= len(doc):
            issues.append({'entry': index, 'message': '页码无效，本条未写入'})
        else:
            groups.setdefault(p, []).append((index, row))
    for p, items in groups.items():
        page, ready = doc[p - 1], []
        extracted = blocks(page)
        for index, row in items:
            try:
                rect, size, origin = locate(page, row, extracted)
                if any((rect & old).get_area() > 0.25 * min(rect.get_area(), old.get_area())
                       for old, _ in ready):
                    raise ValueError('与另一条译文区域重复，请合并条目')
                ready.append((rect, fit(page, row, rect, size, origin, fonts)))
            except (ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
                issues.append({'entry': index, 'p': p, 'b': row.get('b'), 'message': str(exc)})
        if not ready:
            continue
        if overlay:
            for rect, _ in ready:
                page.draw_rect(rect, color=None, fill=(1, 1, 1))
        else:
            for rect, _ in ready:
                page.add_redact_annot(rect, fill=False)
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                                  graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
        for _, writer in ready:
            writer.write_text(page, color=(0, 0, 0))
        written += len(ready)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(suffix='.pdf', dir=output.parent)
    os.close(fd)
    try:
        doc.save(temporary, garbage=3, deflate=True)
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    report = {'written': written, 'retained': len(rows) - written,
              'mode': 'overlay' if overlay else 'replace', 'issues': issues}
    Path(str(output) + '.report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('已写入 %d 条，保留原文 %d 条: %s' % (written, report['retained'], output))
    if issues:
        print('WARN: %d 条未能写入，见 %s.report.json' % (len(issues), output))
    if overlay:
        print('NOTE: 白底覆盖模式保留底层原文；请目检背景、公式与图片。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('output', nargs='?')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--plan', action='store_true')
    mode.add_argument('--show', nargs=2, type=int, metavar=('PAGE', 'BLOCK'))
    parser.add_argument('--plan-file', help='只读取指定的一个 JSONL；默认 <输入.pdf>.pdftrans/plan.jsonl')
    parser.add_argument('--overlay', action='store_true', help='白底覆盖文字，保留底层原文；用于局部删除损坏公式时')
    args = parser.parse_args()
    path = plan_path(args.source, args.plan_file)
    with pymupdf.open(args.source) as doc:
        if args.plan:
            create_plan(args.source, doc, path)
        elif args.show:
            p, b = args.show
            extracted = blocks(doc[p - 1]) if 1 <= p <= len(doc) else []
            if not 0 <= b < len(extracted):
                raise ValueError('页码或块编号超出范围')
            print(json.dumps(extracted[b], ensure_ascii=False, indent=2))
        else:
            rows = load_plan(path, args.source)
            output = args.output or str(Path(args.source).with_name(Path(args.source).stem + '_translated.pdf'))
            rebuild(args.source, output, doc, rows, args.overlay)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError) as exc:
        sys.exit('ERROR: ' + str(exc))
