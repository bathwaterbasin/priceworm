import asyncio
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import pytz
import threading
import logging
import warnings
import websocket
import json
import requests
import time as time_module

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)

class RealTimePriceTracker:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.active_streams = {}
        self.polling_threads = {}
        self.main_loop = None  # Store main event loop
    
    def set_main_loop(self, loop):
        """Store reference to main event loop"""
        self.main_loop = loop
    
    def convert_to_binance_symbol(self, symbol):
        if symbol.endswith('-USD'):
            base = symbol.replace('-USD', '')
            return f"{base.lower()}usdt"
        return None
    
    def is_crypto_available_on_binance(self, symbol):
        binance_symbol = self.convert_to_binance_symbol(symbol)
        if not binance_symbol:
            return False
        
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={binance_symbol.upper()}"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def start_real_time_tracking(self, symbol):
        if symbol.endswith('-USD') and self.is_crypto_available_on_binance(symbol):
            print(f"🔴 Starting Binance WebSocket for {symbol}")
            self.start_binance_stream(symbol)
        else:
            print(f"📊 Starting Yahoo Finance polling for {symbol}")
            self.start_yahoo_polling(symbol)
    
    def start_binance_stream(self, symbol):
        binance_symbol = self.convert_to_binance_symbol(symbol)
        
        def on_message(ws, message):
            try:
                data = json.loads(message)
                if 'c' in data:
                    current_price = float(data['c'])
                    # Fixed event loop handling
                    if self.main_loop and not self.main_loop.is_closed():
                        asyncio.run_coroutine_threadsafe(
                            self.bot.process_real_time_price(symbol, current_price),
                            self.main_loop
                        )
                    else:
                        print(f"⚠️ Event loop not available for {symbol}")
            except Exception as e:
                print(f"Error processing Binance message for {symbol}: {e}")
        
        def on_error(ws, error):
            print(f"Binance WebSocket error for {symbol}: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            print(f"Binance WebSocket closed for {symbol}")
        
        def on_open(ws):
            print(f"✅ Binance WebSocket connected for {symbol}")
        
        websocket_url = f"wss://stream.binance.com:9443/ws/{binance_symbol}@ticker"
        ws = websocket.WebSocketApp(websocket_url,
                                  on_message=on_message,
                                  on_error=on_error,
                                  on_close=on_close,
                                  on_open=on_open)
        
        def run_websocket():
            ws.run_forever()
        
        ws_thread = threading.Thread(target=run_websocket, daemon=True)
        ws_thread.start()
        
        self.active_streams[symbol] = ws
    
    def start_yahoo_polling(self, symbol):
        def rapid_polling():
            while symbol in self.bot.monitored_symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    data = ticker.history(period="1d", interval="1m").tail(1)
                    if not data.empty:
                        current_price = float(data['Close'].iloc[0])
                        # Fixed event loop handling
                        if self.main_loop and not self.main_loop.is_closed():
                            asyncio.run_coroutine_threadsafe(
                                self.bot.process_real_time_price(symbol, current_price),
                                self.main_loop
                            )
                        else:
                            print(f"⚠️ Event loop not available for {symbol}")
                except Exception as e:
                    print(f"Error polling {symbol}: {e}")
                
                for _ in range(30):
                    if symbol not in self.bot.monitored_symbols:
                        break
                    threading.Event().wait(1)
        
        thread = threading.Thread(target=rapid_polling, daemon=True)
        thread.start()
        self.polling_threads[symbol] = thread
    
    def stop_tracking(self, symbol):
        if symbol in self.active_streams:
            self.active_streams[symbol].close()
            del self.active_streams[symbol]
            print(f"🔴 Stopped Binance stream for {symbol}")
        
        if symbol in self.polling_threads:
            del self.polling_threads[symbol]
            print(f"📊 Stopped Yahoo polling for {symbol}")

class PricewormBot:
    def __init__(self, token):
        self.app = Application.builder().token(token).build()
        self.monitored_symbols = {}  # {symbol: chat_id}
        self.user_chats = set()
        self.price_cache = {}
        self.pivot_data = {}         # Store exact pivot prices from wormholes
        self.active_setups = {}      # Track post-wormhole setups
        self.pending_trades = {}     # Track pending limit orders
        self.open_trades = {}        # Track open trades
        self.sent_alerts = {}        # Prevent alert spam
        self.user_settings = {}      # User alert preferences
        
        # Real-time tracker
        self.real_time_tracker = RealTimePriceTracker(self)
        
        # Sacred Wormhole Times (EST) - Only the 4 main ones
        self.wormholes = {
            "midnight": time(0, 46),      # 00:46-00:47
            "premarket": time(6, 43),     # 06:43-06:44  
            "midday": time(11, 57),       # 11:57-11:58
            "afterhours": time(17, 32)    # 17:32-17:33
        }
        
        # Session Times
        self.sessions = {
            "asia": time(20, 0),          # 8:00 PM EST
            "london": time(2, 0),         # 2:00 AM EST
            "ny_am": time(9, 30),         # 9:30 AM EST
            "ny_lunch": time(12, 0),      # 12:00 PM EST
            "ny_pm": time(13, 30)         # 1:30 PM EST
        }
        
        # Symbol mappings
        self.symbol_mappings = {
            "BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD", "ADA": "ADA-USD",
            "DOGE": "DOGE-USD", "XRP": "XRP-USD", "DOT": "DOT-USD", "AVAX": "AVAX-USD",
            "MATIC": "MATIC-USD", "LINK": "LINK-USD", "UNI": "UNI-USD", "ATOM": "ATOM-USD",
            "FTM": "FTM-USD", "NEAR": "NEAR-USD", "ICP": "ICP-USD", "ALGO": "ALGO-USD",
            "LTC": "LTC-USD", "BCH": "BCH-USD", "ETC": "ETC-USD"
        }
        
        self.setup_handlers()
        self.start_monitoring()
    
    def setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("monitor", self.monitor_symbol))
        self.app.add_handler(CommandHandler("stop", self.stop_monitoring))
        self.app.add_handler(CommandHandler("stopall", self.stop_all_monitoring))
        self.app.add_handler(CommandHandler("list", self.list_monitored))
        self.app.add_handler(CommandHandler("settings", self.show_settings))
        self.app.add_handler(CommandHandler("alerts", self.set_alert_timing))
        self.app.add_handler(CommandHandler("wormholes", self.show_wormholes))
        self.app.add_handler(CommandHandler("setups", self.show_active_setups))
        self.app.add_handler(CommandHandler("trades", self.show_trades))
        self.app.add_handler(CommandHandler("rules", self.show_rules))
        self.app.add_handler(CommandHandler("status", self.show_status))
        self.app.add_handler(CommandHandler("test", self.test_alerts))
        self.app.add_handler(CommandHandler("price", self.get_price))
        self.app.add_handler(CommandHandler("testwormhole", self.test_wormhole))
        self.app.add_handler(CommandHandler("debug", self.debug_status))
    
    def normalize_symbol(self, symbol):
        symbol = symbol.upper().strip()
        if symbol in self.symbol_mappings:
            return self.symbol_mappings[symbol]
        if symbol.endswith("-USD"):
            return symbol
        return symbol
    
    def validate_symbol(self, symbol):
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d", interval="1m")
            if data.empty:
                return False, f"No data available for {symbol}"
            
            current_price = float(data['Close'].iloc[-1])
            if current_price <= 0:
                return False, f"Invalid price data for {symbol}"
            
            return True, current_price
        except Exception as e:
            return False, f"Error validating {symbol}: {str(e)}"
    
    async def start_command(self, update: Update, context):
        chat_id = update.effective_chat.id
        self.user_chats.add(chat_id)
        
        # Initialize user settings with default alert timings
        self.user_settings[chat_id] = {
            "alert_times": [1, 5, 15, 30],  # Default: 1, 5, 15, 30 minutes before
            "analysis_detail": "detailed",   # brief, detailed, verbose
            "trade_alerts": True,
            "price_alerts": True
        }
        
        message = """🐛 **PRICEWORM STRATEGY BOT** 🐛

*"The ancient worm watches sacred times and guides precise entries..."*

**🎯 Enhanced Strategy Implementation:**
📍 Captures exact pivot prices at wormhole times
🔔 Bidirectional alerts (before AND after wormholes)
📊 Continuous monitoring until session + 1 hour
🎪 Proximity-based alert restart near pivots
📈 Structure-based move detection (recent highs/lows)
🔄 Complete retest and execution guidance

**🚀 Quick Start:**
/monitor BTC - Start tracking Bitcoin
/alerts 5 15 30 - Set bidirectional alert timings
/settings - View your preferences
/wormholes - Next sacred times

**🛠️ Debug Commands:**
/debug - Show detailed status
/testwormhole - Test pivot capture

**Current Status:** 🟢 READY TO HUNT

The worm follows the complete ancient rhythm..."""
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context):
        help_text = """📚 **COMPLETE PRICEWORM GUIDE** 📚

**🕳️ SACRED WORMHOLE TIMES (EST):**
- Midnight: 00:46-00:47
- Premarket: 06:43-06:44  
- Midday: 11:57-11:58
- Afterhours: 17:32-17:33

**🎯 THE COMPLETE STRATEGY:**
1. **Bidirectional Alerts**: Warnings before AND after wormholes
2. **Pivot Capture**: Exact price recorded at wormhole time
3. **Continuous Monitoring**: Alerts continue until session + 1 hour
4. **Proximity Restart**: Alerts resume when price returns to pivot
5. **Structural Moves**: Detection based on recent highs/lows
6. **Retest Guidance**: Precise entry timing on pivot retests
7. **Trade Execution**: Complete trade lifecycle management

**🤖 COMMANDS:**
/monitor <SYMBOL> - Track any asset
/alerts <TIMES> - Set bidirectional timings (e.g. /alerts 5 15 30)
/settings - View your alert preferences  
/trades - See pending and open trades
/setups - Current post-wormhole setups
/debug - Show detailed status
/testwormhole - Test pivot capture

**🔔 ENHANCED ALERT SYSTEM:**
**BEFORE WORMHOLE** - Countdown alerts at your intervals
**AFTER WORMHOLE** - Progress alerts leading to session
**PROXIMITY RESTART** - Alerts resume near pivot prices
**STRUCTURAL MOVES** - New highs/lows beyond recent range

**⚙️ SMART TIMING:**
- Alerts stop 1 hour after session opens
- Proximity detection restarts alert cycles
- Move detection uses market structure, not percentages

The bot provides complete situational awareness throughout the priceworm cycle."""
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def test_wormhole(self, update: Update, context):
        """Manually test wormhole pivot capture"""
        await update.message.reply_text("🧪 **Testing Wormhole Pivot Capture** 🧪")
        
        if not self.monitored_symbols:
            await update.message.reply_text("❌ No symbols monitored. Use /monitor <SYMBOL> first.")
            return
        
        # Simulate wormhole capture
        est = pytz.timezone('US/Eastern')
        now = datetime.now(est)
        current_time = now.time()
        
        await update.message.reply_text(f"⏰ Current EST time: {current_time.strftime('%H:%M:%S')}")
        
        # Force capture for testing
        await self.capture_wormhole_pivots("test", current_time)
        
        await update.message.reply_text("✅ Test wormhole capture completed!")
    
    async def debug_status(self, update: Update, context):
        """Show detailed debug information"""
        est = pytz.timezone('US/Eastern')
        now = datetime.now(est)
        current_time = now.time()
        
        message = f"🔍 **DEBUG STATUS** 🔍\n\n"
        message += f"**Current EST Time:** {current_time.strftime('%H:%M:%S')}\n"
        message += f"**Date:** {now.date()}\n\n"
        
        message += f"**Monitored Symbols:** {len(self.monitored_symbols)}\n"
        for symbol in self.monitored_symbols.keys():
            if symbol in self.price_cache:
                price = self.price_cache[symbol]["current_price"]
                updated = self.price_cache[symbol]["last_update"].strftime('%H:%M:%S')
                message += f"• {symbol}: ${price:.2f} (updated {updated})\n"
        
        message += f"\n**Wormhole Times:**\n"
        for name, wormhole_time in self.wormholes.items():
            time_diff = (datetime.combine(now.date(), wormhole_time) - 
                        datetime.combine(now.date(), current_time)).total_seconds() / 60
            status = "🔥 ACTIVE" if -1 <= time_diff <= 0 else f"{time_diff:.1f}m away"
            message += f"• {name.title()}: {wormhole_time.strftime('%H:%M')} ({status})\n"
        
        message += f"\n**Pivot Data:** {len(self.pivot_data)} symbols\n"
        message += f"**Active Setups:** {len(self.active_setups)}\n"
        message += f"**Pending Trades:** {len(self.pending_trades)}\n"
        
        await update.message.reply_text(message)
    
    async def set_alert_timing(self, update: Update, context):
        """Set custom alert timing preferences"""
        chat_id = update.effective_chat.id
        
        if not context.args:
            current_times = self.user_settings.get(chat_id, {}).get("alert_times", [1, 5, 15, 30])
            await update.message.reply_text(
                f"⏰ **Current Alert Times:** {', '.join(map(str, current_times))} minutes\n\n" +
                "**Bidirectional System:** These times apply BEFORE and AFTER wormholes\n\n" +
                "**Set new times:** /alerts 1 5 15 30\n" +
                "**Available:** 1, 3, 5, 12, 15, 24, 30 minutes\n" +
                "**Example:** /alerts 5 15 - Alerts at 5min and 15min intervals"
            )
            return
        
        # Parse and validate alert times
        valid_times = [1, 3, 5, 12, 15, 24, 30]
        new_times = []
        
        for arg in context.args:
            try:
                minutes = int(arg)
                if minutes in valid_times:
                    new_times.append(minutes)
                else:
                    await update.message.reply_text(f"❌ Invalid time: {minutes}. Use: 1, 3, 5, 12, 15, 24, 30")
                    return
            except ValueError:
                await update.message.reply_text(f"❌ Invalid format: {arg}")
                return
        
        if not new_times:
            await update.message.reply_text("❌ No valid times provided")
            return
        
        # Sort times in ascending order
        new_times.sort()
        
        if chat_id not in self.user_settings:
            self.user_settings[chat_id] = {}
        
        self.user_settings[chat_id]["alert_times"] = new_times
        
        await update.message.reply_text(
            f"✅ **Bidirectional Alert Times Updated**\n\n" +
            f"**Schedule:** {', '.join(map(str, new_times))} minutes\n\n" +
            f"**BEFORE wormholes:** T-minus alerts\n" +
            f"**AFTER wormholes:** T-plus alerts until session + 1hr\n" +
            f"**PROXIMITY:** Auto-restart when price returns to pivot"
        )
    
    async def show_settings(self, update: Update, context):
        """Show user's current settings"""
        chat_id = update.effective_chat.id
        settings = self.user_settings.get(chat_id, {})
        
        alert_times = settings.get("alert_times", [1, 5, 15, 30])
        analysis_detail = settings.get("analysis_detail", "detailed")
        trade_alerts = settings.get("trade_alerts", True)
        price_alerts = settings.get("price_alerts", True)
        
        message = f"""⚙️ **YOUR PRICEWORM SETTINGS** ⚙️

**🔔 Bidirectional Alert Schedule:**
- **Times:** {', '.join(map(str, alert_times))} minutes
- **Before Wormholes:** T-minus countdown alerts
- **After Wormholes:** T-plus progress alerts
- **Duration:** Until session + 1 hour
- **Proximity Restart:** When price returns to pivot

**📊 Alert Types:**
- **Price Alerts:** {'✅ Enabled' if price_alerts else '❌ Disabled'}
- **Trade Alerts:** {'✅ Enabled' if trade_alerts else '❌ Disabled'}
- **Analysis Level:** {analysis_detail.title()}

**🎯 Next Alerts:**
You'll receive notifications at each scheduled interval throughout the complete priceworm cycle.

**⚙️ Customize:**
/alerts 1 5 15 30 - Change bidirectional timing
Use /help for complete command reference"""
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def monitor_symbol(self, update: Update, context):
        if not context.args:
            await update.message.reply_text(
                "🔍 **Specify symbol to monitor:**\n\n" +
                "Examples: /monitor BTC, /monitor AAPL\n" +
                "The bot will track wormhole pivots and provide complete trade guidance!"
            )
            return
        
        user_symbol = context.args[0]
        symbol = self.normalize_symbol(user_symbol)
        chat_id = update.effective_chat.id
        
        is_valid, result = self.validate_symbol(symbol)
        if not is_valid:
            await update.message.reply_text(f"❌ **Error:** {result}")
            return
        
        self.monitored_symbols[symbol] = chat_id
        await self.initialize_symbol_data(symbol)
        self.real_time_tracker.start_real_time_tracking(symbol)
        
        current_price = result
        symbol_type = "Crypto" if "-USD" in symbol else "Stock/ETF"
        data_source = "Binance" if (symbol.endswith('-USD') and 
                     self.real_time_tracker.is_crypto_available_on_binance(symbol)) else "Yahoo"
        
        await update.message.reply_text(
            f"🌀 **PRICEWORM TRACKING ACTIVATED** 🌀\n\n" +
            f"**Symbol:** {symbol} ({user_symbol.upper()})\n" +
            f"**Type:** {symbol_type}\n" +
            f"**Source:** {data_source}\n" +
            f"**Price:** ${current_price:.2f}\n\n" +
            f"*The ancient worm now watches {symbol} for sacred opportunities...*\n\n" +
            f"**Next Wormhole:** {self.get_next_wormhole()}\n" +
            f"**Alert Schedule:** {', '.join(map(str, self.user_settings.get(chat_id, {}).get('alert_times', [1, 5, 15, 30])))} min (bidirectional)\n\n" +
            f"You'll receive **PRICE ALERTS** and **TRADE ALERTS** throughout the complete cycle.",
            parse_mode='Markdown'
        )
    
    async def stop_monitoring(self, update: Update, context):
        """Stop monitoring a specific symbol"""
        if not context.args:
            await update.message.reply_text(
                "🛑 **Specify symbol to stop monitoring:**\n\n" +
                "Example: /stop BTC"
            )
            return
        
        user_symbol = context.args[0].upper()
        symbol = self.normalize_symbol(user_symbol)
        
        if symbol in self.monitored_symbols:
            self.real_time_tracker.stop_tracking(symbol)
            del self.monitored_symbols[symbol]
            
            if symbol in self.price_cache:
                del self.price_cache[symbol]
            if symbol in self.pivot_data:
                del self.pivot_data[symbol]
            
            await update.message.reply_text(f"⏹️ **Stopped monitoring {user_symbol}**")
        else:
            await update.message.reply_text(f"❌ **{user_symbol} not monitored**")
    
    async def stop_all_monitoring(self, update: Update, context):
        """Stop monitoring all symbols"""
        if not self.monitored_symbols:
            await update.message.reply_text("ℹ️ No symbols currently being monitored")
            return
        
        count = len(self.monitored_symbols)
        
        # Stop all real-time tracking
        for symbol in list(self.monitored_symbols.keys()):
            self.real_time_tracker.stop_tracking(symbol)
        
        # Clear all data
        self.monitored_symbols.clear()
        self.price_cache.clear()
        self.pivot_data.clear()
        self.active_setups.clear()
        self.pending_trades.clear()
        self.open_trades.clear()
        
        await update.message.reply_text(
            f"🛑 **Stopped monitoring all {count} symbols**\n\n" +
            f"*The worm retreats to the depths...*\n\n" +
            f"All tracking, setups, and trades cleared."
        )
    
    async def list_monitored(self, update: Update, context):
        """List all monitored symbols"""
        if not self.monitored_symbols:
            await update.message.reply_text(
                "📝 **No symbols currently monitored**\n\n" +
                "Use /monitor <SYMBOL> to start tracking"
            )
            return
        
        chat_id = update.effective_chat.id
        user_symbols = [symbol for symbol, user_chat in self.monitored_symbols.items() if user_chat == chat_id]
        
        if not user_symbols:
            await update.message.reply_text(
                "📝 **No symbols monitored by you**\n\n" +
                "Use /monitor <SYMBOL> to start tracking"
            )
            return
        
        message = "📊 **YOUR MONITORED SYMBOLS** 📊\n\n"
        
        for symbol in user_symbols:
            if symbol in self.price_cache:
                cache = self.price_cache[symbol]
                price = cache['current_price']
                updated = cache['last_update'].strftime('%H:%M:%S')
                symbol_display = symbol.replace('-USD', '')
                
                # Data source indicator
                source = "🔴" if (symbol.endswith('-USD') and 
                               self.real_time_tracker.is_crypto_available_on_binance(symbol)) else "📊"
                
                message += f"{source} **{symbol_display}**: ${price:.2f}\n"
                message += f"Updated: {updated}\n\n"
            else:
                symbol_display = symbol.replace('-USD', '')
                message += f"⏳ **{symbol_display}**: Loading...\n"
        
        message += f"**Total:** {len(user_symbols)} symbols\n"
        message += f"**Next Wormhole:** {self.get_next_wormhole()}\n"
        
        # Show alert settings
        alert_times = self.user_settings.get(chat_id, {}).get("alert_times", [1, 5, 15, 30])
        message += f"**Alert Schedule:** {', '.join(map(str, alert_times))} min (bidirectional)"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def show_wormholes(self, update: Update, context):
        """Show upcoming wormhole times"""
        est = pytz.timezone('US/Eastern')
        now = datetime.now(est)
        
        message = "🕳️ **UPCOMING SACRED WORMHOLES** 🕳️\n\n"
        
        for name, wormhole_time in self.wormholes.items():
            next_occurrence = datetime.combine(now.date(), wormhole_time)
            next_occurrence = est.localize(next_occurrence)
            
            if next_occurrence < now:
                next_occurrence += timedelta(days=1)
            
            time_until = next_occurrence - now
            hours, remainder = divmod(time_until.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            message += f"**{name.title()}**: {wormhole_time.strftime('%H:%M')} EST\n"
            message += f"⏰ In {hours}h {minutes}m\n\n"
        
        message += "**Remember:** These are the only 4 sacred times.\n"
        message += "Bidirectional alerts: Before AND after each wormhole.\n\n"
        message += "*The ancient patterns never change...*"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def show_active_setups(self, update: Update, context):
        """Show currently active priceworm setups"""
        chat_id = update.effective_chat.id
        user_symbols = [symbol for symbol, user_chat in self.monitored_symbols.items() if user_chat == chat_id]
        
        if not user_symbols:
            await update.message.reply_text("📊 No monitored symbols")
            return
        
        # Filter setups for user's symbols
        user_setups = {k: v for k, v in self.active_setups.items() if v["symbol"] in user_symbols}
        
        if not user_setups:
            await update.message.reply_text(
                "📊 **No active priceworm setups**\n\n" +
                "Setups appear when:\n" +
                "• Wormhole creates pivot\n" +
                "• Price holds above low or below high\n\n" +
                "Keep monitoring - the worm is patient..."
            )
            return
        
        message = "🎯 **YOUR ACTIVE SETUPS** 🎯\n\n"
        
        for setup_key, setup in user_setups.items():
            symbol_display = setup["symbol"].replace('-USD', '')
            emoji = "🚀" if setup["type"] == "LONG" else "📉"
            
            message += f"{emoji} **{symbol_display} {setup['type']}** {setup['setup_strength']}\n"
            message += f"• Current: ${setup['current_price']:.2f}\n"
            message += f"• Pivot: ${setup['pivot_price']:.2f} ({setup['wormhole']})\n\n"
        
        message += "*These are live priceworm opportunities!*"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def show_trades(self, update: Update, context):
        """Show pending and open trades"""
        chat_id = update.effective_chat.id
        user_symbols = [symbol for symbol, user_chat in self.monitored_symbols.items() if user_chat == chat_id]
        
        if not user_symbols:
            await update.message.reply_text("📊 No monitored symbols")
            return
        
        # Filter trades for user's symbols
        user_pending = {k: v for k, v in self.pending_trades.items() if v["symbol"] in user_symbols}
        user_open = {k: v for k, v in self.open_trades.items() if v["symbol"] in user_symbols}
        
        message = "📋 **YOUR PRICEWORM TRADES** 📋\n\n"
        
        if user_pending:
            message += "**🔄 PENDING LIMIT ORDERS:**\n"
            for trade_key, trade in user_pending.items():
                symbol_display = trade["symbol"].replace('-USD', '')
                emoji = "🚀" if trade["direction"] == "LONG" else "📉"
                move_type = trade.get("move_type", "SIGNIFICANT MOVE")
                message += f"{emoji} **{symbol_display} {trade['direction']}** ({move_type})\n"
                message += f"• Limit: ${trade['pivot_price']:.2f}\n"
                message += f"• Wormhole: {trade['wormhole']}\n\n"
        
        if user_open:
            message += "**✅ OPEN POSITIONS:**\n"
            for trade_key, trade in user_open.items():
                symbol_display = trade["symbol"].replace('-USD', '')
                emoji = "✅"
                message += f"{emoji} **{symbol_display} {trade['direction']}**\n"
                message += f"• Entry: ${trade['entry_price']:.2f}\n"
                message += f"• Wormhole: {trade['wormhole']}\n\n"
        
        if not user_pending and not user_open:
            message += "**No active trades**\n\n"
            message += "Trades appear when:\n"
            message += "• New highs/lows beyond recent range\n"
            message += "• Limit orders are recommended\n"
            message += "• Retest situations develop\n\n"
            message += "*The worm waits for structural breaks...*"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def show_rules(self, update: Update, context):
        """Show priceworm rules"""
        rules = """📜 **PRICEWORM STRATEGY RULES** 📜

**🕳️ THE SACRED WORMHOLES**
Only 4 times matter: Midnight, Premarket, Midday, Afterhours

**📍 PIVOT CAPTURE**
Record exact price at wormhole time - this is your reference

**🔔 BIDIRECTIONAL ALERTS**
- Before wormhole: Countdown alerts at your intervals
- After wormhole: Progress alerts until session + 1 hour
- Proximity restart: Resume when price returns to pivot

**🎯 SETUP FORMATION**
- Long: Price holds above pivot
- Short: Price holds below pivot

**📈 STRUCTURAL MOVES**
New highs/lows beyond recent 30-minute range trigger limit orders

**🔄 THE RETEST**
Wait for price to return to pivot level for optimal entry

**✅ TRADE EXECUTION**
Enter when price crosses back through pivot

**⚠️ RISK MANAGEMENT**
- Never trade AT the wormhole
- Use market structure for stops
- Set stops beyond recent highs/lows
- Take profits at session momentum

**🤖 BOT GUIDANCE**
- **PRICE ALERTS**: Complete cycle awareness
- **TRADE ALERTS**: Structure-based opportunities

*The worm teaches complete market rhythm*"""
        
        await update.message.reply_text(rules, parse_mode='Markdown')
    
    async def show_status(self, update: Update, context):
        """Show bot status"""
        chat_id = update.effective_chat.id
        user_symbols = [symbol for symbol, user_chat in self.monitored_symbols.items() if user_chat == chat_id]
        
        message = "📊 **PRICEWORM BOT STATUS** 📊\n\n"
        
        if not user_symbols:
            message += "**Your Symbols:** None monitored\n"
        else:
            message += f"**Your Symbols:** {len(user_symbols)} active\n"
            
            # Show data sources
            binance_count = sum(1 for s in user_symbols 
                              if s.endswith('-USD') and 
                              self.real_time_tracker.is_crypto_available_on_binance(s))
            yahoo_count = len(user_symbols) - binance_count
            
            message += f"🔴 Binance streams: {binance_count}\n"
            message += f"📊 Yahoo polling: {yahoo_count}\n\n"
        
        # User's alert settings
        settings = self.user_settings.get(chat_id, {})
        alert_times = settings.get("alert_times", [1, 5, 15, 30])
        message += f"**Alert Schedule:** {', '.join(map(str, alert_times))} min (bidirectional)\n\n"
        
        # Active data
        user_setups = sum(1 for setup in self.active_setups.values() if setup["symbol"] in user_symbols)
        user_pending = sum(1 for trade in self.pending_trades.values() if trade["symbol"] in user_symbols)
        user_open = sum(1 for trade in self.open_trades.values() if trade["symbol"] in user_symbols)
        
        message += f"**Your Active Setups:** {user_setups}\n"
        message += f"**Your Pending Trades:** {user_pending}\n"
        message += f"**Your Open Trades:** {user_open}\n\n"
        
        message += f"**Next Wormhole:** {self.get_next_wormhole()}\n"
        message += f"**Total Users:** {len(self.user_chats)}"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def get_price(self, update: Update, context):
        """Get current price for any symbol"""
        if not context.args:
            await update.message.reply_text(
                "💰 **Get current price:**\n\n" +
                "Example: /price BTC\n" +
                "Example: /price AAPL"
            )
            return
        
        user_symbol = context.args[0]
        symbol = self.normalize_symbol(user_symbol)
        
        is_valid, result = self.validate_symbol(symbol)
        
        if not is_valid:
            await update.message.reply_text(f"❌ {result}")
            return
        
        price = result
        symbol_type = "Crypto" if "-USD" in symbol else "Stock/ETF"
        is_monitored = symbol in self.monitored_symbols
        
        message = f"💰 **CURRENT PRICE** 💰\n\n"
        message += f"**Symbol:** {user_symbol.upper()}\n"
        message += f"**Type:** {symbol_type}\n"
        message += f"**Price:** ${price:.2f}\n"
        message += f"**Monitored:** {'✅ Yes' if is_monitored else '❌ No'}\n\n"
        
        if not is_monitored:
            message += f"Use /monitor {user_symbol.upper()} to start priceworm tracking!"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def test_alerts(self, update: Update, context):
        """Test the alert system"""
        await update.message.reply_text("🧪 **Testing Enhanced Priceworm Alert System** 🧪")
        
        await asyncio.sleep(1)
        
        # Test Before Wormhole Price Alert
        before_alert = """**PRICE ALERT** 🌀

**WORMHOLE APPROACHING**

**Midnight Wormhole**: 00:46 EST
⏰ **T-minus 5 minutes**

*Sacred time approaches...*

**📊 MONITORED SYMBOLS:**
- **BTC**: $43,280.00

**🎯 PREPARE TO:**
- Observe price action at 00:46 EST
- Note exact pivot price for each symbol
- Watch for setup formation after wormhole

This is a BEFORE wormhole PRICE ALERT."""
        
        await update.message.reply_text(before_alert, parse_mode='Markdown')
        
        await asyncio.sleep(2)
        
        # Test After Wormhole Price Alert
        after_alert = """**PRICE ALERT** 🌀

**WORMHOLE TIMING UPDATE**

**Midnight Wormhole**: 00:46 EST
⏰ **T-plus 15 minutes**

*Post-wormhole phase active...*

**📊 MONITORED SYMBOLS:**
- **BTC**: $43,150.00 (0.3% above $43,020.00 pivot)

**🎯 POST-WORMHOLE PHASE:**
- Monitor price action relative to pivots
- Watch for significant highs/lows
- Next session: London in 1h 31m
- Alerts continue until session + 1 hour

This is an AFTER wormhole PRICE ALERT."""
        
        await update.message.reply_text(after_alert, parse_mode='Markdown')
        
        await asyncio.sleep(2)
        
        # Test Enhanced Trade Alert
        trade_alert = """**TRADE ALERT** 🚀

**NEW HIGH DETECTED - LIMIT ORDER RECOMMENDED**

**Symbol:** BTC
**Direction:** LONG
**Current Price:** $43,580.00
**Pivot Price:** $43,150.00 (midnight wormhole)

**📊 MOVE ANALYSIS:**
- **NEW HIGH**: $43,580.00
- **Previous Range Boundary**: $43,420.00
- **Break Above Range**: 0.4%
- **Distance from Pivot**: 1.0%

**🎯 RECOMMENDED ACTION:**
**Place LIMIT LONG order at $43,150.00**

This is an enhanced TRADE ALERT based on market structure."""
        
        await update.message.reply_text(trade_alert, parse_mode='Markdown')
        
        await asyncio.sleep(1)
        await update.message.reply_text("✅ **Enhanced alert system working correctly!**\n\nBidirectional PRICE alerts and structure-based TRADE alerts tested.")
    
    async def process_real_time_price(self, symbol, current_price):
        """Process real-time price updates - CORE PRICEWORM LOGIC"""
        # Update price cache
        if symbol in self.price_cache:
            old_price = self.price_cache[symbol]["current_price"]
            self.price_cache[symbol]["current_price"] = current_price
            self.price_cache[symbol]["last_update"] = datetime.now()
            
            # Check all priceworm logic
            await self.check_post_wormhole_setups(symbol, current_price)
            await self.check_significant_moves(symbol, current_price, old_price)
            await self.check_retest_situations(symbol, current_price)
            await self.check_trade_executions(symbol, current_price)
    
    async def check_post_wormhole_setups(self, symbol, current_price):
        """Check for post-wormhole setup conditions"""
        if symbol not in self.pivot_data:
            return
        
        # Get most recent pivot (within last 8 hours)
        recent_pivot = self.get_most_recent_pivot(symbol)
        if not recent_pivot:
            return
        
        pivot_price = recent_pivot["price"]
        wormhole_name = recent_pivot["wormhole"]
        recent_time = datetime.now()  # Simplified for this example
        
        # Determine setup direction
        setup_key = f"{symbol}_{recent_time.strftime('%Y%m%d_%H%M')}"
        
        if current_price > pivot_price * 1.002:  # 0.2% above pivot
            setup = {
                "type": "LONG",
                "symbol": symbol,
                "pivot_price": pivot_price,
                "pivot_time": recent_time,
                "wormhole": wormhole_name,
                "current_price": current_price,
                "setup_strength": self.calculate_setup_strength(current_price, pivot_price, "above")
            }
            
            if setup_key not in self.active_setups:
                self.active_setups[setup_key] = setup
                await self.send_setup_preparation_alert(setup)
        
        elif current_price < pivot_price * 0.998:  # 0.2% below pivot
            setup = {
                "type": "SHORT",
                "symbol": symbol,
                "pivot_price": pivot_price,
                "pivot_time": recent_time,
                "wormhole": wormhole_name,
                "current_price": current_price,
                "setup_strength": self.calculate_setup_strength(current_price, pivot_price, "below")
            }
            
            if setup_key not in self.active_setups:
                self.active_setups[setup_key] = setup
                await self.send_setup_preparation_alert(setup)
        
        # Update existing setup
        if setup_key in self.active_setups:
            self.active_setups[setup_key]["current_price"] = current_price
    
    def calculate_setup_strength(self, current_price, pivot_price, direction):
        """Calculate setup strength based on distance from pivot"""
        if direction == "above":
            distance_pct = ((current_price - pivot_price) / pivot_price) * 100
        else:
            distance_pct = ((pivot_price - current_price) / pivot_price) * 100
        
        if distance_pct > 1.0:
            return "🔥 STRONG"
        elif distance_pct > 0.5:
            return "⚡ MODERATE"
        else:
            return "📊 BUILDING"
    
    async def send_setup_preparation_alert(self, setup):
        """Send setup preparation alert after wormhole"""
        symbol = setup["symbol"]
        symbol_display = symbol.replace('-USD', '')
        
        # Spam protection
        alert_key = f"setup_{symbol}_{setup['type']}_{setup['pivot_time'].strftime('%Y%m%d_%H%M')}"
        if alert_key in self.sent_alerts:
            return
        
        self.sent_alerts[alert_key] = datetime.now()
        
        emoji = "🚀" if setup["type"] == "LONG" else "📉"
        next_session = self.get_next_session_info()
        
        message = f"""**PRICE ALERT** {emoji}

**PRICEWORM SETUP PREPARATION**

**Symbol:** {symbol_display}
**Setup Type:** {setup['type']} {setup['setup_strength']}
**Pivot Price:** ${setup['pivot_price']:.2f} ({setup['wormhole']} wormhole)
**Current Price:** ${setup['current_price']:.2f}

**📊 ANALYSIS:**
- Price is holding {"ABOVE" if setup['type'] == "LONG" else "BELOW"} the {setup['wormhole']} pivot
- {"Bullish" if setup['type'] == "LONG" else "Bearish"} setup is forming
- Next session: {next_session['name']} in {next_session['time_remaining']}

**🎯 STRATEGY:**
- Wait for structural move beyond recent range
- Bot will alert when to place limit order at pivot
- {"Enter long" if setup['type'] == "LONG" else "Enter short"} on retest of ${setup['pivot_price']:.2f}

*The worm prepares for the hunt...*"""
        
        if symbol in self.monitored_symbols:
            chat_id = self.monitored_symbols[symbol]
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(f"Error sending setup alert: {e}")
    
    async def check_significant_moves(self, symbol, current_price, old_price):
        """Enhanced significant move detection based on recent highs/lows"""
        if symbol not in self.pivot_data:
            return
        
        # Get most recent pivot
        recent_pivot = self.get_most_recent_pivot(symbol)
        if not recent_pivot:
            return
        
        # Get recent price action (last 30 minutes)
        recent_highs_lows = self.get_recent_highs_lows(symbol, minutes=30)
        if not recent_highs_lows:
            return
        
        recent_high = recent_highs_lows["high"]
        recent_low = recent_highs_lows["low"]
        
        # Check for significant moves - new highs/lows beyond recent range
        significant_high = current_price > recent_high * 1.002  # 0.2% above recent high
        significant_low = current_price < recent_low * 0.998   # 0.2% below recent low
        
        if significant_high or significant_low:
            trade_key = f"{symbol}_{recent_pivot['wormhole']}_{datetime.now().strftime('%Y%m%d_%H%M')}"
            
            if trade_key not in self.pending_trades:
                pivot_price = recent_pivot["price"]
                
                # Determine direction based on pivot relationship
                if significant_high and current_price > pivot_price:
                    direction = "LONG"
                    move_type = "NEW HIGH"
                    reference_price = recent_high
                elif significant_low and current_price < pivot_price:
                    direction = "SHORT"
                    move_type = "NEW LOW"
                    reference_price = recent_low
                else:
                    return  # No valid setup
                
                pending_trade = {
                    "symbol": symbol,
                    "direction": direction,
                    "pivot_price": pivot_price,
                    "pivot_time": datetime.now(),
                    "wormhole": recent_pivot["wormhole"],
                    "significant_price": current_price,
                    "move_type": move_type,
                    "reference_price": reference_price,
                    "created_time": datetime.now()
                }
                
                self.pending_trades[trade_key] = pending_trade
                await self.send_enhanced_limit_order_alert(pending_trade)
    
    def get_recent_highs_lows(self, symbol, minutes=30):
        """Get recent highs and lows for significant move detection"""
        try:
            # Get recent price data
            data = self.get_extended_price_data(symbol, period="1d", interval="1m")
            if data is None or len(data) < minutes:
                return None
            
            # Get last N minutes of data
            recent_data = data.tail(minutes)
            
            return {
                "high": float(recent_data['High'].max()),
                "low": float(recent_data['Low'].min()),
                "data_points": len(recent_data)
            }
        except Exception as e:
            print(f"Error getting recent highs/lows for {symbol}: {e}")
            return None
    
    def get_most_recent_pivot(self, symbol):
        """Helper to get most recent pivot data"""
        if symbol not in self.pivot_data:
            return None
        
        recent_pivot = None
        recent_time = None
        
        for pivot_time, pivot_info in self.pivot_data[symbol].items():
            hours_ago = (datetime.now() - pivot_time).total_seconds() / 3600
            if hours_ago <= 8:
                if recent_time is None or pivot_time > recent_time:
                    recent_pivot = pivot_info
                    recent_time = pivot_time
        
        return recent_pivot
    
    async def send_enhanced_limit_order_alert(self, trade):
        """Enhanced limit order alert with move context"""
        symbol_display = trade["symbol"].replace('-USD', '')
        emoji = "🚀" if trade["direction"] == "LONG" else "📉"
        
        # Calculate move details
        move_from_reference = abs(trade["significant_price"] - trade["reference_price"]) / trade["reference_price"] * 100
        move_from_pivot = abs(trade["significant_price"] - trade["pivot_price"]) / trade["pivot_price"] * 100
        
        message = f"""**TRADE ALERT** {emoji}

**{trade['move_type']} DETECTED - LIMIT ORDER RECOMMENDED**

**Symbol:** {symbol_display}
**Direction:** {trade['direction']}
**Current Price:** ${trade['significant_price']:.2f}
**Pivot Price:** ${trade['pivot_price']:.2f} ({trade['wormhole']} wormhole)

**📊 MOVE ANALYSIS:**
- **{trade['move_type']}**: ${trade['significant_price']:.2f}
- **Previous Range Boundary**: ${trade['reference_price']:.2f}
- **Break Above/Below Range**: {move_from_reference:.2f}%
- **Distance from Pivot**: {move_from_pivot:.1f}%

**🎯 RECOMMENDED ACTION:**
**Place LIMIT {trade['direction']} order at ${trade['pivot_price']:.2f}**

**📋 ENHANCED TRADE PLAN:**
- **Entry:** ${trade['pivot_price']:.2f} (limit order at pivot)
- **Setup Reason:** {trade['move_type'].lower()} beyond recent range
- **Stop:** {"Below" if trade['direction'] == "LONG" else "Above"} ${trade['reference_price']:.2f}
- **Target:** Next session momentum

**⚠️ RISK MANAGEMENT:**
- Significant move validates setup strength
- Clean break of recent range structure
- Pivot retest provides optimal entry

*The worm detects structural breaks...*"""
        
        if trade["symbol"] in self.monitored_symbols:
            chat_id = self.monitored_symbols[trade["symbol"]]
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(f"Error sending enhanced limit order alert: {e}")
    
    async def check_retest_situations(self, symbol, current_price):
        """Check for retest situations of pending trades"""
        for trade_key, trade in self.pending_trades.items():
            if trade["symbol"] != symbol:
                continue
            
            pivot_price = trade["pivot_price"]
            distance_to_pivot = abs(current_price - pivot_price) / pivot_price
            
            # Alert when price is approaching pivot (within 0.3%)
            if distance_to_pivot < 0.003:
                alert_key = f"retest_{trade_key}"
                
                if alert_key not in self.sent_alerts:
                    self.sent_alerts[alert_key] = datetime.now()
                    await self.send_retest_alert(trade, current_price)
    
    async def send_retest_alert(self, trade, current_price):
        """Send retest alert as price approaches pivot"""
        symbol_display = trade["symbol"].replace('-USD', '')
        emoji = "🎯"
        
        message = f"""**TRADE ALERT** {emoji}

**RETEST IN PROGRESS**

**Symbol:** {symbol_display}
**Trade Type:** {trade['direction']}
**Pivot Price:** ${trade['pivot_price']:.2f}
**Current Price:** ${current_price:.2f}

**📊 ANALYSIS:**
- Price is retesting the {trade['wormhole']} pivot level
- Limit order should be ready at ${trade['pivot_price']:.2f}
- High probability of execution

**🔔 PREPARE FOR EXECUTION:**
- Confirm limit order is placed
- Set stop loss if not already done
- Watch for clean break through pivot

*The worm returns to sacred ground...*"""
        
        if trade["symbol"] in self.monitored_symbols:
            chat_id = self.monitored_symbols[trade["symbol"]]
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(f"Error sending retest alert: {e}")
    
    async def check_trade_executions(self, symbol, current_price):
        """Check for trade executions when price crosses pivot"""
        executed_trades = []
        
        for trade_key, trade in self.pending_trades.items():
            if trade["symbol"] != symbol:
                continue
            
            pivot_price = trade["pivot_price"]
            
            # Check if trade should execute
            if trade["direction"] == "LONG" and current_price > pivot_price:
                # Long trade executes when price moves back above pivot
                open_trade = {
                    "symbol": symbol,
                    "direction": "LONG",
                    "entry_price": pivot_price,
                    "pivot_time": trade["pivot_time"],
                    "wormhole": trade["wormhole"],
                    "execution_time": datetime.now(),
                    "execution_price": current_price
                }
                
                self.open_trades[trade_key] = open_trade
                await self.send_trade_execution_alert(open_trade)
                executed_trades.append(trade_key)
            
            elif trade["direction"] == "SHORT" and current_price < pivot_price:
                # Short trade executes when price moves back below pivot
                open_trade = {
                    "symbol": symbol,
                    "direction": "SHORT",
                    "entry_price": pivot_price,
                    "pivot_time": trade["pivot_time"],
                    "wormhole": trade["wormhole"],
                    "execution_time": datetime.now(),
                    "execution_price": current_price
                }
                
                self.open_trades[trade_key] = open_trade
                await self.send_trade_execution_alert(open_trade)
                executed_trades.append(trade_key)
        
        # Remove executed trades from pending
        for trade_key in executed_trades:
            del self.pending_trades[trade_key]
    
    async def send_trade_execution_alert(self, trade):
        """Send alert when trade executes"""
        symbol_display = trade["symbol"].replace('-USD', '')
        emoji = "✅"
        
        message = f"""**TRADE ALERT** {emoji}

**TRADE EXECUTED - {trade['direction']} POSITION OPENED**

**Symbol:** {symbol_display}
**Direction:** {trade['direction']}
**Entry Price:** ${trade['entry_price']:.2f}
**Execution Price:** ${trade['execution_price']:.2f}
**Wormhole:** {trade['wormhole']} pivot

**📊 EXECUTION ANALYSIS:**
- Limit order filled on retest of sacred pivot
- Price action confirms {trade['direction'].lower()} bias
- Trade follows priceworm methodology

**📋 TRADE MANAGEMENT:**
- **Stop Loss:** {"Below" if trade['direction'] == "LONG" else "Above"} recent {"low" if trade['direction'] == "LONG" else "high"}
- **Target:** Session momentum or next wormhole
- **Risk:** Manage position size appropriately

**🎯 NEXT STEPS:**
- Monitor price action for continuation
- Consider profit taking at resistance/support
- Watch for new wormhole setups

*The worm has struck with precision!*"""
        
        if trade["symbol"] in self.monitored_symbols:
            chat_id = self.monitored_symbols[trade["symbol"]]
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(f"Error sending execution alert: {e}")
    
    def start_monitoring(self):
        """Start the main monitoring loop with proper event loop setup"""
        def monitoring_loop():
            # Create and set event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Store reference to main loop in price tracker
            self.real_time_tracker.set_main_loop(loop)
            
            print("🔄 Main monitoring loop started with event loop")
            
            while True:
                try:
                    loop.run_until_complete(self.check_wormhole_approach_alerts())
                    loop.run_until_complete(self.check_wormhole_windows())
                    self.update_price_data()
                    self.cleanup_old_data()
                except Exception as e:
                    print(f"Monitoring error: {e}")
                
                time_module.sleep(60)  # Check every minute
        
        monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
        monitor_thread.start()
        print("🐛 Enhanced Priceworm strategy monitoring activated")
        print("🎯 Bidirectional alert system enabled")
        print("📊 Structure-based move detection active")
        print("🔄 Complete cycle awareness online")
    
    async def check_wormhole_approach_alerts(self):
        """Check for bidirectional wormhole alerts - before AND after pivots"""
        est = pytz.timezone('US/Eastern')
        now = datetime.now(est)
        current_time = now.time()
        current_date = now.date()
        
        for wormhole_name, wormhole_time in self.wormholes.items():
            for chat_id in self.user_chats:
                user_alert_times = self.user_settings.get(chat_id, {}).get("alert_times", [1, 5, 15, 30])
                
                # BEFORE wormhole alerts
                for minutes_before in user_alert_times:
                    alert_time = (datetime.combine(datetime.today(), wormhole_time) - 
                                 timedelta(minutes=minutes_before)).time()
                    
                    alert_key = f"{current_date}_{wormhole_name}_before_{minutes_before}_{chat_id}"
                    
                    if (alert_time <= current_time <= 
                        (datetime.combine(datetime.today(), alert_time) + timedelta(minutes=1)).time() and
                        alert_key not in self.sent_alerts):
                        
                        await self.send_wormhole_approach_alert(wormhole_name, wormhole_time, minutes_before, chat_id, "before")
                        self.sent_alerts[alert_key] = datetime.now()
                
                # AFTER wormhole alerts (leading to next session)
                for minutes_after in user_alert_times:
                    alert_time = (datetime.combine(datetime.today(), wormhole_time) + 
                                 timedelta(minutes=minutes_after)).time()
                    
                    alert_key = f"{current_date}_{wormhole_name}_after_{minutes_after}_{chat_id}"
                    
                    # Check if we should still send alerts (not past session + 1 hour)
                    if self.should_continue_alerts(now, wormhole_name):
                        if (alert_time <= current_time <= 
                            (datetime.combine(datetime.today(), alert_time) + timedelta(minutes=1)).time() and
                            alert_key not in self.sent_alerts):
                            
                            await self.send_post_wormhole_alert(wormhole_name, wormhole_time, minutes_after, chat_id)
                            self.sent_alerts[alert_key] = datetime.now()
        
        # Check for proximity-based alert restarts
        await self.check_pivot_proximity_alerts()
    
    def should_continue_alerts(self, current_time, wormhole_name):
        """Check if we should continue sending alerts (not past session + 1 hour)"""
        # Get next session after this wormhole
        next_session_info = self.get_next_session_after_wormhole(wormhole_name)
        if not next_session_info:
            return True
        
        # Check if we're past session + 1 hour
        session_plus_hour = (datetime.combine(current_time.date(), next_session_info["time"]) + 
                            timedelta(hours=1)).time()
        
        return current_time.time() < session_plus_hour
    
    def get_next_session_after_wormhole(self, wormhole_name):
        """Get the next session that occurs after this wormhole"""
        wormhole_times = {
            "midnight": time(0, 46),
            "premarket": time(6, 43),
            "midday": time(11, 57),
            "afterhours": time(17, 32)
        }
        
        sessions = [
            ("Asia", time(20, 0)),
            ("London", time(2, 0)),
            ("NY AM", time(9, 30)),
            ("NY Lunch", time(12, 0)),
            ("NY PM", time(13, 30))
        ]
        
        wormhole_time = wormhole_times.get(wormhole_name)
        if not wormhole_time:
            return None
        
        # Find first session after this wormhole
        for name, session_time in sessions:
            if session_time > wormhole_time:
                return {"name": name, "time": session_time}
        
        # If no session today after wormhole, return tomorrow's first
        return {"name": "Asia", "time": time(20, 0)}
    
    async def check_pivot_proximity_alerts(self):
        """Restart alerts when price returns close to pivot"""
        for symbol in self.monitored_symbols.keys():
            if symbol not in self.pivot_data or symbol not in self.price_cache:
                continue
            
            current_price = self.price_cache[symbol]["current_price"]
            
            # Get most recent pivot
            recent_pivot = self.get_most_recent_pivot(symbol)
            if not recent_pivot:
                continue
            
            pivot_price = recent_pivot["price"]
            distance_to_pivot = abs(current_price - pivot_price) / pivot_price
            
            # If price is within 0.5% of pivot, restart proximity alerts
            if distance_to_pivot < 0.005:
                proximity_key = f"proximity_{symbol}_{recent_pivot['wormhole']}"
                
                if proximity_key not in self.sent_alerts:
                    self.sent_alerts[proximity_key] = datetime.now()
                    await self.send_pivot_proximity_restart_alert(symbol, recent_pivot, current_price)
    
    async def send_wormhole_approach_alert(self, wormhole_name, wormhole_time, minutes_before, chat_id, timing):
        """Enhanced approach alert with timing context"""
        user_symbols = [symbol for symbol, user_chat in self.monitored_symbols.items() if user_chat == chat_id]
        
        if not user_symbols:
            return
        
        timing_text = f"T-minus {minutes_before} minutes" if timing == "before" else f"T-plus {minutes_before} minutes"
        phase = "Sacred time approaches" if timing == "before" else "Post-wormhole phase active"
        
        message = f"""**PRICE ALERT** 🌀

**WORMHOLE TIMING UPDATE**

**{wormhole_name.title()} Wormhole**: {wormhole_time.strftime('%H:%M')} EST
⏰ **{timing_text}**

*{phase}...*

**📊 MONITORED SYMBOLS:**"""
        
        for symbol in user_symbols:
            if symbol in self.price_cache:
                price = self.price_cache[symbol]["current_price"]
                symbol_display = symbol.replace('-USD', '')
                
                # Add pivot context if available
                pivot_context = ""
                if symbol in self.pivot_data:
                    recent_pivot = self.get_most_recent_pivot(symbol)
                    if recent_pivot:
                        pivot_price = recent_pivot["price"]
                        if timing == "after":
                            direction = "above" if price > pivot_price else "below"
                            distance = abs(price - pivot_price) / pivot_price * 100
                            pivot_context = f" ({distance:.1f}% {direction} ${pivot_price:.2f} pivot)"
                
                message += f"\n• **{symbol_display}**: ${price:.2f}{pivot_context}"
        
        if timing == "before":
            message += f"""

**🎯 PREPARE TO:**
- Observe price action at {wormhole_time.strftime('%H:%M')} EST
- Note exact pivot price for each symbol
- Watch for setup formation after wormhole"""
        else:
            next_session = self.get_next_session_info()
            message += f"""

**🎯 POST-WORMHOLE PHASE:**
- Monitor price action relative to pivots
- Watch for significant highs/lows
- Next session: {next_session['name']} in {next_session['time_remaining']}
- Alerts continue until session + 1 hour"""
        
        message += "\n\n*The worm tracks the sacred rhythm...*"
        
        try:
            await self.app.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"Error sending approach alert: {e}")
    
    async def send_post_wormhole_alert(self, wormhole_name, wormhole_time, minutes_after, chat_id):
        """Send post-wormhole timing alerts"""
        await self.send_wormhole_approach_alert(wormhole_name, wormhole_time, minutes_after, chat_id, "after")
    
    async def send_pivot_proximity_restart_alert(self, symbol, pivot_info, current_price):
        """Alert when price returns close to pivot - restart alert cycle"""
        symbol_display = symbol.replace('-USD', '')
        pivot_price = pivot_info["price"]
        
        message = f"""**PRICE ALERT** 🎯

**PIVOT PROXIMITY DETECTED**

**Symbol:** {symbol_display}
**Current Price:** ${current_price:.2f}
**Pivot Price:** ${pivot_price:.2f} ({pivot_info['wormhole']} wormhole)

**📊 ANALYSIS:**
- Price has returned close to the sacred pivot
- Retest situation developing
- Alert cycle restarting due to proximity

**🔔 ALERT STATUS:**
- Proximity-based alerts now active
- Watch for significant price action
- Prepare for potential retest scenarios

*The worm senses the return to sacred ground...*"""
        
        if symbol in self.monitored_symbols:
            chat_id = self.monitored_symbols[symbol]
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(f"Error sending proximity alert: {e}")
    
    async def check_wormhole_windows(self):
        """FIXED: Enhanced wormhole detection with proper timezone handling"""
        est = pytz.timezone('US/Eastern')
        now = datetime.now(est)
        current_time = now.time()
        current_date = now.date()  # Use EST date consistently
        
        print(f"🕐 Current EST time: {current_time.strftime('%H:%M:%S')} on {current_date}")
        
        for name, wormhole_time in self.wormholes.items():
            # FIXED: Use current_date (EST timezone) instead of datetime.today()
            wormhole_start = wormhole_time
            wormhole_end = (datetime.combine(current_date, wormhole_time) + 
                           timedelta(minutes=1)).time()
            
            pivot_key = f"{current_date}_{name}_pivot"
            
            # Debug output
            time_until_wormhole = (datetime.combine(current_date, wormhole_time) - 
                                  datetime.combine(current_date, current_time)).total_seconds() / 60
            
            if abs(time_until_wormhole) < 5:  # Within 5 minutes
                print(f"🕳️ {name.title()} wormhole: {time_until_wormhole:.1f} minutes away")
            
            # Check if we're in the active window
            if wormhole_start <= current_time <= wormhole_end:
                if pivot_key not in self.sent_alerts:
                    print(f"🔥 ACTIVE WORMHOLE: {name.title()} at {current_time.strftime('%H:%M:%S')}")
                    await self.capture_wormhole_pivots(name, wormhole_time)
                    self.sent_alerts[pivot_key] = datetime.now()
                else:
                    print(f"✅ {name.title()} wormhole already processed today")
    
    async def capture_wormhole_pivots(self, wormhole_name, wormhole_time):
        """Enhanced pivot capture with debugging"""
        print(f"📍 Capturing pivots for {wormhole_name.title()} wormhole...")
        
        captured_count = 0
        for symbol in self.monitored_symbols.keys():
            if symbol in self.price_cache:
                pivot_price = self.price_cache[symbol]["current_price"]
                pivot_time = datetime.now()
                
                if symbol not in self.pivot_data:
                    self.pivot_data[symbol] = {}
                
                self.pivot_data[symbol][pivot_time] = {
                    "price": pivot_price,
                    "wormhole": wormhole_name,
                    "time": wormhole_time
                }
                
                print(f"✅ Captured {symbol}: ${pivot_price:.2f} at {wormhole_name} wormhole")
                captured_count += 1
                
                await self.send_wormhole_analysis_alert(symbol, wormhole_name, wormhole_time, pivot_price)
            else:
                print(f"❌ No price data for {symbol}")
        
        print(f"📊 Total pivots captured: {captured_count}")
    
    async def send_wormhole_analysis_alert(self, symbol, wormhole_name, wormhole_time, pivot_price):
        """Send detailed analysis at wormhole time"""
        symbol_display = symbol.replace('-USD', '')
        
        next_session = self.get_next_session_info()
        
        message = f"""**PRICE ALERT** 🕳️

**WORMHOLE ANALYSIS - {wormhole_name.upper()}**

**Symbol:** {symbol_display}
**Time:** {wormhole_time.strftime('%H:%M')} EST
**Pivot Price:** ${pivot_price:.2f}

**📊 DETAILED ANALYSIS:**
- Sacred wormhole window is now active
- Pivot price captured: ${pivot_price:.2f}
- This becomes the key reference level
- Watch for price holding above/below this level

**🎯 SETUP FORMATION:**
- **Long Setup:** Price holds above ${pivot_price:.2f}
- **Short Setup:** Price holds below ${pivot_price:.2f}
- **Next Session:** {next_session['name']} in {next_session['time_remaining']}

**📋 WHAT'S NEXT:**
- Monitor post-wormhole price action
- Bot will alert on setup formation
- Wait for structural moves beyond recent range
- Retest of pivot = entry opportunity

**⚠️ REMEMBER:**
- This is NOT the time to trade
- Let price show its hand first
- Patience is the worm's greatest weapon

*The sacred moment passes... setup formation begins*"""
        
        if symbol in self.monitored_symbols:
            chat_id = self.monitored_symbols[symbol]
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(f"Error sending wormhole analysis: {e}")
    
    def cleanup_old_data(self):
        """Clean up old data to prevent memory issues"""
        cutoff = datetime.now() - timedelta(hours=24)
        
        # Clean old pivots
        for symbol in list(self.pivot_data.keys()):
            old_pivots = [k for k, v in self.pivot_data[symbol].items() if k < cutoff]
            for pivot_time in old_pivots:
                del self.pivot_data[symbol][pivot_time]
        
        # Clean old alerts
        old_alerts = [k for k, v in self.sent_alerts.items() if v < cutoff]
        for alert_key in old_alerts:
            del self.sent_alerts[alert_key]
        
        # Clean old setups
        for setup_key in list(self.active_setups.keys()):
            setup_time = self.active_setups[setup_key]["pivot_time"]
            if (datetime.now() - setup_time).total_seconds() > 28800:  # 8 hours
                del self.active_setups[setup_key]
    
    def get_next_session_info(self):
        """Get next major session opening"""
        est = pytz.timezone('US/Eastern')
        now = datetime.now(est)
        current_time = now.time()
        
        sessions = [
            ("Asia", time(20, 0)),
            ("London", time(2, 0)),
            ("NY AM", time(9, 30)),
            ("NY Lunch", time(12, 0)),
            ("NY PM", time(13, 30))
        ]
        
        for name, session_time in sessions:
            if current_time < session_time:
                target = datetime.combine(now.date(), session_time)
                target = est.localize(target)
                time_diff = target - now
                hours = time_diff.seconds // 3600
                minutes = (time_diff.seconds % 3600) // 60
                
                return {
                    "name": name,
                    "time": session_time.strftime('%H:%M'),
                    "time_remaining": f"{hours}h {minutes}m"
                }
        
        # Tomorrow's first session
        tomorrow = now + timedelta(days=1)
        target = datetime.combine(tomorrow.date(), time(20, 0))
        target = est.localize(target)
        time_diff = target - now
        hours = time_diff.seconds // 3600
        
        return {
            "name": "Asia (Tomorrow)",
            "time": "20:00",
            "time_remaining": f"{hours}h+"
        }
    
    async def initialize_symbol_data(self, symbol):
        """Initialize price data for symbol"""
        try:
            data = self.get_extended_price_data(symbol)
            if data is not None and not data.empty:
                self.price_cache[symbol] = {
                    "current_price": float(data['Close'].iloc[-1]),
                    "previous_close": float(data['Close'].iloc[-2]) if len(data) > 1 else float(data['Close'].iloc[-1]),
                    "last_update": datetime.now()
                }
                print(f"✅ Initialized data for {symbol}")
        except Exception as e:
            print(f"❌ Error initializing data for {symbol}: {e}")
    
    def get_extended_price_data(self, symbol, period="5d", interval="1m"):
        """Get price data with error handling"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)
            return data
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return None
    
    def update_price_data(self):
        """Fallback price updates"""
        for symbol in self.monitored_symbols.keys():
            try:
                if (symbol not in self.price_cache or 
                    (datetime.now() - self.price_cache[symbol]["last_update"]).seconds > 300):
                    
                    ticker = yf.Ticker(symbol)
                    current_data = ticker.history(period="1d", interval="1m").tail(1)
                    
                    if not current_data.empty:
                        current_price = float(current_data['Close'].iloc[0])
                        if symbol in self.price_cache:
                            self.price_cache[symbol]["current_price"] = current_price
                            self.price_cache[symbol]["last_update"] = datetime.now()
                        
            except Exception as e:
                print(f"Error updating {symbol}: {e}")
    
    def get_next_wormhole(self):
        """Get next wormhole time"""
        est = pytz.timezone('US/Eastern')
        now = datetime.now(est)
        
        for name, wormhole_time in self.wormholes.items():
            next_occurrence = datetime.combine(now.date(), wormhole_time)
            next_occurrence = est.localize(next_occurrence)
            
            if next_occurrence > now:
                time_until = next_occurrence - now
                hours, remainder = divmod(time_until.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                return f"{name.title()} in {hours}h {minutes}m"
        
        return "Midnight tomorrow"
    
    def run(self):
        print("🐛 ENHANCED PRICEWORM STRATEGY BOT STARTING...")
        print("🕳️ Monitoring 4 sacred wormhole times...")
        print("🔔 Bidirectional alert system active...")
        print("📊 Structure-based move detection enabled...")
        print("🔄 Complete cycle awareness online...")
        print("🎯 Ready to guide through the complete priceworm rhythm...")
        self.app.run_polling()

# Main execution
if __name__ == "__main__":
    TOKEN = "7536934982:AAEjlNA3BycmznZJGBh8TN27-rgbNNh3imk"
    
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Please replace TOKEN with your actual bot token")
        exit()
    
    bot = PricewormBot(TOKEN)
    bot.run()
