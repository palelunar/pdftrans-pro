---
name: pdftrans-pro
license: See LICENSE
description: "在 DeepSeek Harness 中翻译 PDF 或制作保留版式的论文译本，尽量保留图片、公式和表格；不用于仅总结或提取文字。"
---

# PDFTrans Pro

适用于 DeepSeek Harness。把 PDF 翻译成用户指定语言，另存结果，尽量保留原版面。

需要装有 `pymupdf` 的 Python 和目标语言字体。Windows 默认宋体/黑体；其他字体用 `PDFTRANS_SIMSUN`、`PDFTRANS_SIMHEI` 指定。缺包时用报错中给出的解释器安装命令。

## 常用流程

```bash
python scripts/pdftrans.py paper.pdf --plan
python scripts/pdftrans.py paper.pdf --list --pending --pages 1-3
# 只读取本批需要的原文并填写 plan.jsonl 的 dst
python scripts/pdftrans.py paper.pdf paper_translated.pdf
python scripts/verify.py paper.pdf paper_translated.pdf
python scripts/pdftrans.py paper_translated.pdf --preview 1,3
```

- **一个 plan.jsonl 是唯一译文来源**。先看紧凑概览，需全文/坐标再用 `--show 页码 块号`；按页处理，避免反复读取整份计划。未填项也可能是有意保留，不能把数量当作漏译结论。
- 逐段忠实翻译，保留数字、引用和限定条件。作者、参考文献条目、纯数字、独立公式和图内标签通常留空；表格文字说明要译。已有 `glossary.json` 时先读一次，跨批次沿用术语，不重复塞进每一条。
- 正文/标题/图注用 PARA。需要合并碎片用 `--merge 页码 块号范围`；文字表格可先用 `--cells 页码 块号` 生成候选单元格，再检查行列。细节见 [格式说明](references/format.md)。
- 空 dst 保留原文。放不下的条目也保留原文并写入 `<输出.pdf>.report.json`；缩字号超过10%会提示。中文断行和字体精简自动处理，正常情况下无需参数。
- 检查报告，并查看预览中的图表/公式。脚本不判断译文语义；行内公式仍需留意，不能把整段替换当成公式保真。确需换策略时可试 `--overlay` 白底覆盖，它保留底层原文，只适合相应的白底区域。

```jsonl
{"p":1,"b":2,"type":"PARA","src":"We propose...","dst":"我们提出……"}
```
