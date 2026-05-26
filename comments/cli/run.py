"""Facebook 评论投放执行入口

并发模型：
- N 条任务线并行（ThreadPoolExecutor）
- 每条线串行处理分配给它的账号队列
- 每个账号的每个 session 独立开关浏览器（不复用）
- 完成一个 session → 关闭浏览器 → 开下一个

容错：
- 浏览器启动失败：重试 2 次（间隔 10s/20s），仍失败跳过该账号
- 代理不通（连续 2 个 session 全部网络失败）：跳过该账号
- 封禁：跳过该账号
- 浏览器崩溃（invalid session）：终止当前 session，跳到下一个 session
- 单条评论超时/失败：session_chain 内部重试 3 次
- 硬超时：单个 session 最长 10 分钟
"""

from __future__ import annotations

import sys
import time
import json
import random
import logging
import argparse
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

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

SESSION_HARD_TIMEOUT = 600  # 单个 session 硬超时 10 分钟
MAX_BROWSER_RETRIES = 2
MAX_CONSECUTIVE_NET_FAILS = 2  # 连续 N 个 session 全网络失败则跳过账号


def load_tasks(tasks_file: Path) -> list[dict]:
    if not tasks_file.exists():
        log.error(f"任务文件不存在: {tasks_file}")
        return []
    with open(tasks_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("tasks", [])


def execute_single_session(env_uid: str, session_tasks: list[dict],
                           line_id: int, session_num: int,
                           stop_event: threading.Event = None) -> SessionResult:
    """执行单个 session：独立开关浏览器。

    浏览器启动异常会向上传递（触发外层重试）。
    session 执行期间的异常在内部处理。
    """
    # browser_session 的 __enter__ 阶段异常（启动失败）会直接抛出
    with browser_session(env_uid, navigate_fb=True) as driver:
        try:
            result = run_session(
                driver,
                account_username=env_uid,
                comment_tasks=session_tasks,
                stop_event=stop_event,
                on_comment_done=lambda idx, r: log.info(
                    f"[线程-{line_id}] S{session_num} 评论 {idx+1}/{len(session_tasks)}: {r.status}"
                ),
            )
            return result
        except Exception as e:
            log.error(f"[线程-{line_id}] S{session_num} 执行异常: {str(e)[:80]}")
            return SessionResult(account=env_uid, comments_failed=len(session_tasks))


def execute_task_line(line_id: int, account_queue: list[tuple],
                      state: StateStore, exec_log: ExecutionLog) -> list[SessionResult]:
    """一条任务线：串行处理多个账号，每个 session 独立开关浏览器。"""
    all_results = []

    for acct_idx, (env_uid, tasks) in enumerate(account_queue):
        log.info(f"[线程-{line_id}] 账号 {acct_idx+1}/{len(account_queue)}: "
                 f"env={env_uid}, 任务={len(tasks)}")

        # 将任务拆分为 session
        sessions = []
        i = 0
        while i < len(tasks):
            size = random.choice(config.COMMENTS_PER_SESSION_OPTIONS)
            sessions.append(tasks[i:i + size])
            i += size

        consecutive_net_fails = 0

        for session_num, session_tasks in enumerate(sessions, 1):
            # 浏览器启动重试
            result = None
            for attempt in range(MAX_BROWSER_RETRIES + 1):
                # 用 stop_event 做硬超时保护
                stop_event = threading.Event()
                timer = threading.Timer(SESSION_HARD_TIMEOUT, lambda: stop_event.set())
                timer.daemon = True
                timer.start()

                try:
                    result = execute_single_session(env_uid, session_tasks, line_id, session_num, stop_event)
                    timer.cancel()
                    break
                except Exception as e:
                    timer.cancel()
                    if attempt < MAX_BROWSER_RETRIES:
                        wait = 10 * (attempt + 1)
                        log.warning(f"[线程-{line_id}] 浏览器启动失败，{wait}s 后重试: {str(e)[:50]}")
                        time.sleep(wait)
                    else:
                        log.error(f"[线程-{line_id}] 浏览器启动失败，跳过: {str(e)[:50]}")
                        result = SessionResult(account=env_uid, comments_failed=len(session_tasks))

            if result is None:
                result = SessionResult(account=env_uid, comments_failed=len(session_tasks))

            all_results.append(result)

            # 记录日志
            exec_log.log_session(env_uid, result.comments_sent, result.comments_failed,
                                 result.banned, result.duration_min)
            for cr in result.results:
                state.record_comment(env_uid, cr.post_url, cr.status)
                exec_log.log_comment(env_uid, cr.post_url, cr.status,
                                     cr.comment_text, cr.error, cr.duration_sec)

            # 封禁 → 跳过该账号
            if result.banned:
                state.mark_account_banned(env_uid, result.ban_type)
                log.warning(f"[线程-{line_id}] 账号 {env_uid} 封号({result.ban_type})，跳过")
                break

            # 检测连续网络失败
            if result.comments_sent == 0 and result.comments_failed > 0:
                all_net_error = all(
                    any(kw in (cr.error or "").lower()
                        for kw in ("navigate_failed", "timeout", "net::err_", "socks", "connection", "浏览器已死"))
                    for cr in result.results if cr.status == "failed"
                ) if result.results else False
                if all_net_error:
                    consecutive_net_fails += 1
                else:
                    consecutive_net_fails = 0
            else:
                consecutive_net_fails = 0

            if consecutive_net_fails >= MAX_CONSECUTIVE_NET_FAILS:
                log.warning(f"[线程-{line_id}] 账号 {env_uid} 连续网络失败，跳过")
                break

            # session 间休息（浏览器已关闭）
            if session_num < len(sessions):
                rest = random.randint(3, 8)
                time.sleep(rest)

        # 账号间休息
        if acct_idx < len(account_queue) - 1:
            rest = random.randint(5, 10)
            log.info(f"[线程-{line_id}] 切换账号，休息 {rest}s")
            time.sleep(rest)

    sent = sum(r.comments_sent for r in all_results)
    failed = sum(r.comments_failed for r in all_results)
    log.info(f"[线程-{line_id}] 完成: {len(account_queue)} 个账号, 成功={sent}, 失败={failed}")
    return all_results


def run(tasks_file: Path, workers: int = 5):
    """主执行函数"""
    all_tasks = load_tasks(tasks_file)
    if not all_tasks:
        log.error("无可执行任务")
        return

    executable = [t for t in all_tasks
                  if t.get("comment_text") and t.get("status") in ("ready", "planned", "pending")]
    if not executable:
        log.error("无可执行任务（缺少 comment_text 或状态不对）")
        return

    data_dir = tasks_file.parent / "runtime"
    state = StateStore(data_dir)
    exec_log = ExecutionLog(data_dir)

    executable = [t for t in executable if not state.is_account_banned(t.get("env_uid", ""))]

    grouped = {}
    for task in executable:
        uid = task.get("env_uid", "")
        if uid:
            grouped.setdefault(uid, []).append(task)

    if not grouped:
        log.error("无可执行任务")
        return

    log.info(f"共 {len(executable)} 条任务，{len(grouped)} 个账号")

    # 分配到 N 条任务线
    account_list = list(grouped.items())
    num_lines = min(workers, len(account_list))
    lines = [[] for _ in range(num_lines)]
    for i, item in enumerate(account_list):
        lines[i % num_lines].append(item)

    log.info(f"任务线: {num_lines} 条，每条 {len(account_list)//num_lines}-{len(account_list)//num_lines+1} 个账号")

    results = []
    with ThreadPoolExecutor(max_workers=num_lines) as executor:
        futures = {}
        for line_id, line_accounts in enumerate(lines):
            future = executor.submit(execute_task_line, line_id + 1, line_accounts, state, exec_log)
            futures[future] = line_id + 1

        for future in as_completed(futures):
            line_id = futures[future]
            try:
                line_results = future.result()
                results.extend(line_results)
            except Exception as e:
                log.error(f"任务线-{line_id} 异常: {e}")

    total_sent = sum(r.comments_sent for r in results)
    total_failed = sum(r.comments_failed for r in results)
    banned_accounts = list(set(r.account for r in results if r.banned))

    log.info("=" * 50)
    log.info(f"执行完成: 成功={total_sent}, 失败={total_failed}")
    if banned_accounts:
        log.warning(f"封号账号: {banned_accounts}")

    result_file = tasks_file.parent / f"result_{int(time.time())}.json"
    result_data = {
        "executed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_sent": total_sent,
        "total_failed": total_failed,
        "banned_accounts": banned_accounts,
        "sessions": len(results),
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
    run(Path(args.tasks), workers=args.workers)


if __name__ == "__main__":
    main()
