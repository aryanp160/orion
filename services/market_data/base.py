from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional

from packages.domain.enums import VenueId
from packages.domain.models import (
    FundingObservation,
    Instrument,
    MarketDataHealth,
    MarkPrice,
    OpenInterestObservation,
    OrderBook,
    Trade,
    VenueCapabilities,
)


class BaseVenueAdapter(ABC):
    """
    Abstract Base Class for Venue Market Data Adapters.
    Every supported venue (Hyperliquid, GMX v2, MockCLOB) implements this interface,
    normalizing proprietary protocols into ORION domain models.
    """

    def __init__(self, venue_id: VenueId):
        self.venue_id = venue_id
        self._last_health: MarketDataHealth = MarketDataHealth(
            venue_id=self.venue_id,
            symbol="ETH-PERP",
            is_healthy=False,
            latency_ms=0.0,
            last_update_ts=datetime.now(timezone.utc),
            staleness_sec=999.0,
            status_message="INITIALIZING",
        )

    @property
    @abstractmethod
    def capabilities(self) -> VenueCapabilities:
        """Venue capability metadata so router/cost-engine never assumes unsupported features."""
        pass

    @abstractmethod
    async def get_instrument(self, symbol: str) -> Optional[Instrument]:
        """Return instrument specifications: tick size, step size, fees, min/max notional."""
        pass

    @abstractmethod
    async def fetch_order_book(self, symbol: str, depth: int = 20) -> OrderBook:
        """
        Fetch normalized L2 order book snapshot.
        For CLOBs: walked levels.
        For Oracle/AMM pools: synthetic depth bands constructed from available pool liquidity.
        """
        pass

    @abstractmethod
    async def fetch_trades(self, symbol: str, limit: int = 50) -> List[Trade]:
        """Fetch recent normalized public trades."""
        pass

    @abstractmethod
    async def fetch_funding(self, symbol: str) -> FundingObservation:
        """Fetch current funding rate normalized to 8-hour basis points."""
        pass

    @abstractmethod
    async def fetch_open_interest(self, symbol: str) -> OpenInterestObservation:
        """Fetch current open interest."""
        pass

    @abstractmethod
    async def fetch_mark_price(self, symbol: str) -> MarkPrice:
        """Fetch current mark price and index price."""
        pass

    @abstractmethod
    async def check_health(self, symbol: str = "ETH-PERP") -> MarketDataHealth:
        """Ping venue API and verify latency, sequence, and staleness."""
        pass
