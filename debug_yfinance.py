#!/usr/bin/env python3
"""Debug yfinance data structure."""

import yfinance as yf
import pandas as pd

# Test what yfinance actually returns
ticker = yf.Ticker("AAPL")
df = ticker.history(start='2023-01-01', end='2023-01-31', interval='1d', auto_adjust=True, actions=False)

print("Raw yfinance data:")
print(f"Type: {type(df)}")
print(f"Shape: {df.shape}")
print(f"Index type: {type(df.index)}")
print(f"Index name: {df.index.name}")
print(f"Columns: {list(df.columns)}")
print(f"Has 'date' column: {'date' in df.columns}")
print(f"Index timezone: {df.index.tz}")
print("\nFirst few rows:")
print(df.head())

# Test the normalization process step by step
print("\n" + "="*50)
print("NORMALIZATION STEPS:")

# Step 1: Check if DatetimeIndex
print(f"1. Is DatetimeIndex: {isinstance(df.index, pd.DatetimeIndex)}")

# Step 2: Timezone handling
if df.index.tz is not None:
    print(f"2. Has timezone: {df.index.tz}")
    df.index = df.index.tz_convert('UTC').tz_localize(None)
    print(f"   After timezone conversion: {df.index.tz}")

# Step 3: Column normalization
print(f"3. Original columns: {list(df.columns)}")
df.columns = df.columns.str.lower()
print(f"   After lowercase: {list(df.columns)}")

# Step 4: Required columns check
required_columns = ['open', 'high', 'low', 'close', 'volume']
missing_columns = [col for col in required_columns if col not in df.columns]
print(f"4. Missing columns: {missing_columns}")

if not missing_columns:
    print("✅ All required columns present!")
    df_final = df[required_columns].copy()
    print(f"Final shape: {df_final.shape}")
    print("Final data:")
    print(df_final.head())
else:
    print("❌ Missing required columns")