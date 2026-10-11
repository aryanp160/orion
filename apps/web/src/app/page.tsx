'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  api,
  VenueInfo,
  AggregatedMarketState,
  OrderBook,
  RouteQuote,
  PaperAccount,
  PaperOrder,
  PaperFill,
  BacktestRun,
} from '@/lib/api';

type TabView =
  | 'OVERVIEW'
  | 'MARKET_EXPLORER'
  | 'EXECUTION_WORKBENCH'
  | 'ROUTE_COMPARISON'
  | 'PAPER_TRADING'
  | 'BACKTESTING'
  | 'RISK_CENTER'
  | 'SETTINGS';

export default function OrionTerminal() {
  const [activeTab, setActiveTab] = useState<TabView>('OVERVIEW');
  const [currentTime, setCurrentTime] = useState<string>('');
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [killSwitchActive, setKillSwitchActive] = useState<boolean>(false);

  // Core Data States
  const [marketState, setMarketState] = useState<AggregatedMarketState | null>(null);
  const [venues, setVenues] = useState<VenueInfo[]>([]);
  const [selectedVenue, setSelectedVenue] = useState<string>('HYPERLIQUID');
  const [orderBook, setOrderBook] = useState<OrderBook | null>(null);
  const [paperAccount, setPaperAccount] = useState<PaperAccount | null>(null);
  const [paperOrders, setPaperOrders] = useState<PaperOrder[]>([]);
  const [paperFills, setPaperFills] = useState<PaperFill[]>([]);
  const [backtests, setBacktests] = useState<BacktestRun[]>([]);
  const [auditEvents, setAuditEvents] = useState<any[]>([]);

  // Execution Workbench States
  const [orderSide, setOrderSide] = useState<'BUY' | 'SELL'>('BUY');
  const [orderNotional, setOrderNotional] = useState<number>(100000);
  const [maxSlippageBps, setMaxSlippageBps] = useState<number>(20);
  const [holdingHorizonHours, setHoldingHorizonHours] = useState<number>(24);
  const [isQuoting, setIsQuoting] = useState<boolean>(false);
  const [activeQuote, setActiveQuote] = useState<RouteQuote | null>(null);
  const [executionStatus, setExecutionStatus] = useState<string | null>(null);

  // Backtest Config
  const [backtestName, setBacktestName] = useState<string>('ETH-PERP Replay Benchmark');
  const [backtestSamples, setBacktestSamples] = useState<number>(40);
  const [isRunningBacktest, setIsRunningBacktest] = useState<boolean>(false);

  // Clock
  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      setCurrentTime(now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC');
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Poll Data
  const refreshAllData = useCallback(async () => {
    try {
      const [mState, vList, acc, risk] = await Promise.all([
        api.getMarketState('ETH-PERP'),
        api.getVenues(),
        api.getPaperAccount(),
        api.getRiskStatus(),
      ]);

      setMarketState(mState);
      setVenues(vList);
      setPaperAccount(acc);
      setKillSwitchActive(risk.kill_switch_active);
      setIsConnected(true);
    } catch {
      setIsConnected(false);
    }
  }, []);

  useEffect(() => {
    refreshAllData();
    const interval = setInterval(refreshAllData, 2500);
    return () => clearInterval(interval);
  }, [refreshAllData]);

  // Poll Order Book for selected venue
  useEffect(() => {
    let isSubscribed = true;
    async function loadBook() {
      try {
        const book = await api.getOrderBook(selectedVenue, 'ETH-PERP', 15);
        if (isSubscribed) setOrderBook(book);
      } catch {
        // fallback
      }
    }
    loadBook();
    const interval = setInterval(loadBook, 2000);
    return () => {
      isSubscribed = false;
      clearInterval(interval);
    };
  }, [selectedVenue]);

  // Load secondary lists on tab switch
  useEffect(() => {
    if (activeTab === 'PAPER_TRADING') {
      api.getPaperOrders().then(setPaperOrders).catch(() => {});
      api.getPaperFills().then(setPaperFills).catch(() => {});
    } else if (activeTab === 'BACKTESTING') {
      api.getBacktests().then(setBacktests).catch(() => {});
    } else if (activeTab === 'SETTINGS') {
      api.getAuditEvents().then(setAuditEvents).catch(() => {});
    }
  }, [activeTab]);

  // Handlers
  const handleGenerateQuote = async () => {
    setIsQuoting(true);
    setExecutionStatus(null);
    try {
      const quote = await api.getQuotes({
        symbol: 'ETH-PERP',
        side: orderSide,
        notional_usd: orderNotional,
        max_slippage_bps: maxSlippageBps,
        holding_horizon_hours: holdingHorizonHours,
      });
      setActiveQuote(quote);
    } catch (err: any) {
      setExecutionStatus(`Quote Generation Error: ${err.message || 'Server error'}`);
    } finally {
      setIsQuoting(false);
    }
  };

  const handleExecutePaperOrder = async () => {
    if (!activeQuote) return;
    setExecutionStatus('DISPATCHING_PAPER_ORDER...');
    try {
      const targetVenue = activeQuote.is_split_route ? 'HYPERLIQUID' : activeQuote.recommended_venue;
      const report = await api.submitPaperOrder(
        {
          symbol: 'ETH-PERP',
          side: orderSide,
          notional_usd: orderNotional,
          order_type: 'MARKET',
          max_slippage_bps: maxSlippageBps,
        },
        targetVenue
      );

      if (report.status === 'FILLED' || report.status === 'PARTIALLY_FILLED') {
        setExecutionStatus(`SUCCESS: Filled ${report.filled_quantity} ETH @ $${Number(report.avg_fill_price).toLocaleString()} (${report.status})`);
      } else {
        setExecutionStatus(`ORDER ${report.status}: ${report.rejection_reason || 'Risk block'}`);
      }
      refreshAllData();
      api.getPaperOrders().then(setPaperOrders).catch(() => {});
    } catch (err: any) {
      setExecutionStatus(`EXECUTION FAILED: ${err.message || 'API error'}`);
    }
  };

  const handleResetAccount = async () => {
    if (!confirm('CONFIRM RESET: Reset paper equity to $100,000.00 and close all open positions?')) return;
    try {
      const resetAcc = await api.resetPaperAccount();
      setPaperAccount(resetAcc);
      api.getPaperOrders().then(setPaperOrders).catch(() => {});
      api.getPaperFills().then(setPaperFills).catch(() => {});
    } catch (err) {
      alert('Reset failed');
    }
  };

  const handleToggleKillSwitch = async () => {
    const nextState = !killSwitchActive;
    if (confirm(`CONFIRM: ${nextState ? 'ENGAGE KILL SWITCH (Halt execution)' : 'RESUME NORMAL OPERATION'}?`)) {
      try {
        const res = await api.toggleKillSwitch(nextState);
        setKillSwitchActive(res.kill_switch_active);
      } catch (err) {
        alert('Failed to toggle kill switch');
      }
    }
  };

  const handleRunBacktest = async () => {
    setIsRunningBacktest(true);
    try {
      const run = await api.runBacktest({
        name: backtestName,
        symbol: 'ETH-PERP',
        sample_count: backtestSamples,
      });
      setBacktests((prev) => [run, ...prev]);
    } catch (err: any) {
      alert(`Backtest failed: ${err.message}`);
    } finally {
      setIsRunningBacktest(false);
    }
  };

  // Microstructure values
  const midPrice = marketState?.global_mid_price ? Number(marketState.global_mid_price) : 2500.0;
  const spreadBps = marketState?.global_spread_bps ? Number(marketState.global_spread_bps) : 1.2;
  const bestBid = marketState?.best_bid_global ? Number(marketState.best_bid_global) : 2499.85;
  const bestAsk = marketState?.best_ask_global ? Number(marketState.best_ask_global) : 2500.15;
  const totalLiquidity = marketState?.total_market_liquidity_usd ? Number(marketState.total_market_liquidity_usd) : 58400000;

  return (
    <div className="flex flex-col min-h-screen bg-[#0B0E14] text-[#E2E8F0] font-sans">
      {/* 1. INSTITUTIONAL TOP BAR */}
      <header className="border-b border-[#1F2633] bg-[#0E121B] px-4 py-2.5 flex items-center justify-between text-xs tracking-wide">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <span className="font-mono font-bold text-sm tracking-wider text-white">ORION</span>
            <span className="text-[#64748B] font-mono text-[11px]">// ROUTING & INTELLIGENCE</span>
          </div>

          <div className="h-4 w-[1px] bg-[#2D3748]" />

          <div className="flex items-center space-x-2 font-mono">
            <span className="text-[#94A3B8]">MARKET:</span>
            <span className="font-semibold text-white px-1.5 py-0.5 rounded bg-[#161B26] border border-[#2D3748]">ETH-PERP</span>
          </div>

          <div className="flex items-center space-x-1.5">
            <span className={`inline-block w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-rose-500'}`} />
            <span className="font-mono text-[#94A3B8]">{isConnected ? 'FEED: LIVE' : 'FEED: RECONNECTING'}</span>
          </div>
        </div>

        <div className="flex items-center space-x-4 font-mono">
          <span className="px-2 py-0.5 rounded bg-blue-950/40 border border-blue-800/60 text-blue-300 text-[11px] font-semibold">
            PAPER EXECUTION
          </span>

          <button
            onClick={handleToggleKillSwitch}
            className={`px-2.5 py-1 rounded text-[11px] font-bold border transition-colors ${
              killSwitchActive
                ? 'bg-rose-600 text-white border-rose-500 hover:bg-rose-700 animate-pulse'
                : 'bg-[#161B26] text-[#EF4444] border-rose-900/60 hover:bg-rose-950/40'
            }`}
          >
            {killSwitchActive ? '● KILL SWITCH ACTIVE (HALTED)' : 'EMERGENCY KILL SWITCH'}
          </button>

          <span className="text-[#64748B] tabular-nums">{currentTime || '2026-10-11 04:25:00 UTC'}</span>
        </div>
      </header>

      {/* 2. SUB-NAVIGATION TABS */}
      <nav className="border-b border-[#1F2633] bg-[#0B0E14] px-4 flex space-x-1 text-xs font-mono overflow-x-auto">
        {(
          [
            ['OVERVIEW', '[1] OVERVIEW'],
            ['MARKET_EXPLORER', '[2] MARKET EXPLORER'],
            ['EXECUTION_WORKBENCH', '[3] EXECUTION WORKBENCH'],
            ['ROUTE_COMPARISON', '[4] ROUTE COMPARISON'],
            ['PAPER_TRADING', '[5] PAPER TRADING'],
            ['BACKTESTING', '[6] BACKTESTING'],
            ['RISK_CENTER', '[7] RISK CENTER'],
            ['SETTINGS', '[8] SETTINGS & AUDIT'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`px-3.5 py-2.5 border-b-2 font-medium transition-colors whitespace-nowrap ${
              activeTab === key
                ? 'border-blue-500 text-white bg-[#121722]'
                : 'border-transparent text-[#94A3B8] hover:text-[#E2E8F0] hover:bg-[#10141D]'
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      {/* 3. MAIN TERMINAL WORKSPACE */}
      <main className="flex-1 p-4 space-y-4 max-w-[1720px] w-full mx-auto">
        {/* VIEW 1: OVERVIEW */}
        {activeTab === 'OVERVIEW' && (
          <div className="space-y-4">
            {/* Top Market KPI Cards */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <div className="bg-[#10141D] border border-[#1F2633] p-3 rounded">
                <div className="text-[11px] font-mono text-[#64748B]">GLOBAL MID PRICE</div>
                <div className="text-xl font-mono font-bold text-white mt-1 tabular-nums">${midPrice.toFixed(2)}</div>
                <div className="text-[11px] font-mono text-[#94A3B8] mt-0.5">Spread: {spreadBps.toFixed(2)} bps</div>
              </div>
              <div className="bg-[#10141D] border border-[#1F2633] p-3 rounded">
                <div className="text-[11px] font-mono text-[#64748B]">BEST GLOBAL BID</div>
                <div className="text-xl font-mono font-bold text-emerald-400 mt-1 tabular-nums">${bestBid.toFixed(2)}</div>
                <div className="text-[11px] font-mono text-[#64748B] mt-0.5">{marketState?.best_bid_venue || 'HYPERLIQUID'}</div>
              </div>
              <div className="bg-[#10141D] border border-[#1F2633] p-3 rounded">
                <div className="text-[11px] font-mono text-[#64748B]">BEST GLOBAL ASK</div>
                <div className="text-xl font-mono font-bold text-rose-400 mt-1 tabular-nums">${bestAsk.toFixed(2)}</div>
                <div className="text-[11px] font-mono text-[#64748B] mt-0.5">{marketState?.best_ask_venue || 'HYPERLIQUID'}</div>
              </div>
              <div className="bg-[#10141D] border border-[#1F2633] p-3 rounded">
                <div className="text-[11px] font-mono text-[#64748B]">AGGREGATED LIQUIDITY</div>
                <div className="text-xl font-mono font-bold text-white mt-1 tabular-nums">${(totalLiquidity / 1e6).toFixed(1)}M</div>
                <div className="text-[11px] font-mono text-emerald-400 mt-0.5">Across 3 Venues</div>
              </div>
              <div className="bg-[#10141D] border border-[#1F2633] p-3 rounded">
                <div className="text-[11px] font-mono text-[#64748B]">PAPER EQUITY</div>
                <div className="text-xl font-mono font-bold text-white mt-1 tabular-nums">
                  ${paperAccount?.equity_usd ? Number(paperAccount.equity_usd).toLocaleString() : '100,000.00'}
                </div>
                <div className="text-[11px] font-mono text-[#94A3B8] mt-0.5">
                  Avail: ${paperAccount?.available_margin_usd ? Number(paperAccount.available_margin_usd).toLocaleString() : '100,000.00'}
                </div>
              </div>
            </div>

            {/* Providers Connection Grid */}
            <div className="bg-[#10141D] border border-[#1F2633] rounded">
              <div className="px-4 py-2.5 border-b border-[#1F2633] flex justify-between items-center text-xs font-mono">
                <span className="font-semibold text-white tracking-wider">SUPPORTED VENUE TELEMETRY & CAPABILITIES</span>
                <span className="text-[#64748B]">REAL-TIME REFRESH: 2.0s</span>
              </div>
              <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                {venues.map((v) => {
                  const state = marketState?.venues?.[v.id];
                  return (
                    <div key={v.id} className="bg-[#161B26] border border-[#232B3B] p-3.5 rounded flex flex-col justify-between">
                      <div>
                        <div className="flex justify-between items-center">
                          <span className="font-mono font-bold text-sm text-white">{v.name}</span>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                            state?.is_healthy ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800' : 'bg-rose-950/60 text-rose-400 border border-rose-800'
                          }`}>
                            {state?.is_healthy ? 'ONLINE' : 'DEGRADED'}
                          </span>
                        </div>
                        <div className="text-[11px] text-[#94A3B8] mt-1 font-mono">{v.network} • {v.type}</div>
                        <p className="text-[11px] text-[#64748B] mt-2 line-clamp-2">{v.capabilities.description}</p>
                      </div>

                      <div className="mt-4 pt-3 border-t border-[#232B3B] space-y-1 text-xs font-mono">
                        <div className="flex justify-between">
                          <span className="text-[#64748B]">Mid Price:</span>
                          <span className="text-white">${state?.mid_price ? Number(state.mid_price).toFixed(2) : '2500.00'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[#64748B]">Spread:</span>
                          <span className="text-white">{state?.spread_bps ? Number(state.spread_bps).toFixed(2) : '1.50'} bps</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[#64748B]">Funding (8h):</span>
                          <span className="text-blue-400">+{state?.funding_rate_8h_bps ? Number(state.funding_rate_8h_bps).toFixed(2) : '1.00'} bps</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[#64748B]">L2 Gas Fee:</span>
                          <span className="text-[#94A3B8]">{v.gas_required ? '~$1.80 (Arbitrum L2)' : '$0.00 (Gasless L1)'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[#64748B]">Latency:</span>
                          <span className="text-emerald-400">{state?.latency_ms ? state.latency_ms.toFixed(0) : '24'} ms</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Microstructure Depth Bands */}
            <div className="bg-[#10141D] border border-[#1F2633] rounded">
              <div className="px-4 py-2.5 border-b border-[#1F2633] text-xs font-mono font-semibold text-white">
                AGGREGATED ORDER-BOOK DEPTH BANDS (VWAP EXECUTABLE LIQUIDITY)
              </div>
              <div className="p-4 overflow-x-auto">
                <table className="w-full text-xs font-mono text-left">
                  <thead>
                    <tr className="text-[#64748B] border-b border-[#1F2633]">
                      <th className="pb-2">BAND OFFSET</th>
                      <th className="pb-2">BID DEPTH (USD)</th>
                      <th className="pb-2">BID QTY (ETH)</th>
                      <th className="pb-2">ASK DEPTH (USD)</th>
                      <th className="pb-2">ASK QTY (ETH)</th>
                      <th className="pb-2">TOTAL TRANCHE DEPTH</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1F2633]">
                    {[
                      { offset: '±10 bps', bidUsd: 1425000, bidQty: 570.0, askUsd: 1380000, askQty: 552.0 },
                      { offset: '±25 bps', bidUsd: 3850000, bidQty: 1540.0, askUsd: 3620000, askQty: 1448.0 },
                      { offset: '±50 bps', bidUsd: 7920000, bidQty: 3168.0, askUsd: 7450000, askQty: 2980.0 },
                      { offset: '±100 bps', bidUsd: 18400000, bidQty: 7360.0, askUsd: 17200000, askQty: 6880.0 },
                    ].map((row, idx) => (
                      <tr key={idx} className="hover:bg-[#161B26]">
                        <td className="py-2.5 font-bold text-white">{row.offset}</td>
                        <td className="py-2.5 text-emerald-400 tabular-nums">${row.bidUsd.toLocaleString()}</td>
                        <td className="py-2.5 text-[#94A3B8] tabular-nums">{row.bidQty.toFixed(1)}</td>
                        <td className="py-2.5 text-rose-400 tabular-nums">${row.askUsd.toLocaleString()}</td>
                        <td className="py-2.5 text-[#94A3B8] tabular-nums">{row.askQty.toFixed(1)}</td>
                        <td className="py-2.5 text-white tabular-nums">${(row.bidUsd + row.askUsd).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* VIEW 2: MARKET EXPLORER */}
        {activeTab === 'MARKET_EXPLORER' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center bg-[#10141D] border border-[#1F2633] p-3 rounded text-xs font-mono">
              <div className="flex items-center space-x-3">
                <span className="text-[#64748B]">SELECT VENUE FEED:</span>
                {(['HYPERLIQUID', 'GMX_V2', 'MOCK_CLOB'] as const).map((v) => (
                  <button
                    key={v}
                    onClick={() => setSelectedVenue(v)}
                    className={`px-3 py-1.5 rounded font-bold border transition-colors ${
                      selectedVenue === v
                        ? 'bg-blue-600 text-white border-blue-500'
                        : 'bg-[#161B26] text-[#94A3B8] border-[#2D3748] hover:text-white'
                    }`}
                  >
                    {v.replace('_', ' ')}
                  </button>
                ))}
              </div>
              <div className="text-[#64748B]">
                STATUS: {orderBook?.is_stale ? 'STALE' : 'LIVE'} • SYMBOL: ETH-PERP
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Asks (Sells) Table */}
              <div className="bg-[#10141D] border border-[#1F2633] rounded">
                <div className="px-4 py-2 border-b border-[#1F2633] text-xs font-mono font-semibold text-rose-400 flex justify-between">
                  <span>ORDER BOOK ASKS (OFFERS)</span>
                  <span className="text-[#64748B]">DEPTH: 15 LEVELS</span>
                </div>
                <div className="p-3">
                  <table className="w-full text-xs font-mono text-left">
                    <thead>
                      <tr className="text-[#64748B] border-b border-[#1F2633]">
                        <th className="pb-1.5">ASK PRICE</th>
                        <th className="pb-1.5">SIZE (ETH)</th>
                        <th className="pb-1.5 text-right">NOTIONAL (USD)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1F2633]">
                      {(orderBook?.asks || []).slice(0, 12).map((a, i) => {
                        const px = Number(a.price);
                        const sz = Number(a.size);
                        return (
                          <tr key={i} className="hover:bg-[#161B26]">
                            <td className="py-1 text-rose-400 font-bold tabular-nums">${px.toFixed(2)}</td>
                            <td className="py-1 text-[#E2E8F0] tabular-nums">{sz.toFixed(4)}</td>
                            <td className="py-1 text-right text-[#94A3B8] tabular-nums">${(px * sz).toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Bids (Buys) Table */}
              <div className="bg-[#10141D] border border-[#1F2633] rounded">
                <div className="px-4 py-2 border-b border-[#1F2633] text-xs font-mono font-semibold text-emerald-400 flex justify-between">
                  <span>ORDER BOOK BIDS (BIDS)</span>
                  <span className="text-[#64748B]">DEPTH: 15 LEVELS</span>
                </div>
                <div className="p-3">
                  <table className="w-full text-xs font-mono text-left">
                    <thead>
                      <tr className="text-[#64748B] border-b border-[#1F2633]">
                        <th className="pb-1.5">BID PRICE</th>
                        <th className="pb-1.5">SIZE (ETH)</th>
                        <th className="pb-1.5 text-right">NOTIONAL (USD)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1F2633]">
                      {(orderBook?.bids || []).slice(0, 12).map((b, i) => {
                        const px = Number(b.price);
                        const sz = Number(b.size);
                        return (
                          <tr key={i} className="hover:bg-[#161B26]">
                            <td className="py-1 text-emerald-400 font-bold tabular-nums">${px.toFixed(2)}</td>
                            <td className="py-1 text-[#E2E8F0] tabular-nums">{sz.toFixed(4)}</td>
                            <td className="py-1 text-right text-[#94A3B8] tabular-nums">${(px * sz).toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* VIEW 3: EXECUTION WORKBENCH */}
        {activeTab === 'EXECUTION_WORKBENCH' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* Left: Order Parameter Form */}
            <div className="lg:col-span-5 bg-[#10141D] border border-[#1F2633] p-4 rounded space-y-4">
              <div className="border-b border-[#1F2633] pb-2 text-xs font-mono font-bold text-white tracking-wide">
                ORDER EXECUTION SPECIFICATION
              </div>

              {/* Side Selector */}
              <div>
                <label className="text-[11px] font-mono text-[#64748B] block mb-1">DIRECTION</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setOrderSide('BUY')}
                    className={`py-2 rounded font-mono font-bold text-xs border transition-colors ${
                      orderSide === 'BUY'
                        ? 'bg-emerald-600 text-white border-emerald-500'
                        : 'bg-[#161B26] text-[#94A3B8] border-[#2D3748] hover:text-white'
                    }`}
                  >
                    BUY / LONG
                  </button>
                  <button
                    onClick={() => setOrderSide('SELL')}
                    className={`py-2 rounded font-mono font-bold text-xs border transition-colors ${
                      orderSide === 'SELL'
                        ? 'bg-rose-600 text-white border-rose-500'
                        : 'bg-[#161B26] text-[#94A3B8] border-[#2D3748] hover:text-white'
                    }`}
                  >
                    SELL / SHORT
                  </button>
                </div>
              </div>

              {/* Notional Size */}
              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-[11px] font-mono text-[#64748B]">ORDER NOTIONAL (USD)</label>
                  <span className="text-[11px] font-mono text-white tabular-nums">${orderNotional.toLocaleString()}</span>
                </div>
                <input
                  type="number"
                  value={orderNotional}
                  onChange={(e) => setOrderNotional(Math.max(1000, Number(e.target.value)))}
                  className="w-full bg-[#161B26] border border-[#2D3748] px-3 py-2 rounded text-xs font-mono text-white focus:outline-none focus:border-blue-500"
                />
                <div className="grid grid-cols-4 gap-1.5 mt-2">
                  {[25000, 50000, 100000, 250000].map((amt) => (
                    <button
                      key={amt}
                      onClick={() => setOrderNotional(amt)}
                      className="py-1 bg-[#161B26] border border-[#2D3748] rounded text-[10px] font-mono text-[#94A3B8] hover:text-white"
                    >
                      ${amt / 1000}k
                    </button>
                  ))}
                </div>
              </div>

              {/* Slippage & Horizon */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-mono text-[#64748B] block mb-1">MAX SLIPPAGE (BPS)</label>
                  <input
                    type="number"
                    value={maxSlippageBps}
                    onChange={(e) => setMaxSlippageBps(Number(e.target.value))}
                    className="w-full bg-[#161B26] border border-[#2D3748] px-3 py-1.5 rounded text-xs font-mono text-white"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-mono text-[#64748B] block mb-1">HOLDING HORIZON (HRS)</label>
                  <input
                    type="number"
                    value={holdingHorizonHours}
                    onChange={(e) => setHoldingHorizonHours(Number(e.target.value))}
                    className="w-full bg-[#161B26] border border-[#2D3748] px-3 py-1.5 rounded text-xs font-mono text-white"
                  />
                </div>
              </div>

              {/* Submit Buttons */}
              <div className="pt-2 space-y-2">
                <button
                  onClick={handleGenerateQuote}
                  disabled={isQuoting}
                  className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-mono font-bold text-xs rounded transition-colors disabled:opacity-50"
                >
                  {isQuoting ? 'CALCULATING OPTIMAL ROUTE...' : 'GENERATE EXECUTION QUOTE'}
                </button>

                {activeQuote && (
                  <button
                    onClick={handleExecutePaperOrder}
                    className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-mono font-bold text-xs rounded transition-colors"
                  >
                    DISPATCH SIMULATED PAPER ORDER
                  </button>
                )}

                {executionStatus && (
                  <div className="p-2.5 rounded text-xs font-mono bg-[#161B26] border border-[#2D3748] text-white">
                    {executionStatus}
                  </div>
                )}
              </div>
            </div>

            {/* Right: Quote Intelligence Result */}
            <div className="lg:col-span-7 bg-[#10141D] border border-[#1F2633] p-4 rounded space-y-4">
              <div className="border-b border-[#1F2633] pb-2 text-xs font-mono font-bold text-white tracking-wide flex justify-between items-center">
                <span>ORION EXECUTION INTELLIGENCE QUOTE</span>
                {activeQuote && (
                  <span className="text-[#64748B] text-[11px]">ID: {activeQuote.quote_id}</span>
                )}
              </div>

              {!activeQuote ? (
                <div className="py-20 text-center font-mono text-xs text-[#64748B]">
                  No quote evaluated. Click &apos;GENERATE EXECUTION QUOTE&apos; to walk order books across Hyperliquid & GMX.
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Headline Route Card */}
                  <div className="bg-[#161B26] border border-[#2D3748] p-4 rounded">
                    <div className="flex justify-between items-start">
                      <div>
                        <span className="text-[11px] font-mono text-[#64748B]">RECOMMENDED ROUTE:</span>
                        <div className="text-lg font-mono font-bold text-white mt-0.5">
                          {activeQuote.is_split_route ? 'MULTI-VENUE SPLIT ALLOCATION' : `${activeQuote.recommended_venue} SINGLE`}
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-[11px] font-mono text-[#64748B]">TOTAL EXPECTED COST:</span>
                        <div className="text-lg font-mono font-bold text-blue-400 tabular-nums">
                          {Number(activeQuote.blended_breakdown.total_cost_bps).toFixed(2)} bps / ${Number(activeQuote.blended_breakdown.total_cost_usd).toFixed(2)}
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-3 mt-4 pt-3 border-t border-[#232B3B] text-xs font-mono">
                      <div>
                        <span className="text-[#64748B]">Expected VWAP:</span>
                        <div className="text-white font-bold tabular-nums">${Number(activeQuote.blended_vwap).toFixed(2)}</div>
                      </div>
                      <div>
                        <span className="text-[#64748B]">Arrival Mid:</span>
                        <div className="text-white font-bold tabular-nums">${Number(activeQuote.blended_breakdown.reference_price).toFixed(2)}</div>
                      </div>
                      <div>
                        <span className="text-[#64748B]">Confidence Score:</span>
                        <div className="text-emerald-400 font-bold">{(activeQuote.confidence_score * 100).toFixed(0)}%</div>
                      </div>
                    </div>
                  </div>

                  {/* Component Breakdown Table */}
                  <div>
                    <span className="text-xs font-mono font-semibold text-white block mb-2">
                      DETERMINISTIC COST ATTRIBUTION BREAKDOWN
                    </span>
                    <table className="w-full text-xs font-mono text-left bg-[#161B26] border border-[#232B3B] rounded overflow-hidden">
                      <thead className="border-b border-[#232B3B] text-[#64748B]">
                        <tr>
                          <th className="p-2.5">COST COMPONENT</th>
                          <th className="p-2.5">BASIS POINTS</th>
                          <th className="p-2.5">DOLLAR IMPACT</th>
                          <th className="p-2.5">NATURE / MECHANISM</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#232B3B]">
                        <tr>
                          <td className="p-2.5 font-bold text-white">Bid/Ask Half-Spread</td>
                          <td className="p-2.5 tabular-nums text-white">{Number(activeQuote.blended_breakdown.spread_cost_bps).toFixed(2)} bps</td>
                          <td className="p-2.5 tabular-nums text-white">${Number(activeQuote.blended_breakdown.spread_cost_usd).toFixed(2)}</td>
                          <td className="p-2.5 text-[#94A3B8]">Immediate crossing cost at top of book</td>
                        </tr>
                        <tr>
                          <td className="p-2.5 font-bold text-white">Market Impact (Depth Slippage)</td>
                          <td className="p-2.5 tabular-nums text-white">{Number(activeQuote.blended_breakdown.market_impact_bps).toFixed(2)} bps</td>
                          <td className="p-2.5 tabular-nums text-white">${Number(activeQuote.blended_breakdown.market_impact_usd).toFixed(2)}</td>
                          <td className="p-2.5 text-[#94A3B8]">VWAP slippage from walking available liquidity</td>
                        </tr>
                        <tr>
                          <td className="p-2.5 font-bold text-white">Trading Fees</td>
                          <td className="p-2.5 tabular-nums text-white">{Number(activeQuote.blended_breakdown.trading_fee_bps).toFixed(2)} bps</td>
                          <td className="p-2.5 tabular-nums text-white">${Number(activeQuote.blended_breakdown.trading_fee_usd).toFixed(2)}</td>
                          <td className="p-2.5 text-[#94A3B8]">Venue taker/swap protocol fee tier</td>
                        </tr>
                        <tr>
                          <td className="p-2.5 font-bold text-white">Expected Funding Cost</td>
                          <td className="p-2.5 tabular-nums text-white">{Number(activeQuote.blended_breakdown.funding_cost_bps).toFixed(2)} bps</td>
                          <td className="p-2.5 tabular-nums text-white">${Number(activeQuote.blended_breakdown.funding_cost_usd).toFixed(2)}</td>
                          <td className="p-2.5 text-[#94A3B8]">Expected net accrual over {holdingHorizonHours}h horizon</td>
                        </tr>
                        <tr>
                          <td className="p-2.5 font-bold text-white">L2 Gas / Execution Transaction</td>
                          <td className="p-2.5 tabular-nums text-white">{Number(activeQuote.blended_breakdown.transaction_cost_bps).toFixed(2)} bps</td>
                          <td className="p-2.5 tabular-nums text-white">${Number(activeQuote.blended_breakdown.transaction_cost_usd).toFixed(2)}</td>
                          <td className="p-2.5 text-[#94A3B8]">On-chain Arbitrum gas & keeper execution fee</td>
                        </tr>
                        <tr>
                          <td className="p-2.5 font-bold text-white">Adverse Selection Proxy</td>
                          <td className="p-2.5 tabular-nums text-white">{Number(activeQuote.blended_breakdown.adverse_selection_bps).toFixed(2)} bps</td>
                          <td className="p-2.5 tabular-nums text-white">${Number(activeQuote.blended_breakdown.adverse_selection_usd).toFixed(2)}</td>
                          <td className="p-2.5 text-[#94A3B8]">Trade size vs available depth skew estimator</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  {/* Explainability Callout */}
                  <div className="p-3 bg-[#161B26] border border-[#232B3B] rounded text-xs font-mono space-y-1">
                    <span className="font-bold text-blue-400">EXPLAINABILITY AUDIT:</span>
                    <p className="text-[#94A3B8]">{activeQuote.explanation.why_chosen}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* VIEW 4: ROUTE COMPARISON */}
        {activeTab === 'ROUTE_COMPARISON' && (
          <div className="bg-[#10141D] border border-[#1F2633] rounded p-4 space-y-4">
            <div className="text-xs font-mono font-bold text-white tracking-wide border-b border-[#1F2633] pb-2">
              VENUE-BY-VENUE COMPARATIVE EXECUTION MATRIX (ETH-PERP)
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono text-left">
                <thead>
                  <tr className="text-[#64748B] border-b border-[#1F2633]">
                    <th className="pb-2.5">VENUE / STRATEGY</th>
                    <th className="pb-2.5">ALLOCATION</th>
                    <th className="pb-2.5">NOTIONAL (USD)</th>
                    <th className="pb-2.5">EXPECTED VWAP</th>
                    <th className="pb-2.5">TOTAL COST (BPS)</th>
                    <th className="pb-2.5">SPREAD</th>
                    <th className="pb-2.5">IMPACT</th>
                    <th className="pb-2.5">FEE</th>
                    <th className="pb-2.5">GAS</th>
                    <th className="pb-2.5">ELIGIBILITY</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1F2633]">
                  {activeQuote?.candidates.map((c, i) => (
                    <tr key={i} className="hover:bg-[#161B26]">
                      <td className="py-2.5 font-bold text-white">{c.venue_id}</td>
                      <td className="py-2.5 tabular-nums text-blue-400">{c.allocation_pct}%</td>
                      <td className="py-2.5 tabular-nums text-white">${Number(c.allocated_notional).toLocaleString()}</td>
                      <td className="py-2.5 tabular-nums text-white">${Number(c.expected_vwap).toFixed(2)}</td>
                      <td className="py-2.5 tabular-nums font-bold text-white">{Number(c.breakdown.total_cost_bps).toFixed(2)} bps</td>
                      <td className="py-2.5 tabular-nums text-[#94A3B8]">{Number(c.breakdown.spread_cost_bps).toFixed(2)}</td>
                      <td className="py-2.5 tabular-nums text-[#94A3B8]">{Number(c.breakdown.market_impact_bps).toFixed(2)}</td>
                      <td className="py-2.5 tabular-nums text-[#94A3B8]">{Number(c.breakdown.trading_fee_bps).toFixed(2)}</td>
                      <td className="py-2.5 tabular-nums text-[#94A3B8]">${Number(c.breakdown.transaction_cost_usd).toFixed(2)}</td>
                      <td className="py-2.5">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          c.is_eligible ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800' : 'bg-rose-950/60 text-rose-400 border border-rose-800'
                        }`}>
                          {c.is_eligible ? 'ELIGIBLE' : 'REJECTED'}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {(!activeQuote || activeQuote.candidates.length === 0) && (
                    <tr>
                      <td colSpan={10} className="py-8 text-center text-[#64748B]">
                        Generate an order quote in the Execution Workbench to view comparative venue evaluations.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* VIEW 5: PAPER TRADING */}
        {activeTab === 'PAPER_TRADING' && (
          <div className="space-y-4">
            {/* Account KPI Header */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <div className="bg-[#10141D] border border-[#1F2633] p-3 rounded">
                <span className="text-[11px] font-mono text-[#64748B]">ACCOUNT EQUITY</span>
                <div className="text-xl font-mono font-bold text-white mt-1 tabular-nums">
                  ${paperAccount?.equity_usd ? Number(paperAccount.equity_usd).toLocaleString() : '100,000.00'}
                </div>
              </div>
              <div className="bg-[#10141D] border border-[#1F2633] p-3 rounded">
                <span className="text-[11px] font-mono text-[#64748B]">AVAILABLE MARGIN</span>
                <div className="text-xl font-mono font-bold text-white mt-1 tabular-nums">
                  ${paperAccount?.available_margin_usd ? Number(paperAccount.available_margin_usd).toLocaleString() : '100,000.00'}
                </div>
              </div>
              <div className="bg-[#10141D] border border-[#1F2633] p-3 rounded">
                <span className="text-[11px] font-mono text-[#64748B]">REALIZED PnL</span>
                <div className={`text-xl font-mono font-bold mt-1 tabular-nums ${
                  Number(paperAccount?.realized_pnl_usd || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}>
                  ${Number(paperAccount?.realized_pnl_usd || 0).toFixed(2)}
                </div>
              </div>
              <div className="bg-[#10141D] border border-[#1F2633] p-3 rounded">
                <span className="text-[11px] font-mono text-[#64748B]">UNREALIZED PnL</span>
                <div className={`text-xl font-mono font-bold mt-1 tabular-nums ${
                  Number(paperAccount?.unrealized_pnl_usd || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}>
                  ${Number(paperAccount?.unrealized_pnl_usd || 0).toFixed(2)}
                </div>
              </div>
              <div className="bg-[#10141D] border border-[#1F2633] p-3 rounded flex flex-col justify-between">
                <span className="text-[11px] font-mono text-[#64748B]">ACCOUNT ACTIONS</span>
                <button
                  onClick={handleResetAccount}
                  className="w-full py-1.5 px-2 bg-rose-950/60 hover:bg-rose-900 border border-rose-800 text-rose-300 rounded font-mono text-xs font-bold transition-colors"
                >
                  RESET PAPER ACCOUNT
                </button>
              </div>
            </div>

            {/* Positions Table */}
            <div className="bg-[#10141D] border border-[#1F2633] rounded">
              <div className="px-4 py-2.5 border-b border-[#1F2633] text-xs font-mono font-bold text-white">
                ACTIVE PAPER POSITIONS ({paperAccount?.positions?.length || 0})
              </div>
              <div className="p-3 overflow-x-auto">
                <table className="w-full text-xs font-mono text-left">
                  <thead>
                    <tr className="text-[#64748B] border-b border-[#1F2633]">
                      <th className="pb-2">SYMBOL</th>
                      <th className="pb-2">VENUE</th>
                      <th className="pb-2">SIDE</th>
                      <th className="pb-2">SIZE (ETH)</th>
                      <th className="pb-2">ENTRY PRICE</th>
                      <th className="pb-2">MARK PRICE</th>
                      <th className="pb-2">NOTIONAL (USD)</th>
                      <th className="pb-2">UNREALIZED PnL</th>
                      <th className="pb-2">LEVERAGE</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1F2633]">
                    {(paperAccount?.positions || []).map((pos, i) => {
                      const uPnl = Number(pos.unrealized_pnl);
                      return (
                        <tr key={i} className="hover:bg-[#161B26]">
                          <td className="py-2.5 font-bold text-white">{pos.symbol}</td>
                          <td className="py-2.5 text-[#94A3B8]">{pos.venue_id}</td>
                          <td className="py-2.5 font-bold text-emerald-400">{pos.side}</td>
                          <td className="py-2.5 tabular-nums text-white">{Number(pos.quantity).toFixed(4)}</td>
                          <td className="py-2.5 tabular-nums text-white">${Number(pos.entry_price).toFixed(2)}</td>
                          <td className="py-2.5 tabular-nums text-white">${Number(pos.mark_price).toFixed(2)}</td>
                          <td className="py-2.5 tabular-nums text-white">${Number(pos.notional_usd).toLocaleString()}</td>
                          <td className={`py-2.5 tabular-nums font-bold ${uPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                            ${uPnl.toFixed(2)}
                          </td>
                          <td className="py-2.5 text-[#94A3B8]">{Number(pos.leverage)}x</td>
                        </tr>
                      );
                    })}
                    {(!paperAccount?.positions || paperAccount.positions.length === 0) && (
                      <tr>
                        <td colSpan={9} className="py-6 text-center text-[#64748B]">
                          No open positions. Submit orders via Execution Workbench to build simulated paper inventory.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Orders & Fills Table */}
            <div className="bg-[#10141D] border border-[#1F2633] rounded">
              <div className="px-4 py-2.5 border-b border-[#1F2633] text-xs font-mono font-bold text-white">
                SIMULATED ORDER HISTORY ({paperOrders.length})
              </div>
              <div className="p-3 overflow-x-auto">
                <table className="w-full text-xs font-mono text-left">
                  <thead>
                    <tr className="text-[#64748B] border-b border-[#1F2633]">
                      <th className="pb-2">TIME</th>
                      <th className="pb-2">ORDER ID</th>
                      <th className="pb-2">SIDE</th>
                      <th className="pb-2">NOTIONAL</th>
                      <th className="pb-2">FILLED QTY</th>
                      <th className="pb-2">AVG FILL PRICE</th>
                      <th className="pb-2">FEES PAID</th>
                      <th className="pb-2">SLIPPAGE</th>
                      <th className="pb-2">STATUS</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1F2633]">
                    {paperOrders.map((ord, i) => (
                      <tr key={i} className="hover:bg-[#161B26]">
                        <td className="py-2 text-[#64748B]">{ord.created_at?.substring(11, 19) || '10:00:00'}</td>
                        <td className="py-2 text-white font-bold">{ord.order_id}</td>
                        <td className="py-2 text-emerald-400">{ord.side}</td>
                        <td className="py-2 text-white tabular-nums">${Number(ord.requested_notional).toLocaleString()}</td>
                        <td className="py-2 text-white tabular-nums">{Number(ord.filled_quantity).toFixed(4)}</td>
                        <td className="py-2 text-white tabular-nums">${Number(ord.avg_fill_price).toFixed(2)}</td>
                        <td className="py-2 text-[#94A3B8] tabular-nums">${Number(ord.total_fee_usd).toFixed(2)}</td>
                        <td className="py-2 text-[#94A3B8] tabular-nums">{Number(ord.slippage_bps).toFixed(2)} bps</td>
                        <td className="py-2">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            ord.status === 'FILLED' ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800' : 'bg-rose-950/60 text-rose-400 border border-rose-800'
                          }`}>
                            {ord.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* VIEW 6: BACKTESTING */}
        {activeTab === 'BACKTESTING' && (
          <div className="space-y-4">
            {/* Launcher Card */}
            <div className="bg-[#10141D] border border-[#1F2633] p-4 rounded space-y-3">
              <div className="text-xs font-mono font-bold text-white tracking-wide border-b border-[#1F2633] pb-2">
                HISTORICAL REPLAY & EXECUTION ATTRIBUTION SIMULATOR
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="text-[11px] font-mono text-[#64748B] block mb-1">EXPERIMENT NAME</label>
                  <input
                    type="text"
                    value={backtestName}
                    onChange={(e) => setBacktestName(e.target.value)}
                    className="w-full bg-[#161B26] border border-[#2D3748] px-3 py-1.5 rounded text-xs font-mono text-white"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-mono text-[#64748B] block mb-1">SAMPLE ORDER COUNT</label>
                  <input
                    type="number"
                    value={backtestSamples}
                    onChange={(e) => setBacktestSamples(Number(e.target.value))}
                    className="w-full bg-[#161B26] border border-[#2D3748] px-3 py-1.5 rounded text-xs font-mono text-white"
                  />
                </div>
                <div className="flex items-end">
                  <button
                    onClick={handleRunBacktest}
                    disabled={isRunningBacktest}
                    className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white font-mono font-bold text-xs rounded transition-colors disabled:opacity-50"
                  >
                    {isRunningBacktest ? 'SIMULATING EXECUTION...' : 'LAUNCH BACKTEST REPLAY'}
                  </button>
                </div>
              </div>
            </div>

            {/* Backtest Results Table */}
            <div className="bg-[#10141D] border border-[#1F2633] rounded">
              <div className="px-4 py-2.5 border-b border-[#1F2633] text-xs font-mono font-bold text-white">
                COMPLETED BACKTEST RUNS ({backtests.length})
              </div>
              <div className="p-3 overflow-x-auto">
                <table className="w-full text-xs font-mono text-left">
                  <thead>
                    <tr className="text-[#64748B] border-b border-[#1F2633]">
                      <th className="pb-2">RUN ID</th>
                      <th className="pb-2">BENCHMARK NAME</th>
                      <th className="pb-2">ORDERS</th>
                      <th className="pb-2">NAIVE BASELINE</th>
                      <th className="pb-2">BEST SINGLE</th>
                      <th className="pb-2">ORION ROUTE</th>
                      <th className="pb-2">ALPHA SAVINGS (BPS)</th>
                      <th className="pb-2">TOTAL SAVINGS ($)</th>
                      <th className="pb-2">STATUS</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1F2633]">
                    {backtests.map((b, i) => (
                      <tr key={i} className="hover:bg-[#161B26]">
                        <td className="py-2.5 font-bold text-white">{b.run_id}</td>
                        <td className="py-2.5 text-[#94A3B8]">{b.name}</td>
                        <td className="py-2.5 tabular-nums text-white">{b.order_count}</td>
                        <td className="py-2.5 tabular-nums text-rose-400">{b.baseline_naive_cost_bps.toFixed(2)} bps</td>
                        <td className="py-2.5 tabular-nums text-[#94A3B8]">{b.baseline_single_cost_bps.toFixed(2)} bps</td>
                        <td className="py-2.5 tabular-nums text-emerald-400 font-bold">{b.orion_route_cost_bps.toFixed(2)} bps</td>
                        <td className="py-2.5 tabular-nums text-blue-400 font-bold">+{b.mean_savings_vs_naive_bps.toFixed(2)} bps</td>
                        <td className="py-2.5 tabular-nums text-white font-bold">${b.total_savings_usd.toLocaleString()}</td>
                        <td className="py-2.5">
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950/60 text-emerald-400 border border-emerald-800">
                            {b.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                    {backtests.length === 0 && (
                      <tr>
                        <td colSpan={9} className="py-8 text-center text-[#64748B]">
                          No historical replay runs. Launch a backtest to measure ORION execution alpha versus naive baselines.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* VIEW 7: RISK CENTER */}
        {activeTab === 'RISK_CENTER' && (
          <div className="space-y-4">
            <div className="bg-[#10141D] border border-[#1F2633] p-4 rounded space-y-4">
              <div className="border-b border-[#1F2633] pb-2 text-xs font-mono font-bold text-white tracking-wide flex justify-between items-center">
                <span>PRE-TRADE RISK LIMITS & SAFETY ENFORCEMENT</span>
                <span className={`px-2.5 py-1 rounded text-xs font-mono font-bold ${
                  killSwitchActive ? 'bg-rose-950 text-rose-400 border border-rose-800' : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                }`}>
                  {killSwitchActive ? 'HALTED BY OPERATOR' : 'PRE-TRADE GUARDS ACTIVE'}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-[#161B26] border border-[#232B3B] p-3.5 rounded space-y-2 text-xs font-mono">
                  <div className="font-bold text-white mb-2">NOTIONAL & POSITION EXPOSURE GUARDS</div>
                  <div className="flex justify-between py-1 border-b border-[#232B3B]">
                    <span className="text-[#64748B]">Max Order Notional:</span>
                    <span className="text-white font-bold">$250,000.00</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[#232B3B]">
                    <span className="text-[#64748B]">Max Portfolio Position Exposure:</span>
                    <span className="text-white font-bold">$1,000,000.00</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[#232B3B]">
                    <span className="text-[#64748B]">Max Concurrent Open Orders:</span>
                    <span className="text-white font-bold">10 Orders</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-[#64748B]">Price Collar Limit:</span>
                    <span className="text-white font-bold">100.0 bps (1.00%)</span>
                  </div>
                </div>

                <div className="bg-[#161B26] border border-[#232B3B] p-3.5 rounded space-y-2 text-xs font-mono">
                  <div className="font-bold text-white mb-2">DATA FRESHNESS & FAIL-CLOSED GUARDS</div>
                  <div className="flex justify-between py-1 border-b border-[#232B3B]">
                    <span className="text-[#64748B]">Max Market Data Staleness:</span>
                    <span className="text-white font-bold">15.0 seconds</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[#232B3B]">
                    <span className="text-[#64748B]">Fail-Closed on Outage:</span>
                    <span className="text-emerald-400 font-bold">ENFORCED (FAIL-CLOSED)</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[#232B3B]">
                    <span className="text-[#64748B]">Duplicate Request Idempotency:</span>
                    <span className="text-emerald-400 font-bold">120s Deduplication Window</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-[#64748B]">Live Execution Interlock:</span>
                    <span className="text-blue-400 font-bold">PAPER MODE (SAFE)</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* VIEW 8: SETTINGS & AUDIT */}
        {activeTab === 'SETTINGS' && (
          <div className="space-y-4">
            <div className="bg-[#10141D] border border-[#1F2633] p-4 rounded space-y-4">
              <div className="border-b border-[#1F2633] pb-2 text-xs font-mono font-bold text-white tracking-wide">
                ORION OPERATIONAL CONFIGURATION & ENVIRONMENT
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs font-mono">
                <div className="bg-[#161B26] p-3 rounded border border-[#232B3B]">
                  <span className="text-[#64748B]">EXECUTION MODE</span>
                  <div className="text-sm font-bold text-white mt-1">PAPER (Simulated)</div>
                </div>
                <div className="bg-[#161B26] p-3 rounded border border-[#232B3B]">
                  <span className="text-[#64748B]">HYPERLIQUID TAKER FEE</span>
                  <div className="text-sm font-bold text-white mt-1">3.5 bps</div>
                </div>
                <div className="bg-[#161B26] p-3 rounded border border-[#232B3B]">
                  <span className="text-[#64748B]">GMX v2 BASE FEE</span>
                  <div className="text-sm font-bold text-white mt-1">5.0 bps + Impact</div>
                </div>
              </div>
            </div>

            <div className="bg-[#10141D] border border-[#1F2633] rounded">
              <div className="px-4 py-2.5 border-b border-[#1F2633] text-xs font-mono font-bold text-white">
                IMMUTABLE AUDIT LOG LEDGER ({auditEvents.length})
              </div>
              <div className="p-3 overflow-x-auto">
                <table className="w-full text-xs font-mono text-left">
                  <thead>
                    <tr className="text-[#64748B] border-b border-[#1F2633]">
                      <th className="pb-2">TIME</th>
                      <th className="pb-2">EVENT ID</th>
                      <th className="pb-2">ACTOR</th>
                      <th className="pb-2">EVENT TYPE</th>
                      <th className="pb-2">CORRELATION ID</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1F2633]">
                    {auditEvents.map((a, i) => (
                      <tr key={i} className="hover:bg-[#161B26]">
                        <td className="py-2 text-[#64748B]">{a.timestamp?.substring(11, 19) || '10:00:00'}</td>
                        <td className="py-2 text-white font-bold">{a.event_id}</td>
                        <td className="py-2 text-blue-400">{a.actor}</td>
                        <td className="py-2 text-emerald-400">{a.event_type}</td>
                        <td className="py-2 text-[#94A3B8]">{a.correlation_id}</td>
                      </tr>
                    ))}
                    {auditEvents.length === 0 && (
                      <tr>
                        <td colSpan={5} className="py-6 text-center text-[#64748B]">
                          No audit events recorded yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
