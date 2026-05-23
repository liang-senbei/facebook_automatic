"""日计划生成 — 分配帖子到账号，生成执行队列

用法:
    python -m comments.cli.plan --posts posts.json --accounts accounts.json --total 100 --output tasks.json
"""

from __future__ import annotations

import sys
import json
import time
import random
import argparse
import logging
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

from comments import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("fb.plan")


def load_posts(posts_file: Path) -> list[dict]:
    """加载帖子列表"""
    with open(posts_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    posts = data if isinstance(data, list) else data.get("posts", [])
    # 按优先级排序
    priority_order = {"high": 0, "medium": 1, "low": 2}
    posts.sort(key=lambda p: priority_order.get(p.get("priority", "medium"), 1))
    return posts


def load_accounts(accounts_file: Path) -> list[dict]:
    """加载账号列表"""
    with open(accounts_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    accounts = data if isinstance(data, list) else data.get("accounts", [])
    # 只使用状态正常的账号
    return [a for a in accounts if a.get("status", "alive") == "alive"]


def generate_plan(
    posts: list[dict],
    accounts: list[dict],
    total: int = 0,
    quota_per_account: int = 0,
) -> list[dict]:
    """生成日计划 — 将帖子分配到账号

    分配策略：
    1. 每个帖子分配 1-N 个账号（根据优先级）
    2. 每个账号每天不超过配额
    3. Round-Robin 保证账号分散
    4. 同一帖子同一账号最多 1 条

    Returns:
        [{"env_uid": "...", "post_url": "...", "comment_text": "", "task_id": "..."}, ...]
    """
    if not quota_per_account:
        quota_per_account = config.DAILY_QUOTA_PER_ACCOUNT

    max_total = len(accounts) * quota_per_account
    if total <= 0 or total > max_total:
        total = min(max_total, len(posts) * 3)  # 默认每帖最多 3 条

    log.info(f"计划参数: 帖子={len(posts)}, 账号={len(accounts)}, 目标={total}, 配额={quota_per_account}/账号")

    # 账号配额追踪
    account_usage = {a["env_uid"]: 0 for a in accounts}
    tasks = []
    # 帖子-账号去重
    post_account_pairs = set()

    # Round-Robin 分配
    account_idx = 0
    for post in posts:
        if len(tasks) >= total:
            break

        post_url = post.get("post_url", post.get("url", ""))
        if not post_url:
            continue

        # 每帖分配的评论数（高优先级多分配）
        priority = post.get("priority", "medium")
        comments_per_post = {"high": 3, "medium": 2, "low": 1}.get(priority, 2)

        for _ in range(comments_per_post):
            if len(tasks) >= total:
                break

            # 找下一个有配额的账号
            found = False
            for _ in range(len(accounts)):
                acct = accounts[account_idx % len(accounts)]
                uid = acct["env_uid"]
                account_idx += 1

                if account_usage[uid] >= quota_per_account:
                    continue
                if (post_url, uid) in post_account_pairs:
                    continue

                # 分配
                task_id = f"t_{int(time.time()*1000)}_{len(tasks):04d}"
                tasks.append({
                    "task_id": task_id,
                    "env_uid": uid,
                    "post_url": post_url,
                    "comment_text": "",  # generate 阶段填充
                    "account_username": acct.get("username", ""),
                    "post_priority": priority,
                    "post_author": post.get("author", ""),
                    "content_preview": post.get("content_preview", post.get("content", ""))[:200],
                    "comment_angle": post.get("comment_angle", ""),
                    "status": "planned",
                })
                account_usage[uid] += 1
                post_account_pairs.add((post_url, uid))
                found = True
                break

            if not found:
                break  # 所有账号配额用完

    # Round-Robin 排序（同一账号的任务分散开）
    random.shuffle(tasks)
    tasks.sort(key=lambda t: (t["env_uid"], random.random()))

    # 重新排序：stride 分散
    if tasks:
        stride_tasks = []
        by_account = {}
        for t in tasks:
            by_account.setdefault(t["env_uid"], []).append(t)

        max_len = max(len(v) for v in by_account.values())
        account_lists = list(by_account.values())
        for i in range(max_len):
            for al in account_lists:
                if i < len(al):
                    stride_tasks.append(al[i])
        tasks = stride_tasks

    log.info(f"计划生成完成: {len(tasks)} 条任务, 使用 {sum(1 for v in account_usage.values() if v > 0)} 个账号")
    return tasks


def main():
    parser = argparse.ArgumentParser(description="Facebook 评论日计划生成")
    parser.add_argument("--posts", required=True, help="帖子列表文件 (JSON)")
    parser.add_argument("--accounts", required=True, help="账号列表文件 (JSON)")
    parser.add_argument("--total", type=int, default=0, help="今日总评论目标 (0=自动)")
    parser.add_argument("--quota", type=int, default=0, help="每账号配额 (0=使用默认)")
    parser.add_argument("--output", default="tasks.json", help="输出任务文件")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    args = parser.parse_args()

    posts = load_posts(Path(args.posts))
    accounts = load_accounts(Path(args.accounts))

    if not posts:
        log.error("帖子列表为空")
        return
    if not accounts:
        log.error("账号列表为空")
        return

    tasks = generate_plan(posts, accounts, total=args.total, quota_per_account=args.quota)

    if args.dry_run:
        log.info("=== 预览模式 ===")
        log.info(f"总任务数: {len(tasks)}")
        # 按账号统计
        by_account = {}
        for t in tasks:
            by_account.setdefault(t["env_uid"], 0)
            by_account[t["env_uid"]] += 1
        for uid, count in sorted(by_account.items(), key=lambda x: -x[1])[:10]:
            log.info(f"  {uid}: {count} 条")
        return

    # 保存任务文件
    output_path = Path(args.output)
    output_data = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(tasks),
        "posts_count": len(posts),
        "accounts_count": len(accounts),
        "tasks": tasks,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    log.info(f"任务文件已保存: {output_path}")


if __name__ == "__main__":
    main()
