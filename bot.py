import os
import time
import threading
import telebot
import requests
import pandas as pd
import numpy as np
import schedule

TOKEN = os.environ.get("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

active_chats = set()
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "NEARUSDT", "ADAUSDT"]

def fetch_kline_data(symbol, interval="1", limit=300):
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
    df = fetch_kline_data(symbol, interval="1", limit=300)
    if df is None or len(df) < 50:
        print(f"[{symbol}] Data not enough.")
        return None

    df['body_high'] = df[['open', 'close']].max(axis=1)
    df['body_low'] = df[['open', 'close']].min(axis=1)

    # 1. پیاده‌سازی دقیق ta.pivotlow و ta.pivothigh مطابق با Pine Script (Swing Length = 3)
    swing_length = 3
    n = len(df)
    ssl_list = [np.nan] * n
    bsl_list = [np.nan] * n
    curr_sl = np.nan
    curr_sh = np.nan

    for i in range(2 * swing_length, n):
        p_idx = i - swing_length
        p_low = df['low'].iloc[p_idx]
        p_high = df['high'].iloc[p_idx]

        left_lows = df['low'].iloc[p_idx - swing_length : p_idx]
        right_lows = df['low'].iloc[p_idx + 1 : i + 1]

        left_highs = df['high'].iloc[p_idx - swing_length : p_idx]
        right_highs = df['high'].iloc[p_idx + 1 : i + 1]

        if (p_low < left_lows).all() and (p_low < right_lows).all():
            curr_sl = p_low
        if (p_high > left_highs).all() and (p_high > right_highs).all():
            curr_sh = p_high

        ssl_list[i] = curr_sl
        bsl_list[i] = curr_sh

    df['ssl'] = ssl_list
    df['bsl'] = bsl_list

    # 2. شکار نقدینگی (Stop Run)
    df['sellSideRun'] = df['low'] < df['ssl'].shift(1)
    df['buySideRun'] = df['high'] > df['bsl'].shift(1)

    # 3. گپ حجمی (Volume Imbalance) - ترکیب حالت Positive و Raw برای محدودیت کمتر
    df['bullPositiveVI'] = df['body_high'] < df['body_low'].shift(1)
    df['bearPositiveVI'] = df['body_low'] > df['body_high'].shift(1)
    
    df['bullRawVI'] = df['close'].shift(1) > df['open']
    df['bearRawVI'] = df['open'] > df['close'].shift(1)

    df['bullVI'] = df['bullPositiveVI'] | df['bullRawVI']
    df['bearVI'] = df['bearPositiveVI'] | df['bearRawVI']

    # 4. کاندید ستاپ (Candidate)
    df['bullCandidate'] = df['sellSideRun'] & (df['close'] < df['open']) & df['bullVI']
    df['bearCandidate'] = df['buySideRun'] & (df['close'] > df['open']) & df['bearVI']

    # 5. تاییدیه ستاپ (Confirmation)
    df['bullConfirmed'] = df['bullCandidate'].shift(1) & (df['close'] > df['high'].shift(1))
    df['bearConfirmed'] = df['bearCandidate'].shift(1) & (df['close'] < df['low'].shift(1))

    last_closed = df.iloc[-2]

    # لاگ دقیق جهت بررسی گام به گام
    print(f"[{symbol} 1m] Price: {last_closed['close']} | SSL: {last_closed['ssl']} | BSL: {last_closed['bsl']} | Candidate: {last_closed['bullCandidate'] or last_closed['bearCandidate']} | Confirmed: {last_closed['bullConfirmed'] or last_closed['bearConfirmed']}")

    if last_closed['bullConfirmed']:
        return f"🟢 **سیگنال خرید (LONG)**\nنماد: {symbol}\nصرافی: MEXC\nتایم‌فریم: ۱ دقیقه\nاستراتژی: ICT Indigo\nقیمت ورود: {last_closed['close']}"
    elif last_closed['bearConfirmed']:
        return f"🔴 **سیگنال فروش (SHORT)**\nنماد: {symbol}\nصرافی: MEXC\nتایم‌فریم: ۱ دقیقه\nاستراتژی: ICT Indigo\nقیمت ورود: {last_closed['close']}"

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
    bot.reply_to(message, "✅ ربات تحلیل‌گر ICT Indigo (مستقیم با مکسی و الگوریتم دقیق) فعال شد.")

if __name__ == "__main__":
    print("Bot is starting with precise ICT Indigo logic...")
    threading.Thread(target=run_scheduler, daemon=True).start()
    bot.infinity_polling()
