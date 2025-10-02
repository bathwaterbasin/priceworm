#!/usr/bin/env python3
"""
Crypto Trading Metrics CLI - PATCHED VERSION
Fixed: Negative limit bug in session data
Added: Perpetual futures analysis, funding rates, institutional signals
"""

import argparse
import requests
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time
from pathlib import Path

def load_env():
    """Load environment variables from .env file"""
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    value = value.strip().strip('"').strip("'")
                    if key == 'TAAPI_API_KEY' and value:
                        return value
    return None

TAAPI_API_KEY = load_env()

# API endpoints
BINANCE_US_API = "https://api.binance.us/api/v3"
BINANCE_API = "https://api.binance.com/api/v3"
BINANCE_FAPI = "https://fapi.binance.com/fapi/v1"
KRAKEN_API = "https://api.kraken.com/0/public"
COINBASE_API = "https://api.coinbase.com/v2"
COINGECKO_API = "https://api.coingecko.com/api/v3"
CRYPTOCOMPARE_API = "https://min-api.cryptocompare.com/data"
DERIBIT_API = "https://www.deribit.com/api/v2/public"
TAAPI_API = "https://api.taapi.io"
BYBIT_API = "https://api.bybit.com/v5"
OKX_API = "https://www.okx.com/api/v5"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json'
}

# Global formatting config
TELEGRAM_MODE = False
LINE_WIDTH = 54  # Default width

def set_telegram_mode(enabled):
    """Enable Telegram-friendly formatting (narrow width)"""
    global TELEGRAM_MODE, LINE_WIDTH
    TELEGRAM_MODE = enabled
    LINE_WIDTH = 55 if enabled else 50

def format_line(char='='):
    """Return a line of appropriate width"""
    return char * LINE_WIDTH

def format_header(text):
    """Format a header with appropriate width"""
    if TELEGRAM_MODE:
        return f"\n{text}\n{format_line('─')}"
    else:
        return f"\n{format_line()}\n{text:^{LINE_WIDTH}}\n{format_line()}"

def format_price(label, value, width=None):
    """Format price output for current mode"""
    if width is None:
        width = 20 if TELEGRAM_MODE else 25
    if TELEGRAM_MODE:
        return f"{label}\n${value:,.2f}"
    else:
        return f"{label:<{width}} ${value:,.2f}"


# ============================================================================
# NEW: PERPETUAL FUTURES FUNCTIONS
# ============================================================================

def get_binance_spot_price(symbol):
    """Fetch spot price from Binance.com (international)"""
    url = f"{BINANCE_API}/ticker/price"
    params = {'symbol': f'{symbol}USDT'}
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return float(resp.json()['price'])
    except:
        return None

def get_binance_perp_data(symbol):
    """Fetch perpetual futures data from Binance.com"""
    params = {'symbol': f'{symbol}USDT'}
    try:
        price_resp = requests.get(f"{BINANCE_FAPI}/ticker/price", params=params, headers=HEADERS, timeout=10)
        price_resp.raise_for_status()
        perp_price = float(price_resp.json()['price'])
        
        premium_resp = requests.get(f"{BINANCE_FAPI}/premiumIndex", params=params, headers=HEADERS, timeout=10)
        premium_resp.raise_for_status()
        premium_data = premium_resp.json()
        
        oi_resp = requests.get(f"{BINANCE_FAPI}/openInterest", params=params, headers=HEADERS, timeout=10)
        oi_resp.raise_for_status()
        open_interest = float(oi_resp.json()['openInterest'])
        
        volume_resp = requests.get(f"{BINANCE_FAPI}/ticker/24hr", params=params, headers=HEADERS, timeout=10)
        volume_resp.raise_for_status()
        volume_data = volume_resp.json()
        
        return {
            'price': perp_price,
            'funding_rate': float(premium_data.get('lastFundingRate', 0)),
            'next_funding_time': int(premium_data.get('nextFundingTime', 0)),
            'mark_price': float(premium_data.get('markPrice', perp_price)),
            'open_interest': open_interest,
            'volume_24h': float(volume_data.get('quoteVolume', 0)),
            'index_price': float(premium_data.get('indexPrice', perp_price))
        }
    except:
        return None

def get_bybit_spot_price(symbol):
    """Fetch spot price from Bybit"""
    url = f"{BYBIT_API}/market/tickers"
    params = {'category': 'spot', 'symbol': f'{symbol}USDT'}
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get('result') and data['result'].get('list'):
            return float(data['result']['list'][0]['lastPrice'])
    except:
        return None

def get_bybit_perp_data(symbol):
    """Fetch perpetual futures data from Bybit"""
    url = f"{BYBIT_API}/market/tickers"
    params = {'category': 'linear', 'symbol': f'{symbol}USDT'}
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get('result') and data['result'].get('list'):
            ticker = data['result']['list'][0]
            return {
                'price': float(ticker['lastPrice']),
                'funding_rate': float(ticker.get('fundingRate', 0)),
                'next_funding_time': ticker.get('nextFundingTime', ''),
                'open_interest': float(ticker.get('openInterest', 0)),
                'volume_24h': float(ticker.get('volume24h', 0))
            }
    except:
        return None

def get_okx_perp_data(symbol):
    """Fetch perpetual futures data from OKX"""
    inst_id = f'{symbol}-USDT-SWAP'
    try:
        ticker_resp = requests.get(f"{OKX_API}/market/ticker", params={'instId': inst_id}, headers=HEADERS, timeout=10)
        ticker_resp.raise_for_status()
        ticker_data = ticker_resp.json()
        
        funding_resp = requests.get(f"{OKX_API}/public/funding-rate", params={'instId': inst_id}, headers=HEADERS, timeout=10)
        funding_resp.raise_for_status()
        funding_data = funding_resp.json()
        
        if ticker_data.get('data') and funding_data.get('data'):
            ticker = ticker_data['data'][0]
            funding = funding_data['data'][0]
            return {
                'price': float(ticker['last']),
                'funding_rate': float(funding.get('fundingRate', 0)),
                'next_funding_time': int(funding.get('nextFundingTime', 0)),
                'open_interest': float(ticker.get('openInterestCcy', 0)),
                'volume_24h': float(ticker.get('volCcy24h', 0))
            }
    except:
        return None

