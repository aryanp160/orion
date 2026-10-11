from datetime import datetime, timezone
from decimal import Decimal

from packages.domain.enums import NetworkId, OrderSide, VenueId, VenueType
from packages.domain.models import (
    FundingObservation,
    Instrument,
    OrderBook,
    OrderBookLevel,
    OrderRequest,
    VenueCapabilities,
)
from services.execution.cost_engine import ExecutionCostEngine


def get_test_book():
    return OrderBook(
        venue_id=VenueId.HYPERLIQUID,
        symbol="ETH-PERP",
        bids=[
            OrderBookLevel(price=Decimal("2500.00"), size=Decimal("10.0")),  # $25,000
            OrderBookLevel(price=Decimal("2498.00"), size=Decimal("20.0")),  # $49,960
            OrderBookLevel(price=Decimal("2495.00"), size=Decimal("40.0")),  # $99,800
        ],
        asks=[
            OrderBookLevel(price=Decimal("2501.00"), size=Decimal("10.0")),  # $25,010
            OrderBookLevel(price=Decimal("2503.00"), size=Decimal("20.0")),  # $50,060
            OrderBookLevel(price=Decimal("2506.00"), size=Decimal("40.0")),  # $100,240
        ],
        timestamp=datetime.now(timezone.utc),
    )


def get_test_instrument():
    return Instrument(
        symbol="ETH-PERP",
        venue_id=VenueId.HYPERLIQUID,
        min_order_size=Decimal("0.001"),
        maker_fee_bps=Decimal("1.0"),
        taker_fee_bps=Decimal("3.5"),
    )


def get_test_capabilities():
    return VenueCapabilities(
        venue_id=VenueId.HYPERLIQUID,
        venue_type=VenueType.CLOB,
        network=NetworkId.HYPERLIQUID_L1,
        has_order_book_l2=True,
        has_funding_rates=True,
        has_open_interest=True,
        supports_market_orders=True,
        supports_limit_orders=True,
        supports_split_routing=True,
        is_on_chain=False,
        gas_fee_required=False,
        fee_tier_configurable=True,
        description="Hyperliquid Test",
    )


def test_vwap_walk_single_level():
    book = get_test_book()
    # Order for $10,000 (fits in first ask level @ 2501.00)
    vwap, notional, qty, fillable = ExecutionCostEngine.walk_order_book(
        book=book,
        side=OrderSide.BUY,
        required_notional=Decimal("10000.0"),
        arrival_mid=Decimal("2500.50"),
    )
    assert vwap == Decimal("2501.00")
    assert fillable is True


def test_vwap_walk_multi_level():
    book = get_test_book()
    # Order for $50,000 (takes $25,010 @ 2501 and $24,990 @ 2503)
    vwap, notional, qty, fillable = ExecutionCostEngine.walk_order_book(
        book=book,
        side=OrderSide.BUY,
        required_notional=Decimal("50000.0"),
        arrival_mid=Decimal("2500.50"),
    )
    # Expected VWAP is between 2501 and 2503
    assert Decimal("2501.00") < vwap < Decimal("2503.00")
    assert fillable is True


def test_cost_breakdown_aggregation_and_funding_sign():
    book = get_test_book()
    inst = get_test_instrument()
    cap = get_test_capabilities()

    # Long order with positive funding (Long pays Short) -> Positive cost
    funding_positive = FundingObservation(
        venue_id=VenueId.HYPERLIQUID,
        symbol="ETH-PERP",
        funding_rate_bps=Decimal("2.0"),  # 2 bps per 8 hours
        timestamp=datetime.now(timezone.utc),
    )

    order_buy = OrderRequest(
        symbol="ETH-PERP",
        side=OrderSide.BUY,
        notional_usd=Decimal("50000.0"),
        holding_horizon_hours=Decimal("16.0"),  # 2x 8h period -> +4.0 bps funding cost
    )

    breakdown_buy = ExecutionCostEngine.calculate_cost_breakdown(
        order=order_buy,
        book=book,
        instrument=inst,
        capabilities=cap,
        funding=funding_positive,
    )

    assert breakdown_buy.funding_cost_bps == Decimal("4.00")
    assert breakdown_buy.total_cost_bps > Decimal("7.50")
    assert breakdown_buy.spread_cost_bps > Decimal("0.0")
    assert breakdown_buy.trading_fee_bps == Decimal("3.50")

    # Short order with positive funding (Short receives from Long) -> Negative cost (Credit)
    order_sell = OrderRequest(
        symbol="ETH-PERP",
        side=OrderSide.SELL,
        notional_usd=Decimal("50000.0"),
        holding_horizon_hours=Decimal("16.0"),
    )

    breakdown_sell = ExecutionCostEngine.calculate_cost_breakdown(
        order=order_sell,
        book=book,
        instrument=inst,
        capabilities=cap,
        funding=funding_positive,
    )

    assert breakdown_sell.funding_cost_bps == Decimal("-4.00")
    assert breakdown_sell.funding_cost_usd < Decimal("0.0")
