"""状态存储 — 管理评论系统的运行状态"""

from __future__ import annotations

import json
import time
import threading
from pathlib import Path
from typing import Optional

_state_lock = threading.Lock()


class StateStore:
    """评论系统状态管理器"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = data_dir / "state.json"
        self._state = self._load()

    def _load(self) -> dict:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return self._default_state()
        return self._default_state()

    def _default_state(self) -> dict:
        return {
            "posts": {},
            "accounts": {},
            "batches": {},
            "stats": {
                "total_sent": 0,
                "total_failed": 0,
                "total_banned": 0,
            },
        }

    def _save(self):
        tmp = self.state_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)
        tmp.replace(self.state_file)

    def get_post_status(self, post_url: str) -> dict:
        with _state_lock:
            return self._state["posts"].get(post_url, {})

    def mark_post_done(self, post_url: str):
        with _state_lock:
            if post_url not in self._state["posts"]:
                self._state["posts"][post_url] = {}
            self._state["posts"][post_url]["status"] = "done"
            self._state["posts"][post_url]["done_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self._save()

    def record_comment(self, env_uid: str, post_url: str, status: str):
        with _state_lock:
            # 更新账号统计
            if env_uid not in self._state["accounts"]:
                self._state["accounts"][env_uid] = {"sent": 0, "failed": 0, "banned": False}
            acct = self._state["accounts"][env_uid]
            if status in ("sent", "unverified"):
                acct["sent"] += 1
                self._state["stats"]["total_sent"] += 1
            elif status == "banned":
                acct["banned"] = True
                self._state["stats"]["total_banned"] += 1
            else:
                acct["failed"] += 1
                self._state["stats"]["total_failed"] += 1

            # 更新帖子统计
            if post_url not in self._state["posts"]:
                self._state["posts"][post_url] = {"completed": 0, "pending": 0}
            self._state["posts"][post_url]["completed"] = \
                self._state["posts"][post_url].get("completed", 0) + 1

            self._save()

    def mark_account_banned(self, env_uid: str, ban_type: str = ""):
        with _state_lock:
            if env_uid not in self._state["accounts"]:
                self._state["accounts"][env_uid] = {"sent": 0, "failed": 0, "banned": False}
            self._state["accounts"][env_uid]["banned"] = True
            self._state["accounts"][env_uid]["ban_type"] = ban_type
            self._save()

    def is_account_banned(self, env_uid: str) -> bool:
        with _state_lock:
            acct = self._state["accounts"].get(env_uid, {})
            return acct.get("banned", False)

    def get_stats(self) -> dict:
        with _state_lock:
            return dict(self._state["stats"])

    def get_account_stats(self, env_uid: str) -> dict:
        with _state_lock:
            return dict(self._state["accounts"].get(env_uid, {}))