# ============================================================================
# NEW COMMANDS
# ============================================================================

def cmd_perp_premium(args):
    """Show spot vs perpetual premium with funding rates"""
    symbol = args.symbol.upper()
    
    if hasattr(args, 'telegram') and args.telegram:
        set_telegram_mode(True)
    
    print(format_header(f"SPOT vs PERP - {symbol}"))
    
    spot_price = get_binance_spot_price(symbol)
    perp_data = get_binance_perp_data(symbol)
    exchange = "Binance"
    
    if not spot_price or not perp_data:
        print("Trying Bybit...")
        spot_price = get_bybit_spot_price(symbol)
        perp_data = get_bybit_perp_data(symbol)
        exchange = "Bybit"
    
    if not spot_price or not perp_data:
        print(f"❌ Failed to fetch {symbol}")
        return
    
    perp_price = perp_data['price']
    funding_rate = perp_data['funding_rate']
    basis = perp_price - spot_price
    basis_pct = (basis / spot_price) * 100
    
    funding_rate_pct = funding_rate * 100
    annualized_funding = funding_rate_pct * 3 * 365
    
    if exchange == "Binance":
        next_funding_dt = datetime.fromtimestamp(perp_data['next_funding_time'] / 1000)
    else:
        next_funding_dt = datetime.fromtimestamp(int(perp_data['next_funding_time']) / 1000)
    
    time_to_funding = next_funding_dt - datetime.now()
    hours_to_funding = time_to_funding.total_seconds() / 3600
    
    print(f"\n{exchange}")
    print(format_price("Spot:", spot_price))
    print(format_price("Perp:", perp_price))
    
    print(f"\n{format_line('─')}")
    print("\nBASIS:")
    print(f"${basis:+,.2f} ({basis_pct:+.3f}%)")
    
    if basis_pct > 0.05:
        print("🟢 PREMIUM (bullish)")
    elif basis_pct < -0.05:
        print("🔴 DISCOUNT (bearish)")
    else:
        print("⚪ NEUTRAL")
    
    print(f"\n{format_line('─')}")
    print("\nFUNDING:")
    print(f"Rate: {funding_rate_pct:+.4f}%")
    print(f"Annual: {annualized_funding:+.1f}%")
    print(f"Next: {next_funding_dt.strftime('%H:%M UTC')}")
    print(f"({hours_to_funding:.1f}h)")
    
    if funding_rate_pct > 0.01:
        print("Longs → Shorts")
    elif funding_rate_pct < -0.01:
        print("Shorts → Longs")
    else:
        print("Neutral")
    
    print(f"\n{format_line('─')}")
    print(f"\nOI: ${perp_data['open_interest']:,.0f}")
    print(f"Vol: ${perp_data['volume_24h']:,.0f}")
    print(f"\n{format_line()}\n")
    
    set_telegram_mode(False)

def cmd_funding(args):
    """Compare funding rates across multiple exchanges"""
    symbol = args.symbol.upper()
    
    if hasattr(args, 'telegram') and args.telegram:
        set_telegram_mode(True)
    
    print(format_header(f"FUNDING RATES - {symbol}"))
    
    exchanges = {}
    
    binance_data = get_binance_perp_data(symbol)
    if binance_data:
        exchanges['Binance'] = binance_data
    
    bybit_data = get_bybit_perp_data(symbol)
    if bybit_data:
        exchanges['Bybit'] = bybit_data
    
    okx_data = get_okx_perp_data(symbol)
    if okx_data:
        exchanges['OKX'] = okx_data
    
    if not exchanges:
        print(f"❌ No data for {symbol}")
        return
    
    print()
    if TELEGRAM_MODE:
        for exchange_name, data in exchanges.items():
            funding_pct = data['funding_rate'] * 100
            annual_pct = funding_pct * 3 * 365
            print(f"{exchange_name}")
            print(f"{funding_pct:+.4f}% ({annual_pct:+.0f}% ann.)")
            print()
    else:
        print(f"{'Exchange':<12} {'Funding %':<12} {'Annual %':<12}")
        print(format_line('─'))
        
        for exchange_name, data in exchanges.items():
            funding_pct = data['funding_rate'] * 100
            annual_pct = funding_pct * 3 * 365
            print(f"{exchange_name:<12} {funding_pct:+.4f}%     {annual_pct:+6.1f}%")
    
    total_funding = sum(d['funding_rate'] * 100 for d in exchanges.values())
    count = len(exchanges)
    avg_funding = total_funding / count
    
    if count > 1:
        print(format_line('─'))
        if TELEGRAM_MODE:
            print(f"Average: {avg_funding:+.4f}%")
        else:
            avg_annual = avg_funding * 3 * 365
            print(f"{'AVERAGE':<12} {avg_funding:+.4f}%     {avg_annual:+6.1f}%")
    
    print(f"\n{format_line('─')}")
    print("\nSIGNAL:")
    
    if avg_funding > 0.02:
        print("Longs crowded")
        print("Risk: long squeeze")
    elif avg_funding < -0.02:
        print("Shorts crowded")
        print("Risk: short squeeze")
    elif abs(avg_funding) < 0.005:
        print("Neutral/balanced")
    else:
        print("Mild bias")
    
    print(f"\n{format_line()}\n")
    set_telegram_mode(False)

