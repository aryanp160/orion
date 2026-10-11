from decimal import Decimal

import pytest

from packages.domain.enums import OrderSide, OrderType
from packages.domain.models import OrderRequest
from services.execution.router import ExecutionRouter


@pytest.mark.asyncio
async def test_router_generates_quote():
    router = ExecutionRouter()
    order = OrderRequest(
        symbol="ETH-PERP",
        side=OrderSide.BUY,
        notional_usd=Decimal("25000.0"),
        order_type=OrderType.MARKET,
        max_slippage_bps=Decimal("20.0"),
    )

    quote = await router.generate_quote(order)
    assert quote.quote_id.startswith("quo_")
    assert quote.blended_vwap > Decimal("0")
    assert quote.blended_breakdown.total_cost_bps > Decimal("0")
    assert "decision" in quote.explanation
    assert len(quote.candidates) > 0


@pytest.mark.asyncio
async def test_router_risk_block():
    router = ExecutionRouter()
    # Trigger risk block via extreme notional
    order = OrderRequest(
        symbol="ETH-PERP",
        side=OrderSide.BUY,
        notional_usd=Decimal("500000.0"),  # Breaches $250k limit
    )

    quote = await router.generate_quote(order)
    assert quote.explanation["decision"] == "NO_ELIGIBLE_ROUTE"
    assert "exceeds limit" in quote.explanation["reason"]
