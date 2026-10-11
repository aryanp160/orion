# ORION Routing Algorithm & Split Allocation Engine

## 1. Candidate Route Evaluation
For a given `OrderRequest` ($S, Q, \text{Horizon}$):
1. Evaluate every active venue adapter.
2. Query L2 depth, funding observation, and connection health.
3. Compute total expected cost:
   $$C_{\text{total}} = C_{\text{spread}} + C_{\text{impact}} + C_{\text{fee}} + C_{\text{funding}} + C_{\text{gas}} + C_{\text{adverse}}$$
4. Apply hard eligibility filters:
   - Venue health: Latency < 2000ms, staleness < 15s.
   - Available depth: Sufficient to fill order or within allowable bounds.
   - Slippage limit: Computed market impact must not exceed user-specified `max_slippage_bps`.
   - Risk Engine approval: Order notional, exposure, and kill switch.

## 2. Multi-Venue Bounded Split Optimizer
When order notional $Q \ge \$50{,}000$ and multiple venues are eligible:
1. Evaluate discrete allocation slices $\alpha \in \{0.50, 0.60, 0.70\}$ across the top two venues:
   $$Q_1 = \alpha \cdot Q, \quad Q_2 = (1 - \alpha) \cdot Q$$
2. Walk order book 1 for $Q_1$ and order book 2 for $Q_2$.
3. Compute blended VWAP:
   $$\text{VWAP}_{\text{blended}} = \frac{\text{VWAP}_1 \cdot Q_1 + \text{VWAP}_2 \cdot Q_2}{Q}$$
4. If blended total cost (including multiple transaction/gas fees) beats the best single venue by $> 0.8\text{ bps}$, recommend the split route.

## 3. Explainability Report
Every quote returns a human-readable and machine-verifiable explanation:
- Why the chosen route or split was selected.
- Explicit rejection reasons for ineligible alternatives.
- Component-level basis point attribution.
