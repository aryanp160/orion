# ORION System Architecture & Execution Intelligence Design

```mermaid
graph TD
    Client[Web UI Terminal / Python SDK / API] --> API[FastAPI Application Layer :8000]
    
    subgraph Market Data Engine
        HL[Hyperliquid L1 Adapter] --> StateEngine[Market State Aggregator]
        GMX[GMX v2 Arbitrum Adapter] --> StateEngine
        Mock[Deterministic Fixture Adapter] --> StateEngine
        StateEngine --> OrderBook[L2 Depth & VWAP Schedule]
        StateEngine --> Basis[Basis & Imbalance Engine]
    end
    
    subgraph Execution & Routing Engine
        API --> RiskPre[Pre-Trade Risk Engine]
        RiskPre -->|PASS/WARN| Router[Deterministic Execution Router]
        RiskPre -->|BLOCK| Halt[Rejection Response]
        
        StateEngine --> Router
        Router --> CostEngine[Deterministic Cost Engine]
        
        CostEngine --> Comp1[Spread Cost]
        CostEngine --> Comp2[Market Impact / VWAP Depth Walk]
        CostEngine --> Comp3[Maker/Taker Fees]
        CostEngine --> Comp4[Holding Horizon Funding]
        CostEngine --> Comp5[L2 Gas & Transaction Costs]
        CostEngine --> Comp6[Adverse Selection Proxy]
        
        Router --> Optimizer[Single vs Split Allocation Optimizer]
    end
    
    subgraph Paper Trading & Research Engine
        Router --> PaperExec[Persistent Paper Trading Engine]
        PaperExec --> DB[(SQLite / PostgreSQL Durable State)]
        Research[Backtesting & Attribution Engine] --> DB
    end
```

## Core Subsystems

1. **Market Data Ingestion Engine**:
   - Queries real public endpoints on Hyperliquid L1 (`https://api.hyperliquid.xyz/info`) and GMX v2 Arbitrum (`https://arbitrum-api.gmxinfra.io/prices/tickers`).
   - Normalizes heterogenous venue models into unified domain models (`OrderBook`, `MarkPrice`, `FundingObservation`).
   - Tracks data freshness, feed latency, and sequence gaps with strict fail-closed degradation.

2. **Deterministic Execution Cost Engine**:
   - Reference Price: Arrival Mid-Price $P_{\text{mid}} = (P_{\text{bid0}} + P_{\text{ask0}}) / 2$.
   - Cost Breakdown: Total Cost = Spread Cost + Depth Impact + Fees + Funding + Gas + Adverse Selection.
   - Strictly prevents double-counting between top-of-book spread and depth impact.

3. **Execution Router**:
   - Evaluates all eligible candidate routes.
   - Evaluates multi-venue split allocations when order notional is substantial, balancing impact reduction against transaction overhead.
   - Produces explainable rejection reasons for all unchosen alternatives.

4. **Pre-Trade Risk Engine**:
   - Enforces notional caps ($250k), position exposure limits ($1M), concurrent order limits (10), slippage collars, stale data blocks, and emergency kill switches.

5. **Persistent Paper Trading & Backtesting**:
   - Realistic fill simulation against real depth with maker/taker fee accounting.
   - Point-in-time sequential replay for execution alpha attribution without look-ahead bias.
