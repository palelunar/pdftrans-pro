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
import shutil
import sys
import tempfile
import unicodedata

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8')

try:
    import pymupdf
except ImportError:
    sys.exit('缺少 PyMuPDF。请用已安装它的 Python，或运行: "%s" -m pip install pymupdf' % sys.executable)

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
                                            for line in block['lines']), 'spans': spans,
                           'lines': block['lines']})
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


def select_pages(spec, count, start=1):
    if spec is None or spec == 'all':
        return set(range(start, start + count))
    selected = set()
    for part in spec.split(','):
        if not re.fullmatch(r'\s*\d+(?:\s*-\s*\d+)?\s*', part):
            raise ValueError('范围格式应为 3-5,7')
        ends = [int(x) for x in part.split('-')]
        if not start <= ends[0] <= ends[-1] < start + count:
            raise ValueError('范围不能倒序或超出边界')
        selected.update(range(ends[0], ends[-1] + 1))
    return selected


def save_plan(path, source, rows):
    """Explicit edits keep one backup; normal builds never rewrite the plan."""
    shutil.copy2(path, str(path) + '.bak')
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.jsonl')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            for row in [{'meta': 1, 'source_sha256': fingerprint(source)}] + rows:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def edit_region(source, doc, path, page_number, block_spec, cells=False):
    if not 1 <= page_number <= len(doc):
        raise ValueError('页码超出范围')
    page, rows = doc[page_number - 1], load_plan(path, source)
    extracted = blocks(page)
    selected = select_pages(block_spec, len(extracted), start=0)
    if cells and len(selected) != 1:
        raise ValueError('--cells 一次指定一个表格块')
    def belongs(row):
        ids = set(row.get('blocks', [row['b']] if 'b' in row else []))
        if row.get('p') != page_number or not ids & selected:
            return False
        if not ids <= selected:
            raise ValueError('已有合并条目跨越选择范围，请完整选择其 blocks')
        return True
    chosen = [r for r in rows if belongs(r)]
    replacements = []
    if cells:
        if any(active(r) for r in chosen):
            raise ValueError('该块已有译文，不能自动拆分译文；请先备份并清空该块 dst')
        b = next(iter(selected))
        for line in extracted[b]['lines']:
            groups = []
            for sp in sorted(line['spans'], key=lambda s: s['bbox'][0]):
                if not groups or sp['bbox'][0] - groups[-1][-1]['bbox'][2] > 1.5 * max(sp['size'], groups[-1][-1]['size']):
                    groups.append([])
                groups[-1].append(sp)
            for group in groups:
                rect = pymupdf.Rect(group[0]['bbox'])
                for sp in group[1:]:
                    rect |= pymupdf.Rect(sp['bbox'])
                text = ' '.join(sp['text'].strip() for sp in group).strip()
                if text:
                    replacements.append({'p': page_number, 'b': b, 'type': 'RECT', 'rect': list(rect),
                                         'size': max(sp['size'] for sp in group), 'src': text, 'dst': ''})
    else:
        rect = pymupdf.Rect(extracted[min(selected)]['rect'])
        for b in selected:
            rect |= pymupdf.Rect(extracted[b]['rect'])
        other = [b for b, block in enumerate(extracted) if b not in selected and
                 (rect & pymupdf.Rect(block['rect'])).get_area() > 0.25 * pymupdf.Rect(block['rect']).get_area()]
        if other:
            raise ValueError('并集还会覆盖未选择的块 %s，请核对同栏区域后明确选择' % other)
        replacements = [{'p': page_number, 'blocks': sorted(selected), 'type': 'RECT', 'rect': list(rect),
                         'src': '\n'.join(extracted[b]['text'] for b in sorted(selected)),
                         'dst': '\n'.join(r['dst'] for r in chosen if active(r))}]
    remaining = [r for r in rows if not belongs(r)]
    insertion = next((i for i, r in enumerate(remaining) if r['p'] > page_number), len(remaining))
    remaining[insertion:insertion] = replacements
    save_plan(path, source, remaining)
    print('已用 %d 条替换 %d 条；请核对 src/dst 和区域。备份: %s.bak' % (len(replacements), len(chosen), path))


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
            # A plan starts with block-level src; selecting one span still identifies that source.
            if kind != 'SPAN' or norm(row['src']) != norm(block['text']):
                raise ValueError('src 与所选原文不一致；请用 --show 核对，将 src 更新为所选文本')
        size = float(row.get('size', size))
    if rect.is_empty or rect.is_infinite or not page.rect.contains(rect) or not 0 < size <= 200:
        raise ValueError('区域或字号无效')
    return rect, size, origin


