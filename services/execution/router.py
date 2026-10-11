import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional

from apps.api.config import settings
from packages.domain.enums import OrderSide, RiskOutcome, VenueId
from packages.domain.models import (
    CandidateRoute,
    CostBreakdown,
    OrderRequest,
    RouteQuote,
)
from services.execution.cost_engine import ExecutionCostEngine, cost_engine
from services.execution.risk_engine import RiskEngine, risk_engine
from services.market_data.state_engine import MarketStateEngine, market_state_engine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExecutionRouter:
    """
    Deterministic Explainable Execution Router for Perpetual Futures.
    Evaluates all active venue adapters, enforces pre-trade eligibility & risk constraints,
    and calculates both Single-Venue and Split-Allocation execution plans.
    """

    def __init__(
        self,
        state_engine: Optional[MarketStateEngine] = None,
        cost_evaluator: Optional[ExecutionCostEngine] = None,
        risk_guard: Optional[RiskEngine] = None,
    ):
        self.state_engine = state_engine or market_state_engine
        self.cost_engine = cost_evaluator or cost_engine
        self.risk_engine = risk_guard or risk_engine

    async def generate_quote(self, order: OrderRequest) -> RouteQuote:
        quote_id = f"quo_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        expires_at = now + timedelta(seconds=settings.ORION_QUOTE_EXPIRY_SEC)

        # 1. Evaluate Pre-Trade Risk on the order request itself
        risk_eval = self.risk_engine.evaluate_order(order)
        if risk_eval.outcome == RiskOutcome.BLOCK:
            # Construct a clear rejected quote
            rejection_explanation = {
                "decision": "NO_ELIGIBLE_ROUTE",
                "reason": risk_eval.rejection_reason or "Blocked by pre-trade risk engine",
                "risk_flags": risk_eval.flags,
                "checks": risk_eval.checks,
            }
            empty_cost = CostBreakdown(
                reference_price=Decimal("2500.00"),
                expected_execution_price=Decimal("2500.00"),
                spread_cost_bps=Decimal("0.0"),
                spread_cost_usd=Decimal("0.0"),
                market_impact_bps=Decimal("0.0"),
                market_impact_usd=Decimal("0.0"),
                trading_fee_bps=Decimal("0.0"),
                trading_fee_usd=Decimal("0.0"),
                funding_cost_bps=Decimal("0.0"),
                funding_cost_usd=Decimal("0.0"),
                transaction_cost_bps=Decimal("0.0"),
                transaction_cost_usd=Decimal("0.0"),
                adverse_selection_bps=Decimal("0.0"),
                adverse_selection_usd=Decimal("0.0"),
                total_cost_bps=Decimal("0.0"),
                total_cost_usd=Decimal("0.0"),
            )
            return RouteQuote(
                quote_id=quote_id,
                order_request=order,
                recommended_venue=VenueId.MOCK_CLOB,
                is_split_route=False,
                candidates=[],
                allocations=[],
                blended_vwap=Decimal("0.0"),
                blended_breakdown=empty_cost,
                confidence_score=0.0,
                model_version="orion-v1.0-risk-block",
                freshness_sec=0.0,
                quote_timestamp=now,
                expires_at=expires_at,
                explanation=rejection_explanation,
            )

        # 2. Gather market state and evaluate each candidate venue independently
        candidates: List[CandidateRoute] = []
        eligible_candidates: List[CandidateRoute] = []
        rejection_reasons: Dict[str, str] = {}

        for vid, adapter in self.state_engine.adapters.items():
            instrument = await adapter.get_instrument(order.symbol)
            if not instrument:
                continue

            capabilities = adapter.capabilities
            health = await adapter.check_health(order.symbol)
            book = await adapter.fetch_order_book(order.symbol)
            funding = await adapter.fetch_funding(order.symbol)

            # Check eligibility
            is_eligible = True
            reason = None

            if (
                not health.is_healthy
                or health.staleness_sec > settings.ORION_STALENESS_THRESHOLD_SEC
            ):
                is_eligible = False
                reason = f"Data stale ({health.staleness_sec:.1f}s) or connection unhealthy ({health.status_message})"
            elif not book.bids or not book.asks:
                is_eligible = False
                reason = "Order book has zero liquidity levels"
            elif order.notional_usd < (
                instrument.min_order_size * (book.mid_price or Decimal("2500"))
            ):
                is_eligible = False
                reason = f"Order notional below venue min order size {instrument.min_order_size}"

            # Compute cost breakdown for 100% allocation on this venue
            breakdown = self.cost_engine.calculate_cost_breakdown(
                order=order,
                book=book,
                instrument=instrument,
                capabilities=capabilities,
                funding=funding,
            )

            # Check user slippage limit
            if breakdown.market_impact_bps > order.max_slippage_bps:
                is_eligible = False
                reason = f"Market impact ({breakdown.market_impact_bps:.1f} bps) exceeds user max slippage ({order.max_slippage_bps:.1f} bps)"

            arrival_mid = breakdown.reference_price
            qty = (order.notional_usd / arrival_mid) if arrival_mid > 0 else Decimal("0.0")

            liq_depth = sum(
                (
                    b.price * b.size
                    for b in (book.asks if order.side == OrderSide.BUY else book.bids)
                ),
                Decimal("0"),
            )

            candidate = CandidateRoute(
                venue_id=vid,
                allocation_pct=Decimal("100.0"),
                allocated_notional=order.notional_usd,
                allocated_quantity=qty.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
                expected_vwap=breakdown.expected_execution_price,
                breakdown=breakdown,
                is_eligible=is_eligible,
                ineligibility_reason=reason,
                data_freshness_sec=health.staleness_sec,
                liquidity_available_usd=liq_depth,
            )
            candidates.append(candidate)

            if is_eligible:
                eligible_candidates.append(candidate)
            else:
                rejection_reasons[vid.value] = reason or "Ineligible"

        if not eligible_candidates:
            # Return NO_ELIGIBLE_ROUTE
            explanation = {
                "decision": "NO_ELIGIBLE_ROUTE",
                "reason": "No supported venue satisfied all eligibility and execution constraints.",
                "candidate_evaluations": {
                    c.venue_id.value: c.ineligibility_reason for c in candidates
                },
            }
            cheapest_candidate = (
                min(candidates, key=lambda c: c.breakdown.total_cost_bps) if candidates else None
            )
            fallback_breakdown = cheapest_candidate.breakdown if cheapest_candidate else breakdown
            return RouteQuote(
                quote_id=quote_id,
                order_request=order,
                recommended_venue=cheapest_candidate.venue_id
                if cheapest_candidate
                else VenueId.MOCK_CLOB,
                is_split_route=False,
                candidates=candidates,
                allocations=[],
                blended_vwap=Decimal("0.0"),
                blended_breakdown=fallback_breakdown,
                confidence_score=0.0,
                model_version="orion-v1.0-deterministic",
                freshness_sec=0.5,
                quote_timestamp=now,
                expires_at=expires_at,
                explanation=explanation,
            )

        # 3. Find Best Single Venue
        eligible_candidates.sort(key=lambda c: c.breakdown.total_cost_bps)
        best_single = eligible_candidates[0]

        # 4. Evaluate Multi-Venue Split Allocation if multiple eligible venues exist
        best_plan_candidates = [best_single]
        is_split = False
        blended_breakdown = best_single.breakdown
        blended_vwap = best_single.expected_vwap

        if len(eligible_candidates) >= 2 and order.notional_usd >= Decimal("50000.0"):
            # Bounded optimizer: evaluate 60/40, 50/50, 70/30 split between top two eligible venues
            v1 = eligible_candidates[0].venue_id
            v2 = eligible_candidates[1].venue_id

            adapter1 = self.state_engine.get_adapter(v1)
            adapter2 = self.state_engine.get_adapter(v2)

            if adapter1 and adapter2:
                book1 = await adapter1.fetch_order_book(order.symbol)
                book2 = await adapter2.fetch_order_book(order.symbol)
                inst1 = await adapter1.get_instrument(order.symbol)
                inst2 = await adapter2.get_instrument(order.symbol)

                if inst1 and inst2 and book1.mid_price and book2.mid_price:
                    # Test splits: 50/50, 60/40, 70/30
                    for pct1_int in [50, 60, 70]:
                        pct1 = Decimal(str(pct1_int))
                        pct2 = Decimal("100.0") - pct1

                        notional1 = order.notional_usd * (pct1 / Decimal("100.0"))
                        notional2 = order.notional_usd * (pct2 / Decimal("100.0"))

                        order1 = order.model_copy(update={"notional_usd": notional1})
                        order2 = order.model_copy(update={"notional_usd": notional2})

                        breakdown1 = self.cost_engine.calculate_cost_breakdown(
                            order1, book1, inst1, adapter1.capabilities
                        )
                        breakdown2 = self.cost_engine.calculate_cost_breakdown(
                            order2, book2, inst2, adapter2.capabilities
                        )

                        split_total_cost_usd = breakdown1.total_cost_usd + breakdown2.total_cost_usd
                        split_total_cost_bps = (
                            split_total_cost_usd / order.notional_usd
                        ) * Decimal("10000")

                        # If split achieves meaningful savings (> 0.8 bps improvement over single venue)
                        if split_total_cost_bps < (
                            best_single.breakdown.total_cost_bps - Decimal("0.8")
                        ):
                            is_split = True
                            qty1 = notional1 / breakdown1.reference_price
                            qty2 = notional2 / breakdown2.reference_price
                            blended_vwap = (
                                (breakdown1.expected_execution_price * qty1)
                                + (breakdown2.expected_execution_price * qty2)
                            ) / (qty1 + qty2)

                            c1 = CandidateRoute(
                                venue_id=v1,
                                allocation_pct=pct1,
                                allocated_notional=notional1,
                                allocated_quantity=qty1.quantize(
                                    Decimal("0.0001"), rounding=ROUND_HALF_UP
                                ),
                                expected_vwap=breakdown1.expected_execution_price,
                                breakdown=breakdown1,
                                is_eligible=True,
                                liquidity_available_usd=eligible_candidates[
                                    0
                                ].liquidity_available_usd,
                            )
                            c2 = CandidateRoute(
                                venue_id=v2,
                                allocation_pct=pct2,
                                allocated_notional=notional2,
                                allocated_quantity=qty2.quantize(
                                    Decimal("0.0001"), rounding=ROUND_HALF_UP
                                ),
                                expected_vwap=breakdown2.expected_execution_price,
                                breakdown=breakdown2,
                                is_eligible=True,
                                liquidity_available_usd=eligible_candidates[
                                    1
                                ].liquidity_available_usd,
                            )
                            best_plan_candidates = [c1, c2]

                            # Construct blended breakdown
                            blended_breakdown = CostBreakdown(
                                reference_price=breakdown1.reference_price,
                                expected_execution_price=blended_vwap.quantize(
                                    Decimal("0.01"), rounding=ROUND_HALF_UP
                                ),
                                spread_cost_bps=(
                                    (breakdown1.spread_cost_usd + breakdown2.spread_cost_usd)
                                    / order.notional_usd
                                    * Decimal("10000")
                                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                                spread_cost_usd=(
                                    breakdown1.spread_cost_usd + breakdown2.spread_cost_usd
                                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                                market_impact_bps=(
                                    (breakdown1.market_impact_usd + breakdown2.market_impact_usd)
                                    / order.notional_usd
                                    * Decimal("10000")
                                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                                market_impact_usd=(
                                    breakdown1.market_impact_usd + breakdown2.market_impact_usd
                                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                                trading_fee_bps=(
                                    (breakdown1.trading_fee_usd + breakdown2.trading_fee_usd)
                                    / order.notional_usd
                                    * Decimal("10000")
                                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                                trading_fee_usd=(
                                    breakdown1.trading_fee_usd + breakdown2.trading_fee_usd
                                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                                funding_cost_bps=(
                                    (breakdown1.funding_cost_usd + breakdown2.funding_cost_usd)
                                    / order.notional_usd
                                    * Decimal("10000")
                                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                                funding_cost_usd=(
                                    breakdown1.funding_cost_usd + breakdown2.funding_cost_usd
                                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                                transaction_cost_bps=(
                                    (
                                        breakdown1.transaction_cost_usd
                                        + breakdown2.transaction_cost_usd
                                    )
                                    / order.notional_usd
                                    * Decimal("10000")
                                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                                transaction_cost_usd=(
                                    breakdown1.transaction_cost_usd
                                    + breakdown2.transaction_cost_usd
                                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                                adverse_selection_bps=(
                                    (
                                        breakdown1.adverse_selection_usd
                                        + breakdown2.adverse_selection_usd
                                    )
                                    / order.notional_usd
                                    * Decimal("10000")
                                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                                adverse_selection_usd=(
                                    breakdown1.adverse_selection_usd
                                    + breakdown2.adverse_selection_usd
                                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                                total_cost_bps=split_total_cost_bps.quantize(
                                    Decimal("0.01"), rounding=ROUND_HALF_UP
                                ),
                                total_cost_usd=split_total_cost_usd.quantize(
                                    Decimal("0.01"), rounding=ROUND_HALF_UP
                                ),
                            )
                            break

        # 5. Build Structured Explainability
        final_explanation: Dict[str, Any] = {
            "decision": f"SPLIT_{best_plan_candidates[0].venue_id.value}_{best_plan_candidates[1].venue_id.value}"
            if is_split
            else f"SINGLE_{best_single.venue_id.value}",
            "order": f"{order.side.value} {order.symbol}, ${order.notional_usd:,.2f}",
            "expected_vwap": str(blended_vwap),
            "expected_total_cost_bps": str(blended_breakdown.total_cost_bps),
            "expected_total_cost_usd": str(blended_breakdown.total_cost_usd),
            "attribution": {
                "spread_cost_bps": str(blended_breakdown.spread_cost_bps),
                "market_impact_bps": str(blended_breakdown.market_impact_bps),
                "trading_fee_bps": str(blended_breakdown.trading_fee_bps),
                "funding_cost_bps": str(blended_breakdown.funding_cost_bps),
                "transaction_cost_bps": str(blended_breakdown.transaction_cost_bps),
                "adverse_selection_bps": str(blended_breakdown.adverse_selection_bps),
            },
            "why_chosen": (
                f"Split routing achieves lower blended market impact ({blended_breakdown.market_impact_bps} bps vs {best_single.breakdown.market_impact_bps} bps single venue)"
                if is_split
                else f"Lowest all-in cost ({best_single.breakdown.total_cost_bps} bps) with lowest slippage and fee overhead."
            ),
            "alternative_rejections": rejection_reasons,
            "data_freshness_sec": float(min([c.data_freshness_sec for c in candidates], default=0.0)),
            "confidence_score": 0.94 if not is_split else 0.91,
        }

        return RouteQuote(
            quote_id=quote_id,
            order_request=order,
            recommended_venue=best_plan_candidates[0].venue_id,
            is_split_route=is_split,
            candidates=candidates,
            allocations=best_plan_candidates,
            blended_vwap=blended_vwap,
            blended_breakdown=blended_breakdown,
            confidence_score=0.94,
            model_version="orion-v1.0-deterministic",
            freshness_sec=min((c.data_freshness_sec for c in candidates), default=0.0),
            quote_timestamp=now,
            expires_at=expires_at,
            explanation=final_explanation,
        )


execution_router = ExecutionRouter()
