"""评论生成 — 异步并发调用 LLM 生成评论"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import aiohttp

from comments import config

log = logging.getLogger("fb.generator")

_model_index = 0


def _next_model() -> str:
    """轮换模型"""
    global _model_index
    if config.COMMENT_LLM_ROTATE:
        model = config.COMMENT_LLM_MODELS[_model_index % len(config.COMMENT_LLM_MODELS)]
        _model_index += 1
        return model
    return config.COMMENT_LLM_MODEL


async def _generate_one(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    post_info: dict,
    brand_context: str,
    persona: Optional[dict] = None,
    api_key: str = "",
) -> dict:
    """生成单条评论"""
    async with semaphore:
        model = _next_model()
        prompt = _build_prompt(post_info, brand_context, persona)

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a social media user writing natural comments on Facebook posts. Write only the comment text, nothing else."},
                {"role": "user", "content": prompt},
            ],
            "temperature": config.COMMENT_LLM_TEMPERATURE,
            "max_tokens": config.COMMENT_LLM_MAX_TOKENS,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        for attempt in range(config.MAX_GENERATE_RETRIES + 1):
            try:
                async with session.post(
                    config.COMMENT_LLM_BASE_URL,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 429:
                        await asyncio.sleep(2 * (attempt + 1))
                        continue
                    data = await resp.json()
                    text = data["choices"][0]["message"]["content"].strip()
                    # 清理引号包裹
                    if text.startswith('"') and text.endswith('"'):
                        text = text[1:-1]
                    return {
                        "post_url": post_info["post_url"],
                        "comment_text": text,
                        "model": model,
                        "status": "generated",
                    }
            except Exception as e:
                if attempt == config.MAX_GENERATE_RETRIES:
                    log.warning(f"生成失败: {post_info.get('post_url', '')[:50]} - {e}")
                    return {
                        "post_url": post_info["post_url"],
                        "comment_text": "",
                        "model": model,
                        "status": "failed",
                        "error": str(e),
                    }
                await asyncio.sleep(1)

    return {"post_url": post_info.get("post_url", ""), "comment_text": "", "status": "failed"}


def _build_prompt(post_info: dict, brand_context: str, persona: Optional[dict] = None) -> str:
    """构建评论生成 prompt"""
    parts = []

    parts.append(f"Post URL: {post_info.get('post_url', '')}")
    if post_info.get("content_preview"):
        parts.append(f"Post content: {post_info['content_preview'][:300]}")
    if post_info.get("author"):
        parts.append(f"Post author: {post_info['author']}")
    if post_info.get("comment_angle"):
        parts.append(f"Comment angle: {post_info['comment_angle']}")

    parts.append(f"\nBrand context: {brand_context}")

    if persona:
        parts.append(f"\nYour persona:")
        if persona.get("identity"):
            parts.append(f"- Identity: {persona['identity']}")
        if persona.get("tone"):
            parts.append(f"- Tone: {persona['tone']}")
        if persona.get("interests"):
            parts.append(f"- Interests: {', '.join(persona['interests'][:5])}")
        if persona.get("emoji_usage"):
            parts.append(f"- Emoji usage: {persona['emoji_usage']}")
        if persona.get("slang_style"):
            parts.append(f"- Slang style: {', '.join(persona['slang_style'][:3])}")

    parts.append("\nWrite a natural, engaging comment (1-3 sentences). Be conversational and authentic.")
    parts.append("Include the brand link naturally if appropriate.")

    return "\n".join(parts)


async def generate_batch(
    tasks: list[dict],
    brand_context: str,
    api_key: str,
    concurrency: int = 50,
    persona: Optional[dict] = None,
) -> list[dict]:
    """批量异步生成评论

    Args:
        tasks: [{"post_url": "...", "content_preview": "...", "author": "...", "comment_angle": "..."}, ...]
        brand_context: 品牌上下文描述
        api_key: LLM API Key
        concurrency: 并发数
        persona: 可选的人设信息

    Returns:
        [{"post_url": "...", "comment_text": "...", "status": "generated/failed"}, ...]
    """
    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async with aiohttp.ClientSession() as session:
        coros = [
            _generate_one(session, semaphore, task, brand_context, persona, api_key)
            for task in tasks
        ]
        results = await asyncio.gather(*coros)

    generated = [r for r in results if r["status"] == "generated"]
    failed = [r for r in results if r["status"] == "failed"]
    log.info(f"生成完成: 成功={len(generated)}, 失败={len(failed)}, 总计={len(results)}")

    return list(results)


def generate_comments(
    tasks: list[dict],
    brand_context: str,
    api_key: str,
    concurrency: int = 50,
    persona: Optional[dict] = None,
) -> list[dict]:
    """同步入口 — 包装 asyncio"""
    return asyncio.run(generate_batch(tasks, brand_context, api_key, concurrency, persona))
