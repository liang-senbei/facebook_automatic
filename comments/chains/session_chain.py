"""Session 行为链 — 单次上线的完整行为序列。

暖场(1-3min) → 评论循环(3-5条，穿插随机动作) → 收尾(0.5-2min)
"""

from __future__ import annotations

import time
import random
import logging
from dataclasses import dataclass, field

from comments.chains import CommentResult
from comments.chains.execute_comment import execute_comment
from comments.actions.random_browse import warmup_browse, cooldown_browse, random_browse
from comments.actions.detect_ban import detect_ban
from comments import config

log = logging.getLogger("fb.session_chain")


@dataclass
class SessionResult:
    account: str
    comments_sent: int = 0
    comments_failed: int = 0
    banned: bool = False
    ban_type: str = ""
    duration_min: float = 0.0
    results: list[CommentResult] = field(default_factory=list)


def run_session(
    driver,
    account_username: str,
    comment_tasks: list[dict],
    session_config: dict | None = None,
    on_comment_done: callable | None = None,
    stop_event=None,
) -> SessionResult:
    """执行单次上线的完整行为链。

    Args:
        driver: Selenium WebDriver（浏览器已打开，已登录）
        account_username: 当前账号用户名
        comment_tasks: [{"post_url": "...", "comment_text": "...", "comment_id": "..."}, ...]
        session_config: 可选配置覆盖
        on_comment_done: 每条评论完成后的回调

    Returns:
        SessionResult
    """
    start = time.time()
    cfg = session_config or {}
    result = SessionResult(account=account_username)

    # 阶段 0：初始封禁检测
    ban = detect_ban(driver)
    if ban.is_banned:
        result.banned = True
        result.ban_type = ban.status
        result.duration_min = (time.time() - start) / 60
        return result

    # 阶段 1：暖场
    warmup_sec = cfg.get("warmup_sec", random.randint(*config.WARMUP_DURATION_SEC))
    try:
        warmup_browse(driver, duration_sec=warmup_sec)
    except Exception:
        pass

    # 暖场后再次检测
    ban = detect_ban(driver)
    if ban.is_banned:
        result.banned = True
        result.ban_type = ban.status
        result.duration_min = (time.time() - start) / 60
        return result

    # 阶段 2：评论循环
    total_comments = len(comment_tasks)
    MAX_COMMENT_RETRIES = 3
    RETRYABLE_ERRORS = ("timeout", "net::ERR_", "connection", "disconnected", "navigate_failed", "comment_box_not_found")
    FATAL_DRIVER_ERRORS = ("invalid session", "no such window", "session not created")

    for i, task in enumerate(comment_tasks):
        # 硬超时检查
        if stop_event and stop_event.is_set():
            log.warning("session 硬超时，终止剩余评论")
            result.comments_failed += (total_comments - i)
            break

        # 动态随机动作概率
        progress = (i + 1) / max(total_comments, 1)
        if progress < 0.3:
            action_prob = config.RANDOM_ACTION_PROB_EARLY
        elif progress < 0.7:
            action_prob = config.RANDOM_ACTION_PROB_MID
        else:
            action_prob = config.RANDOM_ACTION_PROB_LATE

        # 执行评论（带重试）
        comment_result = None
        for attempt in range(MAX_COMMENT_RETRIES):
            try:
                comment_result = execute_comment(
                    driver,
                    post_url=task["post_url"],
                    comment_text=task["comment_text"],
                    like_prob=config.LIKE_BEFORE_COMMENT_PROB,
                )
            except RuntimeError:
                # 浏览器已死，立即终止整个 session
                result.comments_failed += (total_comments - i)
                result.duration_min = round((time.time() - start) / 60, 1)
                return result

            if comment_result.status in ("sent", "unverified", "banned"):
                break

            error_lower = (comment_result.error or "").lower()
            is_driver_dead = any(kw in error_lower for kw in FATAL_DRIVER_ERRORS)
            if is_driver_dead:
                result.comments_failed += 1
                result.results.append(comment_result)
                if on_comment_done:
                    try:
                        on_comment_done(i, comment_result)
                    except Exception:
                        pass
                result.comments_failed += (total_comments - i - 1)
                result.duration_min = round((time.time() - start) / 60, 1)
                return result

            is_retryable = any(kw in error_lower for kw in RETRYABLE_ERRORS)
            if not is_retryable or attempt == MAX_COMMENT_RETRIES - 1:
                break

            wait = 5 * (attempt + 1)
            try:
                driver.refresh()
                time.sleep(wait)
            except Exception:
                time.sleep(wait)

        # 防御 None（所有 attempt 都抛出非预期异常时）
        if comment_result is None:
            comment_result = CommentResult(
                post_url=task["post_url"],
                comment_text=task.get("comment_text", ""),
                status="failed",
                error="unexpected_exception",
            )

        result.results.append(comment_result)

        if on_comment_done:
            try:
                on_comment_done(i, comment_result)
            except Exception:
                pass

        if comment_result.status in ("sent", "unverified"):
            result.comments_sent += 1
        elif comment_result.status == "banned":
            result.banned = True
            result.ban_type = comment_result.ban_type
            break
        else:
            result.comments_failed += 1

        # 评论间穿插等待和随机动作
        if i < total_comments - 1 and not result.banned:
            wait = random.uniform(*config.INTER_COMMENT_WAIT_SEC)
            if random.random() < action_prob:
                t0 = time.time()
                try:
                    random_browse(driver)
                except Exception:
                    pass
                elapsed = time.time() - t0
                remaining = wait - elapsed
                if remaining > 0:
                    time.sleep(remaining)
            else:
                time.sleep(wait)

    # 阶段 3：收尾
    if not result.banned:
        cooldown_sec = cfg.get("cooldown_sec", random.randint(*config.COOLDOWN_DURATION_SEC))
        try:
            cooldown_browse(driver, duration_sec=cooldown_sec)
        except Exception:
            pass

    result.duration_min = round((time.time() - start) / 60, 1)
    return result
