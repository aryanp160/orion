# ORION Persistent Paper Trading Engine

## 1. Safety and Separation
- Mode: strictly controlled by `ORION_EXECUTION_MODE=paper`.
- All simulated executions are tagged `simulated = true` and `role = TAKER`.
- Zero live orders can be dispatched under paper mode.

## 2. Order Lifecycle State Transitions
$$\text{PENDING} \longrightarrow \text{OPEN} \longrightarrow \begin{cases} \text{FILLED} \\ \text{PARTIALLY\_FILLED} \\ \text{CANCELLED} \\ \text{REJECTED} \end{cases}$$

## 3. Position and PnL Accounting
- Long Position PnL: $\text{PnL} = (P_{\text{mark}} - P_{\text{entry}}) \times Q$
- Short Position PnL: $\text{PnL} = (P_{\text{entry}} - P_{\text{mark}}) \times Q$
- Realized PnL: Accrues when closing or reversing positions, net of trading fees.
- Account State: Persisted in SQLite / PostgreSQL, ensuring zero data loss across process restarts.
