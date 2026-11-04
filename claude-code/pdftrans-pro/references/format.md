# 条目与旧任务

- `--show 3 2` 查看第3页第2块及其 spans；`s` 是 spans 中从0开始的序号。
- PARA：`{"p":1,"b":2,"type":"PARA","dst":"译文"}`。可选 `style` 为 body/heading/headc/title。
- SPAN：`{"p":3,"b":2,"s":0,"type":"SPAN","dst":"方法"}`，按原基线写单行单元格。
- RECT：`{"p":3,"type":"RECT","rect":[50,100,120,110],"dst":"方法"}`，区域同时用于擦除与绘制。默认取附近原文字号，也可用 `size` 指定；不要盖到相邻数字或公式。
- `src` 可留作对照，存在时会校验是否对应所选块/span。空 `dst` 保留原文；不需要 status 字段。
- `--plan-file path.jsonl` 在重建和验证时选用其他单文件计划。重复运行 `--plan` 不改写已有内容。
- `verify.py ... --pages 3-5,7` 可只检查当前页，检查结果写回同一份 `<输出.pdf>.report.json`。

旧版多来源任务要先合并成**一个** JSONL：按旧任务实际生效的译文保留一份，移除同一位置过时的 PARA/SPAN/RECT。脚本不再执行 `translations.py` 或自动加载 `translations/`。原旧任务文件可以保留，不会被新脚本修改。

已移除 `--dump`、`--status`、`--work-dir`、`--allow-partial` 和整页重绘选项。现在只需生成计划、填写、重建和检查；公式不再经过整页字体提取重绘。
