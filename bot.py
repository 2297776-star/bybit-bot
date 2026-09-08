import schedule
import os
import time
import threading
import telebot
import requests
import pandas as pd
import numpy as np

TOKEN = os.environ.get("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

CHAT_FILE = "chats.txt"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "NEARUSDT", "ADAUSDT"]
last_sent_signals = {}

def load_chats():
    if os.path.exists(CHAT_FILE):
        with open(CHAT_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_chat(chat_id):
    chats = load_chats()
    if str(chat_id) not in chats:
        with open(CHAT_FILE, "a") as f:
            f.write(f"{chat_id}\n")

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
        return None

    df['body_high'] = df[['open', 'close']].max(axis=1)
    df['body_low'] = df[['open', 'close']].min(axis=1)

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

    df['sellSideRun'] = df['low'] < df['ssl'].shift(1)
    df['buySideRun'] = df['high'] > df['bsl'].shift(1)

    # درست شدن Positive VI — مقایسه بدنه‌ها
    df['bullPositiveVI'] = df['body_low'] > df['body_high'].shift(1)
    df['bearPositiveVI'] = df['body_high'] < df['body_low'].shift(1)

    df['bullRawVI'] = df['close'].shift(1) > df['open']
    df['bearRawVI'] = df['open'] > df['close'].shift(1)

    df['bullVI'] = df['bullPositiveVI'] | df['bullRawVI']
    df['bearVI'] = df['bearPositiveVI'] | df['bearRawVI']

    df['bullCandidate'] = df['sellSideRun'] & (df['close'] < df['open']) & df['bullVI']
    df['bearCandidate'] = df['buySideRun'] & (df['close'] > df['open']) & df['bearVI']

    df['bullConfirmed'] = df['bullCandidate'].shift(1) & (df['close'] > df['high'].shift(1))
    df['bearConfirmed'] = df['bearCandidate'].shift(1) & (df['close'] < df['low'].shift(1))

    # بررسی سه کندل آخر برای از دست نرفتن سیگنال تأییدشده
    for offset in [0, 1, 2]:
        idx = len(df) - 1 - offset
        candle = df.iloc[idx]
        candle_time = candle['timestamp']

        if candle['bullConfirmed']:
            if last_sent_signals.get(f"{symbol}_LONG") != candle_time:
                last_sent_signals[f"{symbol}_LONG"] = candle_time
                print(f"[{symbol} 1m] LONG confirmed at price {candle['close']}")
                return (f"🟢 **سیگنال خرید (LONG)**\n"
                        f"نماد: {symbol}\n"
                        f"صرافی: MEXC\n"
                        f"تایم‌فریم: ۱ دقیقه\n"
                        f"قیمت ورود: {candle['close']}")

        if candle['bearConfirmed']:
            if last_sent_signals.get(f"{symbol}_SHORT") != candle_time:
                last_sent_signals[f"{symbol}_SHORT"] = candle_time
def check_all_markets():
    active_chats = load_chats()
    if not active_chats:
        print("No active chats registered. Send /start to the bot.")
        return

    for symbol in SYMBOLS:
        signal = analyze_ict_indigo(symbol)
        if signal:
            for chat_id in active_chats:
                try:
                    bot.send_message(chat_id, signal, parse_mode="Markdown")
                except Exception as e:
                    print(f"Error sending to {chat_id}: {e}")

def run_scheduler():
    schedule.every(10).seconds.do(check_all_markets)
    while True:
        schedule.run_pending()
        time.sleep(1)

@bot.message_handler(commands=['start'])
def start_bot(message):
    save_chat(message.chat.id)
    bot.reply_to(message, "✅ ثبت‌نام شما انجام شد. سیگنال‌های ICT Indigo دریافت خواهند شد.")

if __name__ == "__main__":
    print("Bot is running with synchronized alert system...")
    threading.Thread(target=run_scheduler, daemon=True).start()
    bot.infinity_polling()



                
                print(f"[{symbol} 1m] SHORT confirmed at price {candle['close']}")
                return (f"🔴 **سیگنال فروش (SHORT)**\n"
                        f"نماد: {symbol}\n"
                        f"صرافی: MEXC\n"
                        f"تایم‌فریم: ۱ دقیقه\n"
                        f"قیمت ورود: {candle['close']}")
                

    return None