def wrap_lines(text, font, size, width, widths=None):
    """CJK character wrapping with punctuation attachment and intact Latin words/references."""
    widths = {} if widths is None else widths
    opening, closing = '（([【《「『“‘', '，。！？、：；,.!?;:）)]】》」』”’%％'
    lines = []
    for paragraph in text.split('\n'):
        units = []
        for token in re.findall(r'\[[0-9][0-9,;\s–—-]*\]|[A-Za-z0-9_]+(?:[./:@+–−-][A-Za-z0-9_]+)*|[^\S\n]+|.', paragraph):
            if units and (token[0] in closing or unicodedata.combining(token[0])):
                if units[-1].isspace():
                    units.pop()
                if units:
                    units[-1] += token
                    continue
            if units and units[-1][-1] in opening:
                if not token.isspace():
                    units[-1] += token
            else:
                units.append(token)
        line, used = '', 0.0
        for unit in units:
            if unit not in widths:
                widths[unit] = font.text_length(unit, fontsize=1)
            advance = widths[unit] * size
            if advance > width + 0.01 and not unit.isspace():
                raise ValueError('单词或引用超过行宽')
            if line and used + advance > width + 0.01:
                lines.append(line.rstrip())
                line, used = '', 0.0
            if not line and unit.isspace():
                continue
            line, used = line + unit, used + advance
        lines.append(line.rstrip())
    return lines


def fit(page, row, rect, size, origin, fonts):
    heading = row.get('style', 'body') in ('heading', 'title', 'headc')
    path = os.environ.get('PDFTRANS_SIMHEI' if heading else 'PDFTRANS_SIMSUN',
                          r'C:\Windows\Fonts\simhei.ttf' if heading else r'C:\Windows\Fonts\simsun.ttc')
    if path not in fonts:
        fonts[path] = pymupdf.Font(fontfile=path)
    font, text = fonts[path], row['dst']
    align = row.get('align', 'center' if row.get('style') in ('title', 'headc', 'caption') else 'left')
    align = {'left': 0, 'center': 0.5, 'right': 1}[align]
    lineheight = float(row.get('lineheight', 1.1))
    if not 1 <= lineheight <= 2:
        raise ValueError('lineheight 应在 1 到 2 之间')
    one_line = row['type'] == 'SPAN' or (row['type'] == 'RECT' and rect.height < size * 1.6)
    widths = {}

    def attempt(candidate):
        writer = pymupdf.TextWriter(page.rect)
        try:
            if one_line:
                width = font.text_length(text, fontsize=candidate)
                if '\n' in text or width > rect.width + 0.5:
                    return None
                writer.append((rect.x0 + (rect.width - width) * align, origin[1]), text, font=font, fontsize=candidate)
            else:
                lines = wrap_lines(text, font, candidate, rect.width, widths)
                height = (font.ascender - font.descender + (len(lines) - 1) * lineheight) * candidate
                if height > rect.height + 0.01:
                    return None
                for number, line in enumerate(lines):
                    x = rect.x0 + (rect.width - font.text_length(line, fontsize=candidate)) * align
                    y = rect.y0 + (font.ascender + number * lineheight) * candidate
                    writer.append((x, y), line, font=font, fontsize=candidate)
            return writer
        except ValueError:
            return None

    writer = attempt(size)
    if writer is not None:
        return writer, size
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
    return writer, low


