from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.database import Base
from services.research.backtester import BacktestEngine


@pytest.fixture
async def test_db_session():
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
async def test_backtest_engine_run(test_db_session):
    engine = BacktestEngine()
    run = await engine.run_backtest(
        db=test_db_session,
        name="Test Replay Run",
        symbol="ETH-PERP",
        sample_count=20,
    )

    assert run.run_id.startswith("bkt_")
    assert run.status == "COMPLETED"
    assert run.order_count == 20
    assert run.completion_rate_pct == Decimal("100.0")
    # ORION route cost must be <= naive baseline cost
    assert run.orion_route_cost_bps <= run.baseline_naive_cost_bps
    assert run.mean_savings_vs_naive_bps >= Decimal("0.0")
    assert "p50" in run.cost_percentiles
    assert "p90" in run.cost_percentiles
