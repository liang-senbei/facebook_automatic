"""数据模型定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PostTarget:
    """目标帖子"""
    post_url: str
    post_id: str = ""
    author: str = ""
    content_preview: str = ""
    priority: str = "medium"  # high / medium / low
    comment_angle: str = ""
    assigned_comments: int = 0
    completed_comments: int = 0
    status: str = "pending"  # pending / in_progress / done


@dataclass
class CommentTask:
    """单条评论任务"""
    task_id: str
    env_uid: str
    post_url: str
    comment_text: str
    account_username: str = ""
    status: str = "pending"  # pending / sent / unverified / failed / banned
    error: str = ""
    created_at: str = ""
    executed_at: str = ""


@dataclass
class AccountInfo:
    """账号信息"""
    env_uid: str
    username: str = ""
    status: str = "alive"  # alive / banned / restricted / cooldown
    daily_sent: int = 0
    daily_quota: int = 20
    persona: Optional[dict] = None
    last_active: str = ""


@dataclass
class DayPlan:
    """日计划"""
    date: str
    client: str
    batch: str = "P1"
    total_target: int = 0
    accounts_used: int = 0
    tasks: list[CommentTask] = field(default_factory=list)
    status: str = "planned"  # planned / running / completed / partial