def cmd_institutional(args):
    """Coinbase spot vs Binance perp - institutional signal"""
    symbol = args.symbol.upper()
    symbols = get_symbol_mapping(symbol)
    
    print(f"\n{'='*LINE_WIDTH}")
    print(f"  INSTITUTIONAL SIGNAL: Coinbase vs Binance Perp - {symbol}")
    print(f"{'='*LINE_WIDTH}\n")
    
    cb_spot = get_coinbase_price(symbols['coinbase'])
    binance_perp_data = get_binance_perp_data(symbol)
    
    if not cb_spot or not binance_perp_data:
        print("Failed to fetch required data")
        return
    
    binance_perp = binance_perp_data['price']
    funding_rate = binance_perp_data['funding_rate']
    basis = binance_perp - cb_spot
    basis_pct = (basis / cb_spot) * 100
    funding_pct = funding_rate * 100
    annual_funding = funding_pct * 3 * 365
    
    print(f"PRICE COMPARISON:")
    print(f"  Coinbase Spot (US):      ${cb_spot:,.2f}")
    print(f"  Binance Perp (Intl):     ${binance_perp:,.2f}")
    print(f"  Difference:              ${basis:+,.2f} ({basis_pct:+.3f}%)")
    
    print(f"\n{'─'*LINE_WIDTH}")
    print(f"\nBASIS ANALYSIS:")
    
    if basis_pct > 0.15:
        print(f"  STRONG PREMIUM on perps")
        print(f"  International traders MORE bullish than US")
    elif basis_pct > 0.05:
        print(f"  MILD PREMIUM on perps")
    elif basis_pct < -0.15:
        print(f"  STRONG DISCOUNT on perps")
        print(f"  International traders MORE bearish than US")
    elif basis_pct < -0.05:
        print(f"  MILD DISCOUNT on perps")
    else:
        print(f"  TIGHT BASIS - markets in sync")
    
    print(f"\n{'─'*LINE_WIDTH}")
    print(f"\nFUNDING RATE:")
    print(f"  Current:                 {funding_pct:+.4f}%")
    print(f"  Annualized:              {annual_funding:+.2f}%")
    
    print(f"\n{'='*LINE_WIDTH}\n")

# ============================================================================
# ORIGINAL FUNCTIONS (WITH BUG FIXES)
# ============================================================================

def get_binance_us_klines(symbol, interval, limit=100):
    """Fetch klines from Binance.US"""
    url = f"{BINANCE_US_API}/klines"
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"❌ Error fetching Binance.US data: {e}")
        return None

