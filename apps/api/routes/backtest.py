import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import BacktestRunDB
from packages.domain.models import BacktestRun
from services.research.backtester import backtest_engine

router = APIRouter(prefix="/api/v1/backtests", tags=["Research & Backtesting"])


class BacktestRequest(BaseModel):
    name: str = "ETH-PERP Execution Quality Replay"
    symbol: str = "ETH-PERP"
    sample_count: int = 40


@router.post("", response_model=BacktestRun)
async def create_backtest_run(
    payload: BacktestRequest, db: AsyncSession = Depends(get_db)
) -> BacktestRun:
    return await backtest_engine.run_backtest(
        db=db,
        name=payload.name,
        symbol=payload.symbol,
        sample_count=payload.sample_count,
    )


@router.get("")
async def list_backtest_runs(
    limit: int = Query(50, ge=1, le=100), db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    query = select(BacktestRunDB).order_by(desc(BacktestRunDB.created_at)).limit(limit)
    res = await db.execute(query)
    runs = res.scalars().all()
    return [
        {
            "run_id": r.run_id,
            "name": r.name,
            "symbol": r.symbol,
            "start_time": r.start_time,
            "end_time": r.end_time,
            "status": r.status,
            "order_count": r.order_count,
            "baseline_naive_cost_bps": r.baseline_naive_cost_bps,
            "baseline_single_cost_bps": r.baseline_single_cost_bps,
            "orion_route_cost_bps": r.orion_route_cost_bps,
            "mean_savings_vs_naive_bps": r.mean_savings_vs_naive_bps,
            "mean_savings_vs_single_bps": r.mean_savings_vs_single_bps,
            "total_savings_usd": r.total_savings_usd,
            "created_at": r.created_at,
        }
        for r in runs
    ]


@router.get("/{run_id}")
async def get_backtest_run(run_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    res = await db.execute(select(BacktestRunDB).where(BacktestRunDB.run_id == run_id))
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail=f"Backtest run {run_id} not found")

    metrics = json.loads(r.metrics_json) if r.metrics_json else {}
    return {
        "run_id": r.run_id,
        "name": r.name,
        "symbol": r.symbol,
        "start_time": r.start_time,
        "end_time": r.end_time,
        "status": r.status,
        "order_count": r.order_count,
        "baseline_naive_cost_bps": r.baseline_naive_cost_bps,
        "baseline_single_cost_bps": r.baseline_single_cost_bps,
        "orion_route_cost_bps": r.orion_route_cost_bps,
        "mean_savings_vs_naive_bps": r.mean_savings_vs_naive_bps,
        "mean_savings_vs_single_bps": r.mean_savings_vs_single_bps,
        "total_savings_usd": r.total_savings_usd,
        "metrics": metrics,
        "created_at": r.created_at,
    }


@router.get("/{run_id}/attribution")
async def get_backtest_attribution(
    run_id: str, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    res = await db.execute(select(BacktestRunDB).where(BacktestRunDB.run_id == run_id))
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail=f"Backtest run {run_id} not found")

    metrics = json.loads(r.metrics_json) if r.metrics_json else {}
    return {
        "run_id": r.run_id,
        "attribution": {
            "naive_baseline_cost_bps": r.baseline_naive_cost_bps,
            "best_single_cost_bps": r.baseline_single_cost_bps,
            "orion_optimized_cost_bps": r.orion_route_cost_bps,
            "savings_vs_naive_bps": r.mean_savings_vs_naive_bps,
            "savings_vs_single_bps": r.mean_savings_vs_single_bps,
            "total_savings_usd": r.total_savings_usd,
            "p50_cost_bps": metrics.get("p50_bps", 0.0),
            "p90_cost_bps": metrics.get("p90_bps", 0.0),
            "p99_cost_bps": metrics.get("p99_bps", 0.0),
        },
        "order_count": r.order_count,
        "sample_evaluated_notional": metrics.get("total_evaluated_notional_usd", 0.0),
    }
