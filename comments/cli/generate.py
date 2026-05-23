"""评论生成 — 为日计划中的任务生成评论文本

用法:
    python -m comments.cli.generate --tasks tasks.json --brand-context "..." --concurrency 50
"""

from __future__ import annotations

import sys
import json
import time
import argparse
import logging
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

from shared.config import DOUBAO_API_KEY
from comments import config
from comments.generator.async_generate import generate_comments

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("fb.generate")


def main():
    parser = argparse.ArgumentParser(description="Facebook 评论生成")
    parser.add_argument("--tasks", required=True, help="任务文件路径 (plan 输出)")
    parser.add_argument("--brand-context", default="", help="品牌上下文描述")
    parser.add_argument("--brand-file", default="", help="品牌上下文文件")
    parser.add_argument("--concurrency", type=int, default=config.COMMENT_LLM_CONCURRENCY,
                        help=f"并发数 (默认 {config.COMMENT_LLM_CONCURRENCY})")
    parser.add_argument("--api-key", default="", help="LLM API Key (默认从 .env 读取)")
    parser.add_argument("--output", default="", help="输出文件 (默认覆盖原文件)")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    args = parser.parse_args()

    # 加载任务
    tasks_path = Path(args.tasks)
    if not tasks_path.exists():
        log.error(f"任务文件不存在: {tasks_path}")
        return

    with open(tasks_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    tasks = data.get("tasks", data) if isinstance(data, dict) else data

    # 筛选需要生成评论的任务
    pending = [t for t in tasks if not t.get("comment_text")]
    if not pending:
        log.info("所有任务已有评论文本，无需生成")
        return

    log.info(f"待生成: {len(pending)} 条 (总计 {len(tasks)} 条)")

    # 品牌上下文
    brand_context = args.brand_context
    if args.brand_file:
        brand_path = Path(args.brand_file)
        if brand_path.exists():
            brand_context = brand_path.read_text(encoding="utf-8").strip()
    if not brand_context:
        brand_context = "A helpful brand that provides value to its community."
        log.warning(f"未指定品牌上下文，使用默认值")

    # API Key
    api_key = args.api_key or DOUBAO_API_KEY
    if not api_key:
        log.error("未配置 LLM API Key (DOUBAO_API_KEY)")
        return

    if args.dry_run:
        log.info("=== 预览模式 ===")
        log.info(f"待生成: {len(pending)} 条")
        log.info(f"品牌上下文: {brand_context[:100]}...")
        log.info(f"并发数: {args.concurrency}")
        log.info(f"模型: {config.COMMENT_LLM_MODELS}")
        return

    # 生成评论
    log.info(f"开始生成评论 (并发={args.concurrency})...")
    start = time.time()

    gen_tasks = [
        {
            "post_url": t["post_url"],
            "content_preview": t.get("content_preview", ""),
            "author": t.get("post_author", ""),
            "comment_angle": t.get("comment_angle", ""),
            "task_id": t.get("task_id", f"t_{i}"),
        }
        for i, t in enumerate(pending)
    ]

    results = generate_comments(
        gen_tasks,
        brand_context=brand_context,
        api_key=api_key,
        concurrency=args.concurrency,
    )

    # 按索引一一回填（每条任务独立生成，不复用）
    filled = 0
    for i, task in enumerate(pending):
        if i < len(results) and results[i]["status"] == "generated":
            task["comment_text"] = results[i]["comment_text"]
            task["status"] = "ready"
            filled += 1

    elapsed = time.time() - start
    log.info(f"生成完成: 成功={filled}, 耗时={elapsed:.1f}s")

    # 保存
    output_path = Path(args.output) if args.output else tasks_path
    if isinstance(data, dict):
        data["tasks"] = tasks
        data["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        data["generated_count"] = filled
    else:
        data = tasks

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info(f"已保存: {output_path}")


if __name__ == "__main__":
    main()
