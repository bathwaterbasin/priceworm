# 🐛 PRICEWORM

A trading analysis tool that tracks key market timing patterns and crypto sentiment metrics across four "sacred times" during the trading day.

## Overview

Priceworm is a market observation tool that focuses on temporal patterns and sentiment indicators across cryptocurrency and traditional futures markets. The system monitors specific times of day when liquidity shifts and market structure changes occur, providing traders with contextual data for decision-making.

**Live Demo:** [bathwaterbasin.github.io/priceworm](https://bathwaterbasin.github.io/priceworm/)

## Features

### Sacred Times Monitor (Wormholes)

Four key times throughout the trading day when market structure transitions occur:

- **00:43 EDT** - Midnight: Overnight positioning and Asian market influence
- **05:43 EDT** - Premarket: European open and early US futures activity
- **12:43 EDT** - Midday: Peak US market liquidity
- **17:43 EDT** - Afterhours: Regular trading session close and futures roll

The tool automatically converts these times to your local timezone and provides countdown timers to the next observation window.

### Trading Methodology: Sacred Wormhole Limit Orders

**Critical Trading Rule:** All trades are placed using **limit orders only** at the exact price level recorded at each of the four sacred wormholes.

**The Process:**
1. Record the price at each sacred time (00:43, 05:43, 12:43, 17:43 EDT)
2. Set limit orders at these exact prices
3. Price often retests these levels during the following session
4. Orders fill when price returns to the wormhole level

These wormhole prices act as intraday support/resistance levels. Market participants frequently revisit these prices as they represent key liquidity transition points. By placing limit orders at wormhole prices, traders position themselves at institutional reference levels rather than chasing momentum.

### Cryptocurrency Metrics Lookup

The crypto metrics tool tracks sentiment and positioning indicators:

- **VWAP (Volume Weighted Average Price)** - Institutional reference price levels
- **Coinbase Premium** - The spread between Coinbase and other exchanges, indicating US institutional buying/selling pressure
- **Futures-to-Spot Bias** - The differential between futures contracts and spot prices, revealing leverage positioning and funding rate dynamics
- **Sacred Time Correlations** - Price action patterns around the four key times

### SPX 500 Futures Gap Analysis

S&P 500 futures gap tracking provides context for broader market sentiment:

- **Weekday Gap** - The price gap that forms daily between 17:00-18:00 EDT when regular trading closes but futures continue
- **Weekend Gap** - The larger gap from Friday 17:00 EDT through Sunday 18:00 EDT
- **Gap Direction & Magnitude** - Critical sentiment indicator for crypto confluence trading

These gaps represent periods when equity index futures trade without the spot market, creating price discovery inefficiencies that often correlate with crypto market sentiment shifts.

## Trading Methodology: Confluence Approach

The Priceworm approach uses confluence between crypto-specific metrics and traditional market gap analysis:

1. **Identify SPX futures gap direction** - Determines broader risk sentiment
2. **Check crypto metrics at sacred times** - VWAP position, Coinbase premium, futures bias
3. **Look for confluence** - When multiple indicators align (e.g., negative SPX gap + negative Coinbase premium + backwardated futures)
4. **Set limit orders at wormhole prices** - Place orders at the exact price from each sacred time
5. **Wait for retest** - Price often returns to these levels during subsequent sessions

The sacred times represent liquidity transition points where these metrics show clearest signals, and the prices at these times become tradeable levels.

## Usage

### Interactive Web Interface

The main page provides:

- **Live Clock** - Shows current time in your local timezone
- **Sacred Time Cards** - Display next occurrence and countdown for each key time
- **Live Price Chart** - Simulated real-time market data visualization
- **Observation Counter** - Tracks user interaction (easter egg feature)

### Keyboard Shortcuts

- `Ctrl + Shift + W` - Reveal secret command input
- Type `worm` anywhere - Trigger pulse effect
- Console commands: `observe()`, `reset()`, `truth()`

### Sound Effects

The page includes ambient audio feedback:
- Glitch sounds on interaction
- Warning tones when approaching sacred times
- Ambient drones for atmosphere

## Lookup Tools (Coming Soon)

### Priceworm Wormhole Lookup Tool
**Status:** In Development

The wormhole lookup tool will provide:
- Historical wormhole price levels for backtesting
- 4x daily trading plan generation
- Automated limit order price suggestions
- Retest statistics and probability analysis
- Integration with crypto exchanges for order placement

Installation and usage procedures will be added when the tool is released.

### SPX Futures Gap Lookup Tool
**Status:** In Development

The SPX gap lookup tool will provide:
- Real-time gap tracking and alerts
- Historical gap analysis and statistics
- Weekend vs weekday gap comparison
- Correlation analysis with crypto market movements
- Gap fill probability indicators

Installation and usage procedures will be added when the tool is released.

## Technical Details

### Timezone Conversion

Sacred times are defined in EDT (UTC-4) and automatically converted to the user's local timezone using JavaScript Date objects. The conversion accounts for:

- Local UTC offset
- Daylight saving time differences
- Next-day rollover when times have passed

### Metrics Calculation

**Coinbase Premium:**
```
Premium = (Coinbase Price - Binance Price) / Binance Price × 100
```

**Futures Basis:**
```
Basis = (Futures Price - Spot Price) / Spot Price × 100
```

Positive basis = Contango (futures higher, bullish leverage)  
Negative basis = Backwardation (futures lower, bearish leverage)

## Data Sources

Users should connect their own data sources for:
- Real-time crypto prices (Coinbase, Binance APIs)
- SPX futures quotes (CME data feeds)
- VWAP calculations (volume-weighted from OHLCV data)

## File Structure

```
priceworm/
├── index.html          # Main interactive page
├── bkg-raw.jpg         # Background image (user-provided)
├── README.md           # This file
├── tools/              # Lookup tools (coming soon)
│   ├── wormhole/       # Wormhole price lookup tool
│   └── spx-gap/        # SPX futures gap analyzer
└── assets/             # Additional images and resources
```

## Contributing

This is a personal trading tool. Feel free to fork and adapt to your own methodology.

## Links

- **Telegram Community:** [t.me/+xVjWoIc81d1mNTEx](https://t.me/+xVjWoIc81d1mNTEx)
- **TradingView Indicator:** [Price Worm Session Pivots](https://www.tradingview.com/script/U4Y5LsGx-Price-Worm-Session-Pivots/)

## Disclaimer

This tool is for educational and research purposes. The "Priceworm" concept is a framework for thinking about market timing and sentiment confluence. 

- Not financial advice
- Past patterns do not guarantee future results
- Trading involves substantial risk of loss
- The mystical/schizoid aesthetic is intentional artistic styling
- Always do your own research and risk management
- Limit orders do not guarantee fills or profits

## License

MIT License - Use at your own risk

---

**THE WORM TURNS • THE MARKET BREATHES • THE DATA NEVER LIES (EXCEPT WHEN IT DOES)**
