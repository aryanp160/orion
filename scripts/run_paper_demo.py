import asyncio
from decimal import Decimal
from apps.api.database import init_db, AsyncSessionLocal
from packages.domain.enums import VenueId, OrderSide, OrderType
from packages.domain.models import OrderRequest
from services.execution.paper_trading import paper_trading_engine

async def main():
    print("=== ORION Execution Intelligence: Paper Trading Demo ===")
    await init_db()

    async with AsyncSessionLocal() as session:
        # Reset account for fresh demo run
        print("\n1. Initializing clean paper account ($100,000 equity)...")
        account = await paper_trading_engine.reset_paper_account(session)
        print(f"   Equity: ${account.equity_usd:,.2f} | Available Margin: ${account.available_margin_usd:,.2f}")

        # Order 1: Buy $50,000 ETH on Hyperliquid
        print("\n2. Executing Buy $50,000 ETH-PERP on Hyperliquid CLOB...")
        order_buy = OrderRequest(
            symbol="ETH-PERP",
            side=OrderSide.BUY,
            notional_usd=Decimal("50000.00"),
            order_type=OrderType.MARKET,
        )
        report_buy = await paper_trading_engine.submit_paper_order(
            db=session,
            order=order_buy,
            venue_id=VenueId.HYPERLIQUID,
        )
        print(f"   Status: {report_buy.status.value}")
        print(f"   Filled: {report_buy.filled_quantity:.4f} ETH @ ${report_buy.avg_fill_price:,.2f} VWAP")
        print(f"   Trading Fee: ${report_buy.total_fee_usd:.2f} | Slippage: {report_buy.slippage_bps:.2f} bps")

        # Account check
        acc_status = await paper_trading_engine.get_account_summary(session)
        print(f"\n3. Portfolio Post-Trade:")
        print(f"   Positions: {len(acc_status.positions)}")
        for pos in acc_status.positions:
            print(f"   - {pos.side.value} {pos.quantity:.4f} {pos.symbol} @ ${pos.entry_price:,.2f} | Unrealized PnL: ${pos.unrealized_pnl:,.2f}")
        print(f"   Total Equity: ${acc_status.equity_usd:,.2f}")

        # Order 2: Close position by selling $50,000 ETH
        print("\n4. Closing position with Sell $50,000 ETH-PERP...")
        order_close = OrderRequest(
            symbol="ETH-PERP",
            side=OrderSide.SELL,
            notional_usd=Decimal("50000.00"),
            order_type=OrderType.MARKET,
        )
        report_close = await paper_trading_engine.submit_paper_order(
            db=session,
            order=order_close,
            venue_id=VenueId.HYPERLIQUID,
        )
        print(f"   Status: {report_close.status.value}")
        print(f"   Exit VWAP: ${report_close.avg_fill_price:,.2f}")

        final_acc = await paper_trading_engine.get_account_summary(session)
        print(f"\n5. Final Realized Performance:")
        print(f"   Realized PnL: ${final_acc.realized_pnl_usd:,.2f}")
        print(f"   Final Equity: ${final_acc.equity_usd:,.2f}")
        print("=== Paper Trading Demo Completed Successfully ===")

if __name__ == "__main__":
    asyncio.run(main())
