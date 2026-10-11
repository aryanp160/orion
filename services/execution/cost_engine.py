from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, Tuple

from packages.domain.enums import OrderSide, OrderType
from packages.domain.models import (
    CostBreakdown,
    FundingObservation,
    GasObservation,
    Instrument,
    OrderBook,
    OrderRequest,
    VenueCapabilities,
)


class ExecutionCostEngine:
    """
    Deterministic Quantitative Execution Cost Engine for Perpetual Futures.

    Reference Benchmark: Arrival Mid-Price P_mid = (P_bid0 + P_ask0) / 2.

    Decomposition:
    Total Expected Cost = Spread Cost + Market Impact (VWAP Slippage) + Trading Fees
                          + Expected Funding Cost (Horizon) + Transaction/Gas Costs
                          + Adverse Selection Proxy.

    Units:
    - Costs are signed in basis points (bps) of requested notional and in USD.
    - Positive bps (+X bps) means an expense/drag on execution performance.
    - Negative bps (-X bps) means a benefit/credit (e.g., funding receipt or maker rebate).
    """

    @staticmethod
    def walk_order_book(
        book: OrderBook,
        side: OrderSide,
        required_notional: Decimal,
        arrival_mid: Decimal,
    ) -> Tuple[Decimal, Decimal, Decimal, bool]:
        """
        Walks the discrete order book depth levels to compute actual executable VWAP.

        Returns:
            - expected_vwap: Weighted Average Fill Price
            - executable_notional: Actual notional that can be filled by current depth
            - executed_quantity: Total contracts/tokens filled
            - is_fully_fillable: True if available depth >= required_notional
        """
        levels = book.asks if side == OrderSide.BUY else book.bids
        if not levels or arrival_mid <= Decimal("0"):
            return arrival_mid, Decimal("0"), Decimal("0"), False

        remaining_notional = required_notional
        cumulative_notional = Decimal("0")
        cumulative_cost_usd = Decimal("0")
        cumulative_qty = Decimal("0")

        for lvl in levels:
            level_price = lvl.price
            level_qty = lvl.size
            level_notional = level_price * level_qty

            if remaining_notional <= level_notional:
                fill_qty = remaining_notional / level_price
                cumulative_qty += fill_qty
                cumulative_notional += remaining_notional
                cumulative_cost_usd += remaining_notional
                remaining_notional = Decimal("0")
                break
            else:
                cumulative_qty += level_qty
                cumulative_notional += level_notional
                cumulative_cost_usd += level_notional
                remaining_notional -= level_notional

        if cumulative_qty > Decimal("0"):
            expected_vwap = (cumulative_cost_usd / cumulative_qty).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            expected_vwap = arrival_mid

        is_fully_fillable = remaining_notional == Decimal("0")
        return expected_vwap, cumulative_notional, cumulative_qty, is_fully_fillable

    @classmethod
    def calculate_cost_breakdown(
        cls,
        order: OrderRequest,
        book: OrderBook,
        instrument: Instrument,
        capabilities: VenueCapabilities,
        funding: Optional[FundingObservation] = None,
        gas: Optional[GasObservation] = None,
        adverse_selection_factor_bps: Decimal = Decimal("1.5"),
    ) -> CostBreakdown:
        notional = order.notional_usd
        arrival_mid = book.mid_price or (instrument.tick_size * Decimal("250000"))

        if not book.bids or not book.asks:
            # Fallback for empty book
            return CostBreakdown(
                reference_price=arrival_mid,
                expected_execution_price=arrival_mid,
                spread_cost_bps=Decimal("5.0"),
                spread_cost_usd=notional * Decimal("0.0005"),
                market_impact_bps=Decimal("10.0"),
                market_impact_usd=notional * Decimal("0.0010"),
                trading_fee_bps=instrument.taker_fee_bps,
                trading_fee_usd=notional * (instrument.taker_fee_bps / Decimal("10000")),
                funding_cost_bps=Decimal("0.0"),
                funding_cost_usd=Decimal("0.0"),
                transaction_cost_bps=Decimal("0.0"),
                transaction_cost_usd=Decimal("0.0"),
                adverse_selection_bps=Decimal("1.0"),
                adverse_selection_usd=notional * Decimal("0.0001"),
                total_cost_bps=Decimal("20.0"),
                total_cost_usd=notional * Decimal("0.0020"),
            )

        # 1. Spread Cost: Half-spread at top of book
        # P_best_ask - P_mid for BUY; P_mid - P_best_bid for SELL
        if order.side == OrderSide.BUY:
            top_level = book.best_ask or arrival_mid
            spread_dist = top_level - arrival_mid
        else:
            top_level = book.best_bid or arrival_mid
            spread_dist = arrival_mid - top_level

        spread_bps = max(Decimal("0.0"), (spread_dist / arrival_mid) * Decimal("10000"))
        spread_usd = notional * (spread_bps / Decimal("10000"))

        # 2. Market Impact (VWAP slippage beyond top of book)
        expected_vwap, fillable_notional, fillable_qty, is_fillable = cls.walk_order_book(
            book=book,
            side=order.side,
            required_notional=notional,
            arrival_mid=arrival_mid,
        )

        # Difference between executable VWAP and top of book represents pure depth impact
        if order.side == OrderSide.BUY:
            impact_dist = max(Decimal("0.0"), expected_vwap - top_level)
        else:
            impact_dist = max(Decimal("0.0"), top_level - expected_vwap)

        market_impact_bps = (impact_dist / arrival_mid) * Decimal("10000")

        # Penalize if notional exceeds full book depth
        if not is_fillable:
            shortfall_ratio = (notional - fillable_notional) / notional
            market_impact_bps += shortfall_ratio * Decimal("50.0")

        market_impact_usd = notional * (market_impact_bps / Decimal("10000"))

        # 3. Trading Fees
        fee_bps = (
            instrument.taker_fee_bps
            if order.order_type == OrderType.MARKET
            else instrument.maker_fee_bps
        )
        fee_usd = notional * (fee_bps / Decimal("10000"))

        # 4. Expected Funding Cost over Holding Horizon
        # Funding rate convention: standardized to 8-hour rate in bps
        # If rate > 0: Longs pay Shorts.
        # BUY (Long): cost is +rate_bps * (horizon / 8)
        # SELL (Short): cost is -rate_bps * (horizon / 8) (i.e. receives funding)
        funding_cost_bps = Decimal("0.0")
        if funding and order.holding_horizon_hours > Decimal("0"):
            horizon_factor = order.holding_horizon_hours / Decimal("8.0")
            rate_bps = funding.funding_rate_bps
            if order.side == OrderSide.BUY:
                funding_cost_bps = rate_bps * horizon_factor
            else:
                funding_cost_bps = -rate_bps * horizon_factor

        funding_cost_usd = notional * (funding_cost_bps / Decimal("10000"))

        # 5. Transaction / Gas Costs
        # On-chain L2 (Arbitrum) incurs sequencer L2 gas + keeper execution fee (~$1.50 - $2.50)
        # Off-chain / Appchain (Hyperliquid) incurs $0 gas fee.
        tx_cost_usd = Decimal("0.0")
        if capabilities.gas_fee_required:
            if gas:
                tx_cost_usd = gas.estimated_tx_cost_usd
            else:
                tx_cost_usd = Decimal("1.80")  # Default conservative Arbitrum keeper execution fee

        tx_cost_bps = (
            (tx_cost_usd / notional) * Decimal("10000") if notional > 0 else Decimal("0.0")
        )

        # 6. Adverse Selection Proxy
        # Configurable estimator based on trade size / market depth ratio
        depth_coverage_ratio = notional / max(fillable_notional, Decimal("1.0"))
        adverse_selection_bps = adverse_selection_factor_bps * min(
            Decimal("3.0"), depth_coverage_ratio
        )
        adverse_selection_usd = notional * (adverse_selection_bps / Decimal("10000"))

        # Total Expected Cost
        total_cost_bps = (
            spread_bps
            + market_impact_bps
            + fee_bps
            + funding_cost_bps
            + tx_cost_bps
            + adverse_selection_bps
        )
        total_cost_usd = (
            spread_usd
            + market_impact_usd
            + fee_usd
            + funding_cost_usd
            + tx_cost_usd
            + adverse_selection_usd
        )

        return CostBreakdown(
            reference_price=arrival_mid.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            expected_execution_price=expected_vwap,
            spread_cost_bps=spread_bps.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            spread_cost_usd=spread_usd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            market_impact_bps=market_impact_bps.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            market_impact_usd=market_impact_usd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            trading_fee_bps=fee_bps.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            trading_fee_usd=fee_usd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            funding_cost_bps=funding_cost_bps.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            funding_cost_usd=funding_cost_usd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            transaction_cost_bps=tx_cost_bps.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            transaction_cost_usd=tx_cost_usd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            adverse_selection_bps=adverse_selection_bps.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            adverse_selection_usd=adverse_selection_usd.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            total_cost_bps=total_cost_bps.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            total_cost_usd=total_cost_usd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        )


cost_engine = ExecutionCostEngine()
