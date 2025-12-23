import ccxt.async_support as ccxt
import pandas as pd
import asyncio
import os
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ===== CONFIGURATION =====
BINANCE_API_KEY = os.getenv("BINANCE_KEY", "UuTdZGp7331MhmnoukbkDW3VtF6Z9hnHMG3b75dWavAlG9e1zNbv2lBrjHkMqMpl")
BINANCE_SECRET = os.getenv("BINANCE_SECRET", "6Rs8ef3mZarvB8I6J2ewSCZwYmmohyyUVE4020AzsqzGoQt6WNXdTwqN1jZwh2i0")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "8488789199:AAGDbx-hu2993dG5O6LJEiSN0nEpFWuVWwk")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5665906172")

SYMBOL = "BTC/USDT"
POSITION_SIZE = 0.001 
# HFT Specifics
VOLATILITY_THRESHOLD = 0.00015 # 0.015% change in 1 second to trigger
PROFIT_TARGET = 0.0005        # 0.05% profit target per scalp
STOP_LOSS = 0.0003            # 0.03% stop loss

exchange = ccxt.binance({
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})
exchange.set_sandbox_mode(True)

bot_state = {"last_price": 0.0, "trades_today": 0, "active_trade": None}

# ===== TELEGRAM COMMANDS =====
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (f"⚡ <b>HFT Status (1s)</b>\n"
           f"Price: ${bot_state['last_price']:,.2f}\n"
           f"Trades Today: {bot_state['trades_today']}\n"
           f"Active Position: {bot_state['active_trade']}")
    await update.message.reply_text(msg, parse_mode='HTML')

# ===== HFT TRADING LOGIC =====
async def execute_hft_trade(side, price, application):
    try:
        if side == 'BUY':
            order = await exchange.create_market_buy_order(SYMBOL, POSITION_SIZE)
            bot_state['active_trade'] = price
        else:
            order = await exchange.create_market_sell_order(SYMBOL, POSITION_SIZE)
            bot_state['active_trade'] = None
        
        bot_state['trades_today'] += 1
        msg = f"⚡ <b>HFT {side}</b> at ${price:,.2f}"
        await application.bot.send_message(TELEGRAM_CHAT_ID, msg, parse_mode='HTML')
    except Exception as e:
        print(f"Trade Error: {e}")

async def hft_loop(application):
    print("HFT 1s Loop Started...")
    prev_price = 0.0
    
    while True:
        try:
            # 1. Fetch Ticker (Fastest data point)
            ticker = await exchange.fetch_ticker(SYMBOL)
            curr_price = ticker['last']
            bot_state['last_price'] = curr_price

            if prev_price > 0:
                # 2. Calculate 1-second price change
                change = (curr_price - prev_price) / prev_price

                # 3. Strategy: Momentum Burst
                # If price jumps up fast and we have no position -> BUY
                if change > VOLATILITY_THRESHOLD and not bot_state['active_trade']:
                    await execute_hft_trade('BUY', curr_price, application)

                # 4. Strategy: Exit Logic (Take Profit / Stop Loss)
                elif bot_state['active_trade']:
                    entry = bot_state['active_trade']
                    profit_pct = (curr_price - entry) / entry
                    
                    if profit_pct >= PROFIT_TARGET or profit_pct <= -STOP_LOSS:
                        await execute_hft_trade('SELL', curr_price, application)

            prev_price = curr_price
            # No sleep or very minimal sleep for HFT
            await asyncio.sleep(1) 

        except Exception as e:
            await asyncio.sleep(1)

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("status", status_command))
    
    loop = asyncio.get_event_loop()
    loop.create_task(hft_loop(application))
    
    print("HFT Bot Online...")
    application.run_polling()
