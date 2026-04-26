from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel

from botvmar.config import runtime
from botvmar.config.env import API_TOKEN
from botvmar.state import shutdown_event, trigger_event
from botvmar.utils.logger import get_logger

logger = get_logger("api")

app = FastAPI(title="BotVMAR Control API", version="0.2.0")


def _require_token(authorization: str | None = Header(default=None)) -> None:
    if not API_TOKEN:
        raise HTTPException(status_code=500, detail="API_TOKEN not configured on server")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
    token = authorization[len("Bearer "):].strip()
    if token != API_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


class StatusResponse(BaseModel):
    bot_enabled: bool
    mode: str
    ticker: str
    trigger_pending: bool
    shutdown_requested: bool


class SimpleResponse(BaseModel):
    ok: bool
    detail: str | None = None


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "message": "BotVMAR API is running",
    }


@app.get("/status", response_model=StatusResponse, dependencies=[Depends(_require_token)])
async def get_status() -> StatusResponse:
    s = await runtime.get()
    return StatusResponse(
        bot_enabled=s.bot_enabled,
        mode=s.mode,
        ticker=s.ticker,
        trigger_pending=trigger_event.is_set(),
        shutdown_requested=shutdown_event.is_set(),
    )


@app.post("/trigger-cycle", response_model=SimpleResponse, dependencies=[Depends(_require_token)])
async def trigger_cycle() -> SimpleResponse:
    """Wake the worker to run a cycle immediately (cancels current sleep)."""
    trigger_event.set()
    logger.info("Manual cycle trigger queued via API")
    return SimpleResponse(ok=True, detail="trigger queued")


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
