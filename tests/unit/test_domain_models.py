from datetime import datetime, timezone
from decimal import Decimal

from packages.domain.enums import OrderSide, OrderType, VenueId
from packages.domain.models import (
    OrderBook,
    OrderBookLevel,
    OrderRequest,
)


def test_order_book_mid_and_spread():
    book = OrderBook(
        venue_id=VenueId.HYPERLIQUID,
        symbol="ETH-PERP",
        bids=[
            OrderBookLevel(price=Decimal("2500.00"), size=Decimal("10.0")),
            OrderBookLevel(price=Decimal("2499.00"), size=Decimal("20.0")),
        ],
        asks=[
            OrderBookLevel(price=Decimal("2501.00"), size=Decimal("10.0")),
            OrderBookLevel(price=Decimal("2502.00"), size=Decimal("20.0")),
        ],
        timestamp=datetime.now(timezone.utc),
    )

    assert book.best_bid == Decimal("2500.00")
    assert book.best_ask == Decimal("2501.00")
    assert book.mid_price == Decimal("2500.50")
    # spread = (2501 - 2500) / 2500.5 * 10000 = 1 / 2500.5 * 10000 ~ 3.999 bps
    assert round(float(book.spread_bps), 2) == 4.00


def test_order_request_validation():
    req = OrderRequest(
        symbol="ETH-PERP",
        side=OrderSide.BUY,
        notional_usd=Decimal("100000.00"),
        order_type=OrderType.MARKET,
        max_slippage_bps=Decimal("20.0"),
    )
    assert req.symbol == "ETH-PERP"
    assert req.notional_usd == Decimal("100000.00")
    assert req.side == OrderSide.BUY
