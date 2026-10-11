# ADR 0001: Core Architecture Decisions

## Status
Accepted

## Context
ORION requires real-time routing intelligence across heterogeneous perpetual futures venues with disparate architectures: Hyperliquid (custom L1 appchain CLOB with gasless transactions) and GMX v2 (Arbitrum One EVM GM oracle liquidity pools with L2 transaction fees).

## Decisions
1. **Deterministic Cost Engine First**:
   Rather than using opaque machine learning models that lack explainability, ORION uses a deterministic, mathematically verifiable execution cost model based on order-book depth walking, explicit fee schedules, and horizon-scaled funding rates.

2. **Unified Order Book Representation**:
   For CLOBs (Hyperliquid, MockCLOB), discrete L2 book levels are directly walked. For oracle/AMM pools (GMX v2), an equivalent synthetic depth schedule is derived from GM pool available liquidity and GMX's dynamic price impact curve.

3. **Fail-Closed Pre-Trade Risk Layer**:
   Risk checks (max notional $250k, max exposure $1M, staleness < 15s) are decoupled from the router and enforced at the backend level. Orders fail closed if market data is degraded or stale.

4. **Paper-Trading Default**:
   `ORION_EXECUTION_MODE=paper` is strictly enforced to guarantee safety. Live trading requires multiple explicit operator opt-ins.
