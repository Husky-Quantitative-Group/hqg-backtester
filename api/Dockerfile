FROM python:3.11-slim

WORKDIR /app

RUN pip install pandas numpy yfinance ta duckdb pyarrow pyyaml ib_insync matplotlib seaborn scipy

COPY backtester/ ./backtester/
COPY api/run_strategy.py ./run_strategy.py