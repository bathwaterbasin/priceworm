"""
Priceworm MCP Server
Sacred time trading metrics for BTC analysis.

Four sacred times (UTC):
- 00:43 → Shanghai
- 06:43 → Dubai  
- 12:43 → DC
- 18:43 → Texas
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from enum import Enum

import ccxt
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("priceworm_mcp")

# Sacred times in UTC (hour, minute)
SACRED_TIMES = [
    (23, 43, "Shanghai"),
    (5, 43, "Dubai"),
    (11, 43, "DC"),
    (17, 43, "Texas"),
]

# Exchange setup
exchange = ccxt.binance()


def get_sacred_boundaries(now: datetime) -> dict:
    """Calculate current, previous, and next sacred time boundaries."""
    today = now.date()
    
    # Build list of sacred moments for today and adjacent days
    sacred_moments = []
    for day_offset in [-1, 0, 1]:
        day = today + timedelta(days=day_offset)
        for hour, minute, name in SACRED_TIMES:
            moment = datetime(day.year, day.month, day.day, hour, minute, tzinfo=timezone.utc)
            sacred_moments.append((moment, name))
    
    # Sort by time
    sacred_moments.sort(key=lambda x: x[0])
    
    # Find current window
    current_sacred = None
    current_name = None
    next_sacred = None
    next_name = None
    
    for i, (moment, name) in enumerate(sacred_moments):
        if moment <= now:
            current_sacred = moment
            current_name = name
            if i + 1 < len(sacred_moments):
                next_sacred, next_name = sacred_moments[i + 1]
        else:
            if current_sacred is None:
                # Edge case: now is before first moment
                current_sacred, current_name = sacred_moments[i - 1] if i > 0 else (moment, name)
                next_sacred, next_name = moment, name
            break
    
    # Get previous 3 windows
    previous_windows = []
    for i, (moment, name) in enumerate(sacred_moments):
        if moment == current_sacred:
            for j in range(1, 4):
                if i - j >= 0:
                    prev_start, prev_name = sacred_moments[i - j]
                    prev_end = sacred_moments[i - j + 1][0] if i - j + 1 < len(sacred_moments) else None
                    previous_windows.append({
                        "start": prev_start,
                        "end": prev_end,
                        "name": prev_name
                    })
            break
    
    return {
        "current_start": current_sacred,
        "current_name": current_name,
        "next_sacred": next_sacred,
        "next_name": next_name,
        "previous_windows": previous_windows
    }


def fetch_ohlcv(symbol: str, start_time: datetime, end_time: datetime) -> list:
    """Fetch 1m candles from exchange."""
    since = int(start_time.timestamp() * 1000)
    until = int(end_time.timestamp() * 1000)
    
    all_candles = []
    current_since = since
    
    while current_since < until:
        candles = exchange.fetch_ohlcv(
            symbol, 
            timeframe='1m', 
            since=current_since, 
            limit=1000
        )
        if not candles:
            break
        all_candles.extend(candles)
        current_since = candles[-1][0] + 60000  # Next minute
        if current_since >= until:
            break
    
    # Filter to exact range
    return [c for c in all_candles if since <= c[0] < until]


def calculate_window_metrics(candles: list) -> dict:
    """Calculate OHLCV metrics from 1m candles."""
    if not candles:
        return None
    
    open_price = candles[0][1]
    high_price = max(c[2] for c in candles)
    low_price = min(c[3] for c in candles)
    close_price = candles[-1][4]
    total_volume = sum(c[5] for c in candles)
    
    # Price position in range (0 = at low, 1 = at high)
    price_range = high_price - low_price
    position_in_range = (close_price - low_price) / price_range if price_range > 0 else 0.5
    
    # Direction
    change_pct = ((close_price - open_price) / open_price) * 100 if open_price > 0 else 0
    
    return {
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": total_volume,
        "change_pct": round(change_pct, 3),
        "position_in_range": round(position_in_range, 3),
        "candle_count": len(candles)
    }


class SymbolInput(BaseModel):
    """Input for symbol-based queries."""
    symbol: str = Field(
        default="BTC/USDT",
        description="Trading pair symbol (e.g., 'BTC/USDT', 'ETH/USDT')"
    )


@mcp.tool(
    name="current_window",
    annotations={
        "title": "Current Sacred Window Metrics",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def current_window(params: SymbolInput) -> str:
    """Get OHLCV metrics for the current sacred time window.
    
    Returns metrics from the most recent :43 boundary to now,
    including price action, volume, and time context.
    
    Args:
        params: Contains symbol (trading pair)
    
    Returns:
        JSON with current window metrics, time info, and next sacred countdown
    """
    now = datetime.now(timezone.utc)
    boundaries = get_sacred_boundaries(now)
    
    # Fetch candles from current window start to now
    candles = fetch_ohlcv(
        params.symbol,
        boundaries["current_start"],
        now
    )
    
    metrics = calculate_window_metrics(candles)
    
    # Time calculations
    elapsed = now - boundaries["current_start"]
    elapsed_minutes = elapsed.total_seconds() / 60
    window_pct = (elapsed_minutes / 360) * 100  # 360 min = 6h
    
    time_to_next = boundaries["next_sacred"] - now
    minutes_to_next = time_to_next.total_seconds() / 60
    
    result = {
        "now_utc": now.isoformat(),
        "window": {
            "name": boundaries["current_name"],
            "start_utc": boundaries["current_start"].isoformat(),
            "elapsed_minutes": round(elapsed_minutes, 1),
            "window_pct": round(window_pct, 1)
        },
        "next_sacred": {
            "name": boundaries["next_name"],
            "time_utc": boundaries["next_sacred"].isoformat(),
            "minutes_until": round(minutes_to_next, 1)
        },
        "metrics": metrics
    }
    
    return json.dumps(result, indent=2)


@mcp.tool(
    name="last_three_windows",
    annotations={
        "title": "Previous Three Sacred Windows",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def last_three_windows(params: SymbolInput) -> str:
    """Get OHLCV metrics for the previous three sacred time windows.
    
    Returns complete metrics for each of the last 3 six-hour windows,
    allowing trend analysis across sacred cycles.
    
    Args:
        params: Contains symbol (trading pair)
    
    Returns:
        JSON with metrics for each of the previous 3 windows
    """
    now = datetime.now(timezone.utc)
    boundaries = get_sacred_boundaries(now)
    
    windows_data = []
    
    for window in boundaries["previous_windows"]:
        if window["end"] is None:
            continue
            
        candles = fetch_ohlcv(
            params.symbol,
            window["start"],
            window["end"]
        )
        
        metrics = calculate_window_metrics(candles)
        
        windows_data.append({
            "name": window["name"],
            "start_utc": window["start"].isoformat(),
            "end_utc": window["end"].isoformat(),
            "metrics": metrics
        })
    
    # Calculate trend across windows
    if len(windows_data) >= 2:
        volume_trend = []
        price_trend = []
        for w in windows_data:
            if w["metrics"]:
                volume_trend.append(w["metrics"]["volume"])
                price_trend.append(w["metrics"]["change_pct"])
        
        summary = {
            "volume_expanding": volume_trend[0] > volume_trend[-1] if len(volume_trend) >= 2 else None,
            "net_change_pct": sum(price_trend) if price_trend else 0,
            "consecutive_direction": all(p > 0 for p in price_trend) or all(p < 0 for p in price_trend)
        }
    else:
        summary = None
    
    result = {
        "now_utc": now.isoformat(),
        "windows": windows_data,
        "summary": summary
    }
    
    return json.dumps(result, indent=2)


@mcp.tool(
    name="next_sacred",
    annotations={
        "title": "Next Sacred Time Info",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def next_sacred(params: SymbolInput) -> str:
    """Get countdown and context for the next sacred time.
    
    Returns time until next :43 boundary, which session it represents,
    and current price for reference.
    
    Args:
        params: Contains symbol (trading pair)
    
    Returns:
        JSON with next sacred time info and current price
    """
    now = datetime.now(timezone.utc)
    boundaries = get_sacred_boundaries(now)
    
    time_to_next = boundaries["next_sacred"] - now
    minutes_to_next = time_to_next.total_seconds() / 60
    hours_to_next = minutes_to_next / 60
    
    # Get current price
    ticker = exchange.fetch_ticker(params.symbol)
    
    result = {
        "now_utc": now.isoformat(),
        "current_window": boundaries["current_name"],
        "next": {
            "name": boundaries["next_name"],
            "time_utc": boundaries["next_sacred"].isoformat(),
            "countdown": {
                "hours": int(hours_to_next),
                "minutes": int(minutes_to_next % 60),
                "total_minutes": round(minutes_to_next, 1)
            }
        },
        "current_price": {
            "last": ticker["last"],
            "bid": ticker["bid"],
            "ask": ticker["ask"]
        }
    }
    
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run()
