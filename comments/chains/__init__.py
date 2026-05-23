"""评论执行链 — 单条评论的完整执行流程"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CommentResult:
    status: str = ""  # sent, unverified, failed, banned
    post_url: str = ""
    comment_text: str = ""
    error: str = ""
    ban_type: str = ""
    duration_sec: float = 0.0
