from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd


class Database:
    def __init__(self, base_path=None):
        if base_path is None:
            # Default to root-level data/ directory
            base_path = Path(__file__).parent.parent.parent / "data"
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.base_path / "market_data.db"
        self._init_database()
    
    def _init_database(self):
        with duckdb.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_bars (
                    symbol VARCHAR NOT NULL,
                    date DATE NOT NULL,
                    open DOUBLE NOT NULL,
                    high DOUBLE NOT NULL,
                    low DOUBLE NOT NULL,
                    close DOUBLE NOT NULL,
                    volume BIGINT NOT NULL,
                    PRIMARY KEY (symbol, date)
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON daily_bars(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON daily_bars(date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_date ON daily_bars(symbol, date)")
    
    def save_daily_data(self, symbol, data):
        if data.empty:
            return
            
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Data must have DatetimeIndex")
        
        required_columns = {"open", "high", "low", "close", "volume"}
        if not required_columns.issubset(data.columns):
            raise ValueError(f"Data must contain columns: {required_columns}")
        
        df_to_insert = data.copy()
        df_to_insert = df_to_insert.reset_index()
        df_to_insert['symbol'] = symbol
        index_col = df_to_insert.columns[0]
        df_to_insert = df_to_insert.rename(columns={index_col: 'date'})
        df_to_insert = df_to_insert[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume']]
        
        with duckdb.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM daily_bars WHERE symbol = ?", [symbol])
            conn.execute("INSERT INTO daily_bars SELECT * FROM df_to_insert")
    
    def load_daily_data(self, symbol):
        with duckdb.connect(str(self.db_path)) as conn:
            result = conn.execute("""
                SELECT date, open, high, low, close, volume
                FROM daily_bars 
                WHERE symbol = ?
                ORDER BY date
            """, [symbol]).fetchdf()
        
        if result.empty:
            return None
        
        # Set date as index
        result['date'] = pd.to_datetime(result['date'])
        result = result.set_index('date')
        
        return result
    
    def load_data_range(self, symbol, start_date, end_date):
        with duckdb.connect(str(self.db_path)) as conn:
            result = conn.execute("""
                SELECT date, open, high, low, close, volume
                FROM daily_bars 
                WHERE symbol = ? 
                AND date >= ? 
                AND date <= ?
                ORDER BY date
            """, [symbol, start_date.date(), end_date.date()]).fetchdf()
        
        if result.empty:
            return None
        
        result['date'] = pd.to_datetime(result['date'])
        result = result.set_index('date')
        
        return result
    
    def symbol_exists(self, symbol):
        with duckdb.connect(str(self.db_path)) as conn:
            result = conn.execute("""
                SELECT COUNT(*) as count 
                FROM daily_bars 
                WHERE symbol = ?
            """, [symbol]).fetchone()
        
        return result[0] > 0 if result else False
    
    def get_available_symbols(self):
        with duckdb.connect(str(self.db_path)) as conn:
            result = conn.execute("""
                SELECT DISTINCT symbol 
                FROM daily_bars 
                ORDER BY symbol
            """).fetchall()
        
        return [row[0] for row in result]
    
    def get_date_range(self, symbol):
        with duckdb.connect(str(self.db_path)) as conn:
            result = conn.execute("""
                SELECT MIN(date) as start_date, MAX(date) as end_date
                FROM daily_bars 
                WHERE symbol = ?
            """, [symbol]).fetchone()
        
        if not result or not result[0]:
            return None
        
        return result[0], result[1]
    
    def export_to_parquet(self, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with duckdb.connect(str(self.db_path)) as conn:
            conn.execute(f"COPY daily_bars TO '{output_path}' (FORMAT PARQUET)")
    
    def get_stats(self):
        with duckdb.connect(str(self.db_path)) as conn:
            result = conn.execute("""
                SELECT 
                    COUNT(DISTINCT symbol) as total_symbols,
                    COUNT(*) as total_bars,
                    MIN(date) as earliest_date,
                    MAX(date) as latest_date
                FROM daily_bars
            """).fetchone()
        
        if not result:
            return {"total_symbols": 0, "total_bars": 0}
        
        return {
            "total_symbols": result[0],
            "total_bars": result[1], 
            "earliest_date": result[2],
            "latest_date": result[3],
            "db_path": str(self.db_path)
        }
