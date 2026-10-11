from typing import Any, Dict, List

import httpx

from packages.domain.models import (
    BacktestRun,
    ExecutionReport,
    OrderRequest,
    PaperAccount,
    RouteQuote,
)


class OrionClient:
    """
    Official Python SDK client for ORION Execution Intelligence Platform.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")

    async def get_health(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            res = await client.get("/health")
            res.raise_for_status()
            return res.json()

    async def get_venues(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            res = await client.get("/api/v1/venues")
            res.raise_for_status()
            return res.json()

    async def get_market_state(self, symbol: str = "ETH-PERP") -> Dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            res = await client.get("/api/v1/market-state", params={"symbol": symbol})
            res.raise_for_status()
            return res.json()

    async def get_quote(self, order: OrderRequest) -> RouteQuote:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            res = await client.post("/api/v1/quotes", json=order.model_dump(mode="json"))
            res.raise_for_status()
            return RouteQuote.model_validate(res.json())

    async def submit_paper_order(
        self, order: OrderRequest, venue_id: str = "HYPERLIQUID"
    ) -> ExecutionReport:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            payload = {"order": order.model_dump(mode="json"), "venue_id": venue_id}
            res = await client.post("/api/v1/paper/orders", json=payload)
            res.raise_for_status()
            return ExecutionReport.model_validate(res.json())

    async def get_paper_account(self) -> PaperAccount:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            res = await client.get("/api/v1/paper/account")
            res.raise_for_status()
            return PaperAccount.model_validate(res.json())

    async def run_backtest(
        self, name: str = "SDK Replay", symbol: str = "ETH-PERP", sample_count: int = 40
    ) -> BacktestRun:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            res = await client.post(
                "/api/v1/backtests",
                json={"name": name, "symbol": symbol, "sample_count": sample_count},
            )
            res.raise_for_status()
            return BacktestRun.model_validate(res.json())
