"""输入评论文本 — 模拟真人逐字输入"""

from __future__ import annotations

import time
import random
import logging

log = logging.getLogger("fb.type_comment")


def type_comment(driver, text: str, char_delay: tuple = (0.03, 0.10)) -> bool:
    """在已聚焦的评论框中逐字输入评论。

    使用 CDP Input.insertText 逐段输入，模拟真人打字节奏。
    Facebook 的 contenteditable div 对 Input.insertText 响应最好。

    Args:
        driver: Selenium WebDriver（评论框已聚焦）
        text: 要输入的评论文本
        char_delay: 每个字符间的延迟范围（秒）

    Returns:
        是否输入成功
    """
    try:
        # 分段输入（每次 1-3 个字符，模拟真人打字）
        i = 0
        while i < len(text):
            chunk_size = random.randint(1, 3)
            chunk = text[i:i + chunk_size]
            driver.execute_cdp_cmd("Input.insertText", {"text": chunk})
            i += chunk_size

            time.sleep(random.uniform(*char_delay))

            # 随机停顿模拟思考（5% 概率）
            if random.random() < 0.05:
                time.sleep(random.uniform(0.3, 0.8))

        # 验证输入内容
        time.sleep(0.5)
        current_text = driver.execute_script("""
            var el = document.activeElement;
            if (!el) return '';
            return el.textContent || el.innerText || el.value || '';
        """)

        if current_text and len(current_text.strip()) > 0:
            return True

        log.warning("输入验证失败：评论框内容为空")
        return False

    except Exception as e:
        log.error(f"输入评论失败: {e}")
        return False


def type_comment_fast(driver, text: str) -> bool:
    """快速输入评论（CDP 一次性插入）。

    当逐字输入失败时的备用方案。
    """
    try:
        driver.execute_cdp_cmd("Input.insertText", {"text": text})
        time.sleep(0.5)

        current_text = driver.execute_script("""
            var el = document.activeElement;
            if (!el) return '';
            return el.textContent || el.innerText || el.value || '';
        """)
        return bool(current_text and len(current_text.strip()) > 0)

    except Exception as e:
        log.error(f"快速输入失败: {e}")
        return False
