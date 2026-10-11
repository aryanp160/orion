import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import settings
from apps.api.database import init_db
from apps.api.routes import (
    analytics_router,
    audit_router,
    backtest_router,
    health_router,
    market_data_router,
    paper_router,
    quotes_router,
    risk_router,
)
from services.market_data.state_engine import market_state_engine

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.ORION_LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("orion.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing ORION database schema...")
    await init_db()
    logger.info("ORION Database initialized.")
    logger.info(
        f"Execution Mode: {settings.ORION_EXECUTION_MODE.upper()} (Live Trading: {settings.ORION_LIVE_TRADING_ENABLED})"
    )
    yield
    logger.info("ORION API shutdown clean.")


app = FastAPI(
    title="ORION Execution Intelligence API",
    description="On-chain Routing & Intelligence for Optimal Notional Execution in Ethereum Perpetual Futures",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permits local Next.js client
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Correlation ID Middleware
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    corr_id = request.headers.get("X-Correlation-ID") or f"corr_{uuid.uuid4().hex[:12]}"
    request.state.correlation_id = corr_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = corr_id
    return response


# Register Routers
app.include_router(health_router)
app.include_router(market_data_router)
app.include_router(quotes_router)
app.include_router(risk_router)
app.include_router(paper_router)
app.include_router(backtest_router)
app.include_router(analytics_router)
app.include_router(audit_router)


# WebSocket Stream for Live Terminal Market Data
@app.websocket("/ws/market-data")
async def websocket_market_data(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket client connected to market-data stream")
    try:
        while True:
            # Poll aggregated market state
            state = await market_state_engine.get_aggregated_state("ETH-PERP")
            await websocket.send_text(state.model_dump_json())
            await asyncio.sleep(settings.ORION_MARKET_DATA_INTERVAL_SEC)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
        try:
            await websocket.close()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "apps.api.main:app", host=settings.ORION_API_HOST, port=settings.ORION_API_PORT, reload=True
    )
