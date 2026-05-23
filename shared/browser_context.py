"""浏览器生命周期 Context Manager — 自动启动/连接/关闭 AdsPower 环境"""

import time
import logging
from contextlib import contextmanager

from .adspower import open_browser, connect_driver, close_browser, api_lock

log = logging.getLogger("browser_context")
if not log.handlers:
    log.setLevel(logging.INFO)
    _fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    _ch = logging.StreamHandler()
    _ch.setFormatter(_fmt)
    log.addHandler(_ch)


@contextmanager
def browser_session(
    user_id: str,
    *,
    use_api_lock: bool = False,
    page_load_timeout: int = 90,
    startup_wait: float = 3.0,
    navigate_fb: bool = False,
):
    """AdsPower 浏览器生命周期管理器（Facebook 版）。

    Args:
        user_id: AdsPower 环境 UID
        use_api_lock: 是否在 open/close 时持有 api_lock
        page_load_timeout: 页面加载超时（秒）
        startup_wait: 浏览器启动后等待时间（秒）
        navigate_fb: 启动后自动导航到 facebook.com
    """
    driver = None
    try:
        if use_api_lock:
            with api_lock:
                ws_url, driver_path = open_browser(user_id)
        else:
            ws_url, driver_path = open_browser(user_id)

        if not ws_url:
            raise RuntimeError(f"open_browser 返回空 ws_url: user_id={user_id}")

        time.sleep(startup_wait)

        driver = connect_driver(ws_url, driver_path)
        driver.set_page_load_timeout(page_load_timeout)

        # 设置窗口大小
        try:
            driver.set_window_size(1920, 1080)
        except Exception:
            pass

        # 关闭多余 tab
        _close_extra_tabs(driver)

        # 导航到 Facebook
        if navigate_fb:
            try:
                driver.get("https://www.facebook.com/")
            except Exception:
                pass
            _poll_page_ready(driver, timeout=60)

        log.info(f"浏览器会话就绪: user_id={user_id}")
        yield driver

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        try:
            if use_api_lock:
                with api_lock:
                    close_browser(user_id)
            else:
                close_browser(user_id)
        except Exception:
            pass


def _poll_page_ready(driver, timeout=60, interval=2):
    """轮询等待 Facebook 页面加载完成"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            url = driver.current_url or ""
            if "facebook.com" not in url:
                time.sleep(interval)
                continue
            text_len = driver.execute_script(
                "return (document.body && document.body.innerText) ? document.body.innerText.length : 0")
            if text_len and text_len > 50:
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def _close_extra_tabs(driver):
    """关闭多余 tab，只保留一个"""
    try:
        handles = driver.window_handles
        if len(handles) <= 1:
            return
        keep = handles[-1]
        for h in handles[:-1]:
            try:
                driver.switch_to.window(h)
                driver.close()
            except Exception:
                pass
        driver.switch_to.window(keep)
    except Exception:
        try:
            remaining = driver.window_handles
            if remaining:
                driver.switch_to.window(remaining[-1])
        except Exception:
            pass
