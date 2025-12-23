
import ccxt.async_support as ccxt
import pandas as pd
import asyncio
import os
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ===== CONFIGURATION =====
# SET TO TRUE ONLY WHEN READY TO TRADE REAL MONEY
MAINNET_CONFIRMATION = True

BINANCE_API_KEY = os.getenv("BINANCE_KEY", "0NLIHcV6lIWDuCakzAAUSE2mq6BrxmDNHCn6l0lCPgq7AAFWcPiqkz2Q9eTbW9Ye")
BINANCE_SECRET = os.getenv("BINANCE_SECRET", "5LVq1iHl5MRAS56SHsrMmx4wAqe1TvURAvNLrlUR4hGcru6F8CpMjRzJK8BqtNiF")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "8488789199:AAGDbx-hu2993dG5O6LJEiSN0nEpFWuVWwk")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5665906172")


SYMBOL = "BTC/USDT"
TRADE_AMOUNT_USDT = 10.0  # Binance minimum is usually $10 for Spot
VOLATILITY_THRESHOLD = 0.0002 # Slightly higher for real market noise
PROFIT_TARGET = 0.0025       # 0.25% (Covers 0.1% buy fee + 0.1% sell fee + profit)
STOP_LOSS = 0.0015           

# Initialize exchange (Mainnet)
exchange = ccxt.binance({
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

# IMPORTANT: No sandbox mode here!
if not MAINNET_CONFIRMATION:
    print("!!! WARNING: MAINNET_CONFIRMATION is False. Bot will not start. !!!")

bot_state = {"last_price": 0.0, "trades_today": 0, "active_trade_price": None, "btc_bought": 0.0}

# ===== COMMANDS =====
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        balance = await exchange.fetch_balance()
        usdt = balance['total'].get('USDT', 0)
        btc = balance['total'].get('BTC', 0)
        await update.message.reply_text(f"💰 <b>Real Balance</b>\nUSDT: ${usdt:,.2f}\nBTC: {btc:.6f}", parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

# ===== TRADING LOGIC =====
async def execute_real_trade(side, price, application):
    if not MAINNET_CONFIRMATION: return

    try:
        if side == 'BUY':
            # Calculate amount of BTC to buy for $10
            quantity = TRADE_AMOUNT_USDT / price
            order = await exchange.create_market_buy_order(SYMBOL, quantity)
            bot_state['active_trade_price'] = price
            bot_state['btc_bought'] = order['filled']
        else:
            # Sell the exact amount of BTC we bought
            order = await exchange.create_market_sell_order(SYMBOL, bot_state['btc_bought'])
            bot_state['active_trade_price'] = None
            bot_state['btc_bought'] = 0.0
        
        bot_state['trades_today'] += 1
        await application.bot.send_message(TELEGRAM_CHAT_ID, f"✅ <b>REAL {side}</b> at ${price:,.2f}")
    except Exception as e:
        await application.bot.send_message(TELEGRAM_CHAT_ID, f"❌ <b>EXECUTION ERROR:</b> {e}")

async def hft_loop(application):
    print("Real HFT Loop Active...")
    prev_price = 0.0
    
    while True:
        try:
            ticker = await exchange.fetch_ticker(SYMBOL)
            curr_price = ticker['last']
            bot_state['last_price'] = curr_price

            if prev_price > 0:
                change = (curr_price - prev_price) / prev_price

                # Entry: Momentum
                if change > VOLATILITY_THRESHOLD and not bot_state['active_trade_price']:
                    await execute_real_trade('BUY', curr_price, application)

                # Exit: TP/SL
                elif bot_state['active_trade_price']:
                    entry = bot_state['active_trade_price']
                    profit_pct = (curr_price - entry) / entry
                    
                    if profit_pct >= PROFIT_TARGET or profit_pct <= -STOP_LOSS:
                        await execute_real_trade('SELL', curr_price, application)

            prev_price = curr_price
            await asyncio.sleep(1) 
        except Exception as e:
            await asyncio.sleep(2)

async def main():
    if not MAINNET_CONFIRMATION: return
    
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("balance", balance_command))
    
    asyncio.create_task(hft_loop(application))
    
    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
