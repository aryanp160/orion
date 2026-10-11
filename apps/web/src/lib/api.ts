// ORION API Client for Trading Terminal Frontend

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export interface VenueInfo {
  id: string;
  name: string;
  network: string;
  type: string;
  capabilities: {
    has_order_book_l2: boolean;
    has_funding_rates: boolean;
    has_open_interest: boolean;
    supports_market_orders: boolean;
    supports_limit_orders: boolean;
    supports_split_routing: boolean;
    is_on_chain: boolean;
    gas_fee_required: boolean;
    description: string;
  };
  is_on_chain: boolean;
  gas_required: boolean;
}

export interface OrderBookLevel {
  price: string | number;
  size: string | number;
  order_count?: number;
}

export interface OrderBook {
  venue_id: string;
  symbol: string;
  bids: OrderBookLevel[];
  asks: OrderBookLevel[];
  timestamp: string;
  receive_timestamp: string;
  is_stale: boolean;
}

export interface VenueMarketState {
  venue_id: string;
  symbol: string;
  best_bid: string | number | null;
  best_ask: string | number | null;
  mid_price: string | number | null;
  spread_bps: string | number | null;
  order_book_imbalance: string | number | null;
  depth_bands: Array<{
    bps_offset: number;
    bid_depth_usd: string | number;
    ask_depth_usd: string | number;
    bid_depth_qty: string | number;
    ask_depth_qty: string | number;
  }>;
  total_liquidity_depth_usd: string | number;
  funding_rate_8h_bps: string | number;
  open_interest_usd: string | number;
  mark_price: string | number;
  basis_bps: string | number;
  data_freshness_sec: number;
  latency_ms: number;
  is_healthy: boolean;
  status_message: string;
}

export interface AggregatedMarketState {
  symbol: string;
  timestamp: string;
  venues: Record<string, VenueMarketState>;
  best_bid_global: string | number | null;
  best_bid_venue: string | null;
  best_ask_global: string | number | null;
  best_ask_venue: string | null;
  global_mid_price: string | number | null;
  global_spread_bps: string | number | null;
  total_market_liquidity_usd: string | number;
}

export interface CostBreakdown {
  reference_price: string | number;
  expected_execution_price: string | number;
  spread_cost_bps: string | number;
  spread_cost_usd: string | number;
  market_impact_bps: string | number;
  market_impact_usd: string | number;
  trading_fee_bps: string | number;
  trading_fee_usd: string | number;
  funding_cost_bps: string | number;
  funding_cost_usd: string | number;
  transaction_cost_bps: string | number;
  transaction_cost_usd: string | number;
  adverse_selection_bps: string | number;
  adverse_selection_usd: string | number;
  total_cost_bps: string | number;
  total_cost_usd: string | number;
}

export interface CandidateRoute {
  venue_id: string;
  allocation_pct: string | number;
  allocated_notional: string | number;
  allocated_quantity: string | number;
  expected_vwap: string | number;
  breakdown: CostBreakdown;
  is_eligible: boolean;
  ineligibility_reason: string | null;
  data_freshness_sec: number;
  liquidity_available_usd: string | number;
}

export interface RouteQuote {
  quote_id: string;
  recommended_venue: string;
  is_split_route: boolean;
  candidates: CandidateRoute[];
  allocations: CandidateRoute[];
  blended_vwap: string | number;
  blended_breakdown: CostBreakdown;
  confidence_score: number;
  freshness_sec: number;
  quote_timestamp: string;
  expires_at: string;
  explanation: Record<string, any>;
}

export interface PaperAccount {
  account_id: string;
  equity_usd: string | number;
  available_margin_usd: string | number;
  used_margin_usd: string | number;
  realized_pnl_usd: string | number;
  unrealized_pnl_usd: string | number;
  initial_balance: string | number;
  total_orders_count: number;
  total_fills_count: number;
  positions: Array<{
    symbol: string;
    venue_id: string;
    side: string;
    quantity: string | number;
    entry_price: string | number;
    mark_price: string | number;
    notional_usd: string | number;
    unrealized_pnl: string | number;
    realized_pnl: string | number;
    margin_allocated: string | number;
    leverage: string | number;
  }>;
}

