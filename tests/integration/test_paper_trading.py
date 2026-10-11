from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.database import Base
from packages.domain.enums import OrderSide, OrderStatus, OrderType, VenueId
from packages.domain.models import OrderRequest
from services.execution.paper_trading import PaperTradingEngine


@pytest.fixture
async def test_db_session():
    # In-memory SQLite for isolated integration testing
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_paper_trading_lifecycle(test_db_session):
    engine = PaperTradingEngine()

    # 1. Check Initial Account
    account = await engine.get_account_summary(test_db_session, "TEST_ACC")
    assert account.equity_usd == Decimal("100000.00")
    assert len(account.positions) == 0

    # 2. Submit Buy Order
    order_buy = OrderRequest(
        symbol="ETH-PERP",
        side=OrderSide.BUY,
        notional_usd=Decimal("25000.00"),
        order_type=OrderType.MARKET,
    )
    report_buy = await engine.submit_paper_order(
        db=test_db_session,
        order=order_buy,
        venue_id=VenueId.MOCK_CLOB,
        account_id="TEST_ACC",
    )

    assert report_buy.status == OrderStatus.FILLED
    assert report_buy.filled_quantity > Decimal("0")
    assert report_buy.total_fee_usd > Decimal("0")
    assert len(report_buy.fills) == 1

    # 3. Check Position Created
    account_after = await engine.get_account_summary(test_db_session, "TEST_ACC")
    assert len(account_after.positions) == 1
    pos = account_after.positions[0]
    assert pos.symbol == "ETH-PERP"
    assert pos.side == OrderSide.BUY
    assert pos.quantity.quantize(Decimal("0.0001")) == report_buy.filled_quantity.quantize(
        Decimal("0.0001")
    )

    # 4. Submit Sell Order to Close Position
    order_sell = OrderRequest(
        symbol="ETH-PERP",
        side=OrderSide.SELL,
        notional_usd=Decimal("25000.00"),
        order_type=OrderType.MARKET,
    )
    report_sell = await engine.submit_paper_order(
        db=test_db_session,
        order=order_sell,
        venue_id=VenueId.MOCK_CLOB,
        account_id="TEST_ACC",
    )
    assert report_sell.status == OrderStatus.FILLED

    # 5. Check Reset
    reset_acc = await engine.reset_paper_account(test_db_session, "TEST_ACC")
    assert len(reset_acc.positions) == 0
    assert reset_acc.equity_usd == Decimal("100000.00")
