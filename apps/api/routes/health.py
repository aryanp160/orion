from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


router = APIRouter(tags=["System"])


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    execution_mode: str
    live_trading_enabled: bool


@router.get("/health", response_model=HealthResponse)
async def get_health():
    return HealthResponse(
        status="HEALTHY",
        version="0.1.0",
        timestamp=utc_now(),
        execution_mode="paper",
        live_trading_enabled=False,
    )


@router.get("/ready", response_model=HealthResponse)
async def get_ready():
    return HealthResponse(
        status="READY",
        version="0.1.0",
        timestamp=utc_now(),
        execution_mode="paper",
        live_trading_enabled=False,
    )
