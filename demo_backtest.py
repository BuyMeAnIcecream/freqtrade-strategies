#!/usr/bin/env python3
"""
Simple Backtesting Demonstration
This script demonstrates how backtesting works with sample cryptocurrency data.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

def generate_sample_data(start_date='2024-01-01', days=365):
    """Generate sample cryptocurrency price data"""
    np.random.seed(42)  # For reproducible results
    
    # Create date range
    dates = pd.date_range(start=start_date, periods=days*24, freq='H')
    
    # Generate price data with some trend and volatility
    base_price = 50000  # Starting price for BTC
    trend = np.linspace(0, 0.3, len(dates))  # 30% upward trend over the year
    noise = np.random.normal(0, 0.02, len(dates))  # 2% daily volatility
    
    # Create price series
    price_changes = trend + noise
    prices = [base_price]
    
    for change in price_changes[1:]:
        new_price = prices[-1] * (1 + change)
        prices.append(new_price)
    
    # Create DataFrame
    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices,
        'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
        'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
        'close': prices,
        'volume': np.random.uniform(1000, 5000, len(dates))
    })
    
    return df

def calculate_indicators(df):
    """Calculate technical indicators"""
    # Simple Moving Averages
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df

def simple_strategy(df):
    """Simple moving average crossover strategy"""
    signals = []
    position = 0  # 0 = no position, 1 = long position
    trades = []
    balance = 10000  # Starting balance
    shares = 0
    
    for i in range(50, len(df)):  # Start after 50 periods to have enough data for indicators
        current_price = df.iloc[i]['close']
        sma_20 = df.iloc[i]['sma_20']
        sma_50 = df.iloc[i]['sma_50']
        rsi = df.iloc[i]['rsi']
        
        # Entry signal: SMA20 > SMA50 and RSI < 70
        if position == 0 and sma_20 > sma_50 and rsi < 70:
            position = 1
            shares = balance / current_price
            entry_price = current_price
            entry_time = df.iloc[i]['timestamp']
            print(f"BUY: {entry_time} at ${current_price:.2f}")
        
        # Exit signal: SMA20 < SMA50 or RSI > 80
        elif position == 1 and (sma_20 < sma_50 or rsi > 80):
            position = 0
            exit_price = current_price
            exit_time = df.iloc[i]['timestamp']
            profit = (exit_price - entry_price) / entry_price
            balance = shares * exit_price
            shares = 0
            
            trades.append({
                'entry_time': entry_time,
                'exit_time': exit_time,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'profit_pct': profit,
                'profit_usd': balance - 10000
            })
            
            print(f"SELL: {exit_time} at ${exit_price:.2f} | Profit: {profit:.2%}")
    
    return trades, balance

def analyze_results(trades, final_balance):
    """Analyze and display backtesting results"""
    if not trades:
        print("No trades were executed!")
        return
    
    df_trades = pd.DataFrame(trades)
    
    print("\n" + "="*60)
    print("BACKTESTING RESULTS")
    print("="*60)
    
    # Basic statistics
    total_trades = len(trades)
    winning_trades = len(df_trades[df_trades['profit_pct'] > 0])
    losing_trades = len(df_trades[df_trades['profit_pct'] < 0])
    
    win_rate = winning_trades / total_trades if total_trades > 0 else 0
    total_return = (final_balance - 10000) / 10000
    
    print(f"Total Trades: {total_trades}")
    print(f"Winning Trades: {winning_trades}")
    print(f"Losing Trades: {losing_trades}")
    print(f"Win Rate: {win_rate:.2%}")
    print(f"Total Return: {total_return:.2%}")
    print(f"Final Balance: ${final_balance:.2f}")
    
    if total_trades > 0:
        avg_profit = df_trades['profit_pct'].mean()
        max_profit = df_trades['profit_pct'].max()
        max_loss = df_trades['profit_pct'].min()
        
        print(f"Average Trade: {avg_profit:.2%}")
        print(f"Best Trade: {max_profit:.2%}")
        print(f"Worst Trade: {max_loss:.2%}")
    
    return df_trades

def plot_results(df, trades):
    """Plot the price data and trade signals"""
    plt.figure(figsize=(15, 10))
    
    # Plot 1: Price and Moving Averages
    plt.subplot(2, 1, 1)
    plt.plot(df['timestamp'], df['close'], label='Price', alpha=0.7)
    plt.plot(df['timestamp'], df['sma_20'], label='SMA 20', alpha=0.8)
    plt.plot(df['timestamp'], df['sma_50'], label='SMA 50', alpha=0.8)
    
    # Mark buy and sell points
    for trade in trades:
        plt.scatter(trade['entry_time'], trade['entry_price'], 
                   color='green', marker='^', s=100, label='Buy' if trade == trades[0] else "")
        plt.scatter(trade['exit_time'], trade['exit_price'], 
                   color='red', marker='v', s=100, label='Sell' if trade == trades[0] else "")
    
    plt.title('Price Chart with Moving Averages and Trade Signals')
    plt.xlabel('Date')
    plt.ylabel('Price ($)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Plot 2: RSI
    plt.subplot(2, 1, 2)
    plt.plot(df['timestamp'], df['rsi'], label='RSI', color='purple')
    plt.axhline(y=70, color='r', linestyle='--', alpha=0.7, label='Overbought (70)')
    plt.axhline(y=30, color='g', linestyle='--', alpha=0.7, label='Oversold (30)')
    plt.title('RSI Indicator')
    plt.xlabel('Date')
    plt.ylabel('RSI')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('backtest_results.png', dpi=300, bbox_inches='tight')
    plt.show()

def main():
    """Main function to run the backtesting demonstration"""
    print("Starting Simple Backtesting Demonstration")
    print("="*50)
    
    # Generate sample data
    print("Generating sample cryptocurrency data...")
    df = generate_sample_data()
    
    # Calculate indicators
    print("Calculating technical indicators...")
    df = calculate_indicators(df)
    
    # Run strategy
    print("Running trading strategy...")
    trades, final_balance = simple_strategy(df)
    
    # Analyze results
    df_trades = analyze_results(trades, final_balance)
    
    # Plot results
    if trades:
        print("\nGenerating plots...")
        plot_results(df, trades)
        print("Plot saved as 'backtest_results.png'")
    
    print("\n" + "="*50)
    print("Backtesting demonstration completed!")
    print("="*50)

if __name__ == "__main__":
    main() 