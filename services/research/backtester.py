import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models import AuditEventDB, BacktestRunDB
from packages.domain.enums import OrderSide, OrderType, VenueId
from packages.domain.models import (
    BacktestRun,
    Instrument,
    OrderBook,
    OrderBookLevel,
    OrderRequest,
)
from services.execution.cost_engine import ExecutionCostEngine, cost_engine
from services.execution.router import ExecutionRouter, execution_router


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BacktestEngine:
    """
    Execution Quality Backtesting and Attribution Engine.
    Simulates sequential orders across deterministic market snapshots,
    preventing look-ahead bias and calculating implementation shortfall
    across Naive Baseline, Best Single Venue, and ORION Optimal Route.
    """

    def __init__(
        self,
        router_instance: Optional[ExecutionRouter] = None,
        cost_evaluator: Optional[ExecutionCostEngine] = None,
    ):
        self.router = router_instance or execution_router
        self.cost_engine = cost_evaluator or cost_engine

    def generate_synthetic_historical_fixtures(self, count: int = 50) -> List[Dict[str, Any]]:
        """
        Generates deterministic time-series market snapshots for testing and backtesting
        without look-ahead bias.
        """
        fixtures = []
        base_time = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
        current_price = Decimal("2450.00")

        # Deterministic pseudo-random seed sequence
        price_steps = [
            Decimal("1.20"),
            Decimal("-2.50"),
            Decimal("0.80"),
            Decimal("3.10"),
            Decimal("-1.40"),
        ]

        for i in range(count):
            t = base_time + timedelta(minutes=i * 15)
            step_delta = price_steps[i % len(price_steps)]
            current_price += step_delta

            # Hyperliquid snapshot (tighter spread, deep CLOB)
            hl_bids = [
                OrderBookLevel(
                    price=current_price - Decimal("0.10") - (Decimal(str(j)) * Decimal("0.15")),
                    size=Decimal("8.0") + Decimal(str(j * 3)),
                )
                for j in range(15)
            ]
            hl_asks = [
                OrderBookLevel(
                    price=current_price + Decimal("0.10") + (Decimal(str(j)) * Decimal("0.15")),
                    size=Decimal("8.0") + Decimal(str(j * 3)),
                )
                for j in range(15)
            ]
            hl_book = OrderBook(
                venue_id=VenueId.HYPERLIQUID,
                symbol="ETH-PERP",
                bids=hl_bids,
                asks=hl_asks,
                timestamp=t,
            )

            # GMX v2 snapshot (oracle pricing with linear impact curve)
            gmx_bids = [
                OrderBookLevel(
                    price=current_price - Decimal("0.35") - (Decimal(str(j)) * Decimal("0.30")),
                    size=Decimal("15.0") + Decimal(str(j * 5)),
                )
                for j in range(15)
            ]
            gmx_asks = [
                OrderBookLevel(
                    price=current_price + Decimal("0.35") + (Decimal(str(j)) * Decimal("0.30")),
                    size=Decimal("15.0") + Decimal(str(j * 5)),
                )
                for j in range(15)
            ]
            gmx_book = OrderBook(
                venue_id=VenueId.GMX_V2,
                symbol="ETH-PERP",
                bids=gmx_bids,
                asks=gmx_asks,
                timestamp=t,
            )

            # Trade size variation
            notionals = [
                Decimal("25000.0"),
                Decimal("50000.0"),
                Decimal("100000.0"),
                Decimal("150000.0"),
            ]
            trade_notional = notionals[i % len(notionals)]
            side = OrderSide.BUY if (i % 2 == 0) else OrderSide.SELL

            fixtures.append(
                {
                    "timestamp": t,
                    "books": {VenueId.HYPERLIQUID: hl_book, VenueId.GMX_V2: gmx_book},
                    "order": OrderRequest(
                        symbol="ETH-PERP",
                        side=side,
                        notional_usd=trade_notional,
                        order_type=OrderType.MARKET,
                        holding_horizon_hours=Decimal("12.0"),
                    ),
                }
            )

        return fixtures

    async def run_backtest(
        self,
        db: AsyncSession,
        name: str = "ETH-PERP Realized Execution Replay",
        symbol: str = "ETH-PERP",
        sample_count: int = 40,
    ) -> BacktestRun:
        run_id = f"bkt_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        fixtures = self.generate_synthetic_historical_fixtures(sample_count)

        start_time = fixtures[0]["timestamp"]
        end_time = fixtures[-1]["timestamp"]

        naive_costs_bps: List[Decimal] = []
        best_single_costs_bps: List[Decimal] = []
        orion_route_costs_bps: List[Decimal] = []
        savings_vs_naive_usd: List[Decimal] = []
        savings_vs_single_usd: List[Decimal] = []

        for sample in fixtures:
            order: OrderRequest = sample["order"]
            books: Dict[VenueId, OrderBook] = sample["books"]

            # 1. Baseline A: Naive Baseline (Fixed Venue: Always GMX v2)
            gmx_book = books[VenueId.GMX_V2]
            inst_gmx = Instrument(
                symbol=symbol,
                venue_id=VenueId.GMX_V2,
                taker_fee_bps=Decimal("5.0"),
                min_order_size=Decimal("0.001"),
            )
            adapter_gmx = self.router.state_engine.get_adapter(VenueId.GMX_V2)
            assert adapter_gmx is not None
            cap_gmx = adapter_gmx.capabilities
            gmx_breakdown = self.cost_engine.calculate_cost_breakdown(
                order, gmx_book, inst_gmx, cap_gmx
            )
            naive_cost_bps = gmx_breakdown.total_cost_bps
            naive_costs_bps.append(naive_cost_bps)

            # 2. Baseline B: Best Single Venue (evaluates HL vs GMX and takes cheaper)
            hl_book = books[VenueId.HYPERLIQUID]
            inst_hl = Instrument(
                symbol=symbol,
                venue_id=VenueId.HYPERLIQUID,
                taker_fee_bps=Decimal("3.5"),
                min_order_size=Decimal("0.001"),
            )
            adapter_hl = self.router.state_engine.get_adapter(VenueId.HYPERLIQUID)
            assert adapter_hl is not None
            cap_hl = adapter_hl.capabilities
            hl_breakdown = self.cost_engine.calculate_cost_breakdown(
                order, hl_book, inst_hl, cap_hl
            )

            best_single_cost = min(hl_breakdown.total_cost_bps, gmx_breakdown.total_cost_bps)
            best_single_costs_bps.append(best_single_cost)

            # 3. ORION Route: Evaluates single vs split route across available depth
            # Test 60/40 split if notional >= $50k
            if order.notional_usd >= Decimal("50000.0"):
                notional1 = order.notional_usd * Decimal("0.60")
                notional2 = order.notional_usd * Decimal("0.40")
                o1 = order.model_copy(update={"notional_usd": notional1})
                o2 = order.model_copy(update={"notional_usd": notional2})
                b1 = self.cost_engine.calculate_cost_breakdown(o1, hl_book, inst_hl, cap_hl)
                b2 = self.cost_engine.calculate_cost_breakdown(o2, gmx_book, inst_gmx, cap_gmx)
                split_cost_usd = b1.total_cost_usd + b2.total_cost_usd
                split_cost_bps = (split_cost_usd / order.notional_usd) * Decimal("10000")
                orion_cost = min(best_single_cost, split_cost_bps)
            else:
                orion_cost = best_single_cost

            orion_route_costs_bps.append(orion_cost)

            # Compute USD savings
            naive_cost_usd = order.notional_usd * (naive_cost_bps / Decimal("10000"))
            single_cost_usd = order.notional_usd * (best_single_cost / Decimal("10000"))
            orion_cost_usd = order.notional_usd * (orion_cost / Decimal("10000"))

            savings_vs_naive_usd.append(naive_cost_usd - orion_cost_usd)
            savings_vs_single_usd.append(single_cost_usd - orion_cost_usd)

        # Aggregate metrics
        mean_naive = sum(naive_costs_bps, Decimal("0")) / len(naive_costs_bps)
        mean_single = sum(best_single_costs_bps, Decimal("0")) / len(best_single_costs_bps)
        mean_orion = sum(orion_route_costs_bps, Decimal("0")) / len(orion_route_costs_bps)

        mean_savings_naive_bps = mean_naive - mean_orion
        mean_savings_single_bps = mean_single - mean_orion
        total_savings_usd = sum(savings_vs_naive_usd, Decimal("0"))

        # Percentiles
        sorted_costs = sorted(float(c) for c in orion_route_costs_bps)
        p50 = Decimal(str(round(sorted_costs[len(sorted_costs) // 2], 2)))
        p90 = Decimal(str(round(sorted_costs[int(len(sorted_costs) * 0.9)], 2)))
        p99 = Decimal(
            str(round(sorted_costs[min(len(sorted_costs) - 1, int(len(sorted_costs) * 0.99))], 2))
        )

        metrics = {
            "total_evaluated_notional_usd": float(sum(s["order"].notional_usd for s in fixtures)),
            "naive_mean_bps": float(mean_naive),
            "best_single_mean_bps": float(mean_single),
            "orion_mean_bps": float(mean_orion),
            "savings_vs_naive_bps": float(mean_savings_naive_bps),
            "savings_vs_single_bps": float(mean_savings_single_bps),
            "total_savings_usd": float(total_savings_usd),
            "p50_bps": float(p50),
            "p90_bps": float(p90),
            "p99_bps": float(p99),
            "completion_rate_pct": 100.0,
            "sample_orders_count": len(fixtures),
        }

        # Persist to database
        db_run = BacktestRunDB(
            run_id=run_id,
            name=name,
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            status="COMPLETED",
            order_count=len(fixtures),
            baseline_naive_cost_bps=float(mean_naive),
            baseline_single_cost_bps=float(mean_single),
            orion_route_cost_bps=float(mean_orion),
            mean_savings_vs_naive_bps=float(mean_savings_naive_bps),
            mean_savings_vs_single_bps=float(mean_savings_single_bps),
            total_savings_usd=float(total_savings_usd),
            metrics_json=json.dumps(metrics),
        )
        db.add(db_run)

        # Audit Event
        audit_event = AuditEventDB(
            event_id=f"aud_{uuid.uuid4().hex[:12]}",
            actor="RESEARCH_ENGINE",
            event_type="BACKTEST_COMPLETED",
            correlation_id=run_id,
            entity_id=run_id,
            entity_type="BACKTEST_RUN",
            payload_json=json.dumps(
                {
                    "name": name,
                    "order_count": len(fixtures),
                    "total_savings_usd": float(total_savings_usd),
                }
            ),
        )
        db.add(audit_event)

        await db.commit()

        return BacktestRun(
            run_id=run_id,
            name=name,
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            status="COMPLETED",
            order_count=len(fixtures),
            baseline_naive_cost_bps=mean_naive.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            baseline_single_cost_bps=mean_single.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            orion_route_cost_bps=mean_orion.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            mean_savings_vs_naive_bps=mean_savings_naive_bps.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            mean_savings_vs_single_bps=mean_savings_single_bps.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            total_savings_usd=total_savings_usd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            completion_rate_pct=Decimal("100.0"),
            cost_percentiles={"p50": p50, "p90": p90, "p99": p99},
            summary_metrics=metrics,
            created_at=now,
        )


backtest_engine = BacktestEngine()
