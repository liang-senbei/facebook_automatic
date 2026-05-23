# Facebook 评论截流系统

> 基于 AdsPower 浏览器指纹管理 + Selenium CDP 控制的 Facebook 自动化评论系统
> 参考 ins-system 架构，针对 Facebook 平台特性适配

## 系统架构

```
facebook_automatic/
├── shared/                 ← 共享基础设施
│   ├── config.py           — .env 加载 + 全局常量
│   ├── adspower.py         — AdsPower 本地 API（浏览器启停）
│   └── browser_context.py  — browser_session() 上下文管理器
│
├── comments/               ← 评论执行系统
│   ├── config.py           — 可调参数（配额/时间/并发/LLM）
│   ├── actions/            — 7 个原子操作（浏览器自动化）
│   │   ├── navigate_post.py    — 导航到帖子
│   │   ├── find_comment_box.py — 定位评论输入框（contenteditable div）
│   │   ├── type_comment.py     — CDP Input.insertText 逐段输入
│   │   ├── submit_comment.py   — Enter 键发送 + 备用按钮
│   │   ├── verify_comment.py   — 验证评论是否成功
│   │   ├── detect_ban.py       — 封禁/风控检测（16关键词 + URL模式）
│   │   └── random_browse.py    — 随机浏览（暖场/收尾/穿插）
│   ├── chains/             — 行为链编排
│   │   ├── execute_comment.py  — 单条评论完整流程（8步）
│   │   └── session_chain.py    — 单次上线行为链（暖场→评论→收尾）
│   ├── generator/          — 评论生成
│   │   └── async_generate.py   — 异步并发 LLM 生成（豆包 API）
│   ├── data/               — 数据层
│   │   ├── state_store.py      — 状态管理（帖子/账号/统计）
│   │   ├── execution_log.py    — JSONL 执行日志（按天轮转）
│   │   └── models.py           — 数据模型定义
│   └── cli/                — CLI 入口
│       ├── plan.py         — 日计划生成（帖子→账号分配）
│       ├── generate.py     — 评论生成（LLM 异步并发）
│       ├── run.py          — 批量执行投放
│       └── status.py       — 状态查看
│
├── config/                 ← 配置文件
│   ├── .env                — 环境变量（API Key 等）
│   └── .env.example        — 模板
│
├── data/                   ← 运行时数据
│   ├── accounts.json       — 账号池
│   ├── sample_posts.json   — 示例帖子
│   └── runtime/            — 执行状态和日志
│
├── test_comment.py         ← 测试脚本
├── requirements.txt        ← Python 依赖
└── reference/              ← 参考项目（ins-system）
```

## 完整工作流

```
plan → generate → run → status
```

### 1. 生成日计划

```bash
python -m comments.cli.plan \
    --posts data/sample_posts.json \
    --accounts data/accounts.json \
    --total 100 \
    --output data/tasks.json
```

### 2. 生成评论（LLM）

```bash
python -m comments.cli.generate \
    --tasks data/tasks.json \
    --brand-context "Your brand description here" \
    --concurrency 50
```

### 3. 执行投放

```bash
python -m comments.cli.run --tasks data/tasks.json --workers 5
```

### 4. 查看状态

```bash
python -m comments.cli.status --tasks data/tasks.json
python -m comments.cli.status --data-dir data/runtime
```

## 测试

```bash
# 探索模式（打开浏览器观察页面）
python test_comment.py --explore --env k1csqgqh

# 暖场测试
python test_comment.py --warmup --env k1csqgqh

# 评论框定位测试
python test_comment.py --find-box --post-url "URL" --env k1csqgqh

# 完整评论测试
python test_comment.py --post-url "URL" --text "Comment text" --env k1csqgqh
```

## 实测结果（2026-05-23）

在 AdsPower 环境 `k1csqgqh` 上验证通过：
- 评论框定位: contenteditable div, aria-label="Write a comment…"
- 输入方式: CDP Input.insertText（逐段输入，模拟打字节奏）
- 发送方式: CDP Enter 键事件
- 单条评论耗时: ~43 秒
- 完整 session（含暖场/收尾）: ~4 分钟

## 与 INS 系统的差异

| 特性 | Instagram | Facebook |
|------|-----------|----------|
| 评论框 | textarea / input | contenteditable div (role=textbox) |
| 输入方式 | CDP keyDown/keyUp | CDP Input.insertText |
| 评论按钮 | aria-label="Comment" | aria-label="Leave a comment" |
| 风控检测 | 18 个关键词 | 16 个关键词 + URL 模式 |
| 每日配额 | 25 条/账号 | 20 条/账号 |
| Session 评论数 | 5-7 条 | 3-5 条 |
| 暖场时长 | 2-5 分钟 | 1-3 分钟 |
| 评论间隔 | 25-45 秒 | 30-60 秒 |
