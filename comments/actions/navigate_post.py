"""导航到 Facebook 帖子页面"""

from __future__ import annotations

import time
import logging

log = logging.getLogger("fb.navigate_post")


def navigate_to_post(driver, post_url: str, timeout: int = 30) -> bool:
    """导航到指定的 Facebook 帖子。

    Args:
        driver: Selenium WebDriver
        post_url: Facebook 帖子 URL
        timeout: 超时时间（秒）

    Returns:
        是否成功加载帖子页面
    """
    try:
        driver.get(post_url)
    except Exception as e:
        log.warning(f"导航超时（可能已部分加载）: {e}")

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            url = driver.current_url or ""
            if "facebook.com" not in url:
                time.sleep(2)
                continue

            # 检测页面是否加载了帖子内容
            has_content = driver.execute_script("""
                // 检测帖子内容区域
                var post = document.querySelector('[data-pagelet*="FeedUnit"], [role="article"], .x1yztbdb');
                if (post) return true;
                // 备用检测：页面文本长度
                var textLen = (document.body.innerText || '').length;
                return textLen > 200;
            """)
            if has_content:
                return True
        except Exception:
            pass
        time.sleep(2)

    return False
