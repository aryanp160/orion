# ORION Venue Integrations & Ingestion Architecture

ORION interfaces with heterogeneous perpetual futures venues, clearly distinguishing architectural mechanisms:

| Venue | Network Scope | Execution Mechanism | Public Ingestion Route | Gas Overhead |
|---|---|---|---|---|
| **Hyperliquid (`HYPERLIQUID`)** | Hyperliquid L1 (custom appchain) | High-speed CLOB | `POST https://api.hyperliquid.xyz/info` | Gasless ($0) |
| **GMX v2 (`GMX_V2`)** | Arbitrum One (Ethereum L2) | GM Oracle Liquidity Pool | `GET https://arbitrum-api.gmxinfra.io/prices/tickers` | ~$1.80 (L2 + Keeper) |
| **Deterministic Fixture (`MOCK_CLOB`)** | Offline Simulation | Deterministic seeded order book | In-memory local fixture | $0 |

## Capability Verification

1. **Hyperliquid**:
   - Order book: Full L2 depth with discrete price and size levels (`l2Book`).
   - Funding: Continuously updating 1-hour rate, normalized to 8-hour basis points.
   - Settlement: USDC margin deposited via Arbitrum bridge.

2. **GMX v2**:
   - Liquidity model: GM pools backed by real crypto/stables with quadratic/linear impact factor.
   - Pricing: Low-latency Chainlink and keeper price signers.
   - L2 Execution: Orders are executed on Arbitrum smart contracts and incur sequencer gas plus keeper execution bounties.

3. **Fail-Closed Staleness Policy**:
   - Any market observation older than 15.0 seconds is flagged `is_stale = true` and rejected by the Pre-Trade Risk Engine.
