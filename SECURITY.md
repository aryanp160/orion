# ORION Security Policy & Operational Safeguards

## 1. Security Architecture & Threat Model

ORION is an institutional execution intelligence and routing platform for Ethereum-related perpetual futures.
Because ORION evaluates market routes and executes paper and potential live orders, security is enforced through strict defense-in-depth layers.

### Key Threat Vectors & Defenses

1. **Unauthorized Order Execution**:
   - **Fail-Closed Default**: `ORION_EXECUTION_MODE=paper` is strictly enforced.
   - **No Live Trading Flag Alone**: Live trading requires `ORION_LIVE_TRADING_ENABLED=true`, valid venue credentials, an explicit operator opt-in flag (`ORION_OPERATOR_OPT_IN=true`), and an allowlisted venue/market.
   - **No Withdrawal Permissions**: Any external API keys configured for trading must have withdrawal and transfer permissions disabled at the venue level.

2. **Unintended Market Risk / Over-Exposure**:
   - **Pre-Trade Risk Engine**: Validates order notional, aggregate position exposure, slippage collars, and concurrent order limits before routing.
   - **Circuit Breakers / Kill Switch**: `ORION_KILL_SWITCH_ACTIVE=true` immediately halts order dispatch.

3. **Stale or Manipulated Market Data**:
   - **Freshness Verification**: Every price, book level, and funding rate is checked against `ORION_STALENESS_THRESHOLD_SEC`. If data is older than threshold, quotes are blocked or flagged stale.
   - **Cross-Source Basis Validation**: Mark and index prices are checked against reference ranges to prevent execution against crossed or corrupt books.

4. **Secrets & Credential Hygiene**:
   - API keys and private keys must never be committed to Git or logged.
   - Sensitive headers and credentials are automatically scrubbed from structured log outputs.

---

## 2. Reporting Vulnerabilities

If you discover a security vulnerability in ORION, please report it via private disclosure rather than opening a public GitHub issue:
- Email: `security@orion-execution.local` or through private GitHub Security Advisories.
- Include reproduction steps and potential impact.