def rebuild(source, output, doc, rows, overlay=False):
    output = Path(output).resolve()
    if output == Path(source).resolve() or (output.exists() and os.path.samefile(source, output)):
        raise ValueError('输出不能覆盖原 PDF')
    groups, issues, warnings, fonts, written = {}, [], [], {}, 0
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
                rotated = [line for b in extracted for line in b['lines']
                           if tuple(line['dir']) != (1, 0) and (rect & pymupdf.Rect(line['bbox'])).get_area() > 0]
                if rotated:
                    raise ValueError('区域包含旋转文字；请调整区域以保留图内标注')
                if any((rect & old).get_area() > 0.25 * min(rect.get_area(), old.get_area())
                       for old, _ in ready):
                    raise ValueError('与另一条译文区域重复，请合并条目')
                writer, actual_size = fit(page, row, rect, size, origin, fonts)
                ready.append((rect, writer))
                if actual_size < size * 0.9:
                    warnings.append({'entry': index, 'p': p, 'b': row.get('b'),
                                     'message': '字号缩小超过10%', 'size': round(actual_size, 2), 'original_size': round(size, 2)})
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
        try:
            doc.subset_fonts()
        except (RuntimeError, ValueError) as exc:
            warnings.append({'message': '字体精简未完成，保留原字体: ' + str(exc)})
        doc.save(temporary, garbage=4, deflate=True)
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    report = {'written': written, 'retained': len(rows) - written,
              'mode': 'overlay' if overlay else 'replace', 'issues': issues, 'warnings': warnings}
    Path(str(output) + '.report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('已写入 %d 条，保留原文 %d 条: %s' % (written, report['retained'], output))
    if issues:
        print('WARN: %d 条未能写入，见 %s.report.json' % (len(issues), output))
    if warnings:
        print('NOTE: %d 项字号/字体提示，见同一报告。' % len(warnings))
    if overlay:
        print('NOTE: 白底覆盖模式保留底层原文；请目检背景、公式与图片。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('output', nargs='?')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--plan', action='store_true')
    mode.add_argument('--show', nargs=2, type=int, metavar=('PAGE', 'BLOCK'))
    mode.add_argument('--list', action='store_true', help='紧凑的计划概览，不输出全文')
    mode.add_argument('--preview', nargs='?', const='all', metavar='PAGES', help='渲染输入 PDF 的页码，例如 1,3-5')
    mode.add_argument('--merge', nargs=2, metavar=('PAGE', 'BLOCKS'), help='明确选择同页块合并为 RECT，例如 4 6-8')
    mode.add_argument('--cells', nargs=2, metavar=('PAGE', 'BLOCK'), help='将未填写的表格块按视觉行与列间距拆为候选单元格')
    parser.add_argument('--pages', help='限制 --list 的页码')
    parser.add_argument('--pending', action='store_true', help='--list 只列未填写项（也可能是有意保留）')
    parser.add_argument('--plan-file', help='只读取指定的一个 JSONL；默认 <输入.pdf>.pdftrans/plan.jsonl')
    parser.add_argument('--overlay', action='store_true', help='白底覆盖文字，保留底层原文；用于局部删除损坏公式时')
    args = parser.parse_args()
    if (args.pending or args.pages) and not args.list:
        parser.error('--pages / --pending 与 --list 一起使用')
    path = plan_path(args.source, args.plan_file)
    with pymupdf.open(args.source) as doc:
        if args.plan:
            create_plan(args.source, doc, path)
        elif args.list:
            rows = load_plan(path, args.source)
            selected = select_pages(args.pages, len(doc))
            shown = [r for r in rows if r['p'] in selected and (not args.pending or not active(r))]
            print('共 %d 条，已填写 %d；本次显示 %d（未填写不等于漏译）' % (len(rows), sum(active(r) for r in rows), len(shown)))
            for row in shown:
                identity = 'b' + str(row['b']) if 'b' in row else 'blocks=' + str(row.get('blocks', 'rect'))
                if 's' in row:
                    identity += '/s' + str(row['s'])
                print('p%d %s %s %s | %s' % (row['p'], identity, row['type'], 'done' if active(row) else 'blank',
                                              re.sub(r'\s+', ' ', row.get('src', ''))[:70]))
        elif args.preview:
            folder = Path(str(Path(args.source).resolve()) + '.preview')
            folder.mkdir(exist_ok=True)
            for p in sorted(select_pages(args.preview, len(doc))):
                image_path = folder / ('p%03d.png' % p)
                doc[p - 1].get_pixmap(dpi=120).save(str(image_path))
                print(image_path)
        elif args.merge or args.cells:
            p, spec = args.merge or args.cells
            edit_region(args.source, doc, path, int(p), spec, cells=bool(args.cells))
        elif args.show:
            p, b = args.show
            extracted = blocks(doc[p - 1]) if 1 <= p <= len(doc) else []
            if not 0 <= b < len(extracted):
                raise ValueError('页码或块编号超出范围')
            block = extracted[b]
            print('p%d b%d rect=%s size=%.2f\n%s' % (p, b, tuple(round(v, 2) for v in block['rect']), block['size'], block['text']))
            for s, sp in enumerate(block['spans']):
                print('s%d rect=%s size=%.2f | %s' % (s, tuple(round(v, 2) for v in sp['bbox']), sp['size'], sp['text']))
        else:
            rows = load_plan(path, args.source)
            output = args.output or str(Path(args.source).with_name(Path(args.source).stem + '_translated.pdf'))
            rebuild(args.source, output, doc, rows, args.overlay)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError) as exc:
        sys.exit('ERROR: ' + str(exc))
