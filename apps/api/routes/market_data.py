from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from packages.domain.enums import VenueId
from packages.domain.models import (
    FundingObservation,
    MarketDataHealth,
    OpenInterestObservation,
    OrderBook,
)
from services.market_data.state_engine import (
    AggregatedMarketState,
    market_state_engine,
)

router = APIRouter(prefix="/api/v1", tags=["Market Data"])


@router.get("/venues")
async def list_venues() -> List[Dict[str, Any]]:
    venues_info = []
    for vid, adapter in market_state_engine.adapters.items():
        cap = adapter.capabilities
        venues_info.append(
            {
                "id": vid.value,
                "name": vid.value.title().replace("_", " "),
                "network": cap.network.value,
                "type": cap.venue_type.value,
                "capabilities": cap.model_dump(),
                "is_on_chain": cap.is_on_chain,
                "gas_required": cap.gas_fee_required,
            }
        )
    return venues_info


@router.get("/markets")
async def list_markets() -> List[Dict[str, Any]]:
    # ETH-PERP default market
    instruments = []
    for _vid, adapter in market_state_engine.adapters.items():
        inst = await adapter.get_instrument("ETH-PERP")
        if inst:
            instruments.append(inst.model_dump())

    return [
        {
            "symbol": "ETH-PERP",
            "base_asset": "ETH",
            "quote_asset": "USD",
            "instruments": instruments,
        }
    ]


@router.get("/market-state", response_model=AggregatedMarketState)
async def get_market_state(symbol: str = Query("ETH-PERP")) -> AggregatedMarketState:
    return await market_state_engine.get_aggregated_state(symbol)


@router.get("/orderbook/{venue}/{symbol}")
async def get_orderbook(venue: str, symbol: str, depth: int = Query(20, ge=1, le=50)) -> OrderBook:
    try:
        vid = VenueId(venue.upper())
    except ValueError as err:
        raise HTTPException(status_code=400, detail=f"Invalid venue {venue}") from err

    adapter = market_state_engine.get_adapter(vid)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Venue adapter not found for {venue}")

    return await adapter.fetch_order_book(symbol, depth=depth)


@router.get("/funding")
async def get_funding(symbol: str = Query("ETH-PERP")) -> List[FundingObservation]:
    observations = []
    for _vid, adapter in market_state_engine.adapters.items():
        obs = await adapter.fetch_funding(symbol)
        observations.append(obs)
    return observations


@router.get("/open-interest")
async def get_open_interest(symbol: str = Query("ETH-PERP")) -> List[OpenInterestObservation]:
    observations = []
    for _vid, adapter in market_state_engine.adapters.items():
        obs = await adapter.fetch_open_interest(symbol)
        observations.append(obs)
    return observations


@router.get("/data-health")
async def get_data_health(symbol: str = Query("ETH-PERP")) -> List[MarketDataHealth]:
    health_reports = []
    for _vid, adapter in market_state_engine.adapters.items():
        h = await adapter.check_health(symbol)
        health_reports.append(h)
    return health_reports
