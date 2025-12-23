import ccxt.async_support as ccxt
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
MARGIN_USD = 1.0      # Your actual $1
LEVERAGE = 10         # 10x Leverage (Total position = $10)
VOLATILITY_THRESHOLD = 0.0002 
PROFIT_TARGET = 0.003 # 0.3% (Higher to cover Futures funding/fees)
STOP_LOSS = 0.002     

# Initialize exchange (Futures Mainnet)
exchange = ccxt.binance({
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'future'} # SWITCH TO FUTURES
})

bot_state = {"last_price": 0.0, "active_pos": None, "amount_btc": 0.0}

# ===== COMMANDS =====
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        balance = await exchange.fetch_balance()
        # In Futures, look at 'USDT' in the total wallet
        usdt = balance['total'].get('USDT', 0)
        await update.message.reply_text(f"💰 <b>Futures Balance</b>\nUSDT: ${usdt:,.2f}\nLeverage: {LEVERAGE}x", parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

# ===== TRADING LOGIC =====
async def setup_leverage():
    """Sets the leverage on Binance once at startup"""
    try:
        await exchange.set_leverage(LEVERAGE, SYMBOL)
        print(f"Leverage set to {LEVERAGE}x for {SYMBOL}")
    except Exception as e:
        print(f"Leverage Setup Error (Might already be set): {e}")

async def execute_futures_trade(side, price, application):
    if not MAINNET_CONFIRMATION: return
    try:
        # Calculate quantity: ($1 * 10 leverage) / current price
        quantity = (MARGIN_USD * LEVERAGE) / price
        
        if side == 'BUY':
            # Open Long
            order = await exchange.create_market_buy_order(SYMBOL, quantity)
            bot_state['active_pos'] = price
            bot_state['amount_btc'] = order['amount']
        else:
            # Close Long
            order = await exchange.create_market_sell_order(SYMBOL, bot_state['amount_btc'])
            bot_state['active_pos'] = None
        
        emoji = "📈" if side == 'BUY' else "🏁"
        await application.bot.send_message(TELEGRAM_CHAT_ID, f"{emoji} <b>FUTURES {side}</b> at ${price:,.2f}")
    except Exception as e:
        await application.bot.send_message(TELEGRAM_CHAT_ID, f"❌ <b>FUTURES ERROR:</b> {e}")

async def hft_loop(application):
    await setup_leverage()
    prev_price = 0.0
    while True:
        try:
            ticker = await exchange.fetch_ticker(SYMBOL)
            curr_price = ticker['last']
            bot_state['last_price'] = curr_price

            if prev_price > 0:
                change = (curr_price - prev_price) / prev_price

                # Entry: Momentum Long
                if change > VOLATILITY_THRESHOLD and not bot_state['active_pos']:
                    await execute_futures_trade('BUY', curr_price, application)

                # Exit: TP/SL
                elif bot_state['active_pos']:
                    entry = bot_state['active_pos']
                    profit_pct = (curr_price - entry) / entry
                    
                    if profit_pct >= PROFIT_TARGET or profit_pct <= -STOP_LOSS:
                        await execute_futures_trade('SELL', curr_price, application)

            prev_price = curr_price
            await asyncio.sleep(1) 
        except Exception as e:
            await asyncio.sleep(2)

async def main():
    if not MAINNET_CONFIRMATION:
        print("Set MAINNET_CONFIRMATION = True to trade.")
        return
    
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
