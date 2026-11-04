[English](README.md) | [简体中文](README.zh-CN.md)

# PDFTrans Pro

**Free for noncommercial use. Commercial use requires prior written authorization from the author and payment of the agreed license fee.**

Contact [palelunar](https://github.com/palelunar) or open a [commercial license request](https://github.com/palelunar/pdftrans-pro/issues/new?title=Commercial%20license%20request). Pricing and scope are agreed separately; public source code does not grant free commercial use.

A small PDF translation skill: create one plan, let the agent fill translations, rebuild, and inspect.

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

## Maintain

Edit common scripts in `claude-code/pdftrans-pro/scripts/`, then run `python tools/sync_scripts.py`. Use `--check` to compare packages. Core regressions: `python -B -m unittest discover -s tests -v`.



## License

This version uses the [PDFTrans Pro Noncommercial License 1.0](LICENSE): source inspection, modification, and noncommercial use and sharing are allowed; commercial use requires a separate paid license. This is a source-available license, not an OSI open-source license. Earlier releases already licensed under MIT are not retroactively relicensed.

Our license covers our code only. Third-party dependencies remain under their own terms. PyMuPDF offers [AGPL and commercial licensing](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright); payment to this project's author does not grant a third-party commercial license.
