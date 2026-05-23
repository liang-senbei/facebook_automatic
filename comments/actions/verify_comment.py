"""验证评论是否发送成功"""

from __future__ import annotations

import time
import logging

log = logging.getLogger("fb.verify_comment")


def verify_comment(driver, comment_text: str, timeout: int = 10) -> bool:
    """验证评论是否出现在页面上。

    Args:
        driver: Selenium WebDriver
        comment_text: 发送的评论文本（用于匹配）
        timeout: 等待超时（秒）

    Returns:
        是否在页面上找到了该评论
    """
    # 取评论前 20 个字符作为匹配关键词
    search_text = comment_text[:20].strip()
    if not search_text:
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            found = driver.execute_script("""
                var searchText = arguments[0].toLowerCase();
                // 查找评论区域的所有文本节点
                var comments = document.querySelectorAll(
                    '[data-testid*="comment"], [aria-label*="Comment"], .x1lliihq'
                );
                // 如果没有特定选择器，搜索整个页面
                if (comments.length === 0) {
                    var bodyText = (document.body.innerText || '').toLowerCase();
                    return bodyText.includes(searchText);
                }
                for (var i = 0; i < comments.length; i++) {
                    var text = (comments[i].textContent || '').toLowerCase();
                    if (text.includes(searchText)) return true;
                }
                return false;
            """, search_text)

            if found:
                return True
        except Exception:
            pass
        time.sleep(2)

    log.warning(f"评论验证超时，未找到: {search_text}...")
    return False
