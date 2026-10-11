# ORION REST & WebSocket API Specification

Base URL: `http://127.0.0.1:8000`  
Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`

## System Endpoints
- `GET /health`: Health status, version, and execution mode.
- `GET /ready`: Readiness probe for load balancers.

## Market Data
- `GET /api/v1/venues`: List of supported venues and capabilities.
- `GET /api/v1/markets`: List of supported trading markets (ETH-PERP).
- `GET /api/v1/market-state?symbol=ETH-PERP`: Aggregated global BBO and venue depth states.
- `GET /api/v1/orderbook/{venue}/{symbol}?depth=20`: Discrete L2 order book snapshot.
- `GET /api/v1/funding?symbol=ETH-PERP`: 8-hour normalized funding rates.
- `GET /api/v1/open-interest?symbol=ETH-PERP`: Open interest metrics.
- `GET /api/v1/data-health`: Health, latency, and staleness stats.

## Execution Intelligence & Routing
- `POST /api/v1/quotes`: Generate deterministic quote with full cost attribution and split analysis.
- `GET /api/v1/quotes/{quote_id}`: Retrieve stored quote.
- `POST /api/v1/routes/preview`: Ephemeral quote preview without DB persistence.

## Paper Trading
- `POST /api/v1/paper/orders`: Submit simulated paper order.
- `GET /api/v1/paper/orders`: List paper orders.
- `GET /api/v1/paper/orders/{order_id}`: Get specific paper order.
- `POST /api/v1/paper/orders/{order_id}/cancel`: Cancel open order.
- `GET /api/v1/paper/account`: Account balance, equity, and margin.
- `GET /api/v1/paper/positions`: List active paper positions.
- `POST /api/v1/paper/reset`: Reset account to initial $100,000 equity.
- `GET /api/v1/paper/fills`: List executed fills.

## Risk Engine & Controls
- `GET /api/v1/risk/status`: Current pre-trade limits and kill switch state.
- `POST /api/v1/risk/kill-switch`: Engage or disengage emergency kill switch.

## Research & Backtesting
- `POST /api/v1/backtests`: Launch execution replay backtest.
- `GET /api/v1/backtests`: List completed backtest runs.
- `GET /api/v1/backtests/{run_id}`: Get backtest metrics and distributions.
- `GET /api/v1/backtests/{run_id}/attribution`: Detailed execution attribution.

## WebSocket Feed
- `ws://127.0.0.1:8000/ws/market-data`: Real-time aggregated market state stream.
