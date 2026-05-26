"""导航到 Facebook 帖子页面"""

from __future__ import annotations

import time
import logging

log = logging.getLogger("fb.navigate_post")

FATAL_ERRORS = ("invalid session", "no such window", "session not created", "browser has closed")


def navigate_to_post(driver, post_url: str, timeout: int = 30) -> bool:
    """导航到指定的 Facebook 帖子。

    Args:
        driver: Selenium WebDriver
        post_url: Facebook 帖子 URL
        timeout: 超时时间（秒）

    Returns:
        是否成功加载帖子页面

    Raises:
        RuntimeError: 浏览器已死（invalid session 等），上层应终止该账号
    """
    try:
        driver.get(post_url)
    except Exception as e:
        err_msg = str(e).lower()
        if any(kw in err_msg for kw in FATAL_ERRORS):
            raise RuntimeError(f"浏览器已死: {str(e)[:80]}")
        log.warning(f"导航超时（可能已部分加载）: {e}")

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            url = driver.current_url or ""
            if "facebook.com" not in url:
                time.sleep(2)
                continue

            has_content = driver.execute_script("""
                var post = document.querySelector('[data-pagelet*="FeedUnit"], [role="article"], .x1yztbdb');
                if (post) return true;
                var textLen = (document.body.innerText || '').length;
                return textLen > 200;
            """)
            if has_content:
                return True
        except Exception as e:
            err_msg = str(e).lower()
            if any(kw in err_msg for kw in FATAL_ERRORS):
                raise RuntimeError(f"浏览器已死: {str(e)[:80]}")
        time.sleep(2)

    return False
