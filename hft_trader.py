import ccxt.async_support as ccxt
import pandas as pd
import asyncio
import os
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ===== CONFIGURATION =====
BINANCE_API_KEY = os.getenv("BINANCE_KEY", "0NLIHcV6lIWDuCakzAAUSE2mq6BrxmDNHCn6l0lCPgq7AAFWcPiqkz2Q9eTbW9Ye")
BINANCE_SECRET = os.getenv("BINANCE_SECRET", "5LVq1iHl5MRAS56SHsrMmx4wAqe1TvURAvNLrlUR4hGcru6F8CpMjRzJK8BqtNiF")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "8488789199:AAGDbx-hu2993dG5O6LJEiSN0nEpFWuVWwk")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5665906172")

SYMBOL = "BTC/USDT"
POSITION_SIZE = 0.001 
VOLATILITY_THRESHOLD = 0.00015 
PROFIT_TARGET = 0.0005        
STOP_LOSS = 0.0003            

# Initialize exchange
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
           f"Active Position: {bot_state['active_trade'] if bot_state['active_trade'] else 'None'}")
    await update.message.reply_text(msg, parse_mode='HTML')

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """FIX: Added balance command to check Testnet funds"""
    try:
        balance = await exchange.fetch_balance()
        usdt = balance['total'].get('USDT', 0)
        btc = balance['total'].get('BTC', 0)
        msg = (f"💰 <b>Testnet Balance</b>\n"
               f"━━━━━━━━━━━━━━\n"
               f"<b>USDT:</b> ${usdt:,.2f}\n"
               f"<b>BTC:</b> {btc:.6f}")
        await update.message.reply_text(msg, parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"❌ Balance Error: {str(e)[:100]}")

# ===== HFT TRADING LOGIC =====
async def execute_hft_trade(side, price, application):
    try:
        if side == 'BUY':
            # Real order on Testnet
            order = await exchange.create_market_buy_order(SYMBOL, POSITION_SIZE)
            bot_state['active_trade'] = price
        else:
            # Real order on Testnet
            order = await exchange.create_market_sell_order(SYMBOL, POSITION_SIZE)
            bot_state['active_trade'] = None
        
        bot_state['trades_today'] += 1
        emoji = "🚀" if side == 'BUY' else "🏁"
        msg = f"{emoji} <b>HFT {side}</b> at ${price:,.2f}"
        await application.bot.send_message(TELEGRAM_CHAT_ID, msg, parse_mode='HTML')
    except Exception as e:
        print(f"Trade Error: {e}")
        await application.bot.send_message(TELEGRAM_CHAT_ID, f"⚠️ Trade Failed: {str(e)[:50]}")

async def hft_loop(application):
    print("HFT 1s Loop Started...")
    prev_price = 0.0
    
    while True:
        try:
            ticker = await exchange.fetch_ticker(SYMBOL)
            curr_price = ticker['last']
            bot_state['last_price'] = curr_price

            if prev_price > 0:
                change = (curr_price - prev_price) / prev_price

                # Entry Logic
                if change > VOLATILITY_THRESHOLD and not bot_state['active_trade']:
                    await execute_hft_trade('BUY', curr_price, application)

                # Exit Logic
                elif bot_state['active_trade']:
                    entry = bot_state['active_trade']
                    profit_pct = (curr_price - entry) / entry
                    
                    if profit_pct >= PROFIT_TARGET or profit_pct <= -STOP_LOSS:
                        await execute_hft_trade('SELL', curr_price, application)

            prev_price = curr_price
            await asyncio.sleep(1) 

        except Exception as e:
            print(f"Loop error: {e}")
            await asyncio.sleep(1)

# ===== MODERN STARTUP =====
async def main():
    # 1. Build Application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # 2. Add Handlers
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("balance", balance_command))
    
    # 3. Start HFT Loop as a background task
    asyncio.create_task(hft_loop(application))
    
    # 4. Start Telegram Bot with conflict protection
    print("HFT Bot Online & Listening...")
    async with application:
        await application.initialize()
        await application.start()
        # drop_pending_updates=True avoids processing old commands on restart
        await application.updater.start_polling(drop_pending_updates=True)
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot shut down.")
