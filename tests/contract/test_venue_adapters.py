import pytest

from packages.domain.enums import NetworkId, VenueId, VenueType
from services.market_data.gmx_v2 import GMXV2Adapter
from services.market_data.hyperliquid import HyperliquidAdapter
from services.market_data.mock_clob import MockCLOBAdapter


def test_hyperliquid_capabilities():
    adapter = HyperliquidAdapter()
    cap = adapter.capabilities
    assert cap.venue_id == VenueId.HYPERLIQUID
    assert cap.venue_type == VenueType.CLOB
    assert cap.network == NetworkId.HYPERLIQUID_L1
    assert cap.has_order_book_l2 is True
    assert cap.is_on_chain is False
    assert cap.gas_fee_required is False


def test_gmx_capabilities():
    adapter = GMXV2Adapter()
    cap = adapter.capabilities
    assert cap.venue_id == VenueId.GMX_V2
    assert cap.venue_type == VenueType.ORACLE_AMM
    assert cap.network == NetworkId.ARBITRUM
    assert cap.is_on_chain is True
    assert cap.gas_fee_required is True


def test_mock_clob_capabilities():
    adapter = MockCLOBAdapter()
    cap = adapter.capabilities
    assert cap.venue_id == VenueId.MOCK_CLOB
    assert cap.venue_type == VenueType.SIMULATED
    assert cap.network == NetworkId.SIMULATED


@pytest.mark.asyncio
async def test_mock_clob_order_book_contract():
    adapter = MockCLOBAdapter()
    book = await adapter.fetch_order_book("ETH-PERP", depth=10)
    assert book.venue_id == VenueId.MOCK_CLOB
    assert len(book.bids) == 10
    assert len(book.asks) == 10
    assert book.best_bid is not None
    assert book.best_ask is not None
    assert book.best_ask > book.best_bid
