"""从预生成评论文件分配任务到账号

适配 fb_comments_final.json 格式：
  {"idx": N, "url": "...", "title": "...", "priority": "High/Medium", "comment_style": "A/B/C/D", "comment": "..."}

分配逻辑：
  1. 按优先级排序（High 优先）
  2. 取前 N 条（不超过 账号数 × 每日配额）
  3. Round-Robin 均匀分配给所有账号
  4. 打散：同一账号的任务来自不同帖子
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
log = logging.getLogger("fb.assign")


def load_comments(comments_file: Path) -> list[dict]:
    """加载预生成评论文件"""
    with open(comments_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 按优先级排序
    priority_order = {"High": 0, "high": 0, "Medium": 1, "medium": 1, "Low": 2, "low": 2}
    data.sort(key=lambda x: priority_order.get(x.get("priority", "Medium"), 1))
    return data


def load_accounts(accounts_file: Path) -> list[dict]:
    """加载账号文件"""
    with open(accounts_file, "r", encoding="utf-8") as f:
        raw = json.load(f)
    accounts = raw if isinstance(raw, list) else raw.get("accounts", [])
    return [a for a in accounts if a.get("status", "alive") == "alive"]


def assign_tasks(
    comments: list[dict],
    accounts: list[dict],
    total: int = 0,
    quota_per_account: int = 0,
) -> list[dict]:
    """将预生成评论分配给账号

    Returns:
        [{"task_id", "env_uid", "serial_number", "post_url", "comment_text", "priority", "status"}, ...]
    """
    if not quota_per_account:
        quota_per_account = config.DAILY_QUOTA_PER_ACCOUNT

    max_total = len(accounts) * quota_per_account
    if total <= 0:
        total = min(max_total, len(comments))
    else:
        total = min(total, max_total, len(comments))

    log.info(f"分配参数: 评论池={len(comments)}, 账号={len(accounts)}, 今日目标={total}, 配额={quota_per_account}/账号")

    # 取前 total 条
    selected = comments[:total]

    # Round-Robin 分配
    tasks = []
    account_usage = {a["env_uid"]: 0 for a in accounts}
    account_idx = 0

    for item in selected:
        url = item.get("url", "")
        comment_text = item.get("comment", "")
        if not url or not comment_text:
            continue

        # 找下一个有配额的账号
        for _ in range(len(accounts)):
            acct = accounts[account_idx % len(accounts)]
            uid = acct["env_uid"]
            account_idx += 1

            if account_usage[uid] >= quota_per_account:
                continue

            task_id = f"t_{int(time.time()*1000)}_{len(tasks):04d}"
            tasks.append({
                "task_id": task_id,
                "env_uid": uid,
                "serial_number": acct.get("serial_number", ""),
                "post_url": url,
                "comment_text": comment_text,
                "priority": item.get("priority", "Medium"),
                "comment_style": item.get("comment_style", ""),
                "title": item.get("title", "")[:100],
                "idx": item.get("idx", 0),
                "status": "ready",
            })
            account_usage[uid] += 1
            break

    # 打散：按 env_uid 分组后交错排列（同一账号的任务不连续）
    by_account = {}
    for t in tasks:
        by_account.setdefault(t["env_uid"], []).append(t)

    shuffled = []
    max_len = max(len(v) for v in by_account.values()) if by_account else 0
    account_lists = list(by_account.values())
    random.shuffle(account_lists)
    for i in range(max_len):
        for al in account_lists:
            if i < len(al):
                shuffled.append(al[i])

    # 统计
    used_accounts = sum(1 for v in account_usage.values() if v > 0)
    avg = len(tasks) / max(used_accounts, 1)
    log.info(f"分配完成: {len(tasks)} 条任务, {used_accounts} 个账号, 平均 {avg:.1f} 条/账号")

    return shuffled


def main():
    parser = argparse.ArgumentParser(description="预生成评论分配到账号")
    parser.add_argument("--comments", required=True, help="预生成评论文件 (JSON)")
    parser.add_argument("--accounts", default="data/accounts.json", help="账号文件")
    parser.add_argument("--total", type=int, default=0, help="今日总量 (0=最大)")
    parser.add_argument("--quota", type=int, default=0, help="每账号配额 (0=默认20)")
    parser.add_argument("--output", default="data/tasks.json", help="输出任务文件")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    args = parser.parse_args()

    comments = load_comments(Path(args.comments))
    accounts = load_accounts(Path(args.accounts))

    if not comments:
        log.error("评论文件为空")
        return
    if not accounts:
        log.error("账号文件为空")
        return

    tasks = assign_tasks(comments, accounts, total=args.total, quota_per_account=args.quota)

    if args.dry_run:
        log.info("=== 预览模式 ===")
        by_acct = {}
        for t in tasks:
            by_acct.setdefault(t["env_uid"], 0)
            by_acct[t["env_uid"]] += 1
        log.info(f"总任务: {len(tasks)}")
        log.info(f"账号分布: min={min(by_acct.values())}, max={max(by_acct.values())}, avg={sum(by_acct.values())/len(by_acct):.1f}")
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": args.comments,
        "total": len(tasks),
        "accounts_used": len(set(t["env_uid"] for t in tasks)),
        "tasks": tasks,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    log.info(f"任务文件已保存: {output_path}")


if __name__ == "__main__":
    main()
