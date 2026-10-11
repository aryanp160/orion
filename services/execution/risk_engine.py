import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from apps.api.config import settings
from packages.domain.enums import RiskOutcome
from packages.domain.models import (
    MarketDataHealth,
    OrderBook,
    OrderRequest,
    RiskAssessment,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RiskEngine:
    """
    Deterministic Pre-Trade Institutional Risk Engine.
    Operates independently of the execution router.
    Evaluates hard safety limits and produces typed PASS, WARN, or BLOCK assessments.
    Enforces fail-closed behavior on data outages or stale quotes.
    """

    def __init__(self):
        self._seen_client_order_ids: Dict[
            str, float
        ] = {}  # idempotency tracking: client_id -> timestamp
        self._kill_switch_active: bool = settings.ORION_KILL_SWITCH_ACTIVE

    def set_kill_switch(self, active: bool):
        self._kill_switch_active = active

    @property
    def is_kill_switch_active(self) -> bool:
        return self._kill_switch_active

    def evaluate_order(
        self,
        order: OrderRequest,
        current_book: Optional[OrderBook] = None,
        health: Optional[MarketDataHealth] = None,
        current_position_notional: Decimal = Decimal("0.0"),
        concurrent_open_orders: int = 0,
    ) -> RiskAssessment:
        flags: List[str] = []
        checks: Dict[str, Dict[str, Any]] = {}
        now = utc_now()

        # 1. Kill Switch Check
        if self._kill_switch_active:
            flags.append("KILL_SWITCH_ACTIVE")
            checks["kill_switch"] = {
                "passed": False,
                "reason": "Emergency kill switch is actively engaged.",
            }
            return RiskAssessment(
                outcome=RiskOutcome.BLOCK,
                symbol=order.symbol,
                requested_notional=order.notional_usd,
                flags=flags,
                checks=checks,
                rejection_reason="Emergency kill switch engaged. Trading halted.",
                timestamp=now,
            )
        else:
            checks["kill_switch"] = {"passed": True}

        # 2. Idempotency / Duplicate Check
        if order.client_order_id:
            last_seen = self._seen_client_order_ids.get(order.client_order_id)
            if last_seen and (time.time() - last_seen) < 120.0:  # 2 minute deduplication window
                flags.append("DUPLICATE_CLIENT_ORDER_ID")
                checks["idempotency"] = {"passed": False, "client_order_id": order.client_order_id}
                return RiskAssessment(
                    outcome=RiskOutcome.BLOCK,
                    symbol=order.symbol,
                    requested_notional=order.notional_usd,
                    flags=flags,
                    checks=checks,
                    rejection_reason=f"Duplicate order detected with client_order_id={order.client_order_id}",
                    timestamp=now,
                )
            self._seen_client_order_ids[order.client_order_id] = time.time()
            checks["idempotency"] = {"passed": True}

        # 3. Maximum Order Notional
        max_notional = Decimal(str(settings.ORION_MAX_ORDER_NOTIONAL))
        if order.notional_usd > max_notional:
            flags.append("MAX_ORDER_NOTIONAL_EXCEEDED")
            checks["order_notional"] = {
                "passed": False,
                "requested": float(order.notional_usd),
                "limit": float(max_notional),
            }
            return RiskAssessment(
                outcome=RiskOutcome.BLOCK,
                symbol=order.symbol,
                requested_notional=order.notional_usd,
                flags=flags,
                checks=checks,
                rejection_reason=f"Order notional ${order.notional_usd} exceeds limit ${max_notional}",
                timestamp=now,
            )
        checks["order_notional"] = {
            "passed": True,
            "requested": float(order.notional_usd),
            "limit": float(max_notional),
        }

        # 4. Total Aggregate Position Exposure
        max_exposure = Decimal(str(settings.ORION_MAX_POSITION_EXPOSURE))
        projected_exposure = current_position_notional + order.notional_usd
        if projected_exposure > max_exposure:
            flags.append("MAX_POSITION_EXPOSURE_EXCEEDED")
            checks["position_exposure"] = {
                "passed": False,
                "projected": float(projected_exposure),
                "limit": float(max_exposure),
            }
            return RiskAssessment(
                outcome=RiskOutcome.BLOCK,
                symbol=order.symbol,
                requested_notional=order.notional_usd,
                flags=flags,
                checks=checks,
                rejection_reason=f"Projected exposure ${projected_exposure} exceeds max portfolio exposure ${max_exposure}",
                timestamp=now,
            )
        checks["position_exposure"] = {
            "passed": True,
            "projected": float(projected_exposure),
            "limit": float(max_exposure),
        }

        # 5. Concurrent Open Orders Limit
        if concurrent_open_orders >= settings.ORION_MAX_CONCURRENT_ORDERS:
            flags.append("MAX_CONCURRENT_ORDERS_REACHED")
            checks["concurrent_orders"] = {
                "passed": False,
                "current": concurrent_open_orders,
                "limit": settings.ORION_MAX_CONCURRENT_ORDERS,
            }
            return RiskAssessment(
                outcome=RiskOutcome.BLOCK,
                symbol=order.symbol,
                requested_notional=order.notional_usd,
                flags=flags,
                checks=checks,
                rejection_reason=f"Concurrent open orders ({concurrent_open_orders}) exceeds limit {settings.ORION_MAX_CONCURRENT_ORDERS}",
                timestamp=now,
            )
        checks["concurrent_orders"] = {"passed": True, "current": concurrent_open_orders}

        # 6. Market Data Staleness & Health Check (Fail-Closed)
        if health and (
            not health.is_healthy or health.staleness_sec > settings.ORION_STALENESS_THRESHOLD_SEC
        ):
            flags.append("MARKET_DATA_STALE_OR_UNHEALTHY")
            checks["market_health"] = {
                "passed": False,
                "staleness_sec": health.staleness_sec,
                "status": health.status_message,
            }
            return RiskAssessment(
                outcome=RiskOutcome.BLOCK,
                symbol=order.symbol,
                requested_notional=order.notional_usd,
                flags=flags,
                checks=checks,
                rejection_reason=f"Venue data stale ({health.staleness_sec}s > {settings.ORION_STALENESS_THRESHOLD_SEC}s) or unhealthy",
                timestamp=now,
            )
        checks["market_health"] = {"passed": True}

        # 7. Price Collar (if limit order or price collar applies)
        if current_book and current_book.mid_price and order.limit_price:
            collar_bps = Decimal(str(settings.ORION_PRICE_COLLAR_BPS))
            mid = current_book.mid_price
            price_dev_bps = (abs(order.limit_price - mid) / mid) * Decimal("10000")
            if price_dev_bps > collar_bps:
                flags.append("PRICE_COLLAR_BREACH")
                checks["price_collar"] = {
                    "passed": False,
                    "deviation_bps": float(price_dev_bps),
                    "limit_bps": float(collar_bps),
                }
                return RiskAssessment(
                    outcome=RiskOutcome.BLOCK,
                    symbol=order.symbol,
                    requested_notional=order.notional_usd,
                    flags=flags,
                    checks=checks,
                    rejection_reason=f"Limit price dev {price_dev_bps:.1f} bps breaches collar {collar_bps:.1f} bps",
                    timestamp=now,
                )
        checks["price_collar"] = {"passed": True}

        # 8. User Slippage Constraint Warning Check
        if order.max_slippage_bps > Decimal(str(settings.ORION_MAX_PERMITTED_SLIPPAGE_BPS)):
            flags.append("HIGH_SLIPPAGE_TOLERANCE")
            checks["slippage_tolerance"] = {
                "passed": True,
                "warning": f"Configured slippage {order.max_slippage_bps} bps is unusually high.",
            }
            return RiskAssessment(
                outcome=RiskOutcome.WARN,
                symbol=order.symbol,
                requested_notional=order.notional_usd,
                flags=flags,
                checks=checks,
                timestamp=now,
            )

        checks["slippage_tolerance"] = {"passed": True}

        return RiskAssessment(
            outcome=RiskOutcome.PASS,
            symbol=order.symbol,
            requested_notional=order.notional_usd,
            flags=flags,
            checks=checks,
            timestamp=now,
        )


risk_engine = RiskEngine()
