import os
import logging
import discord
from discord.ext import commands, tasks
import yfinance as yf
import ta
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from datetime import datetime
import pytz

# Load environment variables from a .env file
load_dotenv()

# ---------------- CONFIG ----------------
# It's better to get the token and handle the case where it's not found
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Check if the token is present before proceeding
if TOKEN is None:
    logging.error("❌ DISCORD_BOT_TOKEN environment variable is not set. Please set the token before running the bot.")
    exit()

# Each symbol is mapped to its alert channel and timeframe
# I've updated this to a dictionary of dictionaries for more flexibility
# You can now specify the timeframe for each symbol's alerts.
STOCK_CHANNELS = {
    "BHARATFORG.NS": {
        "channel_id": 1419206174439374929, 
        "timeframe": "1h"
    },
    "SOL-USD": {
        "channel_id": 1419280867322499165,
        "timeframe": "5m"
    }
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

logging.basicConfig(level=logging.INFO)

# ---------------- MARKET HOURS CHECK ----------------
def is_market_open(symbol: str):
    """
    Checks if the market is open for a given symbol.
    Returns True for non-Indian stocks/crypto, and checks for Indian stocks.
    """
    if symbol.endswith(".NS"):
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        # Check if it's a weekday (Monday=0 to Friday=4)
        if now.weekday() >= 5: # Saturday or Sunday
            return False
        # Check if the time is within market hours (9:15 AM to 3:30 PM IST)
        # Note: 3:30 PM is 15:30
        if now.time() >= datetime.strptime('09:15', '%H:%M').time() and now.time() <= datetime.strptime('15:30', '%H:%M').time():
            return True
        return False
    # Assume other markets are always "open" for the purpose of this bot
    # or handle them with specific logic if needed
    return True

# ---------------- ADVANCED ANALYSIS FUNCTIONS ----------------
def get_fib_levels(df):
    """
    Calculates Fibonacci retracement levels for the last major swing.
    Returns a dictionary of levels or None.
    """
    if df.empty:
        return None
    
    # Find recent swing high and low
    # Check for empty series before calling max/min
    if df["High"].iloc[-25:].empty or df["Low"].iloc[-25:].empty:
        return None
        
    swing_high = df["High"].iloc[-25:].max().item()
    swing_low = df["Low"].iloc[-25:].min().item()
    
    # Explicitly check for equality of scalar values
    if swing_high == swing_low:
        return None
    
    diff = swing_high - swing_low
    
    fib_levels = {
        '23.6%': swing_high - (diff * 0.236),
        '38.2%': swing_high - (diff * 0.382),
        '50%': swing_high - (diff * 0.5),
        '61.8%': swing_high - (diff * 0.618),
        '78.6%': swing_high - (diff * 0.786),
    }
    return fib_levels

# ---------------- ANALYSIS ----------------
def analyze_stock(symbol: str, timeframe: str = "1d"):
    """
    Analyzes a stock or crypto using a more selective "pro-trade" strategy.
    
    Args:
        symbol (str): The stock or crypto ticker symbol.
        timeframe (str): The interval for the data (e.g., "1d", "1h", "5m").
    
    Returns:
        tuple: (price, formatted_message) or (None, error_message).
    """
    try:
        # Use the specified timeframe for data download
        # Updated period to '60d' to support intraday intervals like '5m' and '1h'
        df = yf.download(symbol, period="60d", interval=timeframe, auto_adjust=True)
    except Exception as e:
        return None, f"❌ Error fetching data for {timeframe} timeframe: {e}"

    if df.empty:
        return None, "⚠️ No data available (market closed?)"
    
    # Ensure close prices are a 1-dimensional array
    close_prices = df["Close"].dropna().to_numpy().flatten()
    
    if close_prices.size == 0:
        return None, f"❌ Error: 'Close' price data for {symbol} is empty after cleaning."

    # Indicators
    df["EMA9"] = ta.trend.EMAIndicator(pd.Series(close_prices), window=9).ema_indicator()
    df["EMA21"] = ta.trend.EMAIndicator(pd.Series(close_prices), window=21).ema_indicator()
    df["RSI"] = ta.momentum.RSIIndicator(pd.Series(close_prices)).rsi()
    bb = ta.volatility.BollingerBands(pd.Series(close_prices))
    df["BB_high"] = bb.bollinger_hband()
    df["BB_low"] = bb.bollinger_lband()
    
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()

    try:
        price = df["Close"].iloc[-1].item()
        rsi = df["RSI"].iloc[-1].item()
        ema9 = df["EMA9"].iloc[-1].item()
        ema21 = df["EMA21"].iloc[-1].item()
        bb_high = bb.bollinger_hband().iloc[-1].item()
        bb_low = bb.bollinger_lband().iloc[-1].item()
        sma50 = df["SMA50"].iloc[-1].item()
        sma200 = df["SMA200"].iloc[-1].item()
    except (IndexError, AttributeError):
        return None, "❌ Error: Not enough data points to calculate indicators."

    # ----- Trade decision (More selective "Pro" signals) -----
    signal = "🤝 HOLD / WAIT (no confluence yet)"
    entry = price
    stop_loss = None
    take_profit = None
    confluence = []

    # Check for Golden/Death Cross
    # Added .item() to ensure scalar values for comparison
    sma50_prev = df['SMA50'].iloc[-2].item()
    sma200_prev = df['SMA200'].iloc[-2].item()
    if sma50 > sma200 and sma50_prev < sma200_prev:
        confluence.append("Golden Cross (Bullish)")
    elif sma50 < sma200 and sma50_prev > sma200_prev:
        confluence.append("Death Cross (Bearish)")

    # Check for Fibonacci Retracement
    fib_levels = get_fib_levels(df)
    if fib_levels:
        for level_name, level_price in fib_levels.items():
            # Check if current price is within a small percentage of a Fibonacci level
            if abs(price - level_price) / price < 0.005: # 0.5% tolerance
                confluence.append(f"Price at {level_name} Fib Level")

    # Pro-Buy Signal: Strong Uptrend (EMA9 > EMA21), Oversold RSI, and price near Lower Bollinger Band
    if ema9 > ema21 and rsi < 35 and price <= bb_low:
        signal = "✅ PRO-BUY Setup"
        stop_loss = price * 0.98  # 2% below
        take_profit = price * 1.04  # 4% above
        confluence.extend(["RSI oversold", "Price at Lower BB", "EMA9 > EMA21"])

    # Pro-Sell Signal: Strong Downtrend (EMA9 < EMA21), Overbought RSI, and price near Upper Bollinger Band
    elif ema9 < ema21 and rsi > 65 and price >= bb_high:
        signal = "❌ PRO-SELL Setup"
        stop_loss = price * 1.02  # 2% above
        take_profit = price * 0.96  # 4% below
        confluence.extend(["RSI overbought", "Price at Upper BB", "EMA9 < EMA21"])

    # Only return a message if a strong signal is found
    if not confluence:
        return None, "No strong signal"
    
    msg = f"""
📊 {symbol} Trade Plan ({timeframe})
Price: {price:.2f}

Signal: {signal}
Entry: {entry:.2f}
Stop Loss: {'—' if stop_loss is None else f'{stop_loss:.2f}'}
Take Profit: {'—' if take_profit is None else f'{take_profit:.2f}'}

Confluence: {", ".join(confluence) if confluence else "No strong confluence"}
"""
    return price, msg

# ---------------- BOT EVENTS ----------------
@bot.event
async def on_ready():
    logging.info(f"✅ Logged in as {bot.user}")
    stock_alert.start()

# ---------------- TASK LOOP ----------------
@tasks.loop(minutes=5)
async def stock_alert():
    """Send pro-trader alerts every 5 minutes."""
    for symbol, config in STOCK_CHANNELS.items():
        channel_id = config["channel_id"]
        timeframe = config["timeframe"]
        
        if not is_market_open(symbol):
            logging.info(f"Market for {symbol} is closed. Skipping alert.")
            continue
            
        channel = bot.get_channel(channel_id)
        if channel is None:
            logging.warning(f"Channel {channel_id} not found for {symbol}")
            continue

        try:
            price, msg = analyze_stock(symbol, timeframe=timeframe)
            if msg is not None:
                embed = discord.Embed(
                    title=f"📈 {symbol} Trading Alert",
                    description=msg,
                    color=discord.Color.blue()
                )
                await channel.send(embed=embed)
                logging.info(f"Sent trade plan for {symbol}")
            else:
                logging.info(f"No strong signal for {symbol}. Skipping alert.")
        except Exception as e:
            logging.exception(f"Error in stock_alert for {symbol}: {e}")

# ---------------- MANUAL COMMAND ----------------
@bot.command()
async def plan(ctx, symbol: str, timeframe: str = "1d"):
    """Get live trade plan for a stock/crypto manually."""
    try:
        price, msg = analyze_stock(symbol, timeframe=timeframe)
        if msg is not None:
            embed = discord.Embed(
                title=f"📊 {symbol} Trade Plan ({timeframe})",
                description=msg,
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"➖ No strong signal for {symbol} on {timeframe} at the moment.")
    except Exception as e:
        await ctx.send(f"❌ Error analyzing {symbol}")
        logging.exception(e)

# ---------------- RUN ----------------
bot.run(TOKEN)
