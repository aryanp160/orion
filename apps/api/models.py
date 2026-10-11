from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    String,
    Float,
    Integer,
    DateTime,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from apps.api.database import Base

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class PaperAccountDB(Base):
    __tablename__ = "paper_accounts"

    account_id: Mapped[str] = mapped_column(String(64), primary_key=True, default="PAPER_DEFAULT")
    equity_usd: Mapped[float] = mapped_column(Float, nullable=False, default=100000.0)
    available_margin_usd: Mapped[float] = mapped_column(Float, nullable=False, default=100000.0)
    used_margin_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    realized_pnl_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unrealized_pnl_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    initial_balance: Mapped[float] = mapped_column(Float, nullable=False, default=100000.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    positions: Mapped[List["PaperPositionDB"]] = relationship("PaperPositionDB", back_populates="account", cascade="all, delete-orphan")

class PaperOrderDB(Base):
    __tablename__ = "paper_orders"

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    requested_notional: Mapped[float] = mapped_column(Float, nullable=False)
    requested_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    filled_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    filled_notional: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    remaining_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    avg_fill_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_fee_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    slippage_bps: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING", index=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    fills: Mapped[List["PaperFillDB"]] = relationship("PaperFillDB", back_populates="order", cascade="all, delete-orphan")

class PaperFillDB(Base):
    __tablename__ = "paper_fills"

    fill_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), ForeignKey("paper_orders.order_id"), nullable=False, index=True)
    venue_id: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    fill_price: Mapped[float] = mapped_column(Float, nullable=False)
    fill_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    fill_notional: Mapped[float] = mapped_column(Float, nullable=False)
    fee_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fee_bps: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="TAKER")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    order: Mapped["PaperOrderDB"] = relationship("PaperOrderDB", back_populates="fills")

class PaperPositionDB(Base):
    __tablename__ = "paper_positions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), ForeignKey("paper_accounts.account_id"), nullable=False, default="PAPER_DEFAULT")
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    venue_id: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    mark_price: Mapped[float] = mapped_column(Float, nullable=False)
    notional_usd: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    margin_allocated: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    leverage: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    liquidation_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    account: Mapped["PaperAccountDB"] = relationship("PaperAccountDB", back_populates="positions")

class RouteQuoteDB(Base):
    __tablename__ = "route_quotes"

    quote_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    notional_usd: Mapped[float] = mapped_column(Float, nullable=False)
    recommended_venue: Mapped[str] = mapped_column(String(32), nullable=False)
    blended_vwap: Mapped[float] = mapped_column(Float, nullable=False)
    total_cost_bps: Mapped[float] = mapped_column(Float, nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class BacktestRunDB(Base):
    __tablename__ = "backtest_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="COMPLETED")
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    baseline_naive_cost_bps: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    baseline_single_cost_bps: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    orion_route_cost_bps: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    mean_savings_vs_naive_bps: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    mean_savings_vs_single_bps: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_savings_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

class AuditEventDB(Base):
    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="SYSTEM")
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

class RiskAssessmentDB(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_notional: Mapped[float] = mapped_column(Float, nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    flags_json: Mapped[str] = mapped_column(Text, nullable=False)
    checks_json: Mapped[str] = mapped_column(Text, nullable=False)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
