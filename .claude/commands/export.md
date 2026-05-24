# /export — 导出评论记录

导出 CSV 格式的评论投放记录（账号、帖子、评论内容、状态、时间）

## 流程

1. 确认导出范围：
   - 全部记录（默认）
   - 按日期过滤（--date 2026-05-23）
2. 执行导出：
   ```bash
   python -m comments.cli.export --data-dir data/runtime --output data/comments_log.csv
   ```
3. 展示导出统计（总记录数、按账号/状态分布）

## CSV 字段

日期、时间、账号环境、帖子链接、评论内容、状态、耗时(秒)、错误
