"""Small end-to-end regressions for the single-plan workflow."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import pymupdf

SCRIPTS = Path(__file__).resolve().parents[1] / 'claude-code/pdftrans-pro/scripts'
sys.path.insert(0, str(SCRIPTS))
from pdftrans import wrap_lines, norm


class TranslationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pdftrans-')
        self.root = Path(self.temp.name)
        self.source, self.output = self.root / 'source.pdf', self.root / 'out.pdf'
        self.plan = self.root / 'source.pdf.pdftrans/plan.jsonl'
        font = self.root / 'font.bin'
        font.write_bytes(pymupdf.Font('helv').buffer)
        self.env = dict(os.environ, PDFTRANS_SIMSUN=str(font), PDFTRANS_SIMHEI=str(font), PYTHONDONTWRITEBYTECODE='1')
        self.make_pdf(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def make_pdf(self, path, pages=1, image_color=50):
        with pymupdf.open() as doc:
            for _ in range(pages):
                page = doc.new_page(width=400, height=500)
                page.insert_text((40, 60), 'A source title', fontsize=16)
                page.insert_text((40, 110), 'Original paragraph on the first line.\nMore details on a second line.', fontsize=11)
                page.insert_text((40, 180), '123.45', fontsize=10)
                pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10))
                pix.clear_with(image_color)
                page.insert_image(pymupdf.Rect(40, 210, 100, 270), pixmap=pix)
            doc.save(path)

    def run_script(self, name, *args, success=True):
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(SCRIPTS/name), *map(str, args)],
                                env=self.env, capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def prepare(self):
        self.run_script('pdftrans.py', self.source, '--plan')
        rows = [json.loads(line) for line in self.plan.read_text(encoding='utf-8').splitlines()]
        rows[1]['dst'] = 'Translated title'
        self.save(rows)
        return rows

    def save(self, rows):
        self.plan.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')

    def test_translate_preview_and_overlay_preserve_source(self):
        digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.prepare()
        self.run_script('pdftrans.py', self.source, self.output)
        self.run_script('verify.py', self.source, self.output)
        with pymupdf.open(self.output) as doc:
            self.assertIn('Translated title', doc[0].get_text())
            self.assertIn('Original paragraph', doc[0].get_text())
            self.assertIn('123.45', doc[0].get_text())
        self.run_script('pdftrans.py', self.source, self.output, '--overlay')
        with pymupdf.open(self.output) as doc:
            self.assertIn('A source title', doc[0].get_text())
            self.assertIn('Translated title', doc[0].get_text())
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), digest)
        self.run_script('pdftrans.py', self.source, self.source, success=False)

    def test_replanning_keeps_work_and_rejects_wrong_source(self):
        self.prepare()
        before = self.plan.read_bytes()
        self.run_script('pdftrans.py', self.source, '--plan')
        self.assertEqual(self.plan.read_bytes(), before)
        self.make_pdf(self.source, pages=2)
        self.run_script('pdftrans.py', self.source, '--plan', success=False)
        self.assertEqual(self.plan.read_bytes(), before)

    def test_unfittable_entry_retains_original_and_is_reported(self):
        rows = self.prepare()
        rows[2]['dst'] = 'Far too much text. ' * 100
        self.save(rows)
        self.run_script('pdftrans.py', self.source, self.output)
        report = json.loads(Path(str(self.output)+'.report.json').read_text(encoding='utf-8'))
        self.assertEqual(len(report['issues']), 1)
        with pymupdf.open(self.output) as doc:
            self.assertIn('Original paragraph', doc[0].get_text())
            self.assertIn('Translated title', doc[0].get_text())
        self.run_script('verify.py', self.source, self.output, success=False)

    def test_short_cell_uses_original_baseline(self):
        with pymupdf.open(self.source) as doc:
            page = doc[0]
            page.insert_text((150, 300), 'Pre', fontsize=4.98)
            rect = page.search_for('Pre')[0]
            small = self.root/'small.pdf'
            doc.save(small)
        self.source = small
        self.plan = Path(str(small)+'.pdftrans/plan.jsonl')
        rows = self.prepare()
        rows.append({'p': 1, 'type': 'RECT', 'rect': [rect.x0, rect.y0, rect.x1, rect.y0+4.98],
                     'size': 4.98, 'dst': 'X'})
        self.save(rows)
        self.run_script('pdftrans.py', self.source, self.output)
        report = json.loads(Path(str(self.output)+'.report.json').read_text(encoding='utf-8'))
        self.assertFalse(report['issues'], report)
        with pymupdf.open(self.output) as doc:
            self.assertIn('X', doc[0].get_text())
            self.assertNotIn('Pre', doc[0].get_text())

    def test_validation_catches_page_loss_range_and_image_change(self):
        self.make_pdf(self.source, pages=2)
        self.make_pdf(self.output)
        self.run_script('verify.py', self.source, self.output, success=False)
        self.run_script('verify.py', self.source, self.source, '--pages', '2-1', success=False)
        self.make_pdf(self.source)
        self.make_pdf(self.output, image_color=200)
        self.run_script('verify.py', self.source, self.output, success=False)
        report = json.loads(Path(str(self.output)+'.report.json').read_text(encoding='utf-8'))
        self.assertTrue(any('图片' in issue['message'] for issue in report['verification']['issues']))

    def test_only_the_selected_plan_is_read(self):
        self.prepare()
        extra = self.plan.parent/'translations'
        extra.mkdir()
        (extra/'old.jsonl').write_text('{"p":1,"b":0,"dst":"Unwanted stale translation"}',encoding='utf-8')
        self.run_script('pdftrans.py', self.source, self.output)
        with pymupdf.open(self.output) as doc:
            self.assertIn('Translated title', doc[0].get_text())
            self.assertNotIn('Unwanted', doc[0].get_text())

    def test_cjk_wrap_keeps_punctuation_words_and_citations(self):
        font = pymupdf.Font('china-s')
        text = '方法采用（CSA）结构，参考[10]和[1, 3–5]。English words 不应逐字拆开；验证中文断行。'
        lines = wrap_lines(text, font, 10, 90)
        self.assertEqual(norm(''.join(lines)), norm(text))
        for token in ('（CSA）', '[10]', '[1, 3–5]', 'English', 'words'):
            self.assertTrue(any(token in line for line in lines), (token, lines))
        self.assertTrue(all(font.text_length(line, fontsize=10) <= 90.01 for line in lines))
        self.assertTrue(all(not line.startswith(tuple('，。；）]')) and not line.endswith(tuple('（[')) for line in lines))

    def test_merge_list_and_preview_preserve_completed_work(self):
        self.prepare()
        original = self.plan.read_bytes()
        self.run_script('pdftrans.py', self.source, '--merge', '1', '0-1')
        rows = [json.loads(line) for line in self.plan.read_text(encoding='utf-8').splitlines()]
        merged = next(r for r in rows if r.get('blocks') == [0, 1])
        self.assertEqual(merged['dst'], 'Translated title')
        self.assertFalse(any(r.get('b') in (0, 1) for r in rows))
        self.assertEqual(Path(str(self.plan)+'.bak').read_bytes(), original)
        result = self.run_script('pdftrans.py', self.source, '--list', '--pending', '--pages', '1')
        self.assertNotIn('Translated title', result.stdout)
        self.run_script('pdftrans.py', self.source, '--preview', '1')
        self.assertTrue(Path(str(self.source)+'.preview/p001.png').exists())

    def test_span_accepts_its_original_block_source(self):
        rows = self.prepare()
        rows[2].update(type='SPAN', s=0, dst='Translated span')
        self.save(rows)
        self.run_script('pdftrans.py', self.source, self.output)
        self.run_script('verify.py', self.source, self.output)
        with pymupdf.open(self.output) as doc:
            self.assertIn('Translated span', doc[0].get_text())
            self.assertIn('More details', doc[0].get_text())

    def test_rotated_label_inside_rect_is_preserved_and_reported(self):
        other = self.root/'rotated.pdf'
        with pymupdf.open(self.source) as doc:
            doc[0].insert_text((150, 330), 'Vertical label', rotate=90)
            doc.save(other)
        self.source = other
        self.plan = Path(str(other)+'.pdftrans/plan.jsonl')
        rows = self.prepare()
        rows.append({'p': 1, 'type': 'RECT', 'rect': [130, 250, 200, 340], 'dst': 'Replacement'})
        self.save(rows)
        self.run_script('pdftrans.py', self.source, self.output)
        report = json.loads(Path(str(self.output)+'.report.json').read_text(encoding='utf-8'))
        self.assertTrue(any('旋转' in issue['message'] for issue in report['issues']))
        with pymupdf.open(self.output) as doc:
            self.assertIn('Vertical label', doc[0].get_text())


if __name__ == '__main__':
    unittest.main()
