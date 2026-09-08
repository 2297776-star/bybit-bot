import os
import time
import threading
import telebot
import requests
import pandas as pd
import schedule

TOKEN = os.environ.get("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

active_chats = set()
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "NEARUSDT", "ADAUSDT"]

def fetch_kline_data(symbol, interval="1", limit=100):
    mexc_interval = "1m" if interval == "1" else "5m"
    url = f"https://api.mexc.com/api/v3/klines?symbol={symbol}&interval={mexc_interval}&limit={limit}"
    try:
        response = requests.get(url).json()
        if isinstance(response, list) and len(response) > 0:
            df = pd.DataFrame(response, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'quote_volume', 'trades'])
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)
            return df
    except Exception as e:
        print(f"Error fetching data from MEXC for {symbol}: {e}")
    return None

def analyze_ict_indigo(symbol):
    df = fetch_kline_data(symbol)
    if df is None or len(df) < 50:
        print(f"[{symbol}] Data not enough.")
        return None

    df['body_high'] = df[['open', 'close']].max(axis=1)
    df['body_low'] = df[['open', 'close']].min(axis=1)

    df['pivot_low'] = df['low'].rolling(window=7, center=True).min()
    df['is_pivot_low'] = df['low'] == df['pivot_low']
    df['ssl'] = df['low'].where(df['is_pivot_low']).ffill()

    df['pivot_high'] = df['high'].rolling(window=7, center=True).max()
    df['is_pivot_high'] = df['high'] == df['pivot_high']
    df['bsl'] = df['high'].where(df['is_pivot_high']).ffill()

    df['bullStopRun'] = df['low'] < df['ssl'].shift(1)
    df['bearStopRun'] = df['high'] > df['bsl'].shift(1)

    df['bullPositiveVI'] = (df['body_high'] < df['body_low'].shift(1)) & (df['close'] < df['open'])
    df['bearPositiveVI'] = (df['body_low'] > df['body_high'].shift(1)) & (df['close'] > df['open'])

    df['bullCandidate'] = df['bullStopRun'] & df['bullPositiveVI']
    df['bearCandidate'] = df['bearStopRun'] & df['bearPositiveVI']

    df['bullConfirmed'] = df['bullCandidate'].shift(1) & (df['close'] > df['high'].shift(1))
    df['bearConfirmed'] = df['bearCandidate'].shift(1) & (df['close'] < df['low'].shift(1))

    last_closed = df.iloc[-2]
    
    print(f"Check {symbol} (MEXC 1m) -> Price: {last_closed['close']} | BullConf: {last_closed['bullConfirmed']} | BearConf: {last_closed['bearConfirmed']}")

    if last_closed['bullConfirmed']:
        return f"🟢 **سیگنال خرید (LONG)**\nنماد: {symbol}\nصرافی: MEXC\nتایم‌فریم: ۱ دقیقه\nاستراتژی: ICT Indigo Entry\nقیمت ورود: {last_closed['close']}"
    elif last_closed['bearConfirmed']:
        return f"🔴 **سیگنال فروش (SHORT)**\nنماد: {symbol}\nصرافی: MEXC\nتایم‌فریم: ۱ دقیقه\nاستراتژی: ICT Indigo Entry\nقیمت ورود: {last_closed['close']}"
    
    return None

def check_all_markets():
    if not active_chats:
        print("No active chats registered yet.")
        return
    for symbol in SYMBOLS:
        signal = analyze_ict_indigo(symbol)
        if signal:
            for chat in active_chats:
                try:
                    bot.send_message(chat, signal, parse_mode="Markdown")
                except Exception as e:
                    print(f"Error sending message: {e}")

def run_scheduler():
    schedule.every(1).minute.do(check_all_markets)
    while True:
        schedule.run_pending()
        time.sleep(1)

@bot.message_handler(commands=['start'])
def start_bot(message):
    chat_id = message.chat.id
    active_chats.add(chat_id)
    bot.reply_to(message, "✅ ربات تحلیل‌گر ICT (روی صرافی MEXC و تایم‌فریم ۱ دقیقه بدون فیلتر زمانی) فعال شد.")

if __name__ == "__main__":
    print("Bot is starting with MEXC API (1m)...")
    threading.Thread(target=run_scheduler, daemon=True).start()
    bot.infinity_polling()
