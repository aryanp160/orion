from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import PaperFillDB, PaperOrderDB
from packages.domain.enums import VenueId
from packages.domain.models import (
    ExecutionReport,
    OrderRequest,
    PaperAccount,
    PaperPosition,
)
from services.execution.paper_trading import paper_trading_engine

router = APIRouter(prefix="/api/v1/paper", tags=["Paper Trading"])


class PaperOrderSubmission(BaseModel):
    order: OrderRequest
    venue_id: VenueId = VenueId.HYPERLIQUID


@router.post("/orders", response_model=ExecutionReport)
async def submit_paper_order(
    payload: PaperOrderSubmission, db: AsyncSession = Depends(get_db)
) -> ExecutionReport:
    return await paper_trading_engine.submit_paper_order(
        db=db,
        order=payload.order,
        venue_id=payload.venue_id,
    )


@router.get("/orders")
async def list_paper_orders(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    query = select(PaperOrderDB).order_by(desc(PaperOrderDB.created_at)).limit(limit)
    if status:
        query = query.where(PaperOrderDB.status == status.upper())

    result = await db.execute(query)
    orders = result.scalars().all()
    return [
        {
            "order_id": o.order_id,
            "client_order_id": o.client_order_id,
            "symbol": o.symbol,
            "side": o.side,
            "order_type": o.order_type,
            "requested_notional": o.requested_notional,
            "requested_quantity": o.requested_quantity,
            "filled_quantity": o.filled_quantity,
            "filled_notional": o.filled_notional,
            "remaining_quantity": o.remaining_quantity,
            "avg_fill_price": o.avg_fill_price,
            "total_fee_usd": o.total_fee_usd,
            "slippage_bps": o.slippage_bps,
            "status": o.status,
            "rejection_reason": o.rejection_reason,
            "created_at": o.created_at,
            "updated_at": o.updated_at,
        }
        for o in orders
    ]


@router.get("/orders/{order_id}")
async def get_paper_order(order_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    res = await db.execute(select(PaperOrderDB).where(PaperOrderDB.order_id == order_id))
    o = res.scalar_one_or_none()
    if not o:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    return {
        "order_id": o.order_id,
        "client_order_id": o.client_order_id,
        "symbol": o.symbol,
        "side": o.side,
        "order_type": o.order_type,
        "requested_notional": o.requested_notional,
        "requested_quantity": o.requested_quantity,
        "filled_quantity": o.filled_quantity,
        "filled_notional": o.filled_notional,
        "remaining_quantity": o.remaining_quantity,
        "avg_fill_price": o.avg_fill_price,
        "total_fee_usd": o.total_fee_usd,
        "slippage_bps": o.slippage_bps,
        "status": o.status,
        "rejection_reason": o.rejection_reason,
        "created_at": o.created_at,
    }


@router.post("/orders/{order_id}/cancel")
async def cancel_paper_order(order_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    success = await paper_trading_engine.cancel_paper_order(db, order_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Could not cancel order {order_id} (may already be filled or cancelled)",
        )
    return {"order_id": order_id, "status": "CANCELLED", "message": "Order successfully cancelled"}


@router.get("/account", response_model=PaperAccount)
async def get_paper_account(db: AsyncSession = Depends(get_db)) -> PaperAccount:
    return await paper_trading_engine.get_account_summary(db)


@router.get("/positions", response_model=List[PaperPosition])
async def list_paper_positions(db: AsyncSession = Depends(get_db)) -> List[PaperPosition]:
    summary = await paper_trading_engine.get_account_summary(db)
    return summary.positions


@router.post("/reset", response_model=PaperAccount)
async def reset_paper_account(db: AsyncSession = Depends(get_db)) -> PaperAccount:
    return await paper_trading_engine.reset_paper_account(db)


@router.get("/fills")
async def list_paper_fills(
    limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    query = select(PaperFillDB).order_by(desc(PaperFillDB.created_at)).limit(limit)
    res = await db.execute(query)
    fills = res.scalars().all()
    return [
        {
            "fill_id": f.fill_id,
            "order_id": f.order_id,
            "venue_id": f.venue_id,
            "symbol": f.symbol,
            "side": f.side,
            "fill_price": f.fill_price,
            "fill_quantity": f.fill_quantity,
            "fill_notional": f.fill_notional,
            "fee_usd": f.fee_usd,
            "fee_bps": f.fee_bps,
            "role": f.role,
            "created_at": f.created_at,
        }
        for f in fills
    ]
