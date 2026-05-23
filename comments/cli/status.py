"""状态查看 — 显示当前评论系统运行状态

用法:
    python -m comments.cli.status --tasks tasks.json
    python -m comments.cli.status --data-dir ./data
"""

from __future__ import annotations

import sys
import json
import argparse
import logging
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

from comments.data.state_store import StateStore
from comments.data.execution_log import ExecutionLog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("fb.status")


def show_tasks_status(tasks_file: Path):
    """显示任务文件的状态"""
    if not tasks_file.exists():
        log.error(f"文件不存在: {tasks_file}")
        return

    with open(tasks_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    tasks = data.get("tasks", data) if isinstance(data, dict) else data

    # 统计
    total = len(tasks)
    by_status = {}
    by_account = {}
    for t in tasks:
        status = t.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        uid = t.get("env_uid", "unknown")
        by_account.setdefault(uid, {"total": 0, "sent": 0, "failed": 0})
        by_account[uid]["total"] += 1
        if status in ("sent", "unverified"):
            by_account[uid]["sent"] += 1
        elif status == "failed":
            by_account[uid]["failed"] += 1

    has_text = sum(1 for t in tasks if t.get("comment_text"))

    print("\n" + "=" * 50)
    print(f"  任务文件: {tasks_file.name}")
    if isinstance(data, dict):
        print(f"  创建时间: {data.get('created_at', 'N/A')}")
        print(f"  生成时间: {data.get('generated_at', 'N/A')}")
    print("=" * 50)
    print(f"\n  总任务数: {total}")
    print(f"  已有评论: {has_text} ({has_text*100//max(total,1)}%)")
    print(f"\n  状态分布:")
    for status, count in sorted(by_status.items()):
        pct = count * 100 // max(total, 1)
        bar = "█" * (pct // 5)
        print(f"    {status:12s}: {count:4d} ({pct}%) {bar}")

    print(f"\n  账号统计 (前10):")
    sorted_accounts = sorted(by_account.items(), key=lambda x: -x[1]["total"])
    for uid, stats in sorted_accounts[:10]:
        print(f"    {uid[:12]:12s}: 总={stats['total']:3d}, 成功={stats['sent']:3d}, 失败={stats['failed']:3d}")

    if len(sorted_accounts) > 10:
        print(f"    ... 还有 {len(sorted_accounts) - 10} 个账号")
    print()


def show_data_dir_status(data_dir: Path):
    """显示数据目录的状态"""
    if not data_dir.exists():
        log.error(f"目录不存在: {data_dir}")
        return

    state = StateStore(data_dir)
    exec_log = ExecutionLog(data_dir)

    stats = state.get_stats()
    today_logs = exec_log.read_today()

    print("\n" + "=" * 50)
    print(f"  数据目录: {data_dir}")
    print("=" * 50)
    print(f"\n  累计统计:")
    print(f"    发送成功: {stats.get('total_sent', 0)}")
    print(f"    发送失败: {stats.get('total_failed', 0)}")
    print(f"    封号数:   {stats.get('total_banned', 0)}")

    print(f"\n  今日日志: {len(today_logs)} 条记录")
    if today_logs:
        sessions = [r for r in today_logs if r.get("type") == "session"]
        comments = [r for r in today_logs if r.get("type") == "comment"]
        print(f"    Session: {len(sessions)}")
        print(f"    评论:    {len(comments)}")
        sent = sum(1 for c in comments if c.get("status") in ("sent", "unverified"))
        failed = sum(1 for c in comments if c.get("status") == "failed")
        print(f"    成功/失败: {sent}/{failed}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Facebook 评论系统状态")
    parser.add_argument("--tasks", help="任务文件路径")
    parser.add_argument("--data-dir", help="数据目录路径")
    args = parser.parse_args()

    if args.tasks:
        show_tasks_status(Path(args.tasks))
    elif args.data_dir:
        show_data_dir_status(Path(args.data_dir))
    else:
        # 默认查看 data/ 目录
        default_dir = _ROOT / "data"
        if default_dir.exists():
            show_data_dir_status(default_dir)
        else:
            log.info("请指定 --tasks 或 --data-dir 参数")


if __name__ == "__main__":
    main()
