# /comment-deploy — Facebook 评论投放

确认帖子 → 确认账号 → 生成评论 → 审核 → 执行投放 → 导出记录

## 流程

1. **确认目标帖子**：
   - 用户提供 Facebook 帖子 URL 列表
   - 或从 `data/sample_posts.json` 读取已有帖子池
   - 确认每个帖子的优先级和评论切入角度

2. **确认账号**：
   - 读取 `data/accounts.json` 展示可用账号
   - 用户确认使用哪些账号（env_uid 列表）
   - 展示：可用账号数 × 每日配额 = 最大可发量

3. **确认参数**：
   - 今日总评论数（--total）
   - 并发数（--workers，默认 2）
   - 品牌上下文（评论围绕什么主题生成）

4. **生成日计划**：
   ```bash
   python -m comments.cli.plan --posts POSTS --accounts ACCOUNTS --total N --output data/tasks.json
   ```

5. **生成评论**：
   ```bash
   python -m comments.cli.generate --tasks data/tasks.json --brand-context "..." --concurrency 50
   ```

6. **展示评论样本供审核**（至少展示 5 条）

7. **用户确认后执行投放**：
   ```bash
   python -m comments.cli.run --tasks data/tasks.json --workers N
   ```

8. **导出记录**：
   ```bash
   python -m comments.cli.export --data-dir data/runtime --output data/comments_log.csv
   ```

## 注意

- 生成的评论必须展示给用户审核后才能执行投放
- 并发数必须询问用户确认
- 同一帖子同一账号最多 1 条评论
- 每账号每日上限 20 条
- 执行前确认 AdsPower 已启动
