# Facebook 评论截流系统 — 操作手册

> 本文件是 Claude Code 进入 facebook_automatic/ 时自动加载的操作系统。

## 强制规则

1. **确认纪律**：执行投放前必须让用户确认帖子列表、账号、评论内容
2. **并发纪律**：启动任何批量任务前，必须向用户展示可选并发数并等待确认
3. **审核纪律**：LLM 生成的评论必须展示样本给用户审核后才能投放
4. **AdsPower 纪律**：执行前确认 AdsPower 客户端已启动

## 用户指令 → 动作映射

| 触发词 | 动作 | 对应 Skill |
|--------|------|-----------|
| "发评论""投放""部署评论" | 评论投放全流程 | `/comment-deploy` |
| "状态""进度""看看情况" | 系统状态总览 | `/fb-status` |
| "导出""记录""CSV" | 导出评论记录 | `/export` |

## 系统架构

```
facebook_automatic/
├── shared/           ← 基础设施（config、adspower、browser_context）
├── comments/
│   ├── actions/      ← 7 个原子操作（浏览器自动化）
│   ├── chains/       ← 行为链（execute_comment + session_chain）
│   ├── generator/    ← LLM 评论生成（豆包 API 异步并发）
│   ├── data/         ← 数据层（state + log + models）
│   ├── cli/          ← 5 个 CLI 工具（plan/generate/run/status/export）
│   └── config.py     ← 可调参数
├── config/.env       ← API Key（不提交 git）
├── data/             ← 运行时数据（不提交 git）
└── .claude/commands/ ← 3 个 Skill 定义
```

## CLI 调用手册

### 评论投放完整流程

```bash
# Step 1: 生成日计划
python -m comments.cli.plan --posts data/posts.json --accounts data/accounts.json --total N --output data/tasks.json

# Step 2: 生成评论
python -m comments.cli.generate --tasks data/tasks.json --brand-context "品牌描述" --concurrency 50

# Step 3: 执行投放
python -m comments.cli.run --tasks data/tasks.json --workers 2

# Step 4: 查看状态
python -m comments.cli.status --tasks data/tasks.json

# Step 5: 导出记录
python -m comments.cli.export --data-dir data/runtime --output data/comments_log.csv
```

### 单环境测试

```bash
python test_comment.py --explore --env ENV_UID
python test_comment.py --post-url "URL" --text "评论" --env ENV_UID
```

## 数据文件格式

### accounts.json

```json
{
  "accounts": [
    {"env_uid": "k1csqgqh", "username": "xxx", "status": "alive", "daily_quota": 20}
  ]
}
```

### posts.json

```json
{
  "posts": [
    {
      "post_url": "https://www.facebook.com/...",
      "author": "作者名",
      "content_preview": "帖子内容预览",
      "priority": "high/medium/low",
      "comment_angle": "评论切入角度"
    }
  ]
}
```

## 配置参数（comments/config.py）

| 参数 | 值 | 说明 |
|------|---|------|
| DAILY_QUOTA_PER_ACCOUNT | 20 | 每账号每天上限 |
| COMMENTS_PER_SESSION_OPTIONS | [3,4,5] | 每 session 条数 |
| WARMUP_DURATION_SEC | (60,180) | 暖场时长 |
| INTER_COMMENT_WAIT_SEC | (30,60) | 评论间隔 |
| MAX_CONCURRENT_BROWSERS | 5 | 最大并发 |
| LIKE_BEFORE_COMMENT_PROB | 0.60 | 点赞概率 |

## 测试环境

| 编号 | env_uid | 用途 |
|------|---------|------|
| 2007 | k1csqgqh | 测试账号 |
| 2008 | k1csqgqi | 测试账号 |
