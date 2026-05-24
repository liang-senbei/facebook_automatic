"""执行日志 — 按天记录每条评论的执行结果"""

from __future__ import annotations

import json
import time
from pathlib import Path


class ExecutionLog:
    """JSONL 格式的执行日志（按天轮转）"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _log_file(self) -> Path:
        date = time.strftime("%Y-%m-%d")
        return self.data_dir / f"log_{date}.jsonl"

    def append(self, record: dict):
        record.setdefault("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))
        with open(self._log_file(), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def log_comment(self, env_uid: str, post_url: str, status: str,
                    comment_text: str = "", error: str = "", duration: float = 0):
        self.append({
            "type": "comment",
            "env_uid": env_uid,
            "post_url": post_url,
            "status": status,
            "comment_text": comment_text,
            "error": error,
            "duration_sec": round(duration, 1),
        })

    def log_session(self, env_uid: str, sent: int, failed: int,
                    banned: bool, duration_min: float):
        self.append({
            "type": "session",
            "env_uid": env_uid,
            "sent": sent,
            "failed": failed,
            "banned": banned,
            "duration_min": round(duration_min, 1),
        })

    def read_today(self) -> list[dict]:
        log_file = self._log_file()
        if not log_file.exists():
            return []
        records = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return records
