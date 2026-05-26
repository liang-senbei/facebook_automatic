"""单条评论执行流程 — 导航→定位→输入→发送→验证"""

from __future__ import annotations

import time
import random
import logging

from comments.chains import CommentResult
from comments.actions.navigate_post import navigate_to_post
from comments.actions.find_comment_box import find_comment_box
from comments.actions.type_comment import type_comment, type_comment_fast
from comments.actions.submit_comment import submit_comment, submit_comment_fallback
from comments.actions.verify_comment import verify_comment
from comments.actions.detect_ban import detect_ban
from comments import config

log = logging.getLogger("fb.execute_comment")


def execute_comment(
    driver,
    post_url: str,
    comment_text: str,
    like_prob: float = 0.6,
) -> CommentResult:
    """执行单条评论的完整流程。

    流程：
    1. 导航到帖子
    2. 模拟阅读（随机等待）
    3. 可选：点赞帖子
    4. 定位评论框
    5. 输入评论
    6. 发送评论
    7. 验证评论

    Args:
        driver: Selenium WebDriver
        post_url: 帖子 URL
        comment_text: 评论内容
        like_prob: 评论前点赞概率

    Returns:
        CommentResult
    """
    start = time.time()
    result = CommentResult(post_url=post_url, comment_text=comment_text)

    # Step 1: 导航到帖子
    try:
        if not navigate_to_post(driver, post_url):
            result.status = "failed"
            result.error = "navigate_failed"
            result.duration_sec = time.time() - start
            return result
    except RuntimeError as e:
        # 浏览器已死，向上传递
        result.status = "failed"
        result.error = str(e)
        result.duration_sec = time.time() - start
        raise

    # Step 2: 检测封禁
    ban = detect_ban(driver)
    if ban.is_banned:
        result.status = "banned"
        result.ban_type = ban.status
        result.duration_sec = time.time() - start
        return result

    # Step 3: 模拟阅读
    time.sleep(random.uniform(*config.IDLE_BEFORE_COMMENT_SEC))

    # Step 4: 可选点赞
    if random.random() < like_prob:
        _try_like_post(driver)
        time.sleep(random.uniform(1, 3))

    # Step 5: 定位评论框
    if not find_comment_box(driver):
        result.status = "failed"
        result.error = "comment_box_not_found"
        result.duration_sec = time.time() - start
        return result

    time.sleep(random.uniform(0.5, 1.5))

    # Step 6: 输入评论
    typed = type_comment(driver, comment_text)
    if not typed:
        # 备用方案
        typed = type_comment_fast(driver, comment_text)
    if not typed:
        result.status = "failed"
        result.error = "type_failed"
        result.duration_sec = time.time() - start
        return result

    time.sleep(random.uniform(0.5, 2.0))

    # Step 7: 发送评论
    sent = submit_comment(driver)
    if not sent:
        sent = submit_comment_fallback(driver)
    if not sent:
        # 再次检测是否被封
        ban = detect_ban(driver)
        if ban.is_banned:
            result.status = "banned"
            result.ban_type = ban.status
        else:
            result.status = "failed"
            result.error = "submit_failed"
        result.duration_sec = time.time() - start
        return result

    # Step 8: 验证评论
    verified = verify_comment(driver, comment_text, timeout=8)
    result.status = "sent" if verified else "unverified"
    result.duration_sec = time.time() - start
    return result


def _try_like_post(driver):
    """尝试点赞当前帖子"""
    try:
        driver.execute_script("""
            var likeBtn = document.querySelector(
                '[aria-label="Like"][aria-pressed="false"], ' +
                '[aria-label="like"][aria-pressed="false"], ' +
                '[aria-label="赞"][aria-pressed="false"]'
            );
            if (likeBtn) likeBtn.click();
        """)
    except Exception:
        pass
