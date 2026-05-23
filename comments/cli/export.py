"""评论记录导出 — 生成 CSV 格式的评论投放记录

用法:
    python -m comments.cli.export --data-dir data/runtime --output data/comments_log.csv
    python -m comments.cli.export --data-dir data/runtime --date 2026-05-23
"""

from __future__ import annotations

import sys
import csv
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("fb.export")


def export_csv(data_dir: Path, output: Path, date_filter: str = ""):
    """从 JSONL 日志导出 CSV 记录"""
    data_dir = Path(data_dir)
    if not data_dir.exists():
        log.error(f"数据目录不存在: {data_dir}")
        return

    # 收集所有日志文件
    log_files = sorted(data_dir.glob("log_*.jsonl"))
    if date_filter:
        log_files = [f for f in log_files if date_filter in f.name]

    if not log_files:
        log.error("未找到日志文件")
        return

    # 读取所有评论记录
    records = []
    for log_file in log_files:
        date_str = log_file.stem.replace("log_", "")
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("type") == "comment":
                        records.append({
                            "日期": date_str,
                            "时间": entry.get("timestamp", ""),
                            "账号环境": entry.get("env_uid", ""),
                            "帖子链接": entry.get("post_url", ""),
                            "评论内容": entry.get("comment_text", ""),
                            "状态": entry.get("status", ""),
                            "耗时(秒)": entry.get("duration_sec", 0),
                            "错误": entry.get("error", ""),
                        })
                except json.JSONDecodeError:
                    pass

    if not records:
        log.info("无评论记录")
        return

    # 写入 CSV
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["日期", "时间", "账号环境", "帖子链接", "评论内容", "状态", "耗时(秒)", "错误"])
        writer.writeheader()
        writer.writerows(records)

    log.info(f"已导出 {len(records)} 条记录 → {output}")

    # 打印统计
    by_account = {}
    by_status = {}
    for r in records:
        uid = r["账号环境"]
        status = r["状态"]
        by_account[uid] = by_account.get(uid, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1

    print(f"\n{'='*50}")
    print(f"  导出统计")
    print(f"{'='*50}")
    print(f"  总记录数: {len(records)}")
    print(f"  日志文件: {len(log_files)} 个")
    print(f"\n  按状态:")
    for status, count in sorted(by_status.items()):
        print(f"    {status}: {count}")
    print(f"\n  按账号:")
    for uid, count in sorted(by_account.items()):
        print(f"    {uid}: {count} 条")


def main():
    parser = argparse.ArgumentParser(description="Facebook 评论记录导出 CSV")
    parser.add_argument("--data-dir", default="data/runtime", help="数据目录 (默认 data/runtime)")
    parser.add_argument("--output", default="data/comments_log.csv", help="输出 CSV 文件路径")
    parser.add_argument("--date", default="", help="按日期过滤 (如 2026-05-23)")
    args = parser.parse_args()

    export_csv(Path(args.data_dir), Path(args.output), date_filter=args.date)


if __name__ == "__main__":
    main()
