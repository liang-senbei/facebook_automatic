# /fb-status — 系统状态总览

聚合评论系统运行状态，一屏展示

## 流程

1. **账号状态**：读取 `data/accounts.json` 统计各状态数量
2. **今日执行情况**：读取 `data/runtime/log_*.jsonl` 统计今日发送/失败/封号
3. **任务进度**：如有 `data/tasks.json`，展示完成率
4. **累计统计**：读取 `data/runtime/state.json` 展示总发送量

## 输出格式

```
| 维度 | 状态 | 详情 |
|------|------|------|
| 账号池 | X 存活 / Y 封禁 | 按 status 分组 |
| 今日投放 | N 成功 / M 失败 | 成功率 |
| 累计 | 总发送 / 总失败 / 封号数 | 全量统计 |
| 任务 | 已完成/总计 | 当前批次进度 |
```

## 快捷命令

```bash
python -m comments.cli.status --data-dir data/runtime
python -m comments.cli.status --tasks data/tasks.json
```
