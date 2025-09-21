# Discord Stock Trading Bot

## Overview
This is a Discord bot that provides professional stock and cryptocurrency trading analysis using technical indicators. The bot automatically sends trading alerts to Discord channels and responds to manual commands for real-time analysis.

## Project Architecture
- **Language**: Python 3.12
- **Main Bot File**: `bot.py`
- **Configuration**: Uses `.env` file for Discord bot token
- **Dependencies**: discord.py, yfinance, ta (technical analysis), pandas, numpy, pytz, python-dotenv

## Features
- **Automated Trading Alerts**: Sends trading signals every 5 minutes for configured symbols
- **Multi-Timeframe Analysis**: Supports 1d, 1h, 5m intervals
- **Technical Indicators**: Uses EMA, RSI, Bollinger Bands, SMA, Fibonacci retracements
- **Market Hours Detection**: Respects trading hours for Indian (.NS) stocks
- **Manual Commands**: `!plan <symbol> [timeframe]` for on-demand analysis

## Current Configuration
- BHARATFORG.NS: 1-hour alerts in channel 1419206174439374929
- SOL-USD: 5-minute alerts in channel 1419280867322499165

## Bot Setup
The bot requires a Discord token set in the DISCORD_BOT_TOKEN environment variable. It uses advanced technical analysis to provide "pro-trader" style signals with confluence factors.

## Recent Changes
- 2025-09-21: Initial setup in Replit environment with all dependencies installed
- Bot configured to run as a continuous background service