"""AdsPower 本地 API 封装 — 浏览器启停、环境管理"""

from __future__ import annotations

import os
import time
import logging
import threading
import requests

from .config import ADS_API_KEY, ADS_API_URL

log = logging.getLogger("adspower")
if not log.handlers:
    log.setLevel(logging.INFO)
    _fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    _ch = logging.StreamHandler()
    _ch.setFormatter(_fmt)
    log.addHandler(_ch)

api_lock = threading.RLock()
_last_call = [0.0]
_MIN_INTERVAL = 2.0  # 最小间隔 2 秒（多并发时避免 AdsPower 过载）


def _throttle():
    with api_lock:
        now = time.time()
        elapsed = now - _last_call[0]
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        _last_call[0] = time.time()


def ads_api():
    return os.environ.get("ADS_API_URL", ADS_API_URL)


def ads_headers():
    key = os.environ.get("ADS_API_KEY", ADS_API_KEY)
    return {"Authorization": f"Bearer {key}"} if key else {}


def _ads_request(method, url, max_retries=3, **kwargs):
    kwargs.setdefault("headers", ads_headers())
    kwargs.setdefault("timeout", 30)

    for attempt in range(max_retries):
        _throttle()
        try:
            if method == "GET":
                r = requests.get(url, **kwargs)
            else:
                r = requests.post(url, **kwargs)
            r.raise_for_status()
            data = r.json()

            if data.get("code") == -1 and "Too many" in data.get("msg", ""):
                wait = 2 * (2 ** attempt)
                log.warning(f"AdsPower 限流，{wait}s 后重试 ({attempt+1}/{max_retries})")
                time.sleep(wait)
                continue

            return data
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 * (attempt + 1))

    return {"code": -1, "msg": "max retries exceeded"}


def open_browser(user_id, headless=False):
    """打开 AdsPower 浏览器，返回 (ws_url, driver_path)"""
    url = f"{ads_api()}/api/v1/browser/start"
    params = {"user_id": user_id}
    if headless:
        params["headless"] = 1

    data = _ads_request("GET", url, params=params, timeout=60)
    if data["code"] != 0:
        raise RuntimeError(f"打开浏览器失败: {data['msg']}")
    ws = data["data"]["ws"]["selenium"]
    driver_path = data["data"]["webdriver"]
    log.info(f"浏览器已打开: user_id={user_id}")
    return ws, driver_path


def connect_driver(ws_url, driver_path):
    """连接 AdsPower 已打开的浏览器"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    opts = Options()
    opts.add_experimental_option("debuggerAddress", ws_url)
    service = Service(executable_path=driver_path)
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(60)
    return driver


def close_browser(user_id):
    """关闭 AdsPower 浏览器"""
    try:
        url = f"{ads_api()}/api/v1/browser/stop"
        data = _ads_request("GET", url, params={"user_id": user_id}, timeout=15)
        if data.get("code") == 0:
            log.info(f"浏览器已关闭: user_id={user_id}")
        elif "not open" in data.get("msg", "").lower():
            log.debug(f"浏览器已处于关闭状态: user_id={user_id}")
        else:
            log.warning(f"关闭浏览器异常: {data.get('msg')}")
    except Exception as e:
        log.warning(f"关闭浏览器异常: {e}")
