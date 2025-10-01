"""Data storage system for historical market data."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


class LocalStorage:
    """Local file-based storage for historical market data."""
    
    def __init__(self, base_path: str | Path):
        self.base_path = Path(base_path)
        self._ensure_directories()
        self._available_symbols = self._load_available_symbols()
    
    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        directories = [
            self.base_path / "daily",
            self.base_path / "metadata",
            self.base_path / "adjustments" / "splits",
            self.base_path / "adjustments" / "dividends",
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _load_available_symbols(self) -> Set[str]:
        """Load list of available symbols from metadata."""
        metadata_file = self.base_path / "metadata" / "available_symbols.json"
        
        if metadata_file.exists():
            with open(metadata_file, "r") as f:
                data = json.load(f)
                return set(data.get("symbols", []))
        
        return set()
    
    def _save_available_symbols(self) -> None:
        """Save list of available symbols to metadata."""
        metadata_file = self.base_path / "metadata" / "available_symbols.json"
        
        with open(metadata_file, "w") as f:
            json.dump({
                "symbols": list(self._available_symbols),
                "last_updated": datetime.now().isoformat()
            }, f, indent=2)
    
    def get_available_symbols(self) -> Set[str]:
        """Get set of available symbols."""
        return self._available_symbols.copy()
    
    def save_daily_data(self, symbol: str, data: pd.DataFrame, merge: bool = True) -> None:
        """Save daily OHLCV data for a symbol.
        
        Args:
            symbol: Symbol to save
            data: DataFrame with OHLCV data
            merge: If True, merge with existing data and remove duplicates
        """
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Data must have DatetimeIndex")
        
        # Ensure data has required columns
        required_columns = {"open", "high", "low", "close", "volume"}
        if not required_columns.issubset(data.columns):
            raise ValueError(f"Data must contain columns: {required_columns}")
        
        file_path = self.base_path / "daily" / f"{symbol}.parquet"
        
        # Merge with existing data if requested and file exists
        if merge and file_path.exists():
            existing_data = self.load_daily_data(symbol)
            if existing_data is not None and not existing_data.empty:
                # Combine old and new data
                combined = pd.concat([existing_data, data])
                # Remove duplicates, keeping the last occurrence (newest data)
                combined = combined[~combined.index.duplicated(keep='last')]
                # Sort by date
                combined = combined.sort_index()
                data = combined
        
        # Save to Parquet file
        table = pa.Table.from_pandas(data, preserve_index=True)
        pq.write_table(table, file_path)
        
        # Update available symbols
        self._available_symbols.add(symbol)
        self._save_available_symbols()
    
    def load_daily_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Load daily OHLCV data for a symbol."""
        if symbol not in self._available_symbols:
            return None
        
        file_path = self.base_path / "daily" / f"{symbol}.parquet"
        
        if not file_path.exists():
            return None
        
        # Load from Parquet file
        table = pq.read_table(file_path)
        df = table.to_pandas()
        
        # Ensure index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        return df
    
    def get_data_range(self, symbol: str) -> Optional[tuple[datetime, datetime]]:
        """Get the date range of available data for a symbol."""
        data = self.load_daily_data(symbol)
        if data is None or data.empty:
            return None
        
        start_date = data.index.min().to_pydatetime()
        end_date = data.index.max().to_pydatetime()
        
        return start_date, end_date
    
    def symbol_exists(self, symbol: str) -> bool:
        """Check if symbol data exists."""
        return symbol in self._available_symbols
    
    def remove_symbol(self, symbol: str) -> bool:
        """Remove all data for a symbol."""
        if symbol not in self._available_symbols:
            return False
        
        # Remove daily data file
        file_path = self.base_path / "daily" / f"{symbol}.parquet"
        if file_path.exists():
            file_path.unlink()
        
        # Update available symbols
        self._available_symbols.remove(symbol)
        self._save_available_symbols()
        
        return True
    
    def get_storage_info(self) -> Dict:
        """Get storage information and statistics."""
        total_symbols = len(self._available_symbols)
        
        # Calculate total storage size
        total_size = 0
        daily_dir = self.base_path / "daily"
        if daily_dir.exists():
            for file_path in daily_dir.glob("*.parquet"):
                total_size += file_path.stat().st_size
        
        return {
            "total_symbols": total_symbols,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "base_path": str(self.base_path),
            "available_symbols": sorted(list(self._available_symbols)),
        }
