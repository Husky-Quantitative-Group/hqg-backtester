from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd


class BaseDataSource(ABC):
    @abstractmethod
    def pull_historical_data(self, symbol, start_date, end_date, **kwargs):
        pass
    
    @abstractmethod
    def is_available(self):
        pass
    
    def normalize_dataframe(self, df):
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'date' in df.columns:
                df = df.set_index('date')
            elif 'timestamp' in df.columns:
                df = df.set_index('timestamp')
            else:
                df.index = pd.to_datetime(df.index)
        
        if df.index.tz is not None:
            df.index = df.index.tz_convert('UTC').tz_localize(None)
        
        df.columns = df.columns.str.lower()
        
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        df = df[required_columns].copy()
        
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)
        df['volume'] = df['volume'].astype(int)
        
        df = df[~df.index.duplicated(keep='last')]
        df = df.sort_index()
        df = df.dropna()
        
        return df
