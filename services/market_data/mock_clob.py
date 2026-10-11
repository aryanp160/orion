from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from packages.domain.enums import NetworkId, VenueId, VenueType
from packages.domain.models import (
    FundingObservation,
    Instrument,
    MarketDataHealth,
    MarkPrice,
    OpenInterestObservation,
    OrderBook,
    OrderBookLevel,
    Trade,
    VenueCapabilities,
)
from services.market_data.base import BaseVenueAdapter


class MockCLOBAdapter(BaseVenueAdapter):
    """
    Deterministic Offline Fixture Venue Adapter.
    Provides mathematically reproducible order book depth, trades, funding rates,
    and zero latency for isolated unit, contract, and backtesting benchmarks.
    """

    def __init__(self, base_mid_price: Decimal = Decimal("2500.00")):
        super().__init__(VenueId.MOCK_CLOB)
        self.base_mid_price = base_mid_price
        self._is_healthy = True

    @property
    def capabilities(self) -> VenueCapabilities:
        return VenueCapabilities(
            venue_id=VenueId.MOCK_CLOB,
            venue_type=VenueType.SIMULATED,
            network=NetworkId.SIMULATED,
            has_order_book_l2=True,
            has_funding_rates=True,
            has_open_interest=True,
            supports_market_orders=True,
            supports_limit_orders=True,
            supports_split_routing=True,
            is_on_chain=False,
            gas_fee_required=False,
            fee_tier_configurable=True,
            description="Deterministic offline CLOB fixture for test reproducibility",
        )

    async def get_instrument(self, symbol: str) -> Optional[Instrument]:
        return Instrument(
            symbol=symbol,
            base_asset="ETH",
            quote_asset="USD",
            venue_id=VenueId.MOCK_CLOB,
            min_order_size=Decimal("0.001"),
            max_order_size=Decimal("1000.0"),
            step_size=Decimal("0.0001"),
            tick_size=Decimal("0.01"),
            max_leverage=50,
            maker_fee_bps=Decimal("1.0"),
            taker_fee_bps=Decimal("3.0"),
        )

    async def fetch_order_book(self, symbol: str, depth: int = 20) -> OrderBook:
        now_utc = datetime.now(timezone.utc)
        mid = self.base_mid_price
        half_spread = Decimal("0.25")  # $0.50 spread

        bids: List[OrderBookLevel] = []
        asks: List[OrderBookLevel] = []

        for i in range(depth):
            step = Decimal(str(i))
            bid_px = mid - half_spread - (step * Decimal("0.20"))
            ask_px = mid + half_spread + (step * Decimal("0.20"))
            size = Decimal("5.0") + (step * Decimal("2.5"))
            bids.append(OrderBookLevel(price=bid_px, size=size))
            asks.append(OrderBookLevel(price=ask_px, size=size))

        return OrderBook(
            venue_id=VenueId.MOCK_CLOB,
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=now_utc,
            receive_timestamp=now_utc,
            is_stale=False,
        )

    async def fetch_trades(self, symbol: str, limit: int = 50) -> List[Trade]:
        return []

    async def fetch_funding(self, symbol: str) -> FundingObservation:
        return FundingObservation(
            venue_id=VenueId.MOCK_CLOB,
            symbol=symbol,
            funding_rate_bps=Decimal("1.0"),  # 1.0 bps per 8 hours
            interval_hours=Decimal("8.0"),
            timestamp=datetime.now(timezone.utc),
        )

    async def fetch_open_interest(self, symbol: str) -> OpenInterestObservation:
        return OpenInterestObservation(
            venue_id=VenueId.MOCK_CLOB,
            symbol=symbol,
            open_interest_notional=Decimal("100000000.0"),
            timestamp=datetime.now(timezone.utc),
        )

    async def fetch_mark_price(self, symbol: str) -> MarkPrice:
        return MarkPrice(
            venue_id=VenueId.MOCK_CLOB,
            symbol=symbol,
            mark_price=self.base_mid_price,
            index_price=self.base_mid_price,
            basis_bps=Decimal("0.0"),
            timestamp=datetime.now(timezone.utc),
        )

    async def check_health(self, symbol: str = "ETH-PERP") -> MarketDataHealth:
        return MarketDataHealth(
            venue_id=VenueId.MOCK_CLOB,
            symbol=symbol,
            is_healthy=self._is_healthy,
            latency_ms=0.1,
            last_update_ts=datetime.now(timezone.utc),
            staleness_sec=0.0,
            status_message="ONLINE_DETERMINISTIC_FIXTURE",
        )
