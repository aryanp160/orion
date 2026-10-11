from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel

from apps.api.config import settings
from services.execution.risk_engine import risk_engine

router = APIRouter(prefix="/api/v1/risk", tags=["Risk Controls"])


class KillSwitchPayload(BaseModel):
    active: bool


@router.get("/status")
async def get_risk_status() -> Dict[str, Any]:
    return {
        "kill_switch_active": risk_engine.is_kill_switch_active,
        "limits": {
            "max_order_notional_usd": settings.ORION_MAX_ORDER_NOTIONAL,
            "max_position_exposure_usd": settings.ORION_MAX_POSITION_EXPOSURE,
            "max_permitted_slippage_bps": settings.ORION_MAX_PERMITTED_SLIPPAGE_BPS,
            "max_fee_budget_bps": settings.ORION_MAX_FEE_BUDGET_BPS,
            "max_concurrent_orders": settings.ORION_MAX_CONCURRENT_ORDERS,
            "price_collar_bps": settings.ORION_PRICE_COLLAR_BPS,
            "staleness_threshold_sec": settings.ORION_STALENESS_THRESHOLD_SEC,
        },
        "status": "HALTED" if risk_engine.is_kill_switch_active else "OPERATIONAL",
    }


@router.post("/kill-switch")
async def toggle_kill_switch(payload: KillSwitchPayload) -> Dict[str, Any]:
    risk_engine.set_kill_switch(payload.active)
    return {
        "kill_switch_active": risk_engine.is_kill_switch_active,
        "status": "HALTED" if risk_engine.is_kill_switch_active else "OPERATIONAL",
        "message": f"Kill switch successfully set to {payload.active}",
    }
