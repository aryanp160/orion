import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from packages.domain.enums import VenueId
from packages.domain.models import (
    FundingObservation,
    MarketDataHealth,
    MarkPrice,
    OpenInterestObservation,
    OrderBook,
)
from services.market_data.base import BaseVenueAdapter
from services.market_data.gmx_v2 import GMXV2Adapter
from services.market_data.hyperliquid import HyperliquidAdapter
from services.market_data.mock_clob import MockCLOBAdapter


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketDepthBand(BaseModel):
    bps_offset: int
    bid_depth_usd: Decimal
    ask_depth_usd: Decimal
    bid_depth_qty: Decimal
    ask_depth_qty: Decimal


class VenueMarketState(BaseModel):
    venue_id: VenueId
    symbol: str
    best_bid: Optional[Decimal] = None
    best_ask: Optional[Decimal] = None
    mid_price: Optional[Decimal] = None
    spread_bps: Optional[Decimal] = None
    order_book_imbalance: Optional[Decimal] = (
        None  # (bid_depth - ask_depth) / (bid_depth + ask_depth)
    )
    depth_bands: List[MarketDepthBand] = Field(default_factory=list)
    total_liquidity_depth_usd: Decimal = Field(default=Decimal("0.0"))
    funding_rate_8h_bps: Decimal = Field(default=Decimal("0.0"))
    open_interest_usd: Decimal = Field(default=Decimal("0.0"))
    mark_price: Decimal = Field(default=Decimal("0.0"))
    basis_bps: Decimal = Field(default=Decimal("0.0"))
    data_freshness_sec: float = 0.0
    latency_ms: float = 0.0
    is_healthy: bool = True
    status_message: str = "ONLINE"
    timestamp: datetime = Field(default_factory=utc_now)


class AggregatedMarketState(BaseModel):
    symbol: str = "ETH-PERP"
    timestamp: datetime = Field(default_factory=utc_now)
    venues: Dict[VenueId, VenueMarketState]
    best_bid_global: Optional[Decimal] = None
    best_bid_venue: Optional[VenueId] = None
    best_ask_global: Optional[Decimal] = None
    best_ask_venue: Optional[VenueId] = None
    global_mid_price: Optional[Decimal] = None
    global_spread_bps: Optional[Decimal] = None
    total_market_liquidity_usd: Decimal = Field(default=Decimal("0.0"))
    realized_volatility_bps: Decimal = Field(
        default=Decimal("25.0")
    )  # Baseline 15-min annualized proxy


