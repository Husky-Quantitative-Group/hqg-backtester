from pathlib import Path
import pandas as pd


class Database:
    def __init__(self, base_path=None):
        if base_path is None:
            # Default to root-level data/ directory
            base_path = Path(__file__).parent.parent.parent / "data"
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_symbol_path(self, symbol):
        return self.base_path / f"{symbol}.parquet"
    
    def save_daily_data(self, symbol, data):
        if data.empty:
            return
        
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Data must have DatetimeIndex")
        
        required_columns = {"open", "high", "low", "close", "volume"}
        if not required_columns.issubset(data.columns):
            raise ValueError(f"Data must contain columns: {required_columns}")
        
        df = data[["open", "high", "low", "close", "volume"]].copy()
        df.to_parquet(self._get_symbol_path(symbol))
    
    def load_daily_data(self, symbol):
        path = self._get_symbol_path(symbol)
        if not path.exists():
            return None
        
        df = pd.read_parquet(path)
        return df if not df.empty else None
    
    def load_data_range(self, symbol, start_date, end_date):
        df = self.load_daily_data(symbol)
        if df is None:
            return None
        
        df = df[(df.index >= start_date) & (df.index <= end_date)]
        return df if not df.empty else None
    
    def symbol_exists(self, symbol):
        return self._get_symbol_path(symbol).exists()
    
    def get_available_symbols(self):
        return sorted([p.stem for p in self.base_path.glob("*.parquet")])
    
    def get_date_range(self, symbol):
        df = self.load_daily_data(symbol)
        if df is None or df.empty:
            return None
        return df.index.min(), df.index.max()
    
    def get_stats(self):
        symbols = self.get_available_symbols()
        total_bars = 0
        earliest = None
        latest = None
        
        for symbol in symbols:
            df = self.load_daily_data(symbol)
            if df is not None and not df.empty:
                start, end = df.index.min(), df.index.max()
                if earliest is None or start < earliest:
                    earliest = start
                if latest is None or end > latest:
                    latest = end
                total_bars += len(df)
        
        return {
            "total_symbols": len(symbols),
            "total_bars": total_bars,
            "earliest_date": earliest,
            "latest_date": latest,
            "data_path": str(self.base_path)
        }
