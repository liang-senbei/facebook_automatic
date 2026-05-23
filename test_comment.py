"""Facebook 评论截流 — 单环境测试脚本

使用 AdsPower 环境 k1csqgqh 进行 Facebook 评论功能测试。

用法:
    python test_comment.py --post-url "https://www.facebook.com/xxx/posts/yyy" --text "测试评论"
    python test_comment.py --explore  # 仅打开浏览器探索 Facebook 页面结构
"""

from __future__ import annotations

import sys
import time
import argparse
import logging
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))

from shared.browser_context import browser_session
from comments.actions.navigate_post import navigate_to_post
from comments.actions.find_comment_box import find_comment_box
from comments.actions.type_comment import type_comment, type_comment_fast
from comments.actions.submit_comment import submit_comment
from comments.actions.detect_ban import detect_ban
from comments.actions.random_browse import warmup_browse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("fb.test")

# AdsPower 测试环境
TEST_ENV_UID = "k1csqgqh"


def test_explore():
    """探索模式：打开浏览器导航到 Facebook，手动观察页面结构"""
    log.info(f"探索模式：打开环境 {TEST_ENV_UID}")

    with browser_session(TEST_ENV_UID, navigate_fb=True) as driver:
        log.info(f"当前 URL: {driver.current_url}")

        # 检测登录状态
        ban = detect_ban(driver)
        if ban.is_banned:
            log.error(f"账号异常: {ban.status} - {ban.detail}")
            return

        log.info("Facebook 页面已加载，账号状态正常")
        log.info("浏览器将保持打开 300 秒，请手动观察页面结构...")

        # 保持浏览器打开一段时间供观察
        time.sleep(300)


def test_warmup():
    """测试暖场浏览行为"""
    log.info(f"暖场测试：环境 {TEST_ENV_UID}")

    with browser_session(TEST_ENV_UID, navigate_fb=True) as driver:
        ban = detect_ban(driver)
        if ban.is_banned:
            log.error(f"账号异常: {ban.status}")
            return

        log.info("开始暖场浏览（60秒）...")
        warmup_browse(driver, duration_sec=60)
        log.info("暖场完成")


def test_find_comment_box(post_url: str):
    """测试定位评论框"""
    log.info(f"评论框定位测试：{post_url}")

    with browser_session(TEST_ENV_UID, navigate_fb=True) as driver:
        # 导航到帖子
        if not navigate_to_post(driver, post_url):
            log.error("导航到帖子失败")
            return

        log.info("帖子页面已加载")
        time.sleep(2)

        # 定位评论框
        found = find_comment_box(driver)
        if found:
            log.info("评论框定位成功！")
        else:
            log.error("评论框定位失败")

        # 保持打开供观察
        time.sleep(30)


def test_full_comment(post_url: str, comment_text: str):
    """完整评论流程测试"""
    log.info(f"完整评论测试：{post_url}")
    log.info(f"评论内容：{comment_text}")

    with browser_session(TEST_ENV_UID, navigate_fb=True) as driver:
        ban = detect_ban(driver)
        if ban.is_banned:
            log.error(f"账号异常: {ban.status}")
            return

        # 简短暖场
        log.info("暖场中...")
        warmup_browse(driver, duration_sec=30)

        # 导航到帖子
        log.info("导航到帖子...")
        if not navigate_to_post(driver, post_url):
            log.error("导航失败")
            return

        time.sleep(3)

        # 定位评论框
        log.info("定位评论框...")
        if not find_comment_box(driver):
            log.error("评论框定位失败")
            time.sleep(30)
            return

        time.sleep(1)

        # 输入评论
        log.info("输入评论...")
        typed = type_comment(driver, comment_text)
        if not typed:
            log.warning("逐字输入失败，尝试快速输入...")
            typed = type_comment_fast(driver, comment_text)
        if not typed:
            log.error("输入评论失败")
            time.sleep(30)
            return

        time.sleep(2)

        # 发送评论
        log.info("发送评论...")
        sent = submit_comment(driver)
        if sent:
            log.info("评论发送成功！")
        else:
            log.warning("Enter 发送失败，等待手动确认...")

        # 保持打开供观察
        time.sleep(30)


def main():
    parser = argparse.ArgumentParser(description="Facebook 评论功能测试")
    parser.add_argument("--explore", action="store_true", help="探索模式（仅打开浏览器）")
    parser.add_argument("--warmup", action="store_true", help="测试暖场浏览")
    parser.add_argument("--find-box", action="store_true", help="测试定位评论框")
    parser.add_argument("--post-url", type=str, help="帖子 URL")
    parser.add_argument("--text", type=str, default="Great post! 👍", help="评论内容")
    parser.add_argument("--env", type=str, default=TEST_ENV_UID, help="AdsPower 环境 UID")
    args = parser.parse_args()

    global TEST_ENV_UID
    TEST_ENV_UID = args.env

    if args.explore:
        test_explore()
    elif args.warmup:
        test_warmup()
    elif args.find_box:
        if not args.post_url:
            log.error("需要 --post-url 参数")
            return
        test_find_comment_box(args.post_url)
    elif args.post_url:
        test_full_comment(args.post_url, args.text)
    else:
        # 默认探索模式
        test_explore()


if __name__ == "__main__":
    main()
