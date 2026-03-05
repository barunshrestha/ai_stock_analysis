"""
Stock Scanner and Technical Analysis Module
Fetches stock data and calculates technical indicators to identify trading setups
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json


def calculate_sma(data, window=20):
    """Calculate Simple Moving Average"""
    return data.rolling(window=window).mean()


def calculate_rsi(data, window=14):
    """Calculate Relative Strength Index (RSI)"""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_atr(high, low, close, window=14):
    """Calculate Average True Range (ATR)"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=window).mean()
    return atr


def fetch_stock_data(ticker, days=60):
    """Fetch stock data for the specified number of days"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 10)  # Add buffer for indicator calculations
        
        stock = yf.Ticker(ticker)
        hist_data = stock.history(start=start_date, end=end_date)
        
        if hist_data.empty:
            return None, "No data available for this ticker"
        
        return hist_data, None
    except Exception as e:
        return None, f"Error fetching data: {str(e)}"


def calculate_technical_indicators(hist_data):
    """Calculate all technical indicators"""
    if hist_data is None or hist_data.empty:
        return None, "No data available"
    
    try:
        # Calculate indicators
        hist_data['SMA_20'] = calculate_sma(hist_data['Close'], window=20)
        hist_data['RSI'] = calculate_rsi(hist_data['Close'], window=14)
        hist_data['ATR'] = calculate_atr(
            hist_data['High'], 
            hist_data['Low'], 
            hist_data['Close'], 
            window=14
        )
        
        # Get latest values
        latest = hist_data.iloc[-1]
        previous = hist_data.iloc[-2] if len(hist_data) > 1 else latest
        
        indicators = {
            'current_price': float(latest['Close']),
            'sma_20': float(latest['SMA_20']) if pd.notna(latest['SMA_20']) else None,
            'rsi': float(latest['RSI']) if pd.notna(latest['RSI']) else None,
            'atr': float(latest['ATR']) if pd.notna(latest['ATR']) else None,
            'high': float(latest['High']),
            'low': float(latest['Low']),
            'volume': float(latest['Volume']),
            'price_change_pct': float(((latest['Close'] - previous['Close']) / previous['Close']) * 100) if len(hist_data) > 1 else 0.0
        }
        
        return indicators, None
    except Exception as e:
        return None, f"Error calculating indicators: {str(e)}"


def identify_setup(indicators):
    """
    Identify trading setup based on technical criteria:
    - Price near 20-day SMA (within 2% range)
    - RSI between 40-60 (neutral-bullish zone)
    
    Returns setup status and details
    """
    if indicators is None:
        return False, "No indicators available"
    
    try:
        current_price = indicators['current_price']
        sma_20 = indicators['sma_20']
        rsi = indicators['rsi']
        atr = indicators['atr']
        
        setup_found = False
        setup_details = []
        
        # Check if price is near 20-day SMA (within 2% range)
        if sma_20 and current_price > 0:
            price_deviation = abs(current_price - sma_20) / sma_20 * 100
            near_sma = price_deviation <= 2.0
            
            if near_sma:
                setup_found = True
                setup_details.append(f"Price is near 20-day SMA ({price_deviation:.2f}% deviation)")
            else:
                setup_details.append(f"Price is {price_deviation:.2f}% away from 20-day SMA")
        
        # Check RSI condition (40-60 is neutral-bullish)
        if rsi is not None:
            if 40 <= rsi <= 60:
                setup_found = True
                setup_details.append(f"RSI is in neutral-bullish zone ({rsi:.2f})")
            else:
                setup_details.append(f"RSI is {rsi:.2f} (target: 40-60)")
        
        # Define terms
        definitions = {
            "20-day SMA": "Simple Moving Average over 20 days - shows the average price over the past 20 trading days, indicating the general price trend",
            "RSI (14)": "Relative Strength Index over 14 periods - momentum indicator that measures speed and magnitude of price changes. Values 40-60 indicate neutral to bullish momentum",
            "ATR": "Average True Range - measures market volatility by calculating the average range between high and low prices. Higher ATR means higher volatility",
            "Price near SMA": "Price within 2% of the 20-day SMA suggests the stock is trading near its recent average, potentially indicating a consolidation or reversal point",
            "Neutral-bullish RSI": "RSI between 40-60 suggests the stock is not overbought (above 70) or oversold (below 30), providing room for upward movement"
        }
        
        return setup_found, {
            'setup_detected': setup_found,
            'details': setup_details,
            'definitions': definitions,
            'indicators': indicators
        }
    except Exception as e:
        return False, f"Error identifying setup: {str(e)}"


def generate_trade_params(ticker, indicators, atr_multiplier=2.0):
    """
    Generate trade parameters for different timeframes
    
    Args:
        ticker: Stock ticker symbol
        indicators: Dictionary with technical indicators
        atr_multiplier: Multiplier for stop-loss (default: 2.0 means 2 * ATR)
    
    Returns:
        JSON object with 5 setups for different timeframes
    """
    if indicators is None or indicators.get('atr') is None:
        return None, "ATR not available for trade parameter calculation"
    
    try:
        entry_price = indicators['current_price']
        atr = indicators['atr']
        stop_loss_distance = atr * atr_multiplier
        
        # Calculate stop-loss
        stop_loss = entry_price - stop_loss_distance
        
        # Calculate risk per share
        risk_per_share = entry_price - stop_loss
        
        # Timeframes configuration
        timeframes = {
            "Intraday": {
                "duration": "Same day",
                "description": "Quick scalping opportunities, entry and exit within trading session"
            },
            "Swing (Short-term)": {
                "duration": "2-5 days",
                "description": "Short-term swing trades capturing momentum moves"
            },
            "Swing (Medium-term)": {
                "duration": "1-3 weeks",
                "description": "Medium-term swing trades for trend continuation"
            },
            "Position (Long-term)": {
                "duration": "1-3 months",
                "description": "Longer-term positions for major trend moves"
            },
            "Investment (Strategic)": {
                "duration": "3+ months",
                "description": "Strategic long-term positions based on fundamental and technical alignment"
            }
        }
        
        setups = []
        
        for timeframe_name, timeframe_info in timeframes.items():
            # Target 1: 1:1 Risk-to-Reward
            target1 = entry_price + risk_per_share
            
            # Target 2: 2:1 Risk-to-Reward
            target2 = entry_price + (risk_per_share * 2)
            
            setup = {
                "timeframe": timeframe_name,
                "duration": timeframe_info["duration"],
                "description": timeframe_info["description"],
                "entry": round(entry_price, 2),
                "stop_loss": round(stop_loss, 2),
                "target_1": round(target1, 2),
                "target_2": round(target2, 2),
                "risk_per_share": round(risk_per_share, 2),
                "reward_1": round(target1 - entry_price, 2),
                "reward_2": round(target2 - entry_price, 2),
                "risk_reward_1": "1:1",
                "risk_reward_2": "2:1",
                "stop_loss_pct": round((stop_loss_distance / entry_price) * 100, 2),
                "target_1_pct": round(((target1 - entry_price) / entry_price) * 100, 2),
                "target_2_pct": round(((target2 - entry_price) / entry_price) * 100, 2)
            }
            
            setups.append(setup)
        
        result = {
            "ticker": ticker,
            "generated_at": datetime.now().isoformat(),
            "entry_price": entry_price,
            "atr": atr,
            "atr_multiplier": atr_multiplier,
            "setups": setups
        }
        
        return result, None
        
    except Exception as e:
        return None, f"Error generating trade parameters: {str(e)}"


def scan_stock(ticker, days=60):
    """
    Complete stock scanning process
    
    Returns:
        (setup_info, trade_params, error)
    """
    # Fetch data
    hist_data, error = fetch_stock_data(ticker, days)
    if error:
        return None, None, error
    
    # Calculate indicators
    indicators, error = calculate_technical_indicators(hist_data)
    if error:
        return None, None, error
    
    # Identify setup
    setup_found, setup_info = identify_setup(indicators)
    
    # Generate trade parameters
    trade_params, error = generate_trade_params(ticker, indicators)
    if error:
        return setup_info, None, error
    
    return setup_info, trade_params, None

