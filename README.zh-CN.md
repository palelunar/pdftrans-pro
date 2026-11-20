[English](README.md) | 简体中文

# PDFTrans Pro

PDFTrans Pro 让模型按段翻译论文，再把译文放回原页。读者可以对着原图读译文，也可以只翻表格里的文字、保留旁边的数值。

## Pro 强在哪？

- **少拼碎句。** 在 25 页的 RCaware-nnUNetv2 论文上，旧版 PDFTrans 把原文拆成 7,336 个计划条目，其中 7,077 个只有一两个词。Pro 按原文块生成 448 条，条目少了 94%，模型可以连着上下文翻译正文。
- **找下一段时少读内容。** 模型可以先扫待填条目的短预览，再展开需要翻译的原文。19 页的 ESRVS 论文完整计划有 73,779 个字符，待填概览只有 7,219 个字符。这衡量的是挑选段落时要读多少文字，整篇翻译的 token 消耗另计。
- **只改需要翻译的区域。** 在 ESRVS 第 18 页的超参数表里，Pro 将 48 个文字片段整理成 12 个候选单元格。只翻译 6 个标签后，把原文和译本按 144 dpi 渲染对照，右侧数值列逐像素一致。正文中的复杂行内公式仍需看预览复核。

**相同译文，生成的 PDF 更小。** Pro 保存时只嵌入用到的字形。下表用同一份原文和已填译文，对比[上一版 Pro](https://github.com/palelunar/pdftrans-pro/commit/e470ec358aad06dd1f0ccf348a7a5570f19c33cd) 与[改进版](https://github.com/palelunar/pdftrans-pro/commit/b706fcb7295f58ac13c8254616ace4fef49868ed)。耗时为同机单次生成 PDF 的时间。

| 论文 | 两版写入的译文条数 | 输出 PDF（上版 → 改进版） | 生成耗时（上版 → 改进版） |
|---|---:|---:|---:|
| SA-UNetv2（5 页） | 44 | 15.75 → 0.86 MB | 1.81 → 0.87 秒 |
| ESRVS（19 页） | 93 | 17.32 → 2.50 MB | 2.04 → 1.07 秒 |

## 安装

本地新版：

```powershell
.\install.ps1 -Tool codex
# 也支持 claude、opencode、dsh；dsh 另传 -HarnessPath
```

macOS/Linux：`./install.sh codex`；安装其他工具时替换参数，DSH 用 `./install.sh dsh <harness目录>`。

已发布版本的一行安装命令（仓库本地修改需发布后才会包含）：

```powershell
irm https://raw.githubusercontent.com/palelunar/pdftrans-pro/main/install.ps1 | iex
```

```bash
curl -fsSL https://raw.githubusercontent.com/palelunar/pdftrans-pro/main/install.sh | bash
```

`claude-code/pdftrans-pro/` 供 Codex、Claude Code、opencode 使用；`deepseek-harness/pdftrans-pro/` 保留独立入口。每套包含 `SKILL.md`、两个脚本、格式说明和许可证。

## 使用

需要 Python 和 PyMuPDF：`pip install pymupdf`。从技能目录运行：

```bash
python scripts/pdftrans.py paper.pdf --plan
# 编辑 paper.pdf.pdftrans/plan.jsonl：填 dst，留空则保留原文
python scripts/pdftrans.py paper.pdf paper_translated.pdf
python scripts/verify.py paper.pdf paper_translated.pdf
```

- 只读取一个计划，不自动合并文件、不执行旧 Python 译文。
- 正文按块处理；表格可用 SPAN 保留基线、RECT 定位单元格。格式见技能内 `references/format.md`。
- 不再提取字体整页重绘。无法排入的条目保留原文并提示；原 PDF 不覆盖。
- 只产生计划、输出 PDF 和一份 `.report.json`，不生成任务清单、进度镜像或成批问题截图。
- 默认局部替换文字。若它损坏公式，可用 `--overlay` 白底覆盖；底层原文仍存在，彩色背景需特别目检。
- Windows 默认宋体/黑体；用 `PDFTRANS_SIMSUN`、`PDFTRANS_SIMHEI` 指定其他字体。扫描件需先 OCR。
- 验证覆盖页数、页面尺寸、图片对象、译文和保留文本；语义、漏译和视觉质量仍需检查。

旧任务先将实际生效的译文合成单个 JSONL，再用 `--plan-file` 指定；旧文件不会被清理。本地评测材料不上传到此仓库。

## 少读、少返工

- `--list --pending --pages 1-3`：紧凑的本批待填视图；用 `--show 页 块` 按需取全文。
- `--merge 页 块范围`：合并同页碎片；`--cells 页 块`：为文字表格生成候选单元格。修改保留一份计划备份。
- `--preview 1,3-5`：直接生成页面 PNG；输入应为要查看的原文或译本。
- 自动中文断行、标点避头尾和字体子集化；缩字号超过10%会提示。无需额外依赖。
- 图注可用 `style: "caption"`，其他对齐用 `align`。不自动拉大行距填满留白。

## 维护

公共脚本在 `claude-code/pdftrans-pro/scripts/` 修改后运行 `python tools/sync_scripts.py`；`--check` 检查两套脚本一致。核心回归：`python -B -m unittest discover -s tests -v`。

[许可证](LICENSE)
