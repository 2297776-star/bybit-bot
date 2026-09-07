import os
import telebot
import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

def get_bybit_price(symbol):
    symbol = symbol.upper().strip()
    url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}USDT"
    try:
        response = requests.get(url).json()
        if response['retCode'] == 0 and response['result']['list']:
            price = response['result']['list'][0]['lastPrice']
            return f"💰 قیمت {symbol}: {price} دلار"
        else:
            return "❌ نماد پیدا نشد (مثال: BTC)."
    except Exception:
        return "⚠️ خطا در ارتباط با بای‌بیت."

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "سلام! نماد ارز را بفرست (مثلاً BTC):")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    bot.reply_to(message, get_bybit_price(message.text))

print("Bot is starting...")
bot.infinity_polling()
