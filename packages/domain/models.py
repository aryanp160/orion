from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from packages.domain.enums import (
    ExecutionPreference,
    LiquidityRole,
    NetworkId,
    OrderSide,
    OrderStatus,
    OrderType,
    RiskOutcome,
    VenueId,
    VenueType,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# 1. Venue & Capabilities
class VenueCapabilities(BaseModel):
    model_config = ConfigDict(frozen=True)
    venue_id: VenueId
    venue_type: VenueType
    network: NetworkId
    has_order_book_l2: bool
    has_funding_rates: bool
    has_open_interest: bool
    supports_market_orders: bool
    supports_limit_orders: bool
    supports_split_routing: bool
    is_on_chain: bool
    gas_fee_required: bool
    fee_tier_configurable: bool
    description: str


class Venue(BaseModel):
    id: VenueId
    name: str
    network: NetworkId
    venue_type: VenueType
    base_url: str
    capabilities: VenueCapabilities
    is_active: bool = True


# 2. Market / Instrument
class Instrument(BaseModel):
    symbol: str  # e.g. "ETH-PERP" or "ETH"
    base_asset: str = "ETH"
    quote_asset: str = "USD"
    venue_id: VenueId
    min_order_size: Decimal = Field(default=Decimal("0.001"))
    max_order_size: Decimal = Field(default=Decimal("1000.0"))
    step_size: Decimal = Field(default=Decimal("0.0001"))
    tick_size: Decimal = Field(default=Decimal("0.01"))
    max_leverage: int = 50
    maker_fee_bps: Decimal = Field(default=Decimal("1.0"))
    taker_fee_bps: Decimal = Field(default=Decimal("3.5"))


class Market(BaseModel):
    symbol: str
    supported_venues: List[VenueId]
    instruments: Dict[VenueId, Instrument]


# 3. OrderBook & Levels
class OrderBookLevel(BaseModel):
    price: Decimal
    size: Decimal
    order_count: Optional[int] = None


class OrderBook(BaseModel):
    venue_id: VenueId
    symbol: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: datetime = Field(default_factory=utc_now)
    receive_timestamp: datetime = Field(default_factory=utc_now)
    sequence_id: Optional[int] = None
    is_stale: bool = False

    @property
    def best_bid(self) -> Optional[Decimal]:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Optional[Decimal]:
        return self.asks[0].price if self.asks else None

    @property
    def mid_price(self) -> Optional[Decimal]:
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / Decimal("2")
        return None

    @property
    def spread_bps(self) -> Optional[Decimal]:
        if self.best_bid and self.best_ask and self.best_bid > 0:
            mid = (self.best_bid + self.best_ask) / Decimal("2")
            if mid > 0:
                return ((self.best_ask - self.best_bid) / mid) * Decimal("10000")
        return None


# 4. Trade
class Trade(BaseModel):
    trade_id: str
    venue_id: VenueId
    symbol: str
    price: Decimal
    size: Decimal
    side: OrderSide
    timestamp: datetime = Field(default_factory=utc_now)


# 5. FundingObservation
class FundingObservation(BaseModel):
    venue_id: VenueId
    symbol: str
    funding_rate_bps: Decimal  # Normalized to 8-hour rate in basis points for consistency
    interval_hours: Decimal = Field(default=Decimal("1.0"))
    predicted_next_rate_bps: Optional[Decimal] = None
    next_funding_time: Optional[datetime] = None
    timestamp: datetime = Field(default_factory=utc_now)


# 6. OpenInterestObservation
class OpenInterestObservation(BaseModel):
    venue_id: VenueId
    symbol: str
    open_interest_notional: Decimal
    open_interest_contracts: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=utc_now)


# 7. MarkPrice & IndexPrice
class MarkPrice(BaseModel):
    venue_id: VenueId
    symbol: str
    mark_price: Decimal
    index_price: Optional[Decimal] = None
    basis_bps: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=utc_now)


class IndexPrice(BaseModel):
    symbol: str
    price: Decimal
    sources: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=utc_now)


# 8. MarketDataHealth
class MarketDataHealth(BaseModel):
    venue_id: VenueId
    symbol: str
    is_healthy: bool
    latency_ms: float
    last_update_ts: datetime
    staleness_sec: float
    sequence_gaps: int = 0
    status_message: str = "HEALTHY"


# 9. GasObservation
class GasObservation(BaseModel):
    network: NetworkId
    base_fee_gwei: Decimal
    priority_fee_gwei: Decimal
    eth_usd_price: Decimal
    l1_rollup_fee_usd: Decimal = Field(default=Decimal("0.0"))
    estimated_tx_cost_usd: Decimal
    timestamp: datetime = Field(default_factory=utc_now)


# 10. OrderRequest
class OrderRequest(BaseModel):
    symbol: str = "ETH-PERP"
    side: OrderSide
    notional_usd: Decimal
    order_type: OrderType = OrderType.MARKET
    execution_preference: ExecutionPreference = ExecutionPreference.MINIMIZE_COST
    max_slippage_bps: Decimal = Field(default=Decimal("20.0"))
    max_duration_sec: Decimal = Field(default=Decimal("60.0"))
    holding_horizon_hours: Decimal = Field(default=Decimal("24.0"))
    limit_price: Optional[Decimal] = None
    client_order_id: Optional[str] = None


