import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models import (
    AuditEventDB,
    PaperAccountDB,
    PaperFillDB,
    PaperOrderDB,
    PaperPositionDB,
)
from packages.domain.enums import (
    LiquidityRole,
    OrderSide,
    OrderStatus,
    RiskOutcome,
    VenueId,
)
from packages.domain.models import (
    ExecutionReport,
    Fill,
    OrderRequest,
    PaperAccount,
    PaperPosition,
)
from services.execution.cost_engine import ExecutionCostEngine, cost_engine
from services.execution.risk_engine import RiskEngine, risk_engine
from services.market_data.state_engine import MarketStateEngine, market_state_engine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PaperTradingEngine:
    """
    Deterministic Institutional Paper Trading Engine.
    Executes simulated orders against actual market depth, tracks real-time PnL,
    calculates maker/taker fees, manages multi-fill order lifecycle, and persists state in SQLite/PostgreSQL.
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

    async def get_or_create_account(
        self, db: AsyncSession, account_id: str = "PAPER_DEFAULT"
    ) -> PaperAccountDB:
        result = await db.execute(
            select(PaperAccountDB).where(PaperAccountDB.account_id == account_id)
        )
        account = result.scalar_one_or_none()
        if not account:
            account = PaperAccountDB(
                account_id=account_id,
                equity_usd=100000.0,
                available_margin_usd=100000.0,
                used_margin_usd=0.0,
                realized_pnl_usd=0.0,
                unrealized_pnl_usd=0.0,
                initial_balance=100000.0,
            )
            db.add(account)
            await db.commit()
            await db.refresh(account)
        return account

    async def get_account_summary(
        self, db: AsyncSession, account_id: str = "PAPER_DEFAULT"
    ) -> PaperAccount:
        account_db = await self.get_or_create_account(db, account_id)

        # Load positions
        pos_result = await db.execute(
            select(PaperPositionDB).where(PaperPositionDB.account_id == account_id)
        )
        positions_db = pos_result.scalars().all()

        # Update real-time mark prices and unrealized PnL
        total_unrealized_pnl = Decimal("0.0")
        total_used_margin = Decimal("0.0")
        positions_list: List[PaperPosition] = []

        for p in positions_db:
            # Poll current mark price
            adapter = self.state_engine.get_adapter(VenueId(p.venue_id))
            mark_px = Decimal(str(p.mark_price))
            if adapter:
                try:
                    mp = await adapter.fetch_mark_price(p.symbol)
                    mark_px = mp.mark_price
                    p.mark_price = float(mark_px)
                except Exception:
                    pass

            entry_px = Decimal(str(p.entry_price))
            qty = Decimal(str(p.quantity))
            notional = qty * mark_px
            p.notional_usd = float(notional)

            # Unrealized PnL
            if p.side == OrderSide.BUY.value:
                u_pnl = (mark_px - entry_px) * qty
            else:
                u_pnl = (entry_px - mark_px) * qty

            p.unrealized_pnl = float(u_pnl)
            total_unrealized_pnl += u_pnl
            margin_for_pos = notional / Decimal(str(p.leverage or 1.0))
            p.margin_allocated = float(margin_for_pos)
            total_used_margin += margin_for_pos

            positions_list.append(
                PaperPosition(
                    symbol=p.symbol,
                    venue_id=VenueId(p.venue_id),
                    side=OrderSide(p.side),
                    quantity=qty,
                    entry_price=entry_px,
                    mark_price=mark_px,
                    notional_usd=notional,
                    unrealized_pnl=u_pnl.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    realized_pnl=Decimal(str(p.realized_pnl)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    margin_allocated=margin_for_pos.quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    leverage=Decimal(str(p.leverage or 1.0)),
                    liquidation_price=Decimal(str(p.liquidation_price))
                    if p.liquidation_price
                    else None,
                    updated_at=p.updated_at or utc_now(),
                )
            )

        # Update account balances
        init_bal = Decimal(str(account_db.initial_balance))
        realized_pnl = Decimal(str(account_db.realized_pnl_usd))
        current_equity = init_bal + realized_pnl + total_unrealized_pnl
        avail_margin = max(Decimal("0.0"), current_equity - total_used_margin)

        account_db.equity_usd = float(current_equity)
        account_db.available_margin_usd = float(avail_margin)
        account_db.used_margin_usd = float(total_used_margin)
        account_db.unrealized_pnl_usd = float(total_unrealized_pnl)
        await db.commit()

        # Count total orders and fills
        orders_cnt_res = await db.execute(select(PaperOrderDB.order_id))
        fills_cnt_res = await db.execute(select(PaperFillDB.fill_id))

        return PaperAccount(
            account_id=account_id,
            equity_usd=current_equity.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            available_margin_usd=avail_margin.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            used_margin_usd=total_used_margin.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            realized_pnl_usd=realized_pnl.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            unrealized_pnl_usd=total_unrealized_pnl.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            initial_balance=init_bal,
            total_orders_count=len(orders_cnt_res.scalars().all()),
            total_fills_count=len(fills_cnt_res.scalars().all()),
            positions=positions_list,
            updated_at=utc_now(),
        )

    async def submit_paper_order(
        self,
        db: AsyncSession,
        order: OrderRequest,
        venue_id: VenueId = VenueId.HYPERLIQUID,
        account_id: str = "PAPER_DEFAULT",
    ) -> ExecutionReport:
        order_id = f"ord_{uuid.uuid4().hex[:12]}"

        # 1. Evaluate Pre-Trade Risk
        adapter = self.state_engine.get_adapter(venue_id) or self.state_engine.get_adapter(
            VenueId.MOCK_CLOB
        )
        assert adapter is not None
        book = await adapter.fetch_order_book(order.symbol)
        health = await adapter.check_health(order.symbol)
        inst = await adapter.get_instrument(order.symbol)

        account_db = await self.get_or_create_account(db, account_id)

        # Check concurrent orders
        open_orders_res = await db.execute(
            select(PaperOrderDB).where(
                PaperOrderDB.status.in_(["PENDING", "OPEN", "PARTIALLY_FILLED"])
            )
        )
        open_orders_count = len(open_orders_res.scalars().all())

        # Total position exposure
        positions_res = await db.execute(
            select(PaperPositionDB.notional_usd).where(PaperPositionDB.account_id == account_id)
        )
        total_pos_notional = Decimal(str(sum(positions_res.scalars().all())))

        risk_eval = self.risk_engine.evaluate_order(
            order=order,
            current_book=book,
            health=health,
            current_position_notional=total_pos_notional,
            concurrent_open_orders=open_orders_count,
        )

        if risk_eval.outcome == RiskOutcome.BLOCK:
            # Create REJECTED order record
            rej_order = PaperOrderDB(
                order_id=order_id,
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                side=order.side.value,
                order_type=order.order_type.value,
                requested_notional=float(order.notional_usd),
                requested_quantity=float(order.notional_usd / (book.mid_price or Decimal("2500"))),
                filled_quantity=0.0,
                filled_notional=0.0,
                remaining_quantity=float(order.notional_usd / (book.mid_price or Decimal("2500"))),
                status=OrderStatus.REJECTED.value,
                rejection_reason=risk_eval.rejection_reason,
            )
            db.add(rej_order)
            await db.commit()

            return ExecutionReport(
                report_id=f"rep_{uuid.uuid4().hex[:10]}",
                order_id=order_id,
                client_order_id=order.client_order_id,
                status=OrderStatus.REJECTED,
                symbol=order.symbol,
                side=order.side,
                order_type=order.order_type,
                requested_notional=order.notional_usd,
                requested_quantity=(
                    order.notional_usd / (book.mid_price or Decimal("2500"))
                ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
                remaining_quantity=(
                    order.notional_usd / (book.mid_price or Decimal("2500"))
                ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
                rejection_reason=risk_eval.rejection_reason,
            )

        # 2. Simulate Order Execution against Order Book Depth
        arrival_mid = book.mid_price or Decimal("2500.00")
        expected_vwap, fillable_notional, fillable_qty, is_fully_fillable = (
            self.cost_engine.walk_order_book(
                book=book,
                side=order.side,
                required_notional=order.notional_usd,
                arrival_mid=arrival_mid,
            )
        )

        # Calculate slippage vs arrival price
        if order.side == OrderSide.BUY:
            slippage_bps = ((expected_vwap - arrival_mid) / arrival_mid) * Decimal("10000")
        else:
            slippage_bps = ((arrival_mid - expected_vwap) / arrival_mid) * Decimal("10000")

        # Maker/Taker fee calculation
        taker_fee_bps = inst.taker_fee_bps if inst else Decimal("3.5")
        fee_usd = (fillable_notional * (taker_fee_bps / Decimal("10000"))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        order_status = OrderStatus.FILLED if is_fully_fillable else OrderStatus.PARTIALLY_FILLED
        req_qty = (order.notional_usd / arrival_mid).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        rem_qty = max(Decimal("0.0"), req_qty - fillable_qty).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

        # Create Order record
        order_db = PaperOrderDB(
            order_id=order_id,
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side.value,
            order_type=order.order_type.value,
            requested_notional=float(order.notional_usd),
            requested_quantity=float(req_qty),
            filled_quantity=float(fillable_qty),
            filled_notional=float(fillable_notional),
            remaining_quantity=float(rem_qty),
            avg_fill_price=float(expected_vwap),
            total_fee_usd=float(fee_usd),
            slippage_bps=float(slippage_bps),
            status=order_status.value,
        )
        db.add(order_db)

        # Create Fill record
        fill_id = f"fil_{uuid.uuid4().hex[:12]}"
        fill_db = PaperFillDB(
            fill_id=fill_id,
            order_id=order_id,
            venue_id=venue_id.value,
            symbol=order.symbol,
            side=order.side.value,
            fill_price=float(expected_vwap),
            fill_quantity=float(fillable_qty),
            fill_notional=float(fillable_notional),
            fee_usd=float(fee_usd),
            fee_bps=float(taker_fee_bps),
            role=LiquidityRole.TAKER.value,
        )
        db.add(fill_db)

        # 3. Update Position & PnL Accounting
        pos_id = f"pos_{account_id}_{venue_id.value}_{order.symbol}"
        pos_query = await db.execute(select(PaperPositionDB).where(PaperPositionDB.id == pos_id))
        pos_db = pos_query.scalar_one_or_none()

        if not pos_db:
            # Open new position
            pos_db = PaperPositionDB(
                id=pos_id,
                account_id=account_id,
                symbol=order.symbol,
                venue_id=venue_id.value,
                side=order.side.value,
                quantity=float(fillable_qty),
                entry_price=float(expected_vwap),
                mark_price=float(arrival_mid),
                notional_usd=float(fillable_notional),
                unrealized_pnl=0.0,
                realized_pnl=-float(fee_usd),  # Deduct fees
                margin_allocated=float(fillable_notional / Decimal("10.0")),  # 10x leverage default
                leverage=10.0,
            )
            db.add(pos_db)
        else:
            # Existing position: compute blended entry or realized PnL on reduction/reversal
            existing_qty = Decimal(str(pos_db.quantity))
            existing_side = OrderSide(pos_db.side)
            existing_entry = Decimal(str(pos_db.entry_price))

            if existing_side == order.side:
                # Add to existing position
                new_qty = existing_qty + fillable_qty
                blended_entry = (
                    (existing_entry * existing_qty) + (expected_vwap * fillable_qty)
                ) / new_qty
                pos_db.quantity = float(new_qty)
                pos_db.entry_price = float(blended_entry)
                pos_db.notional_usd = float(new_qty * arrival_mid)
                pos_db.realized_pnl -= float(fee_usd)
            else:
                # Reducing or reversing position
                if fillable_qty <= existing_qty:
                    # Partial close
                    realized = (
                        (expected_vwap - existing_entry)
                        if existing_side == OrderSide.BUY
                        else (existing_entry - expected_vwap)
                    ) * fillable_qty
                    rem_pos_qty = existing_qty - fillable_qty
                    pos_db.quantity = float(rem_pos_qty)
                    pos_db.notional_usd = float(rem_pos_qty * arrival_mid)
                    pos_db.realized_pnl += float(realized - fee_usd)
                    account_db.realized_pnl_usd += float(realized - fee_usd)
                else:
                    # Full close and flip
                    flip_qty = fillable_qty - existing_qty
                    realized = (
                        (expected_vwap - existing_entry)
                        if existing_side == OrderSide.BUY
                        else (existing_entry - expected_vwap)
                    ) * existing_qty
                    pos_db.side = order.side.value
                    pos_db.quantity = float(flip_qty)
                    pos_db.entry_price = float(expected_vwap)
                    pos_db.notional_usd = float(flip_qty * arrival_mid)
                    pos_db.realized_pnl += float(realized - fee_usd)
                    account_db.realized_pnl_usd += float(realized - fee_usd)

        # Audit event
        audit_event = AuditEventDB(
            event_id=f"aud_{uuid.uuid4().hex[:12]}",
            actor="PAPER_TRADER",
            event_type="PAPER_ORDER_EXECUTED",
            correlation_id=order_id,
            entity_id=order_id,
            entity_type="ORDER",
            payload_json=f'{{"status":"{order_status.value}","filled_notional":{fillable_notional},"vwap":{expected_vwap},"fee_usd":{fee_usd}}}',
        )
        db.add(audit_event)

        await db.commit()

        fill_domain = Fill(
            fill_id=fill_id,
            order_id=order_id,
            venue_id=venue_id,
            symbol=order.symbol,
            side=order.side,
            fill_price=expected_vwap,
            fill_quantity=fillable_qty,
            fill_notional=fillable_notional,
            fee_usd=fee_usd,
            fee_bps=taker_fee_bps,
            role=LiquidityRole.TAKER,
            simulated=True,
        )

        return ExecutionReport(
            report_id=f"rep_{uuid.uuid4().hex[:10]}",
            order_id=order_id,
            client_order_id=order.client_order_id,
            status=order_status,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            requested_notional=order.notional_usd,
            requested_quantity=req_qty,
            filled_quantity=fillable_qty,
            filled_notional=fillable_notional,
            remaining_quantity=rem_qty,
            avg_fill_price=expected_vwap,
            total_fee_usd=fee_usd,
            slippage_bps=slippage_bps.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            fills=[fill_domain],
        )

    async def cancel_paper_order(self, db: AsyncSession, order_id: str) -> bool:
        result = await db.execute(select(PaperOrderDB).where(PaperOrderDB.order_id == order_id))
        order_db = result.scalar_one_or_none()
        if not order_db or order_db.status in ["FILLED", "CANCELLED", "REJECTED"]:
            return False

        order_db.status = OrderStatus.CANCELLED.value
        await db.commit()
        return True

    async def reset_paper_account(
        self, db: AsyncSession, account_id: str = "PAPER_DEFAULT"
    ) -> PaperAccount:
        account_db = await self.get_or_create_account(db, account_id)
        # Delete positions
        pos_res = await db.execute(
            select(PaperPositionDB).where(PaperPositionDB.account_id == account_id)
        )
        for p in pos_res.scalars().all():
            await db.delete(p)

        account_db.equity_usd = float(account_db.initial_balance)
        account_db.available_margin_usd = float(account_db.initial_balance)
        account_db.used_margin_usd = 0.0
        account_db.realized_pnl_usd = 0.0
        account_db.unrealized_pnl_usd = 0.0

        await db.commit()
        return await self.get_account_summary(db, account_id)


paper_trading_engine = PaperTradingEngine()