class MarketStateEngine:
    """
    Unified Market State Aggregator.
    Maintains active connections/polls to Hyperliquid, GMX v2, and MockCLOB,
    calculating microstructural indicators (VWAP depth bands, imbalance, basis, spread).
    """

    def __init__(self):
        self.adapters: Dict[VenueId, BaseVenueAdapter] = {
            VenueId.HYPERLIQUID: HyperliquidAdapter(),
            VenueId.GMX_V2: GMXV2Adapter(),
            VenueId.MOCK_CLOB: MockCLOBAdapter(),
        }
        self._cached_states: Dict[VenueId, VenueMarketState] = {}
        self._last_aggregated: Optional[AggregatedMarketState] = None

    def get_adapter(self, venue_id: VenueId) -> Optional[BaseVenueAdapter]:
        return self.adapters.get(venue_id)

    async def poll_venue_state(
        self, venue_id: VenueId, symbol: str = "ETH-PERP"
    ) -> VenueMarketState:
        adapter = self.adapters.get(venue_id)
        if not adapter:
            raise ValueError(f"Unknown venue {venue_id}")

        now = utc_now()
        book_task = adapter.fetch_order_book(symbol)
        funding_task = adapter.fetch_funding(symbol)
        oi_task = adapter.fetch_open_interest(symbol)
        mark_task = adapter.fetch_mark_price(symbol)
        health_task = adapter.check_health(symbol)

        book, funding, oi, mark, health = await asyncio.gather(
            book_task, funding_task, oi_task, mark_task, health_task, return_exceptions=True
        )

        # Fallbacks for any exception
        valid_book = (
            book
            if isinstance(book, OrderBook)
            else OrderBook(
                venue_id=venue_id,
                symbol=symbol,
                bids=[],
                asks=[],
                timestamp=now,
                receive_timestamp=now,
                is_stale=True,
            )
        )
        valid_funding = (
            funding
            if isinstance(funding, FundingObservation)
            else FundingObservation(
                venue_id=venue_id, symbol=symbol, funding_rate_bps=Decimal("0.0"), timestamp=now
            )
        )
        valid_oi = (
            oi
            if isinstance(oi, OpenInterestObservation)
            else OpenInterestObservation(
                venue_id=venue_id,
                symbol=symbol,
                open_interest_notional=Decimal("0.0"),
                timestamp=now,
            )
        )
        valid_mark = (
            mark
            if isinstance(mark, MarkPrice)
            else MarkPrice(
                venue_id=venue_id, symbol=symbol, mark_price=Decimal("2500.0"), timestamp=now
            )
        )
        valid_health = (
            health
            if isinstance(health, MarketDataHealth)
            else MarketDataHealth(
                venue_id=venue_id,
                symbol=symbol,
                is_healthy=False,
                latency_ms=999.0,
                last_update_ts=now,
                staleness_sec=999.0,
                status_message="FETCH_FAILED",
            )
        )

        # Compute depth bands and imbalance
        best_bid = valid_book.best_bid
        best_ask = valid_book.best_ask
        mid = valid_book.mid_price or valid_mark.mark_price
        spread_bps = valid_book.spread_bps

        depth_bands: List[MarketDepthBand] = []
        imbalance: Optional[Decimal] = None
        total_depth_usd = Decimal("0.0")

        if mid and valid_book.bids and valid_book.asks:
            # 10, 25, 50, 100 bps depth bands
            for bps in [10, 25, 50, 100]:
                cutoff_bid = mid * (Decimal("1") - Decimal(bps) / Decimal("10000"))
                cutoff_ask = mid * (Decimal("1") + Decimal(bps) / Decimal("10000"))

                bid_qty = sum(
                    (b.size for b in valid_book.bids if b.price >= cutoff_bid), Decimal("0")
                )
                ask_qty = sum(
                    (a.size for a in valid_book.asks if a.price <= cutoff_ask), Decimal("0")
                )

                bid_usd = sum(
                    (b.price * b.size for b in valid_book.bids if b.price >= cutoff_bid),
                    Decimal("0"),
                )
                ask_usd = sum(
                    (a.price * a.size for a in valid_book.asks if a.price <= cutoff_ask),
                    Decimal("0"),
                )

                depth_bands.append(
                    MarketDepthBand(
                        bps_offset=bps,
                        bid_depth_usd=bid_usd,
                        ask_depth_usd=ask_usd,
                        bid_depth_qty=bid_qty,
                        ask_depth_qty=ask_qty,
                    )
                )

            # Total depth
            total_bid_usd = sum((b.price * b.size for b in valid_book.bids), Decimal("0"))
            total_ask_usd = sum((a.price * a.size for a in valid_book.asks), Decimal("0"))
            total_depth_usd = total_bid_usd + total_ask_usd

            if (total_bid_usd + total_ask_usd) > 0:
                imbalance = (total_bid_usd - total_ask_usd) / (total_bid_usd + total_ask_usd)

        # Staleness calculation
        staleness_sec = (now - valid_book.receive_timestamp).total_seconds()

        state = VenueMarketState(
            venue_id=venue_id,
            symbol=symbol,
            best_bid=best_bid,
            best_ask=best_ask,
            mid_price=mid,
            spread_bps=spread_bps,
            order_book_imbalance=round(imbalance, 4) if imbalance is not None else None,
            depth_bands=depth_bands,
            total_liquidity_depth_usd=total_depth_usd,
            funding_rate_8h_bps=valid_funding.funding_rate_bps,
            open_interest_usd=valid_oi.open_interest_notional,
            mark_price=valid_mark.mark_price,
            basis_bps=valid_mark.basis_bps or Decimal("0.0"),
            data_freshness_sec=round(staleness_sec, 2),
            latency_ms=valid_health.latency_ms,
            is_healthy=valid_health.is_healthy,
            status_message=valid_health.status_message,
            timestamp=now,
        )

        self._cached_states[venue_id] = state
        return state

    async def get_aggregated_state(self, symbol: str = "ETH-PERP") -> AggregatedMarketState:
        # Poll all venues concurrently
        poll_tasks = [self.poll_venue_state(vid, symbol) for vid in self.adapters.keys()]
        venue_states_list = await asyncio.gather(*poll_tasks)

        venue_states: Dict[VenueId, VenueMarketState] = {s.venue_id: s for s in venue_states_list}

        # Global BBO
        best_bid_global = None
        best_bid_venue = None
        best_ask_global = None
        best_ask_venue = None
        total_liq = Decimal("0.0")

        for vid, state in venue_states.items():
            if not state.is_healthy:
                continue
            total_liq += state.total_liquidity_depth_usd
            if state.best_bid is not None:
                if best_bid_global is None or state.best_bid > best_bid_global:
                    best_bid_global = state.best_bid
                    best_bid_venue = vid
            if state.best_ask is not None:
                if best_ask_global is None or state.best_ask < best_ask_global:
                    best_ask_global = state.best_ask
                    best_ask_venue = vid

        global_mid = None
        global_spread_bps = None
        if best_bid_global and best_ask_global:
            global_mid = (best_bid_global + best_ask_global) / Decimal("2")
            if global_mid > 0:
                global_spread_bps = ((best_ask_global - best_bid_global) / global_mid) * Decimal(
                    "10000"
                )

        aggregated = AggregatedMarketState(
            symbol=symbol,
            timestamp=utc_now(),
            venues=venue_states,
            best_bid_global=best_bid_global,
            best_bid_venue=best_bid_venue,
            best_ask_global=best_ask_global,
            best_ask_venue=best_ask_venue,
            global_mid_price=global_mid,
            global_spread_bps=global_spread_bps,
            total_market_liquidity_usd=total_liq,
        )
        self._last_aggregated = aggregated
        return aggregated


# Global singleton instance
market_state_engine = MarketStateEngine()
