# ORION Pre-Trade Risk Engine

The Risk Engine operates as an independent gatekeeper before any execution plan or paper order is submitted.

## Configurable Risk Controls

| Parameter | Default Value | Action on Breach |
|---|---|---|
| `ORION_MAX_ORDER_NOTIONAL` | $250,000.00 USD | **BLOCK** |
| `ORION_MAX_POSITION_EXPOSURE` | $1,000,000.00 USD | **BLOCK** |
| `ORION_MAX_CONCURRENT_ORDERS` | 10 Orders | **BLOCK** |
| `ORION_PRICE_COLLAR_BPS` | 100.0 bps (1.0%) | **BLOCK** |
| `ORION_STALENESS_THRESHOLD_SEC` | 15.0 seconds | **BLOCK** (Fail-closed) |
| `ORION_KILL_SWITCH_ACTIVE` | false | **BLOCK** (Full trading halt) |
| `ORION_MAX_PERMITTED_SLIPPAGE_BPS`| 50.0 bps | **WARN** |

## Fail-Closed Architecture
If critical market data is unavailable or a venue connection drops, the risk engine immediately blocks order dispatch rather than permitting unhedged or unverified execution.
