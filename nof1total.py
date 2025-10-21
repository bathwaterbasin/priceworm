#!/usr/bin/env python3
"""
NOF1.AI ALPHA ARENA - REALIZED PROFIT TRACKER
Telegram-formatted output
"""

import requests
from datetime import datetime

HYPERLIQUID_API = "https://api.hyperliquid.xyz"

MODELS = {
    "DeepSeek": {
        "address": "0xc20ac4dc4188660cbf555448af52694ca62b0734",
        "initial_capital": 10000,
        "emoji": "🥇"
    },
    "Grok-4": {
        "address": "0x56d652e62998251b56c8398fb11fcfe464c08f84",
        "initial_capital": 10000,
        "emoji": "🥈"
    },
    "Claude": {
        "address": "0x59fa085d106541a834017b97060bcbbb0aa82869",
        "initial_capital": 10000,
        "emoji": "🥉"
    },
    "GPT-5": {
        "address": "0x67293d914eafb26878534571add81f6bd2d9fe06",
        "initial_capital": 10000,
        "emoji": "4️⃣"
    },
    "Gemini": {
        "address": "0x1b7a7d099a670256207a30dd0ae13d35f278010f",
        "initial_capital": 10000,
        "emoji": "5️⃣"
    },
    "Qwen3": {
        "address": "0x7a8fd8bba33e37361ca6b0cb4518a44681bad2f3",
        "initial_capital": 10000,
        "emoji": "6️⃣"
    }
}

def get_user_fills(wallet_address):
    """Get user's trading fills from Hyperliquid"""
    try:
        payload = {"type": "userFills", "user": wallet_address}
        response = requests.post(f"{HYPERLIQUID_API}/info", json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return None

def calculate_realized_pnl(fills):
    """Calculate total realized P&L from fills"""
    if not fills:
        return 0.0
    realized_pnl = 0.0
    try:
        for fill in fills:
            if "closedPnl" in fill:
                realized_pnl += float(fill["closedPnl"])
    except:
        pass
    return realized_pnl

def main():
    print("\n" + "="*90)
    print("🤖  NOF1.AI ALPHA ARENA")
    print("="*90)
    print(f"⏰  {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
    
    results = {}
    
    for model_name, wallet_info in MODELS.items():
        fills = get_user_fills(wallet_info['address'])
        
        if fills and isinstance(fills, list):
            realized_pnl = calculate_realized_pnl(fills)
            num_trades = len(fills)
            cash_out_value = wallet_info['initial_capital'] + realized_pnl
            return_pct = (realized_pnl / wallet_info['initial_capital'] * 100)
            
            results[model_name] = {
                "realized_pnl": realized_pnl,
                "return_pct": return_pct,
                "cash_out_value": cash_out_value,
                "num_trades": num_trades
            }
    
    # Display leaderboard
    print("="*90)
    print("📊 LEADERBOARD")
    print("="*90)
    print(f"{'Rank':<6} {'Model':<12} {'Cash Out':<14} {'P&L':<14} {'Return':<10} {'Trades':<8}")
    print("-"*90)
    
    sorted_results = sorted(results.items(), key=lambda x: x[1]['cash_out_value'], reverse=True)
    
    for rank, (model_name, data) in enumerate(sorted_results, 1):
        realized_pnl = data['realized_pnl']
        return_pct = data['return_pct']
        cash_out_value = data['cash_out_value']
        num_trades = data['num_trades']
        
        rank_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣"][min(rank-1, 5)]
        trend = "📈" if return_pct > 10 else "📗" if return_pct > 0 else "📘" if return_pct > -20 else "📉"
        
        print(f"{rank_emoji}  #{rank:<2} {model_name:<12} ${cash_out_value:>9,.0f}  ${realized_pnl:>9,.0f}  {return_pct:>+6.1f}%  {num_trades:>3}  {trend}")
    
    print("="*90)
    
    # Summary
    if results:
        total_combined = sum(data['cash_out_value'] for data in results.values())
        avg_return = sum(data['return_pct'] for data in results.values()) / len(results)
        
        print(f"\n💰 Total: ${total_combined:,.0f} | Avg Return: {avg_return:+.1f}%\n")
    
    print("="*90)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Make sure 'requests' is installed: pip install requests")
