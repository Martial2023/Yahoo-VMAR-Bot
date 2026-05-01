from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel

from botvmar.adapters.registry import known_platforms
from botvmar.config import runtime
from botvmar.config.env import API_TOKEN
from botvmar.config.platforms import load_enabled
from botvmar.state import (
    queue_manual_trigger,
    shutdown_event,
    trigger_event,
)
from botvmar.utils.logger import get_logger

logger = get_logger("api")

app = FastAPI(title="BotVMAR Control API", version="0.3.0")


def _require_token(authorization: str | None = Header(default=None)) -> None:
    if not API_TOKEN:
        raise HTTPException(status_code=500, detail="API_TOKEN not configured on server")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
    token = authorization[len("Bearer "):].strip()
    if token != API_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


class PlatformStatus(BaseModel):
    platform: str
    display_name: str
    enabled: bool
    mode: str
    schedule_slots: list[str]


class StatusResponse(BaseModel):
    bot_enabled: bool
    mode: str
    ticker: str
    trigger_pending: bool
    shutdown_requested: bool
    enabled_platforms: list[PlatformStatus]
    known_platforms: list[str]


class SimpleResponse(BaseModel):
    ok: bool
    detail: str | None = None


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "message": "BotVMAR API is running: multiplatform",
    }


@app.get("/status", response_model=StatusResponse, dependencies=[Depends(_require_token)])
async def get_status() -> StatusResponse:
    s = await runtime.get()
    platforms = await load_enabled()
    return StatusResponse(
        bot_enabled=s.bot_enabled,
        mode=s.mode,
        ticker=s.ticker,
        trigger_pending=trigger_event.is_set(),
        shutdown_requested=shutdown_event.is_set(),
        enabled_platforms=[
            PlatformStatus(
                platform=p.platform,
                display_name=p.display_name,
                enabled=p.enabled,
                mode=p.mode,
                schedule_slots=p.schedule_slots,
            )
            for p in platforms
        ],
        known_platforms=known_platforms(),
    )


@app.post("/trigger-cycle", response_model=SimpleResponse, dependencies=[Depends(_require_token)])
async def trigger_cycle() -> SimpleResponse:
    """Wake the worker to run a cycle for ALL enabled platforms immediately."""
    await queue_manual_trigger(None)
    logger.info("Manual cycle trigger queued via API (all platforms)")
    return SimpleResponse(ok=True, detail="trigger queued (all platforms)")


@app.post(
    "/trigger-cycle/{platform}",
    response_model=SimpleResponse,
    dependencies=[Depends(_require_token)],
)
async def trigger_cycle_for_platform(platform: str) -> SimpleResponse:
    """Wake the worker to run a cycle for a single platform.

    The platform must be a known adapter name (`yahoo_finance`, `reddit`, ...).
    Whether it actually runs still depends on `platform_settings.enabled`.
    """
    platform = platform.strip().lower()
    if platform not in known_platforms():
        raise HTTPException(
            status_code=400,
            detail=f"Unknown platform '{platform}'. Known: {known_platforms()}",
        )
    await queue_manual_trigger(platform)
    logger.info("Manual cycle trigger queued via API for platform=%s", platform)
    return SimpleResponse(ok=True, detail=f"trigger queued for {platform}")


@app.post("/reload-config", response_model=SimpleResponse, dependencies=[Depends(_require_token)])
async def reload_config() -> SimpleResponse:
    s = await runtime.load()
    return SimpleResponse(ok=True, detail=f"reloaded — mode={s.mode} enabled={s.bot_enabled}")


@app.post("/stop", response_model=SimpleResponse, dependencies=[Depends(_require_token)])
async def stop() -> SimpleResponse:
    shutdown_event.set()
    trigger_event.set()  # wake worker so it sees shutdown
    logger.warning("Shutdown requested via API")
    return SimpleResponse(ok=True, detail="shutdown requested")
