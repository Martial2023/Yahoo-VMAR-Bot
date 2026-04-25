"""AI generator via OpenRouter — replies and proactive posts about VMAR.

Prompts and model parameters come from `botvmar.config.runtime` (Postgres),
so they can be tuned from the admin dashboard without redeploying.
"""

from __future__ import annotations

import asyncio

from openai import AsyncOpenAI

from botvmar.config import runtime
from botvmar.config.env import OPENROUTER_KEY
from botvmar.utils.logger import get_logger

logger = get_logger("ai")

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not OPENROUTER_KEY:
            raise ValueError("OPENROUTER_KEY is not set in .env")
        _client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_KEY,
        )
    return _client


async def _call_ai(system: str, user_message: str, max_retries: int = 3) -> str | None:
    client = _get_client()
    settings = await runtime.get()

    for attempt in range(1, max_retries + 1):
        try:
            response = await client.chat.completions.create(
                model=settings.ai_model,
                max_tokens=300,
                temperature=settings.ai_temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
            )
            text = (response.choices[0].message.content or "").strip()
            logger.info("AI response generated (%d chars, attempt %d, model %s)", len(text), attempt, settings.ai_model)
            return text
        except Exception as e:
            error_str = str(e)
            # Erreurs d'auth/permission : inutile de retry, c'est définitif.
            if any(code in error_str for code in ("401", "403", "User not found", "Invalid API")):
                logger.error("AI auth error — check OPENROUTER_KEY: %s", e)
                return None
            if "rate" in error_str.lower() or "429" in error_str:
                wait = 2 ** attempt * 5
                logger.warning("Rate limited (attempt %d/%d), waiting %ds: %s", attempt, max_retries, wait, e)
                await asyncio.sleep(wait)
            else:
                logger.error("API error (attempt %d/%d): %s", attempt, max_retries, e)
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)

    logger.error("All %d attempts to call AI failed", max_retries)
    return None


async def generate_reply(comment_text: str, comment_author: str) -> str | None:
    settings = await runtime.get()
    user_message = (
        f"Un utilisateur nommé '{comment_author}' a posté ce commentaire sur la page VMAR de Yahoo Finance :\n\n"
        f'"{comment_text}"\n\n'
        f"Génère une réponse naturelle à ce commentaire."
    )
    reply = await _call_ai(settings.reply_prompt, user_message)
    if reply:
        logger.info("Generated reply for comment by %s: %s...", comment_author, reply[:80])
    return reply


async def generate_post(context: str = "") -> str | None:
    settings = await runtime.get()
    user_message = "Génère un commentaire proactif pour la page communauté VMAR sur Yahoo Finance."
    if context:
        user_message += f"\n\nContexte additionnel : {context}"

    post = await _call_ai(settings.post_prompt, user_message)
    if post:
        logger.info("Generated proactive post: %s...", post[:80])
    return post