export interface PaperOrder {
  order_id: string;
  client_order_id?: string;
  symbol: string;
  side: string;
  order_type: string;
  requested_notional: number;
  requested_quantity: number;
  filled_quantity: number;
  filled_notional: number;
  remaining_quantity: number;
  avg_fill_price: number;
  total_fee_usd: number;
  slippage_bps: number;
  status: string;
  rejection_reason?: string;
  created_at: string;
}

export interface PaperFill {
  fill_id: string;
  order_id: string;
  venue_id: string;
  symbol: string;
  side: string;
  fill_price: number;
  fill_quantity: number;
  fill_notional: number;
  fee_usd: number;
  fee_bps: number;
  role: string;
  created_at: string;
}

export interface BacktestRun {
  run_id: string;
  name: string;
  symbol: string;
  start_time: string;
  end_time: string;
  status: string;
  order_count: number;
  baseline_naive_cost_bps: number;
  baseline_single_cost_bps: number;
  orion_route_cost_bps: number;
  mean_savings_vs_naive_bps: number;
  mean_savings_vs_single_bps: number;
  total_savings_usd: number;
  metrics?: Record<string, any>;
  created_at: string;
}

export const api = {
  async getHealth() {
    const res = await fetch(`${API_BASE}/health`);
    return res.json();
  },

  async getVenues(): Promise<VenueInfo[]> {
    const res = await fetch(`${API_BASE}/api/v1/venues`);
    return res.json();
  },

  async getMarketState(symbol = 'ETH-PERP'): Promise<AggregatedMarketState> {
    const res = await fetch(`${API_BASE}/api/v1/market-state?symbol=${symbol}`);
    return res.json();
  },

  async getOrderBook(venue: string, symbol = 'ETH-PERP', depth = 20): Promise<OrderBook> {
    const res = await fetch(`${API_BASE}/api/v1/orderbook/${venue}/${symbol}?depth=${depth}`);
    return res.json();
  },

  async getQuotes(order: {
    symbol: string;
    side: 'BUY' | 'SELL';
    notional_usd: number | string;
    order_type?: string;
    max_slippage_bps?: number | string;
    holding_horizon_hours?: number | string;
  }): Promise<RouteQuote> {
    const res = await fetch(`${API_BASE}/api/v1/quotes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(order),
    });
    return res.json();
  },

  async getRiskStatus() {
    const res = await fetch(`${API_BASE}/api/v1/risk/status`);
    return res.json();
  },

  async toggleKillSwitch(active: boolean) {
    const res = await fetch(`${API_BASE}/api/v1/risk/kill-switch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active }),
    });
    return res.json();
  },

  async submitPaperOrder(order: any, venue_id = 'HYPERLIQUID') {
    const res = await fetch(`${API_BASE}/api/v1/paper/orders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ order, venue_id }),
    });
    return res.json();
  },

  async getPaperAccount(): Promise<PaperAccount> {
    const res = await fetch(`${API_BASE}/api/v1/paper/account`);
    return res.json();
  },

  async getPaperOrders(): Promise<PaperOrder[]> {
    const res = await fetch(`${API_BASE}/api/v1/paper/orders`);
    return res.json();
  },

  async getPaperFills(): Promise<PaperFill[]> {
    const res = await fetch(`${API_BASE}/api/v1/paper/fills`);
    return res.json();
  },

  async cancelPaperOrder(orderId: string) {
    const res = await fetch(`${API_BASE}/api/v1/paper/orders/${orderId}/cancel`, {
      method: 'POST',
    });
    return res.json();
  },

  async resetPaperAccount(): Promise<PaperAccount> {
    const res = await fetch(`${API_BASE}/api/v1/paper/reset`, { method: 'POST' });
    return res.json();
  },

  async runBacktest(payload: { name?: string; symbol?: string; sample_count?: number }): Promise<BacktestRun> {
    const res = await fetch(`${API_BASE}/api/v1/backtests`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return res.json();
  },

  async getBacktests(): Promise<BacktestRun[]> {
    const res = await fetch(`${API_BASE}/api/v1/backtests`);
    return res.json();
  },

  async getExecutionQuality() {
    const res = await fetch(`${API_BASE}/api/v1/analytics/execution-quality`);
    return res.json();
  },

  async getAuditEvents() {
    const res = await fetch(`${API_BASE}/api/v1/audit/events`);
    return res.json();
  },
};
