import asyncio
from apps.api.database import init_db, AsyncSessionLocal
from services.research.backtester import backtest_engine

async def main():
    print("=== ORION Execution Intelligence: Backtest & Attribution Demo ===")
    await init_db()

    async with AsyncSessionLocal() as session:
        print("\n1. Launching sequential backtest execution replay (50 samples)...")
        run = await backtest_engine.run_backtest(
            db=session,
            name="ETH-PERP Quantitative Attribution Benchmark",
            symbol="ETH-PERP",
            sample_count=50,
        )

        print(f"\n2. Run Results [ID: {run.run_id}]:")
        print(f"   Evaluated Orders: {run.order_count}")
        print(f"   Order Completion Rate: {run.completion_rate_pct}%")
        print("\n3. Cost Model Comparison (Basis Points):")
        print(f"   - Naive Baseline (Fixed Single Venue): {run.baseline_naive_cost_bps:.2f} bps")
        print(f"   - Best Single Venue:                 {run.baseline_single_cost_bps:.2f} bps")
        print(f"   - ORION Optimized Route:             {run.orion_route_cost_bps:.2f} bps")
        print("\n4. Execution Alpha & Savings Generated:")
        print(f"   - Savings vs Naive Baseline: {run.mean_savings_vs_naive_bps:.2f} bps")
        print(f"   - Savings vs Best Single:    {run.mean_savings_vs_single_bps:.2f} bps")
        print(f"   - Total Dollar Savings:      ${run.total_savings_usd:,.2f}")
        print("\n5. Cost Percentiles:")
        print(f"   - P50 (Median Cost): {run.cost_percentiles.get('p50', 0):.2f} bps")
        print(f"   - P90 (Tail Cost):   {run.cost_percentiles.get('p90', 0):.2f} bps")
        print(f"   - P99 (Extreme):     {run.cost_percentiles.get('p99', 0):.2f} bps")
        print("=== Backtest Demo Completed Successfully ===")

if __name__ == "__main__":
    asyncio.run(main())
