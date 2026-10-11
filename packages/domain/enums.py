from enum import Enum

class VenueId(str, Enum):
    HYPERLIQUID = "HYPERLIQUID"
    GMX_V2 = "GMX_V2"
    MOCK_CLOB = "MOCK_CLOB"

class VenueType(str, Enum):
    CLOB = "CLOB"          # Central Limit Order Book
    ORACLE_AMM = "ORACLE_AMM"  # Synthetic Oracle / Pool
    SIMULATED = "SIMULATED"    # Local test fixture

class NetworkId(str, Enum):
    ARBITRUM = "ARBITRUM"
    ETHEREUM = "ETHEREUM"
    HYPERLIQUID_L1 = "HYPERLIQUID_L1"
    SIMULATED = "SIMULATED"

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    TWAP = "TWAP"

class ExecutionPreference(str, Enum):
    MINIMIZE_COST = "MINIMIZE_COST"
    MINIMIZE_IMPACT = "MINIMIZE_IMPACT"
    PASSIVE_LIMIT = "PASSIVE_LIMIT"
    BALANCED_RISK = "BALANCED_RISK"

class RiskOutcome(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class LiquidityRole(str, Enum):
    TAKER = "TAKER"
    MAKER = "MAKER"