# 11. CostComponentAttribution
class CostBreakdown(BaseModel):
    reference_price: Decimal
    expected_execution_price: Decimal
    spread_cost_bps: Decimal
    spread_cost_usd: Decimal
    market_impact_bps: Decimal
    market_impact_usd: Decimal
    trading_fee_bps: Decimal
    trading_fee_usd: Decimal
    funding_cost_bps: Decimal
    funding_cost_usd: Decimal
    transaction_cost_bps: Decimal
    transaction_cost_usd: Decimal
    adverse_selection_bps: Decimal
    adverse_selection_usd: Decimal
    total_cost_bps: Decimal
    total_cost_usd: Decimal


# 12. CandidateRouteQuote
class CandidateRoute(BaseModel):
    venue_id: VenueId
    allocation_pct: Decimal = Field(default=Decimal("100.0"))
    allocated_notional: Decimal
    allocated_quantity: Decimal
    expected_vwap: Decimal
    breakdown: CostBreakdown
    is_eligible: bool = True
    ineligibility_reason: Optional[str] = None
    data_freshness_sec: float = 0.0
    liquidity_available_usd: Decimal = Field(default=Decimal("0.0"))


# 13. RouteQuote & RouteDecision
class RouteQuote(BaseModel):
    quote_id: str
    order_request: OrderRequest
    recommended_venue: VenueId
    is_split_route: bool = False
    candidates: List[CandidateRoute]
    allocations: List[CandidateRoute]  # Chosen execution allocations
    blended_vwap: Decimal
    blended_breakdown: CostBreakdown
    confidence_score: float = 0.95
    model_version: str = "orion-v1.0-deterministic"
    freshness_sec: float = 0.5
    quote_timestamp: datetime = Field(default_factory=utc_now)
    expires_at: datetime
    explanation: Dict[str, Any]


class RouteDecision(BaseModel):
    decision_id: str
    quote_id: str
    selected_plan: str
    allocations: List[Dict[str, Any]]
    alternative_rejections: Dict[str, str]
    risk_approval: bool
    explanation_summary: str
    timestamp: datetime = Field(default_factory=utc_now)


# 14. OrderPlan
class OrderSlice(BaseModel):
    slice_id: str
    venue_id: VenueId
    notional: Decimal
    quantity: Decimal
    target_price: Decimal
    max_slippage_bps: Decimal


class OrderPlan(BaseModel):
    plan_id: str
    order_request: OrderRequest
    slices: List[OrderSlice]
    created_at: datetime = Field(default_factory=utc_now)


# 15. ExecutionReport & Fill
class Fill(BaseModel):
    fill_id: str
    order_id: str
    venue_id: VenueId
    symbol: str
    side: OrderSide
    fill_price: Decimal
    fill_quantity: Decimal
    fill_notional: Decimal
    fee_usd: Decimal
    fee_bps: Decimal
    role: LiquidityRole = LiquidityRole.TAKER
    timestamp: datetime = Field(default_factory=utc_now)
    simulated: bool = True


class ExecutionReport(BaseModel):
    report_id: str
    order_id: str
    client_order_id: Optional[str] = None
    status: OrderStatus
    symbol: str
    side: OrderSide
    order_type: OrderType
    requested_notional: Decimal
    requested_quantity: Decimal
    filled_quantity: Decimal = Field(default=Decimal("0.0"))
    filled_notional: Decimal = Field(default=Decimal("0.0"))
    remaining_quantity: Decimal
    avg_fill_price: Decimal = Field(default=Decimal("0.0"))
    total_fee_usd: Decimal = Field(default=Decimal("0.0"))
    slippage_bps: Decimal = Field(default=Decimal("0.0"))
    fills: List[Fill] = Field(default_factory=list)
    rejection_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


# 16. FeeRecord
class FeeRecord(BaseModel):
    venue_id: VenueId
    maker_fee_bps: Decimal
    taker_fee_bps: Decimal
    tier_name: str = "STANDARD"
    protocol_overhead_usd: Decimal = Field(default=Decimal("0.0"))


# 17. PaperPosition & Account
class PaperPosition(BaseModel):
    symbol: str
    venue_id: VenueId
    side: OrderSide
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal
    notional_usd: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    margin_allocated: Decimal
    leverage: Decimal = Field(default=Decimal("1.0"))
    liquidation_price: Optional[Decimal] = None
    updated_at: datetime = Field(default_factory=utc_now)


class PaperAccount(BaseModel):
    account_id: str = "PAPER_DEFAULT"
    equity_usd: Decimal
    available_margin_usd: Decimal
    used_margin_usd: Decimal
    realized_pnl_usd: Decimal
    unrealized_pnl_usd: Decimal
    initial_balance: Decimal
    total_orders_count: int = 0
    total_fills_count: int = 0
    positions: List[PaperPosition] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


# 18. RiskAssessment
class RiskAssessment(BaseModel):
    outcome: RiskOutcome
    symbol: str
    requested_notional: Decimal
    flags: List[str] = Field(default_factory=list)
    checks: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    rejection_reason: Optional[str] = None
    timestamp: datetime = Field(default_factory=utc_now)


# 19. BacktestRun & Execution Attribution
class BacktestRun(BaseModel):
    run_id: str
    name: str
    symbol: str
    start_time: datetime
    end_time: datetime
    status: str
    order_count: int
    baseline_naive_cost_bps: Decimal
    baseline_single_cost_bps: Decimal
    orion_route_cost_bps: Decimal
    mean_savings_vs_naive_bps: Decimal
    mean_savings_vs_single_bps: Decimal
    total_savings_usd: Decimal
    completion_rate_pct: Decimal
    cost_percentiles: Dict[str, Decimal] = Field(default_factory=dict)
    summary_metrics: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


# 20. AuditEvent
class AuditEvent(BaseModel):
    event_id: str
    actor: str = "SYSTEM"
    event_type: str
    correlation_id: str
    entity_id: str
    entity_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utc_now)
