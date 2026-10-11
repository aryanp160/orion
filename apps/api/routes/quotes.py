import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import AuditEventDB, RouteQuoteDB
from packages.domain.models import OrderRequest, RouteQuote
from services.execution.router import execution_router

router = APIRouter(prefix="/api/v1", tags=["Quotes & Routing"])


@router.post("/quotes", response_model=RouteQuote)
async def create_quote(order: OrderRequest, db: AsyncSession = Depends(get_db)) -> RouteQuote:
    quote = await execution_router.generate_quote(order)

    # Persist quote to DB
    db_quote = RouteQuoteDB(
        quote_id=quote.quote_id,
        symbol=order.symbol,
        side=order.side.value,
        notional_usd=float(order.notional_usd),
        recommended_venue=quote.recommended_venue.value,
        blended_vwap=float(quote.blended_vwap),
        total_cost_bps=float(quote.blended_breakdown.total_cost_bps),
        total_cost_usd=float(quote.blended_breakdown.total_cost_usd),
        payload_json=quote.model_dump_json(),
        created_at=quote.quote_timestamp,
        expires_at=quote.expires_at,
    )
    db.add(db_quote)

    audit = AuditEventDB(
        event_id=f"aud_quo_{quote.quote_id[4:]}",
        actor="ROUTER",
        event_type="QUOTE_GENERATED",
        correlation_id=quote.quote_id,
        entity_id=quote.quote_id,
        entity_type="QUOTE",
        payload_json=json.dumps(
            {
                "symbol": order.symbol,
                "side": order.side.value,
                "notional": float(order.notional_usd),
                "venue": quote.recommended_venue.value,
                "is_split": quote.is_split_route,
                "cost_bps": float(quote.blended_breakdown.total_cost_bps),
            }
        ),
    )
    db.add(audit)

    await db.commit()
    return quote


@router.post("/routes/preview", response_model=RouteQuote)
async def preview_route(order: OrderRequest) -> RouteQuote:
    # Ephemeral preview without DB persistence
    return await execution_router.generate_quote(order)


@router.get("/quotes/{quote_id}", response_model=RouteQuote)
async def get_quote(quote_id: str, db: AsyncSession = Depends(get_db)) -> RouteQuote:
    res = await db.execute(select(RouteQuoteDB).where(RouteQuoteDB.quote_id == quote_id))
    db_quote = res.scalar_one_or_none()
    if not db_quote:
        raise HTTPException(status_code=404, detail=f"Quote {quote_id} not found")

    return RouteQuote.model_validate_json(db_quote.payload_json)
