"""发送评论 — 点击 Post comment 按钮"""

from __future__ import annotations

import time
import logging

log = logging.getLogger("fb.submit_comment")


def submit_comment(driver, wait_after: float = 3.0) -> bool:
    """点击 Facebook 的 Post comment 按钮发送评论。

    Facebook 评论框中 Enter 是换行，需要点击专门的提交按钮。

    Args:
        driver: Selenium WebDriver（评论已输入完毕）
        wait_after: 发送后等待时间（秒）

    Returns:
        是否发送成功（评论框清空视为成功）
    """
    try:
        # 点击 "Post comment" 按钮
        clicked = driver.execute_script("""
            // 策略1: 精确匹配 aria-label="Post comment"
            var btn = document.querySelector('[aria-label="Post comment"]');
            if (btn) {
                btn.click();
                return 'post_comment';
            }

            // 策略2: 模糊匹配
            var candidates = document.querySelectorAll('[aria-label*="Post"], [aria-label*="post"], [aria-label*="Submit"], [aria-label*="发表"], [aria-label*="发送"]');
            for (var i = 0; i < candidates.length; i++) {
                var el = candidates[i];
                var label = (el.getAttribute('aria-label') || '').toLowerCase();
                if ((label.includes('post') && label.includes('comment')) || label === 'post' || label.includes('submit')) {
                    var rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        el.click();
                        return 'fallback: ' + el.getAttribute('aria-label');
                    }
                }
            }

            return null;
        """)

        if not clicked:
            log.warning("未找到 Post comment 按钮")
            return False

        log.info(f"点击提交按钮: {clicked}")
        time.sleep(wait_after)

        # 验证：检查评论框是否清空（清空=发送成功）
        box_empty = driver.execute_script("""
            var box = document.querySelector('[role="textbox"][aria-label*="comment" i], [role="textbox"][aria-label*="Write" i]');
            if (!box) return true;  // 评论框消失也算成功
            var text = (box.textContent || box.innerText || '').trim();
            return text.length === 0;
        """)

        if box_empty:
            return True

        # 评论框没清空，检查是否有风控
        blocked = driver.execute_script("""
            var bodyText = (document.body.innerText || '').toLowerCase();
            return bodyText.includes("you can't use this feature") ||
                   bodyText.includes("you're temporarily blocked") ||
                   bodyText.includes("try again later") ||
                   bodyText.includes("couldn't post") ||
                   bodyText.includes("此功能暂时不可用") ||
                   bodyText.includes("暂时被限制");
        """)

        if blocked:
            log.warning("检测到风控限制")
            return False

        # 评论框没清空但也没报错，可能是网络延迟
        log.warning("评论框未清空，可能发送失败")
        return False

    except Exception as e:
        log.error(f"发送评论失败: {e}")
        return False


def submit_comment_fallback(driver) -> bool:
    """备用发送方式：使用 Enter 键（某些 Facebook 版本可能支持）。"""
    try:
        driver.execute_cdp_cmd("Input.dispatchKeyEvent", {
            "type": "keyDown", "key": "Enter", "code": "Enter",
            "text": "\r",
            "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13
        })
        driver.execute_cdp_cmd("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": "Enter", "code": "Enter",
            "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13
        })

        time.sleep(3)

        # 检查评论框是否清空
        box_empty = driver.execute_script("""
            var box = document.querySelector('[role="textbox"][aria-label*="comment" i], [role="textbox"][aria-label*="Write" i]');
            if (!box) return true;
            return (box.textContent || '').trim().length === 0;
        """)

        return bool(box_empty)

    except Exception as e:
        log.error(f"备用发送失败: {e}")
        return False
