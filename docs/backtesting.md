# ORION Backtesting & Execution Attribution Engine

## 1. Methodology & Benchmark Baselines
ORION compares proposed executions against multiple standardized baselines:

1. **Naive Baseline A (Fixed Single Venue)**:
   Routes 100% of the order to a fixed default venue (e.g. Always GMX or Always Hyperliquid) without strategy or depth awareness.
2. **Best Single Venue Baseline B**:
   Evaluates each candidate venue individually at decision time and selects the best single venue.
3. **ORION Optimal Route**:
   Applies dynamic routing, walking multiple venue order books and evaluating multi-venue split allocations.

## 2. Prevention of Look-Ahead Bias
- All market state inputs (bids, asks, depths, funding observations) are strictly locked to decision-time snapshots.
- Future price movements or future fills are never accessed to make earlier routing decisions.

## 3. Metrics Calculated
- Implementation Shortfall: Shortfall against arrival mid-price benchmark.
- Mean Savings vs Naive Baseline (bps and USD).
- Mean Savings vs Best Single Venue (bps and USD).
- Cost Distribution Percentiles: P50 (median), P90 (tail), P99 (extreme).
- Completion and fill rates.
