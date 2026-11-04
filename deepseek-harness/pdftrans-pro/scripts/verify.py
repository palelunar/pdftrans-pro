#!/usr/bin/env python3
"""Check a translated PDF against its source and single JSONL plan."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import pymupdf
from pdftrans import active, blocks, load_plan, locate, norm, plan_path


def parse_pages(spec, count):
    if spec is None:
        return set(range(1, count + 1))
    pages = set()
    for part in spec.split(','):
        if not re.fullmatch(r'\s*\d+(?:\s*-\s*\d+)?\s*', part):
            raise ValueError('--pages 格式应为 3-5,7')
        ends = [int(n) for n in part.split('-')]
        if not 1 <= ends[0] <= ends[-1] <= count:
            raise ValueError('--pages 不能为空、倒序或超出页数')
        pages.update(range(ends[0], ends[-1] + 1))
    return pages


def images(page):
    return Counter((image['digest'].hex(), tuple(round(v, 3) for v in image['transform']))
                   for image in page.get_image_info(hashes=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('output')
    parser.add_argument('--plan-file')
    parser.add_argument('--pages')
    args = parser.parse_args()
    path = plan_path(args.source, args.plan_file)
    rows = load_plan(path, args.source) if path.exists() else []
    issues = []
    with pymupdf.open(args.source) as source, pymupdf.open(args.output) as output:
        if len(source) != len(output):
            issues.append({'message': '页数不一致: %d -> %d' % (len(source), len(output))})
        pages = parse_pages(args.pages, min(len(source), len(output)))
        if not pages:
            raise ValueError('没有可以比较的页面')
        for p in sorted(pages):
            before, after = source[p - 1], output[p - 1]
            if (before.rect, before.cropbox, before.rotation) != (after.rect, after.cropbox, after.rotation):
                issues.append({'p': p, 'message': '页面尺寸/裁剪/旋转变化'})
            if images(before) != images(after):
                issues.append({'p': p, 'message': '图片对象内容或位置变化'})
            extracted, replaced = blocks(before), []
            for row in rows:
                if row.get('p') != p or not active(row):
                    continue
                try:
                    rect, _, _ = locate(before, row, extracted)
                    replaced.append(rect)
                    actual = norm(after.get_text('text', clip=rect + (-1, -2, 1, 2)))
                    if norm(row['dst']) not in actual:
                        issues.append({'p': p, 'b': row.get('b'), 'message': '未找到完整译文: ' + row['dst'][:60]})
                except (ValueError, KeyError, TypeError) as exc:
                    issues.append({'p': p, 'message': str(exc)})
            # Only check retained text when a plan tells us which regions were replaced.
            if rows:
                missing = []
                for block in extracted:
                    for sp in block['spans']:
                        rect = pymupdf.Rect(sp['bbox'])
                        if any((rect & area).get_area() > 0 for area in replaced):
                            continue
                        actual = norm(after.get_text('text', clip=rect + (-1, -2, 1, 2)))
                        if norm(sp['text']) and norm(sp['text']) not in actual:
                            missing.append(sp['text'])
                if missing:
                    issues.append({'p': p, 'message': '需目检 %d 处保留文本/公式' % len(missing), 'examples': missing[:5]})
    report_path = Path(args.output + '.report.json')
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    report['verification'] = {'pages': sorted(pages), 'issues': issues, 'plan_checked': bool(rows)}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    for item in issues[:10]:
        print('WARN p%s: %s' % (item.get('p', '-'), item['message']))
    print('%s: %d 页，%d 项提示；报告 %s' % ('ISSUES FOUND' if issues else 'CHECKED', len(pages), len(issues), report_path))
    print('检查不能判断译文语义或未填条目是否应译；交付前检查漏译并目检版式。')
    return 1 if issues else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        sys.exit('ERROR: ' + str(exc))
