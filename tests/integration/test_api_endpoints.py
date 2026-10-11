import httpx
import pytest

from apps.api.main import app


@pytest.mark.asyncio
async def test_api_public_endpoints():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Health & Ready
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "HEALTHY"

        r = await client.get("/ready")
        assert r.status_code == 200
        assert r.json()["status"] == "READY"

        # Venues
        r = await client.get("/api/v1/venues")
        assert r.status_code == 200
        venues = r.json()
        assert len(venues) >= 2

        # Markets
        r = await client.get("/api/v1/markets")
        assert r.status_code == 200
        assert r.json()[0]["symbol"] == "ETH-PERP"

        # Market State
        r = await client.get("/api/v1/market-state")
        assert r.status_code == 200
        state = r.json()
        assert "venues" in state

        # Risk Status
        r = await client.get("/api/v1/risk/status")
        assert r.status_code == 200
        assert r.json()["status"] == "OPERATIONAL"

        # Quote Generation
        quote_payload = {
            "symbol": "ETH-PERP",
            "side": "BUY",
            "notional_usd": "25000.00",
            "order_type": "MARKET",
            "max_slippage_bps": "20.0",
        }
        r = await client.post("/api/v1/quotes", json=quote_payload)
        assert r.status_code == 200
        quote_data = r.json()
        assert "quote_id" in quote_data
        assert float(quote_data["blended_vwap"]) > 0

        # Paper Order Submission
        paper_order_payload = {
            "order": quote_payload,
            "venue_id": "MOCK_CLOB",
        }
        r = await client.post("/api/v1/paper/orders", json=paper_order_payload)
        assert r.status_code == 200
        report = r.json()
        assert report["status"] in ["FILLED", "PARTIALLY_FILLED"]

        # Paper Account
        r = await client.get("/api/v1/paper/account")
        assert r.status_code == 200
        assert float(r.json()["equity_usd"]) > 0

        # Backtest Run
        bkt_payload = {
            "name": "API Test Replay",
            "symbol": "ETH-PERP",
            "sample_count": 10,
        }
        r = await client.post("/api/v1/backtests", json=bkt_payload)
        assert r.status_code == 200
        bkt_res = r.json()
        assert bkt_res["status"] == "COMPLETED"

        # Analytics
        r = await client.get("/api/v1/analytics/execution-quality")
        assert r.status_code == 200
        assert "total_evaluated_orders" in r.json()

        # Audit events
        r = await client.get("/api/v1/audit/events")
        assert r.status_code == 200
        assert len(r.json()) > 0
