from apps.api.routes.analytics import router as analytics_router
from apps.api.routes.audit import router as audit_router
from apps.api.routes.backtest import router as backtest_router
from apps.api.routes.health import router as health_router
from apps.api.routes.market_data import router as market_data_router
from apps.api.routes.paper import router as paper_router
from apps.api.routes.quotes import router as quotes_router
from apps.api.routes.risk import router as risk_router

__all__ = [
    "health_router",
    "market_data_router",
    "quotes_router",
    "risk_router",
    "paper_router",
    "backtest_router",
    "analytics_router",
    "audit_router",
]
