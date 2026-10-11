# ORION Quantitative Execution Cost Model

## 1. Objective and Sign Conventions

The ORION Execution Cost Engine calculates the expected shortfall and total execution drag for a proposed perpetual futures order:
$$\text{Expected Total Cost} = C_{\text{spread}} + C_{\text{impact}} + C_{\text{fee}} + C_{\text{funding}} + C_{\text{tx}} + C_{\text{adverse}}$$

### Sign Convention
- **Positive basis points (+bps) / Positive USD (+$)**: Execution drag or expense.
- **Negative basis points (-bps) / Negative USD (-$)**: Execution credit or benefit (e.g. favorable funding receipt or maker rebate).

---

## 2. Mathematical Component Definitions

### A. Reference Arrival Benchmark
The reference price $P_{\text{ref}}$ is the arrival mid-price at decision time:
$$P_{\text{ref}} = \frac{P_{\text{bid}, 0} + P_{\text{ask}, 0}}{2}$$

### B. Spread Cost
The difference between the arrival mid-price and the top of the book:
- For a BUY / LONG:
  $$C_{\text{spread, bps}} = \frac{P_{\text{ask}, 0} - P_{\text{ref}}}{P_{\text{ref}}} \times 10{,}000$$
- For a SELL / SHORT:
  $$C_{\text{spread, bps}} = \frac{P_{\text{ref}} - P_{\text{bid}, 0}}{P_{\text{ref}}} \times 10{,}000$$

### C. Market Impact & VWAP Depth Slippage
For marketable orders, the order book is walked iteratively:
$$\text{VWAP} = \frac{\sum_{i=1}^{k} P_i \cdot Q_i}{\sum_{i=1}^{k} Q_i}$$
The depth market impact isolates slippage beyond the top level to prevent double-counting:
- For a BUY:
  $$C_{\text{impact, bps}} = \max\left(0, \frac{\text{VWAP} - P_{\text{ask}, 0}}{P_{\text{ref}}}\right) \times 10{,}000$$
- For a SELL:
  $$C_{\text{impact, bps}} = \max\left(0, \frac{P_{\text{bid}, 0} - \text{VWAP}}{P_{\text{ref}}}\right) \times 10{,}000$$

### D. Expected Funding Cost Over Holding Horizon
Perpetual contracts accrue funding based on position notional:
$$C_{\text{funding, bps}} = \text{Sign}(\text{Side}) \times R_{\text{funding, 8h}} \times \left(\frac{T_{\text{horizon, hours}}}{8.0}\right)$$
- If funding rate $R > 0$ (longs pay shorts):
  - BUY (Long): $+C_{\text{funding}}$ (added expense)
  - SELL (Short): $-C_{\text{funding}}$ (credit received)

### E. Transaction / Gas Overhead
- Arbitrum One (GMX v2): Incurs L2 execution gas fee + Chainlink keeper cost ($\sim\$1.80$).
- Hyperliquid L1: Gasless trading ($\$0.00$).
$$C_{\text{tx, bps}} = \frac{\text{Gas Cost USD}}{\text{Order Notional USD}} \times 10{,}000$$
