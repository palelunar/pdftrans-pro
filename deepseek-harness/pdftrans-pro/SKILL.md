---
name: pdftrans-pro
license: LicenseRef-PDFTrans-Pro-Noncommercial-1.0
description: "在 DeepSeek Harness 中翻译 PDF 或制作保留版式的论文译本，尽量保留图片、公式和表格；不用于仅总结或提取文字。"
---

# PDFTrans Pro

适用于 DeepSeek Harness。把 PDF 翻译成用户指定语言，另存结果，尽量保留原版面。

需要 Python、`pymupdf` 和目标语言字体。Windows 默认宋体/黑体；其他字体用 `PDFTRANS_SIMSUN`、`PDFTRANS_SIMHEI` 指定。

## 三步使用

```bash
python scripts/pdftrans.py paper.pdf --plan
# 逐页编辑 paper.pdf.pdftrans/plan.jsonl，填写 dst
python scripts/pdftrans.py paper.pdf paper_translated.pdf
python scripts/verify.py paper.pdf paper_translated.pdf
```

- **只编辑一个 plan.jsonl**；重建只读这个文件，不合并其他译文文件。
- 计划按整块原文生成。正文、标题和图注用 PARA；表格文字按单元格用 SPAN 或 RECT，别把整张表当段落重排。
- 逐段忠实翻译，保留数字、引用、限定条件。作者、参考文献条目、纯数字、公式和图内标签通常留空，保持原样；表格说明文字要翻译。
- 空 `dst` 保留原文。可随时重建；某条放不下时也保留该处原文，问题汇总到 `<输出.pdf>.report.json`，修该条后重跑。
- 交付前检查漏译，渲染几页查看图表与公式。脚本检查不能证明翻译语义正确。

```jsonl
{"p":1,"b":2,"type":"PARA","src":"We propose...","dst":"我们提出……"}
```

`p/b` 从计划复制。需要表格单元格、自定义区域或接续旧译文时，再读 [格式说明](references/format.md)。局部替换损坏公式时可试 `--overlay`：它用白底覆盖原文再绘译文，保留底层原文文本；只适合相应的白底区域，需目检。
