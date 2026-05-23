"""定位 Facebook 评论输入框 — 查找 + 点击激活 + 焦点验证"""

from __future__ import annotations

import time
import logging

log = logging.getLogger("fb.find_comment_box")


def find_comment_box(driver, max_attempts: int = 3) -> bool:
    """定位并激活 Facebook 评论输入框。

    Facebook 评论框通常是 contenteditable div 或带有特定 aria-label 的元素。

    Args:
        driver: Selenium WebDriver
        max_attempts: 最大尝试次数

    Returns:
        是否成功聚焦到评论输入框
    """
    for attempt in range(max_attempts):
        activated = driver.execute_script("""
            var isVisible = function(el) {
                if (!el) return false;
                var rect = el.getBoundingClientRect();
                var style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 &&
                       style.visibility !== 'hidden' &&
                       style.display !== 'none';
            };

            // Facebook 评论框通常是 contenteditable div
            // 策略1: 查找带有 comment 相关属性的 contenteditable 元素
            var editables = Array.from(document.querySelectorAll(
                '[contenteditable="true"], [role="textbox"]'
            )).filter(function(el) {
                if (!isVisible(el)) return false;
                var ph = (el.getAttribute('aria-placeholder') || el.getAttribute('placeholder') || '').toLowerCase();
                var al = (el.getAttribute('aria-label') || '').toLowerCase();
                var dataph = (el.getAttribute('data-placeholder') || '').toLowerCase();
                // 匹配评论相关的 placeholder
                return ph.includes('comment') || ph.includes('write a') ||
                       ph.includes('评论') || ph.includes('留言') ||
                       al.includes('comment') || al.includes('write a') ||
                       al.includes('评论') || al.includes('留言') ||
                       dataph.includes('comment') || dataph.includes('write') ||
                       ph.includes('leave a');
            });

            if (editables.length > 0) {
                var box = editables[0];
                box.scrollIntoView({behavior: 'auto', block: 'center'});
                var rect = box.getBoundingClientRect();
                var x = rect.left + rect.width / 2;
                var y = rect.top + rect.height / 2;
                ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(function(type) {
                    box.dispatchEvent(new MouseEvent(type, {
                        bubbles: true, cancelable: true, clientX: x, clientY: y, view: window
                    }));
                });
                box.focus();
                return {found: true, type: 'contenteditable'};
            }

            // 策略2: 查找评论区域的触发按钮（评论图标）
            var commentBtns = document.querySelectorAll('[aria-label*="Comment"], [aria-label*="comment"], [aria-label*="评论"], [aria-label="Leave a comment"]');
            for (var i = 0; i < commentBtns.length; i++) {
                var btn = commentBtns[i];
                if (isVisible(btn)) {
                    btn.click();
                    return {found: false, triggered: true};
                }
            }

            // 策略3: 查找包含 "Write a comment" 文本的占位符区域
            var placeholders = document.querySelectorAll('[data-placeholder], [aria-placeholder]');
            for (var j = 0; j < placeholders.length; j++) {
                var ph = placeholders[j];
                var text = (ph.getAttribute('data-placeholder') || ph.getAttribute('aria-placeholder') || '').toLowerCase();
                if ((text.includes('write') || text.includes('comment')) && isVisible(ph)) {
                    ph.click();
                    ph.focus();
                    return {found: true, type: 'placeholder'};
                }
            }

            return {found: false, triggered: false};
        """)

        if activated and activated.get("found"):
            time.sleep(0.5)
            # 验证焦点
            focus_ok = driver.execute_script("""
                var el = document.activeElement;
                if (!el) return false;
                return el.getAttribute('contenteditable') === 'true' ||
                       el.getAttribute('role') === 'textbox' ||
                       el.tagName === 'TEXTAREA' || el.tagName === 'INPUT';
            """)
            if focus_ok:
                return True

        if activated and activated.get("triggered"):
            time.sleep(2)
            continue

        time.sleep(2)

    return False