def get_kraken_ohlc(symbol, interval=1, count=100):
    """Fetch OHLC data from Kraken"""
    url = f"{KRAKEN_API}/OHLC"
    params = {
        'pair': symbol,
        'interval': interval,
        'count': count
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get('error') and len(data['error']) > 0:
            return None
        pair_key = list(data['result'].keys())[0]
        return data['result'][pair_key]
    except Exception as e:
        return None

def get_binance_us_price(symbol):
    """Fetch spot price from Binance.US"""
    url = f"{BINANCE_US_API}/ticker/price"
    params = {'symbol': symbol}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return float(resp.json()['price'])
    except Exception as e:
        return None

def get_coinbase_price(symbol):
    """Fetch spot price from Coinbase"""
    url = f"{COINBASE_API}/prices/{symbol}/spot"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return float(resp.json()['data']['amount'])
    except Exception as e:
        return None

def get_kraken_ticker(pair):
    """Fetch current price from Kraken"""
    url = f"{KRAKEN_API}/Ticker"
    params = {'pair': pair}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get('error') and len(data['error']) > 0:
            return None
        pair_key = list(data['result'].keys())[0]
        return float(data['result'][pair_key]['c'][0])
    except Exception as e:
        return None

def calculate_vwap_from_ohlc(ohlc_data):
    """Calculate VWAP from OHLC data (Kraken format)"""
    total_volume = 0
    total_pv = 0
    
    for candle in ohlc_data:
        close = float(candle[4])
        volume = float(candle[6])
        pv = close * volume
        total_pv += pv
        total_volume += volume
    
    if total_volume == 0:
        return None
    
    return total_pv / total_volume

def calculate_vwap(klines):
    """Calculate VWAP from klines data (Binance.US format)"""
    total_volume = 0
    total_pv = 0
    
    for kline in klines:
        close = float(kline[4])
        volume = float(kline[5])
        pv = close * volume
        total_pv += pv
        total_volume += volume
    
    if total_volume == 0:
        return None
    
    return total_pv / total_volume

def calculate_current_price_binance(klines):
    """Get current price from latest kline (Binance.US format)"""
    if not klines:
        return None
    return float(klines[-1][4])

def calculate_current_price_kraken(ohlc_data):
    """Get current price from latest candle (Kraken format)"""
    if not ohlc_data:
        return None
    return float(ohlc_data[-1][4])

def analyze_trend_binance(klines):
    """Analyze trend from Binance.US klines"""
    if len(klines) < 2:
        return "UNKNOWN", 0
    
    closes = [float(k[4]) for k in klines]
    return calculate_trend(closes)

def analyze_trend_kraken(ohlc_data):
    """Analyze trend from Kraken OHLC"""
    if len(ohlc_data) < 2:
        return "UNKNOWN", 0
    
    closes = [float(c[4]) for c in ohlc_data]
    return calculate_trend(closes)

def calculate_trend(closes):
    """Calculate trend from close prices"""
    n = len(closes)
    x = list(range(n))
    x_mean = sum(x) / n
    y_mean = sum(closes) / n
    
    numerator = sum((x[i] - x_mean) * (closes[i] - y_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
    
    if denominator == 0:
        return "FLAT", 0
    
    slope = numerator / denominator
    slope_pct = (slope / y_mean) * 100
    
    if slope_pct > 0.1:
        return "RISING", slope_pct
    elif slope_pct < -0.1:
        return "FALLING", slope_pct
    else:
        return "FLAT", slope_pct

def get_quarter_info(timezone='UTC'):
    """Calculate current quarter and quarter boundaries"""
    try:
        tz = ZoneInfo(timezone)
    except:
        print(f"❌ Invalid timezone: {timezone}. Using UTC.")
        tz = ZoneInfo('UTC')
    
    now = datetime.now(tz)
    now_utc = now.astimezone(ZoneInfo('UTC'))
    
    q_times = [
        (1, 4, 43),
        (2, 10, 43),
        (3, 16, 43),
        (4, 22, 43),
    ]
    
    current_q = 4
    q_start = None
    
    for q, hour, minute in q_times:
        q_time = now_utc.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now_utc >= q_time:
            current_q = q
            q_start = q_time
    
    if now_utc.hour < 4 or (now_utc.hour == 4 and now_utc.minute < 43):
        current_q = 4
        yesterday = now_utc - timedelta(days=1)
        q_start = yesterday.replace(hour=22, minute=43, second=0, microsecond=0)
    
    return current_q, q_start, now, now_utc

def get_symbol_mapping(symbol):
    """Map common symbol to exchange-specific formats"""
    symbol = symbol.upper()
    
    mappings = {
        'BTC': {
            'binance_us': 'BTCUSDT',
            'kraken': 'XXBTZUSD',
            'coinbase': 'BTC-USD',
        },
        'ETH': {
            'binance_us': 'ETHUSDT',
            'kraken': 'XETHZUSD',
            'coinbase': 'ETH-USD',
        },
        'SOL': {
            'binance_us': 'SOLUSDT',
            'kraken': 'SOLUSD',
            'coinbase': 'SOL-USD',
        },
        'MATIC': {
            'binance_us': 'MATICUSDT',
            'kraken': 'MATICUSD',
            'coinbase': 'MATIC-USD',
        }
    }
    
    return mappings.get(symbol, {
        'binance_us': f'{symbol}USDT',
        'kraken': f'{symbol}USD',
        'coinbase': f'{symbol}-USD',
    })

def get_kline_at_time(symbol, target_time, use_kraken=False):
    """Get the kline/candle at a specific time"""
    now = datetime.now(ZoneInfo('UTC'))
    if target_time.tzinfo is None:
        target_time_aware = target_time.replace(tzinfo=ZoneInfo('UTC'))
    else:
        target_time_aware = target_time
    
    minutes_ago = int((now - target_time_aware).total_seconds() / 60)
    
    limit = min(minutes_ago + 10, 1000)
    if limit < 1:
        limit = 10
    
    if use_kraken:
        ohlc = get_kraken_ohlc(symbol, interval=1, count=limit)
        if not ohlc:
            return None
        
        target_ts = int(target_time_aware.timestamp())
        closest_candle = None
        min_diff = float('inf')
        
        for candle in ohlc:
            candle_ts = int(candle[0])
            diff = abs(candle_ts - target_ts)
            if diff < min_diff:
                min_diff = diff
                closest_candle = candle
        
        return closest_candle
    else:
        klines = get_binance_us_klines(symbol, '1m', limit=limit)
        if not klines:
            return None
        
        target_ts = int(target_time_aware.timestamp() * 1000)
        closest_kline = None
        min_diff = float('inf')
        
        for kline in klines:
            kline_ts = kline[0]
            diff = abs(kline_ts - target_ts)
            if diff < min_diff:
                min_diff = diff
                closest_kline = kline
        
        return closest_kline

def get_session_data(symbols, current_q, now_utc):
    """Get current and previous session data - FIXED for negative limits"""
    q_hours = {1: 4, 2: 10, 3: 16, 4: 22}
    current_hour = q_hours[current_q]
    session_start = now_utc.replace(hour=current_hour, minute=43, second=0, microsecond=0)
    
    prev_q = current_q - 1 if current_q > 1 else 4
    prev_hour = q_hours[prev_q]
    prev_session_start = now_utc.replace(hour=prev_hour, minute=43, second=0, microsecond=0)
    
    if prev_session_start > session_start:
        prev_session_start = prev_session_start - timedelta(days=1)
    
    # FIXED: Calculate minutes and ensure they're positive
    current_minutes = int((now_utc - session_start).total_seconds() / 60)
    if current_minutes < 1:
        current_minutes = 1  # Minimum 1 minute
    
    prev_session_end = session_start
    prev_session_minutes = int((prev_session_end - prev_session_start).total_seconds() / 60)
    if prev_session_minutes < 1:
        prev_session_minutes = 1  # Minimum 1 minute
    
    # Fetch current session data
    current_klines = get_binance_us_klines(symbols['binance_us'], '1m', limit=min(current_minutes, 1000))
    if not current_klines:
        current_ohlc = get_kraken_ohlc(symbols['kraken'], interval=1, count=min(current_minutes, 720))
        if current_ohlc:
            current_data = ('kraken', current_ohlc)
        else:
            current_data = None
    else:
        current_data = ('binance', current_klines)
    
    # Fetch previous session data
    prev_klines = get_binance_us_klines(symbols['binance_us'], '1m', limit=min(prev_session_minutes + current_minutes, 1000))
    if prev_klines and len(prev_klines) > current_minutes:
        prev_klines = prev_klines[:-current_minutes] if current_minutes > 0 else prev_klines
        prev_data = ('binance', prev_klines[-prev_session_minutes:] if prev_session_minutes < len(prev_klines) else prev_klines)
    else:
        prev_ohlc = get_kraken_ohlc(symbols['kraken'], interval=1, count=min(prev_session_minutes + current_minutes, 720))
        if prev_ohlc and len(prev_ohlc) > current_minutes:
            prev_ohlc = prev_ohlc[:-current_minutes] if current_minutes > 0 else prev_ohlc
            prev_data = ('kraken', prev_ohlc[-prev_session_minutes:] if prev_session_minutes < len(prev_ohlc) else prev_ohlc)
        else:
            prev_data = None
    
    return current_data, prev_data

def cmd_vwap(args):
    """Calculate variance from daily VWAP and session VWAPs"""
    symbol = args.symbol.upper()
    symbols = get_symbol_mapping(symbol)
    
    print(f"\n📊 VWAP Analysis for {symbol}")
    print("=" * LINE_WIDTH)
    
    current_q, q_start, now_local, now_utc = get_quarter_info('UTC')
    
    # Daily VWAP (last 24 hours)
    klines = get_binance_us_klines(symbols['binance_us'], '1m', limit=1440)
    if klines:
        daily_vwap = calculate_vwap(klines)
        current = calculate_current_price_binance(klines)
    else:
        ohlc = get_kraken_ohlc(symbols['kraken'], interval=1, count=1440)
        if ohlc:
            daily_vwap = calculate_vwap_from_ohlc(ohlc)
            current = calculate_current_price_kraken(ohlc)
        else:
            print("❌ Unable to fetch data")
            return
    
    if daily_vwap and current:
        daily_variance = ((current - daily_vwap) / daily_vwap) * 100
        
        print(f"Current Price:         ${current:,.2f}")
        print()
        print("DAILY VWAP (24h)")
        print(f"  VWAP:                ${daily_vwap:,.2f}")
        print(f"  Variance:            {daily_variance:+.2f}%")
        
        if daily_variance > 0:
            print(f"  Bias:                🟢 Bullish (Above VWAP)")
        else:
            print(f"  Bias:                🔴 Bearish (Below VWAP)")
        print()
    
    # Session VWAPs
    current_data, prev_data = get_session_data(symbols, current_q, now_utc)
    
    # Current Session VWAP
    if current_data:
        data_type, data = current_data
        if len(data) > 0:
            if data_type == 'binance':
                session_vwap = calculate_vwap(data)
            else:
                session_vwap = calculate_vwap_from_ohlc(data)
            
            if session_vwap and current:
                session_variance = ((current - session_vwap) / session_vwap) * 100
                
                print(f"CURRENT SESSION VWAP (Q{current_q})")
                print(f"  VWAP:                ${session_vwap:,.2f}")
                print(f"  Variance:            {session_variance:+.2f}%")
                
                if session_variance > 0:
                    print(f"  Bias:                🟢 Bullish (Above VWAP)")
                else:
                    print(f"  Bias:                🔴 Bearish (Below VWAP)")
                print()
    
    # Previous Session VWAP
    if prev_data:
        data_type, data = prev_data
        if len(data) > 0:
            if data_type == 'binance':
                prev_vwap = calculate_vwap(data)
                prev_close = float(data[-1][4])
            else:
                prev_vwap = calculate_vwap_from_ohlc(data)
                prev_close = float(data[-1][4])
            
            if prev_vwap and prev_close:
                prev_variance = ((prev_close - prev_vwap) / prev_vwap) * 100
                
                prev_q = current_q - 1 if current_q > 1 else 4
                print(f"PREVIOUS SESSION VWAP (Q{prev_q})")
                print(f"  VWAP:                ${prev_vwap:,.2f}")
                print(f"  Close:               ${prev_close:,.2f}")
                print(f"  Variance:            {prev_variance:+.2f}%")
                
                if prev_variance > 0:
                    print(f"  Bias:                🟢 Bullish (Closed Above VWAP)")
                else:
                    print(f"  Bias:                🔴 Bearish (Closed Below VWAP)")
                print()
    
    print()
def cmd_quarters(args):
    """Analyze daily quarters and deviation from each quarter open"""
    symbol = args.symbol.upper()
    symbols = get_symbol_mapping(symbol)
    timezone = args.timezone if hasattr(args, 'timezone') else 'UTC'
    
    print(f"\n🕐 DAILY QUARTERS ANALYSIS for {symbol}")
    print("=" * LINE_WIDTH)
    
    current_q, q_start, now_local, now_utc = get_quarter_info(timezone)
    
    print(f"Current Time ({timezone}): {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    if timezone != 'UTC':
        print(f"Current Time (UTC):     {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Current Quarter:        Q{current_q}")
    print(f"Q{current_q} Started (UTC):   {q_start.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if timezone != 'UTC':
        try:
            tz = ZoneInfo(timezone)
            q_start_local = q_start.astimezone(tz)
            print(f"Q{current_q} Started ({timezone}): {q_start_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        except:
            pass
    
    print()
    print("📍 Quarter Times:")
    q_times_display = [
        (1, 4, 43, "Q1"),
        (2, 10, 43, "Q2"),
        (3, 16, 43, "Q3"),
        (4, 22, 43, "Q4"),
    ]
    
    if timezone != 'UTC':
        try:
            tz = ZoneInfo(timezone)
            for q_num, hour, minute, label in q_times_display:
                utc_time = now_utc.replace(hour=hour, minute=minute, second=0, microsecond=0)
                local_time = utc_time.astimezone(tz)
                marker = " ← CURRENT" if q_num == current_q else ""
                print(f"   {label}: {hour:02d}:{minute:02d} UTC = {local_time.strftime('%H:%M %Z')}{marker}")
        except:
            pass
    
    print()
    
    # Get current price
    current_price = get_binance_us_price(symbols['binance_us'])
    if not current_price:
        current_price = get_kraken_ticker(symbols['kraken'])
    
    if not current_price:
        print("❌ Unable to fetch current price")
        return
    
    print(f"Current Price:          ${current_price:,.2f}")
    print()
    print("-" * LINE_WIDTH)
    
    q_times = [
        (1, 4, 43, "04:43 UTC"),
        (2, 10, 43, "10:43 UTC"),
        (3, 16, 43, "16:43 UTC"),
        (4, 22, 43, "22:43 UTC"),
    ]
    
    use_kraken = get_binance_us_price(symbols['binance_us']) is None
    
    for q_num, hour, minute, time_str in q_times:
        q_time = now_utc.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if q_time > now_utc:
            q_time = q_time - timedelta(days=1)
        
        candle = get_kline_at_time(symbols['kraken'] if use_kraken else symbols['binance_us'], 
                                   q_time, use_kraken=use_kraken)
        
        if candle:
            q_open = float(candle[1])
            deviation = current_price - q_open
            deviation_pct = (deviation / q_open) * 100
            
            marker = " ← CURRENT" if q_num == current_q else ""
            
            time_display = time_str
            if timezone != 'UTC':
                try:
                    tz = ZoneInfo(timezone)
                    q_time_local = q_time.astimezone(tz)
                    local_time = q_time_local.strftime('%H:%M %Z')
                    time_display = f"{time_str} ({local_time})"
                except:
                    pass
            
            print(f"Q{q_num} ({time_display}){marker}")
            print(f"  Open Price:     ${q_open:,.2f}")
            print(f"  Deviation:      ${deviation:+,.2f} ({deviation_pct:+.2f}%)")
            
            if deviation_pct > 0:
                print(f"  Status:         🟢 Above Q{q_num} open")
            else:
                print(f"  Status:         🔴 Below Q{q_num} open")
            print()
        else:
            print(f"Q{q_num} ({time_display})")
            print(f"  ❌ Unable to fetch open price")
            print()
    
    print("-" * LINE_WIDTH)
    print()

def cmd_all(args):
    """Show all metrics for a symbol"""
    symbol = args.symbol.upper()
    
    print(f"\n{'='*LINE_WIDTH}")
    print(f"  COMPLETE METRICS FOR {symbol}")
    print(f"{'='*LINE_WIDTH}")
    
    if not hasattr(args, 'timezone'):
        args.timezone = 'UTC'
    
    symbols = get_symbol_mapping(symbol)
    
    # Run all analysis commands
    cmd_vwap(args)
    cmd_trend(args)
    cmd_premium(args)
    cmd_perp_premium(args)
    cmd_funding(args)
    cmd_institutional(args)
    cmd_quarters(args)
    
    # Generate Market Context Summary
    print(f"\n{'='*LINE_WIDTH}")
    print(f"  📋 MARKET CONTEXT & TRADING SUMMARY")
    print(f"{'='*LINE_WIDTH}\n")
    
    # Gather current data for analysis
    current_price = get_binance_us_price(symbols['binance_us'])
    if not current_price:
        current_price = get_kraken_ticker(symbols['kraken'])
    
    # VWAP Analysis Summary
    current_q, q_start, now_local, now_utc = get_quarter_info(args.timezone)
    klines = get_binance_us_klines(symbols['binance_us'], '1m', limit=1440)
    if klines:
        daily_vwap = calculate_vwap(klines)
        daily_variance = ((current_price - daily_vwap) / daily_vwap) * 100 if daily_vwap else 0
    else:
        ohlc = get_kraken_ohlc(symbols['kraken'], interval=1, count=1440)
        if ohlc:
            daily_vwap = calculate_vwap_from_ohlc(ohlc)
            daily_variance = ((current_price - daily_vwap) / daily_vwap) * 100 if daily_vwap else 0
        else:
            daily_variance = 0
    
    # Trend Analysis Summary
    klines_4h = get_binance_us_klines(symbols['binance_us'], '4h', limit=24)
    if klines_4h:
        trend, slope = analyze_trend_binance(klines_4h)
    else:
        ohlc_4h = get_kraken_ohlc(symbols['kraken'], interval=240, count=24)
        if ohlc_4h:
            trend, slope = analyze_trend_kraken(ohlc_4h)
        else:
            trend, slope = "UNKNOWN", 0
    
    # Premium Analysis Summary
    cb_price = get_coinbase_price(symbols['coinbase'])
    comp_price = get_binance_us_price(symbols['binance_us']) or get_kraken_ticker(symbols['kraken'])
    premium = ((cb_price - comp_price) / comp_price) * 100 if (cb_price and comp_price) else 0
    
    # Perp/Funding Analysis Summary
    perp_data = get_binance_perp_data(symbol)
    if perp_data:
        funding_pct = perp_data['funding_rate'] * 100
    else:
        funding_pct = 0
    
    print("🎯 VWAP POSITION:")
    if daily_variance > 0.5:
        print(f"   • Price is {abs(daily_variance):.2f}% ABOVE daily VWAP - bullish momentum")
    elif daily_variance < -0.5:
        print(f"   • Price is {abs(daily_variance):.2f}% BELOW daily VWAP - bearish pressure")
    else:
        print(f"   • Price is near VWAP (within 0.5%) - neutral/consolidating")
    print()
    
    print("📈 TREND MOMENTUM:")
    if trend == "RISING" and slope > 0.2:
        print(f"   • Strong uptrend ({slope:+.2f}% per 4h)")
    elif trend == "RISING":
        print(f"   • Weak uptrend ({slope:+.2f}% per 4h)")
    elif trend == "FALLING" and slope < -0.2:
        print(f"   • Strong downtrend ({slope:+.2f}% per 4h)")
    elif trend == "FALLING":
        print(f"   • Weak downtrend ({slope:+.2f}% per 4h)")
    else:
        print(f"   • Flat/ranging ({slope:+.2f}% per 4h)")
    print()
    
    print("💰 INSTITUTIONAL SIGNAL (Coinbase Premium):")
    if premium > 0.5:
        print(f"   • Coinbase trading at +{premium:.2f}% premium - institutions buying")
    elif premium < -0.5:
        print(f"   • Coinbase at {premium:.2f}% discount - institutions selling")
    else:
        print(f"   • Coinbase premium neutral ({premium:+.2f}%)")
    print()
    
    print("💸 FUNDING RATE:")
    if funding_pct > 0.02:
        print(f"   • High positive funding ({funding_pct:+.4f}%) - longs crowded")
    elif funding_pct < -0.02:
        print(f"   • High negative funding ({funding_pct:+.4f}%) - shorts crowded")
    else:
        print(f"   • Neutral funding ({funding_pct:+.4f}%)")
    print()
    
    print("⚡ NEXT SESSION TRADING PLAN:")
    
    bullish_signals = 0
    bearish_signals = 0
    
    if daily_variance > 0.5:
        bullish_signals += 1
    elif daily_variance < -0.5:
        bearish_signals += 1
        
    if trend == "RISING":
        bullish_signals += 1
    elif trend == "FALLING":
        bearish_signals += 1
        
    if premium > 0.5:
        bullish_signals += 1
    elif premium < -0.5:
        bearish_signals += 1
        
    if funding_pct > 0.02:
        bullish_signals += 1
    elif funding_pct < -0.02:
        bearish_signals += 1
    
    if bullish_signals > bearish_signals + 1:
        print(f"   • BULLISH BIAS ({bullish_signals} bullish vs {bearish_signals} bearish signals)")
    elif bearish_signals > bullish_signals + 1:
        print(f"   • BEARISH BIAS ({bearish_signals} bearish vs {bullish_signals} bullish signals)")
    else:
        print(f"   • NEUTRAL/MIXED ({bullish_signals} bullish vs {bearish_signals} bearish signals)")
    
        print(f"\n{'='*LINE_WIDTH}\n")
        print("DAILY VWAP (24h)")
        print(f"  VWAP:                ${daily_vwap:,.2f}")
        print(f"  Variance:            {daily_variance:+.2f}%")
        
        if daily_variance > 0:
            print(f"  Bias:                🟢 Bullish (Above VWAP)")
        else:
            print(f"  Bias:                🔴 Bearish (Below VWAP)")
        print()
    
    # Session VWAPs
    current_data, prev_data = get_session_data(symbols, current_q, now_utc)
    
    # Current Session VWAP
    if current_data:
        data_type, data = current_data
        if len(data) > 0:
            if data_type == 'binance':
                session_vwap = calculate_vwap(data)
            else:
                session_vwap = calculate_vwap_from_ohlc(data)
            
            if session_vwap and current_price:
                session_variance = ((current_price - session_vwap) / session_vwap) * 100
                
                print(f"CURRENT SESSION VWAP (Q{current_q})")
                print(f"  VWAP:                ${session_vwap:,.2f}")
                print(f"  Variance:            {session_variance:+.2f}%")
                
                if session_variance > 0:
                    print(f"  Bias:                🟢 Bullish (Above VWAP)")
                else:
                    print(f"  Bias:                🔴 Bearish (Below VWAP)")
                print()
    
    # Previous Session VWAP
    if prev_data:
        data_type, data = prev_data
        if len(data) > 0:
            if data_type == 'binance':
                prev_vwap = calculate_vwap(data)
                prev_close = float(data[-1][4])
            else:
                prev_vwap = calculate_vwap_from_ohlc(data)
                prev_close = float(data[-1][4])
            
            if prev_vwap and prev_close:
                prev_variance = ((prev_close - prev_vwap) / prev_vwap) * 100
                
                prev_q = current_q - 1 if current_q > 1 else 4
                print(f"PREVIOUS SESSION VWAP (Q{prev_q})")
                print(f"  VWAP:                ${prev_vwap:,.2f}")
                print(f"  Close:               ${prev_close:,.2f}")
                print(f"  Variance:            {prev_variance:+.2f}%")
                
                if prev_variance > 0:
                    print(f"  Bias:                🟢 Bullish (Closed Above VWAP)")
                else:
                    print(f"  Bias:                🔴 Bearish (Closed Below VWAP)")
                print()
    
    print()

def cmd_trend(args):
    """Analyze 4-hour trend"""
    symbol = args.symbol.upper()
    symbols = get_symbol_mapping(symbol)
    
    print(f"\n📈 4-Hour Trend Analysis for {symbol}")
    print("=" * LINE_WIDTH)
    
    klines = get_binance_us_klines(symbols['binance_us'], '4h', limit=24)
    if klines:
        trend, slope = analyze_trend_binance(klines)
        current = calculate_current_price_binance(klines)
        first_price = float(klines[0][4])
    else:
        ohlc = get_kraken_ohlc(symbols['kraken'], interval=240, count=24)
        if ohlc:
            trend, slope = analyze_trend_kraken(ohlc)
            current = calculate_current_price_kraken(ohlc)
            first_price = float(ohlc[0][4])
        else:
            print("❌ Unable to fetch data")
            return
    
    change = ((current - first_price) / first_price) * 100
    
    print(f"Current Price:    ${current:,.2f}")
    print(f"Period Start:     ${first_price:,.2f}")
    print(f"Change:           {change:+.2f}%")
    print(f"Trend Slope:      {slope:+.3f}% per 4h")
    
    if trend == "RISING":
        print(f"Direction:        🟢 RISING")
    elif trend == "FALLING":
        print(f"Direction:        🔴 FALLING")
    else:
        print(f"Direction:        ⚪ FLAT")
    
    print()

def cmd_premium(args):
    """Calculate Coinbase premium over other exchanges"""
    symbol = args.symbol.upper()
    symbols = get_symbol_mapping(symbol)
    
    print(f"\n💰 Coinbase Premium for {symbol}")
    print("=" * LINE_WIDTH)
    
    cb_price = get_coinbase_price(symbols['coinbase'])
    comp_price = get_binance_us_price(symbols['binance_us'])
    comp_source = "Binance.US"
    
    if not comp_price:
        comp_price = get_kraken_ticker(symbols['kraken'])
        comp_source = "Kraken"
    
    if cb_price and comp_price:
        premium = ((cb_price - comp_price) / comp_price) * 100
        
        print(f"Coinbase Price:   ${cb_price:,.2f}")
        print(f"{comp_source} Price:    ${comp_price:,.2f}")
        print(f"Premium:          {premium:+.2f}%")
        
        if premium > 0.5:
            print(f"Status:           🟢 Significant Premium (bullish signal)")
        elif premium < -0.5:
            print(f"Status:           🔴 Discount (bearish signal)")
        else:
            print(f"Status:           ⚪ Neutral")
    else:
        print("❌ Unable to fetch prices from exchanges")
    
    print()

def cmd_basis(args):
    """Calculate basis between exchanges"""
    symbol = args.symbol.upper()
    symbols = get_symbol_mapping(symbol)
    
    print(f"\n📉 Exchange Basis Analysis for {symbol}")
    print("=" * LINE_WIDTH)
    
    us_spot = get_coinbase_price(symbols['coinbase'])
    binance_us = get_binance_us_price(symbols['binance_us'])
    kraken = get_kraken_ticker(symbols['kraken'])
    
    prices = {}
    if us_spot:
        prices['Coinbase'] = us_spot
    if binance_us:
        prices['Binance.US'] = binance_us
    if kraken:
        prices['Kraken'] = kraken
    
    if len(prices) >= 2:
        for exchange, price in sorted(prices.items(), key=lambda x: x[1], reverse=True):
            print(f"  {exchange:<15} ${price:,.2f}")
        
        max_price = max(prices.values())
        min_price = min(prices.values())
        spread = max_price - min_price
        spread_pct = (spread / min_price) * 100
        
        print()
        print(f"Spread:                    ${spread:,.2f} ({spread_pct:.2f}%)")
    else:
        print("❌ Unable to fetch sufficient price data")
    
    print()

def main():
    parser = argparse.ArgumentParser(
        description='Enhanced Crypto Trading Metrics CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python crypto.py vwap BTC                    # VWAP variance analysis
  python crypto.py trend ETH                   # 4-hour trend analysis
  python crypto.py premium BTC                 # Coinbase premium
  python crypto.py basis SOL                   # Exchange basis
  python crypto.py quarters BTC -tz America/New_York  # Quarters analysis
  python crypto.py all BTC -tz America/New_York        # All metrics
  python crypto.py perp BTC                    # Spot vs perp premium + funding
  python crypto.py funding ETH                 # Compare funding rates
  python crypto.py institutional BTC           # Coinbase vs Binance perp signal
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # NEW COMMANDS
    perp_parser = subparsers.add_parser('perp', help='Spot vs perpetual premium analysis')
    perp_parser.add_argument('symbol', help='Crypto symbol (e.g., BTC, ETH)')
    perp_parser.add_argument('--telegram', '-tg', action='store_true',
                            help='Format for Telegram (narrow width)')
    
    funding_parser = subparsers.add_parser('funding', help='Compare funding rates across exchanges')
    funding_parser.add_argument('symbol', help='Crypto symbol')
    funding_parser.add_argument('--telegram', '-tg', action='store_true',
                               help='Format for Telegram (narrow width)')
    
    institutional_parser = subparsers.add_parser('institutional', help='Coinbase vs Binance perp signal')
    institutional_parser.add_argument('symbol', help='Crypto symbol')
    institutional_parser.add_argument('--telegram', '-tg', action='store_true',
                                     help='Format for Telegram (narrow width)')
    
    # EXISTING COMMANDS
    vwap_parser = subparsers.add_parser('vwap', help='Calculate variance from daily VWAP')
    vwap_parser.add_argument('symbol', help='Crypto symbol (e.g., BTC, ETH)')
    
    trend_parser = subparsers.add_parser('trend', help='Analyze 4-hour trend')
    trend_parser.add_argument('symbol', help='Crypto symbol')
    
    premium_parser = subparsers.add_parser('premium', help='Calculate Coinbase premium')
    premium_parser.add_argument('symbol', help='Crypto symbol')
    
    basis_parser = subparsers.add_parser('basis', help='Exchange basis analysis')
    basis_parser.add_argument('symbol', help='Crypto symbol')
    
    quarters_parser = subparsers.add_parser('quarters', help='Analyze daily quarters')
    quarters_parser.add_argument('symbol', help='Crypto symbol')
    quarters_parser.add_argument('--timezone', '-tz', default='UTC', 
                                help='Timezone (e.g., America/New_York)')
    
    all_parser = subparsers.add_parser('all', help='Show all metrics')
    all_parser.add_argument('symbol', help='Crypto symbol')
    all_parser.add_argument('--timezone', '-tz', default='UTC', 
                           help='Timezone (e.g., America/New_York)')
    all_parser.add_argument('--telegram', '-tg', action='store_true',
                           help='Format output for Telegram (narrow width)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # NEW COMMAND HANDLERS
    if args.command == 'perp':
        cmd_perp_premium(args)
    elif args.command == 'funding':
        cmd_funding(args)
    elif args.command == 'institutional':
        cmd_institutional(args)
    # EXISTING COMMAND HANDLERS
    elif args.command == 'vwap':
        cmd_vwap(args)
    elif args.command == 'trend':
        cmd_trend(args)
    elif args.command == 'premium':
        cmd_premium(args)
    elif args.command == 'basis':
        cmd_basis(args)
    elif args.command == 'quarters':
        cmd_quarters(args)
    elif args.command == 'all':
        cmd_all(args)

if __name__ == '__main__':
    main()
