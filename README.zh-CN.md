[English](README.md) | 简体中文

# PDFTrans Pro

**非商业使用免费；商用必须事先取得作者书面授权，并支付双方约定的授权费。**

商业授权请联系 [palelunar](https://github.com/palelunar)，或提交 [商业授权申请](https://github.com/palelunar/pdftrans-pro/issues/new?title=Commercial%20license%20request)。授权费用和范围单独约定，公开源码不代表免费商用。

一个轻量的 PDF 翻译技能：生成单文件计划，由模型填译文，再原位重建并检查。

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

## 维护

公共脚本在 `claude-code/pdftrans-pro/scripts/` 修改后运行 `python tools/sync_scripts.py`；`--check` 检查两套脚本一致。核心回归：`python -B -m unittest discover -s tests -v`。



## 许可

本版本采用 [PDFTrans Pro Noncommercial License 1.0](LICENSE)：允许查看源码、修改和非商业使用及分享，商业使用需单独付费授权。属于源码可用（source-available）许可，不是 OSI 定义的开源许可。以前已按 MIT 发布的旧版本不受追溯变更。

本项目的授权仅覆盖本项目代码；PyMuPDF 等第三方依赖须另行遵守其许可证。PyMuPDF 提供 [AGPL 与商业授权](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)，向本项目支付授权费不会自动取得第三方商业许可。
