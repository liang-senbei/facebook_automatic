"""Facebook 封禁/风控检测"""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger("fb.detect_ban")

BAN_KEYWORDS = [
    "your account has been disabled",
    "your account has been suspended",
    "you can't use this feature",
    "you're temporarily blocked",
    "we've restricted your account",
    "account restricted",
    "temporarily restricted",
    "this content isn't available",
    "something went wrong",
    "confirm your identity",
    "security check required",
    "checkpoint",
    "账号已被停用",
    "暂时被限制",
    "此功能暂时不可用",
    "确认你的身份",
]

BAN_URL_PATTERNS = [
    "/checkpoint/",
    "/login/",
    "/disabled/",
    "/help/contact/",
    "/recover/",
]


@dataclass
class BanResult:
    is_banned: bool = False
    status: str = ""
    detail: str = ""


def detect_ban(driver) -> BanResult:
    """检测当前页面是否存在封禁/风控信号。

    Returns:
        BanResult 包含封禁状态和详情
    """
    try:
        url = driver.current_url or ""

        # URL 检测
        for pattern in BAN_URL_PATTERNS:
            if pattern in url:
                if "/checkpoint/" in url:
                    return BanResult(is_banned=True, status="checkpoint", detail=url)
                if "/login/" in url:
                    return BanResult(is_banned=True, status="logged_out", detail=url)
                if "/disabled/" in url:
                    return BanResult(is_banned=True, status="disabled", detail=url)
                return BanResult(is_banned=True, status="restricted", detail=url)

        # 页面文本检测
        body_text = driver.execute_script(
            "return (document.body && document.body.innerText) ? document.body.innerText.substring(0, 3000).toLowerCase() : '';"
        )

        for keyword in BAN_KEYWORDS:
            if keyword.lower() in body_text:
                status = "disabled" if "disabled" in keyword else \
                         "suspended" if "suspended" in keyword else \
                         "blocked" if "blocked" in keyword else \
                         "restricted" if "restricted" in keyword else \
                         "checkpoint" if "checkpoint" in keyword or "identity" in keyword else \
                         "unknown"
                return BanResult(is_banned=True, status=status, detail=keyword)

        return BanResult(is_banned=False)

    except Exception as e:
        log.warning(f"封禁检测异常: {e}")
        return BanResult(is_banned=False)
