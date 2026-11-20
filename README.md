[English](README.md) | [简体中文](README.zh-CN.md)

# PDFTrans Pro

PDFTrans Pro lets an agent translate a paper paragraph by paragraph and puts the translation back on the original pages. Readers can follow the text alongside the original figures, and the agent can translate table labels while keeping the values in place.

## Why Pro?

- **Fewer fragments to piece together.** On the 25-page RCaware-nnUNetv2 paper, the original PDFTrans generated 7,336 plan entries, including 7,077 with just one or two words. Pro grouped the same source into 448 text blocks. That's 94% fewer entries, with surrounding words available when translating a passage.
- **Less to read when choosing the next passage.** The agent can scan short previews of pending entries and expand a passage on demand. On the 19-page ESRVS paper, the full plan contained 73,779 characters. The pending overview took 7,219. These counts measure the text needed to select passages. Total translation tokens were not measured.
- **Edit just the part that needs translation.** In the hyperparameter table on page 18 of ESRVS, Pro grouped 48 text fragments into 12 candidate cells. After translating six labels, the adjacent value column was pixel-identical to the original at 144 dpi. Complex inline equations within translated paragraphs still need a visual check.

**The same translations in smaller PDFs.** Pro embeds only the font glyphs it uses. The comparison below used the same source PDFs and prefilled translations with the [previous Pro release](https://github.com/palelunar/pdftrans-pro/commit/e470ec358aad06dd1f0ccf348a7a5570f19c33cd) and the [updated release](https://github.com/palelunar/pdftrans-pro/commit/b706fcb7295f58ac13c8254616ace4fef49868ed). Build times cover one PDF rebuild per version on the same machine.

| Paper | Translations written by each version | Output PDF (previous → updated) | Build time (previous → updated) |
|---|---:|---:|---:|
| SA-UNetv2 (5 pages) | 44 | 15.75 → 0.86 MB | 1.81 → 0.87 s |
| ESRVS (19 pages) | 93 | 17.32 → 2.50 MB | 2.04 → 1.07 s |

## Install

Install this local revision with `./install.ps1 -Tool codex` on Windows or `./install.sh codex` on macOS/Linux. Both installers also support `claude`, `opencode`, and `dsh`; DSH additionally takes its checkout path (`-HarnessPath` on Windows).

One-line installation of the published version (local edits are included only after publication):

```powershell
irm https://raw.githubusercontent.com/palelunar/pdftrans-pro/main/install.ps1 | iex
```

```bash
curl -fsSL https://raw.githubusercontent.com/palelunar/pdftrans-pro/main/install.sh | bash
```

`claude-code/pdftrans-pro/` supports Codex, Claude Code, and opencode; `deepseek-harness/pdftrans-pro/` has its own entrypoint. Each package contains SKILL.md, two scripts, a short format reference, and LICENSE.

## Use

Install Python and PyMuPDF (`pip install pymupdf`), then run from the skill directory:

```bash
python scripts/pdftrans.py paper.pdf --plan
# Fill dst in paper.pdf.pdftrans/plan.jsonl; blanks retain the original text
python scripts/pdftrans.py paper.pdf paper_translated.pdf
python scripts/verify.py paper.pdf paper_translated.pdf
```

- One plan is the sole translation source. No automatic file merging or Python translation execution.
- Paragraphs remain whole; use SPAN for baseline-aligned table text or RECT for a custom cell. See `references/format.md` inside the skill.
- No full-page font extraction/redraw. Unfittable entries retain the original text and are reported; the input PDF is never overwritten.
- Outputs are the plan, translated PDF, and one `.report.json`; no job manifests, progress snapshots, or batches of issue images.
- Default rendering replaces text locally. If it damages formulas, `--overlay` paints white covers and translated text. The original text layer remains, and colored backgrounds need visual review.
- Windows defaults to SimSun/SimHei; override with `PDFTRANS_SIMSUN` and `PDFTRANS_SIMHEI`. Scanned documents need OCR first.
- Checks cover pages, geometry, image objects, translations, and retained text. Review meaning, omissions, and appearance yourself.

For old jobs, flatten the effective translations into one JSONL and select it with `--plan-file`. Existing files are not removed. Local evaluation artifacts are excluded from this repository.

## Less reading and rework

- `--list --pending --pages 1-3` gives a compact batch view; `--show PAGE BLOCK` supplies details only when needed.
- `--merge PAGE BLOCKS` combines selected fragments; `--cells PAGE BLOCK` proposes table cells. Explicit edits keep one plan backup.
- `--preview 1,3-5` renders the supplied source or translated PDF to PNG.
- CJK wrapping, punctuation attachment, and font subsetting run automatically. Reductions below 90% of the original font size are reported. No extra dependency is needed.
- Use `style: "caption"` for centered captions or `align` for explicit alignment. Line spacing is not automatically stretched to fill a block.

## Maintain

Edit common scripts in `claude-code/pdftrans-pro/scripts/`, then run `python tools/sync_scripts.py`. Use `--check` to compare packages. Core regressions: `python -B -m unittest discover -s tests -v`.

[License](LICENSE)
