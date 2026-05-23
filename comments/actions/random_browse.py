"""Facebook 随机浏览行为 — 暖场/收尾/穿插"""

from __future__ import annotations

import time
import random
import logging

log = logging.getLogger("fb.random_browse")


def warmup_browse(driver, duration_sec: int = 120):
    """暖场浏览：模拟真人在 Facebook 上的随机浏览行为。

    Args:
        driver: Selenium WebDriver
        duration_sec: 暖场持续时间（秒）
    """
    start = time.time()
    actions = [_scroll_feed, _view_notifications, _browse_marketplace, _scroll_feed]

    while time.time() - start < duration_sec:
        action = random.choice(actions)
        try:
            action(driver)
        except Exception:
            pass
        time.sleep(random.uniform(3, 8))


def cooldown_browse(driver, duration_sec: int = 60):
    """收尾浏览：评论完成后的自然行为。"""
    start = time.time()
    while time.time() - start < duration_sec:
        try:
            _scroll_feed(driver)
        except Exception:
            pass
        time.sleep(random.uniform(3, 6))


def random_browse(driver):
    """穿插在评论间的随机动作（单次）。"""
    actions = [_scroll_feed, _like_random_post, _view_notifications]
    action = random.choice(actions)
    try:
        action(driver)
    except Exception:
        pass


def _scroll_feed(driver):
    """随机滚动 Feed"""
    scroll_amount = random.randint(300, 800)
    driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
    time.sleep(random.uniform(2, 5))

    # 偶尔回滚
    if random.random() < 0.3:
        driver.execute_script(f"window.scrollBy(0, -{random.randint(100, 300)});")
        time.sleep(random.uniform(1, 3))


def _like_random_post(driver):
    """随机点赞一个帖子"""
    driver.execute_script("""
        var likeButtons = document.querySelectorAll(
            '[aria-label="Like"], [aria-label="like"], [aria-label="赞"]'
        );
        var unliked = Array.from(likeButtons).filter(function(btn) {
            return btn.getAttribute('aria-pressed') !== 'true' &&
                   window.getComputedStyle(btn).display !== 'none';
        });
        if (unliked.length > 0) {
            var idx = Math.floor(Math.random() * Math.min(unliked.length, 3));
            unliked[idx].click();
        }
    """)
    time.sleep(random.uniform(1, 3))


def _view_notifications(driver):
    """查看通知（不点击具体通知）"""
    try:
        driver.execute_script("""
            var notiBtn = document.querySelector('[aria-label="Notifications"], [aria-label="通知"]');
            if (notiBtn) notiBtn.click();
        """)
        time.sleep(random.uniform(2, 4))
        # 关闭通知面板
        driver.execute_script("document.body.click();")
    except Exception:
        pass


def _browse_marketplace(driver):
    """浏览 Marketplace（仅滚动）"""
    try:
        driver.get("https://www.facebook.com/marketplace/")
        time.sleep(random.uniform(3, 6))
        driver.execute_script(f"window.scrollBy(0, {random.randint(200, 500)});")
        time.sleep(random.uniform(2, 4))
        driver.get("https://www.facebook.com/")
        time.sleep(random.uniform(2, 4))
    except Exception:
        pass
