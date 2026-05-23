"""Facebook 评论投放执行入口 — 连接 AdsPower 浏览器执行评论任务"""

from __future__ import annotations

import sys
import time
import json
import logging
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 项目根目录加入 path
_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

from shared.browser_context import browser_session
from comments.chains.session_chain import run_session, SessionResult
from comments.data.state_store import StateStore
from comments.data.execution_log import ExecutionLog
from comments import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("fb.run")


def load_tasks(tasks_file: Path) -> list[dict]:
    """加载评论任务文件"""
    if not tasks_file.exists():
        log.error(f"任务文件不存在: {tasks_file}")
        return []
    with open(tasks_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("tasks", [])


def execute_worker(env_uid: str, tasks: list[dict], worker_id: int) -> SessionResult:
    """单个 worker：打开浏览器 → 执行 session → 关闭"""
    log.info(f"[Worker-{worker_id}] 启动: env={env_uid}, 任务数={len(tasks)}")

    try:
        with browser_session(env_uid, navigate_fb=True) as driver:
            result = run_session(
                driver,
                account_username=env_uid,
                comment_tasks=tasks,
                on_comment_done=lambda i, r: log.info(
                    f"[Worker-{worker_id}] 评论 {i+1}/{len(tasks)}: {r.status}"
                ),
            )
            log.info(
                f"[Worker-{worker_id}] 完成: 成功={result.comments_sent}, "
                f"失败={result.comments_failed}, 封号={result.banned}, "
                f"耗时={result.duration_min}min"
            )
            return result
    except Exception as e:
        log.error(f"[Worker-{worker_id}] 异常: {e}")
        return SessionResult(account=env_uid, comments_failed=len(tasks))


def run(tasks_file: Path, workers: int = 5):
    """主执行函数"""
    all_tasks = load_tasks(tasks_file)
    if not all_tasks:
        log.error("无可执行任务")
        return

    # 只执行有评论文本且状态为 ready/planned 的任务
    executable = [t for t in all_tasks if t.get("comment_text") and t.get("status") in ("ready", "planned", "pending")]
    if not executable:
        log.error("无可执行任务（缺少 comment_text 或状态不对）")
        return

    # 初始化状态管理
    data_dir = tasks_file.parent / "runtime"
    state = StateStore(data_dir)
    exec_log = ExecutionLog(data_dir)

    # 过滤已封号的账号
    executable = [t for t in executable if not state.is_account_banned(t.get("env_uid", ""))]

    # 按 env_uid 分组
    grouped = {}
    for task in executable:
        uid = task.get("env_uid", "")
        if uid:
            grouped.setdefault(uid, []).append(task)

    if not grouped:
        log.error("任务中缺少 env_uid 字段")
        return

    log.info(f"共 {len(executable)} 条可执行任务，分配到 {len(grouped)} 个账号")

    # 按 session 分组（每个账号按 COMMENTS_PER_SESSION_OPTIONS 分 session）
    import random
    session_queue = []
    for uid, tasks in grouped.items():
        i = 0
        while i < len(tasks):
            session_size = random.choice(config.COMMENTS_PER_SESSION_OPTIONS)
            session_tasks = tasks[i:i + session_size]
            session_queue.append((uid, session_tasks))
            i += session_size

    log.info(f"共 {len(session_queue)} 个 session 待执行")

    # 并发执行
    results = []
    with ThreadPoolExecutor(max_workers=min(workers, len(grouped))) as executor:
        futures = {}
        for i, (uid, tasks) in enumerate(session_queue):
            future = executor.submit(execute_worker, uid, tasks, i + 1)
            futures[future] = (uid, tasks)

        for future in as_completed(futures):
            uid, tasks = futures[future]
            try:
                result = future.result()
                results.append(result)

                # 记录日志
                exec_log.log_session(uid, result.comments_sent, result.comments_failed,
                                     result.banned, result.duration_min)
                for cr in result.results:
                    state.record_comment(uid, cr.post_url, cr.status)
                    exec_log.log_comment(uid, cr.post_url, cr.status,
                                         cr.comment_text, cr.error, cr.duration_sec)

                if result.banned:
                    state.mark_account_banned(uid, result.ban_type)

            except Exception as e:
                log.error(f"Worker 异常 (env={uid}): {e}")

    # 汇总
    total_sent = sum(r.comments_sent for r in results)
    total_failed = sum(r.comments_failed for r in results)
    banned_accounts = [r.account for r in results if r.banned]

    log.info("=" * 50)
    log.info(f"执行完成: 成功={total_sent}, 失败={total_failed}")
    if banned_accounts:
        log.warning(f"封号账号: {banned_accounts}")

    # 保存执行结果
    result_file = tasks_file.parent / f"result_{int(time.time())}.json"
    result_data = {
        "executed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_sent": total_sent,
        "total_failed": total_failed,
        "banned_accounts": banned_accounts,
        "sessions": len(results),
        "details": [
            {
                "account": r.account,
                "sent": r.comments_sent,
                "failed": r.comments_failed,
                "banned": r.banned,
                "ban_type": r.ban_type,
                "duration_min": r.duration_min,
            }
            for r in results
        ],
    }
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
    log.info(f"结果已保存: {result_file}")


def main():
    parser = argparse.ArgumentParser(description="Facebook 评论投放执行")
    parser.add_argument("--tasks", required=True, help="任务文件路径 (JSON)")
    parser.add_argument("--workers", type=int, default=config.MAX_CONCURRENT_BROWSERS,
                        help=f"并发数 (默认 {config.MAX_CONCURRENT_BROWSERS})")
    args = parser.parse_args()

    tasks_file = Path(args.tasks)
    run(tasks_file, workers=args.workers)


if __name__ == "__main__":
    main()
