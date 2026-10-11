from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ORION_ENV: str = "development"
    ORION_LOG_LEVEL: str = "INFO"
    ORION_API_HOST: str = "127.0.0.1"
    ORION_API_PORT: int = 8000
    ORION_CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # Database
    ORION_DATABASE_URL: str = "sqlite+aiosqlite:///./orion.db"

    # Redis
    ORION_REDIS_ENABLED: bool = False
    ORION_REDIS_URL: str = "redis://localhost:6379/0"

    # Execution Modes & Safeguards
    ORION_EXECUTION_MODE: str = "paper"
    ORION_LIVE_TRADING_ENABLED: bool = False
    ORION_OPERATOR_OPT_IN: bool = False
    ORION_DEMO_FIXTURES_ENABLED: bool = True

    # Security
    ORION_API_KEY_ENABLED: bool = False
    ORION_API_KEY: str = "orion_dev_secret_key_change_in_prod"

    # Market Data
    ORION_MARKET_DATA_INTERVAL_SEC: float = 2.0
    ORION_STALENESS_THRESHOLD_SEC: float = 15.0
    ORION_QUOTE_EXPIRY_SEC: float = 30.0

    # External Provider Base URLs
    ARBITRUM_RPC_URL: str = "https://arb1.arbitrum.io/rpc"
    ETHEREUM_RPC_URL: str = "https://eth.llamarpc.com"
    HYPERLIQUID_API_BASE: str = "https://api.hyperliquid.xyz"
    GMX_API_BASE: str = "https://arbitrum-api.gmxinfra.io"

    # Default Fees (BPS)
    ORION_HYPERLIQUID_TAKER_FEE_BPS: float = 3.5
    ORION_HYPERLIQUID_MAKER_FEE_BPS: float = 1.0
    ORION_GMX_TRADING_FEE_BPS: float = 5.0

    # Risk Controls
    ORION_MAX_ORDER_NOTIONAL: float = 250000.0
    ORION_MAX_POSITION_EXPOSURE: float = 1000000.0
    ORION_MAX_PERMITTED_SLIPPAGE_BPS: float = 50.0
    ORION_MAX_FEE_BUDGET_BPS: float = 25.0
    ORION_MAX_CONCURRENT_ORDERS: int = 10
    ORION_PRICE_COLLAR_BPS: float = 100.0
    ORION_KILL_SWITCH_ACTIVE: bool = False

    # Paper Account Initial Balance
    ORION_PAPER_INITIAL_EQUITY: float = 100000.0


settings = Settings()
