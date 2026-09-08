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
    url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={interval}&limit={limit}"
    try:
        response = requests.get(url).json()
        if response['retCode'] == 0:
            df = pd.DataFrame(response['result']['list'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
            df = df.iloc[::-1].reset_index(drop=True)
            df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)
            return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
    return None

def analyze_ict_indigo(symbol):
    df = fetch_kline_data(symbol)
    if df is None or len(df) < 50:
        print(f"[{symbol}] Data not enough.")
        return None

    df['body_high'] = df[['open', 'close']].max(axis=1)
    df['body_low'] = df[['open', 'close']].min(axis=1)

    # 1. تشخیص نقدینگی (Swing Low / High)
    df['pivot_low'] = df['low'].rolling(window=7, center=True).min()
    df['is_pivot_low'] = df['low'] == df['pivot_low']
    df['ssl'] = df['low'].where(df['is_pivot_low']).ffill()

    df['pivot_high'] = df['high'].rolling(window=7, center=True).max()
    df['is_pivot_high'] = df['high'] == df['pivot_high']
    df['bsl'] = df['high'].where(df['is_pivot_high']).ffill()

    # 2. شکار نقدینگی (Stop Run)
    df['bullStopRun'] = df['low'] < df['ssl'].shift(1)
    df['bearStopRun'] = df['high'] > df['bsl'].shift(1)

    # 3. گپ حجمی (Volume Imbalance)
    df['bullPositiveVI'] = (df['body_high'] < df['body_low'].shift(1)) & (df['close'] < df['open'])
    df['bearPositiveVI'] = (df['body_low'] > df['body_high'].shift(1)) & (df['close'] > df['open'])

    # 4. کاندید شدن برای ستاپ (بدون فیلتر زمانی)
    df['bullCandidate'] = df['bullStopRun'] & df['bullPositiveVI']
    df['bearCandidate'] = df['bearStopRun'] & df['bearPositiveVI']

    # 5. تاییدیه ستاپ در کندل بعدی
    df['bullConfirmed'] = df['bullCandidate'].shift(1) & (df['close'] > df['high'].shift(1))
    df['bearConfirmed'] = df['bearCandidate'].shift(1) & (df['close'] < df['low'].shift(1))

    last_closed = df.iloc[-2]
    
    print(f"Check {symbol} (1m) -> Price: {last_closed['close']} | BullConf: {last_closed['bullConfirmed']} | BearConf: {last_closed['bearConfirmed']}")

    if last_closed['bullConfirmed']:
        return f"🟢 **سیگنال خرید (LONG)**\nنماد: {symbol}\nتایم‌فریم: ۱ دقیقه\nاستراتژی: ICT Indigo Entry\nقیمت ورود: {last_closed['close']}"
    elif last_closed['bearConfirmed']:
        return f"🔴 **سیگنال فروش (SHORT)**\nنماد: {symbol}\nتایم‌فریم: ۱ دقیقه\nاستراتژی: ICT Indigo Entry\nقیمت ورود: {last_closed['close']}"
    
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
    # تنظیم روی هر ۱ دقیقه
    schedule.every(1).minute.do(check_all_markets)
    while True:
        schedule.run_pending()
        time.sleep(1)

@bot.message_handler(commands=['start'])
def start_bot(message):
    chat_id = message.chat.id
    active_chats.add(chat_id)
    bot.reply_to(message, "✅ ربات تحلیل‌گر ICT روی تایم‌فریم ۱ دقیقه فعال شد.")

if __name__ == "__main__":
    print("Bot is starting and analyzer thread (1m) is running...")
    threading.Thread(target=run_scheduler, daemon=True).start()
    bot.infinity_polling()
