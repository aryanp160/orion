from datetime import datetime, timezone
from decimal import Decimal

from packages.domain.enums import OrderSide, RiskOutcome, VenueId
from packages.domain.models import (
    MarketDataHealth,
    OrderRequest,
)
from services.execution.risk_engine import RiskEngine


def test_risk_engine_normal_pass():
    engine = RiskEngine()
    order = OrderRequest(
        symbol="ETH-PERP",
        side=OrderSide.BUY,
        notional_usd=Decimal("50000.0"),
        client_order_id="unique_ord_1",
    )
    eval_res = engine.evaluate_order(order)
    assert eval_res.outcome == RiskOutcome.PASS
    assert len(eval_res.flags) == 0


def test_risk_engine_max_notional_block():
    engine = RiskEngine()
    order = OrderRequest(
        symbol="ETH-PERP",
        side=OrderSide.BUY,
        notional_usd=Decimal("300000.0"),  # Exceeds $250k default limit
    )
    eval_res = engine.evaluate_order(order)
    assert eval_res.outcome == RiskOutcome.BLOCK
    assert "MAX_ORDER_NOTIONAL_EXCEEDED" in eval_res.flags


def test_risk_engine_kill_switch_block():
    engine = RiskEngine()
    engine.set_kill_switch(True)
    order = OrderRequest(
        symbol="ETH-PERP",
        side=OrderSide.BUY,
        notional_usd=Decimal("10000.0"),
    )
    eval_res = engine.evaluate_order(order)
    assert eval_res.outcome == RiskOutcome.BLOCK
    assert "KILL_SWITCH_ACTIVE" in eval_res.flags


def test_risk_engine_idempotency_block():
    engine = RiskEngine()
    order1 = OrderRequest(
        symbol="ETH-PERP",
        side=OrderSide.BUY,
        notional_usd=Decimal("10000.0"),
        client_order_id="dup_test_123",
    )
    eval1 = engine.evaluate_order(order1)
    assert eval1.outcome == RiskOutcome.PASS

    # Immediate second order with identical client_order_id
    eval2 = engine.evaluate_order(order1)
    assert eval2.outcome == RiskOutcome.BLOCK
    assert "DUPLICATE_CLIENT_ORDER_ID" in eval2.flags


def test_risk_engine_stale_data_block():
    engine = RiskEngine()
    stale_health = MarketDataHealth(
        venue_id=VenueId.HYPERLIQUID,
        symbol="ETH-PERP",
        is_healthy=False,
        latency_ms=120.0,
        last_update_ts=datetime.now(timezone.utc),
        staleness_sec=45.0,  # Stale > 15s
        status_message="FEED_STALE",
    )
    order = OrderRequest(
        symbol="ETH-PERP",
        side=OrderSide.BUY,
        notional_usd=Decimal("10000.0"),
    )
    eval_res = engine.evaluate_order(order, health=stale_health)
    assert eval_res.outcome == RiskOutcome.BLOCK
    assert "MARKET_DATA_STALE_OR_UNHEALTHY" in eval_res.flags
