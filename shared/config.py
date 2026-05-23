"""Facebook 评论截流系统 — 配置加载"""

import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / "config" / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

ADS_API_KEY = os.environ.get("ADS_API_KEY", "")
ADS_API_URL = os.environ.get("ADS_API_URL", "http://127.0.0.1:50325")
DOUBAO_API_KEY = os.environ.get("DOUBAO_API_KEY", "")
