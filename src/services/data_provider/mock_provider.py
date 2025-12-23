import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict
from .base_provider import BaseDataProvider


class MockDataProvider(BaseDataProvider):
    """ Mock data provider for testing. Generates synthetic price data. """
    
    def __init__(self, initial_prices: Dict[str, float] = None):
        super().__init__()
        self.initial_prices = initial_prices or {}
    
    async def get_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        bar_size: timedelta = timedelta(days=1)
    ) -> pd.DataFrame:
        """Generate mock data."""
        import numpy as np
        
        # gen date range
        periods = int((end_date - start_date) / bar_size) + 1
        dates = pd.date_range(start=start_date, periods=periods, freq=bar_size)
        
        data = pd.DataFrame(index=dates)
        
        for symbol in symbols:
            initial_price = self.initial_prices.get(symbol, 100.0)
            
            # random walk with slight upward drift
            returns = np.random.normal(0.0005, 0.02, len(dates))
            prices = initial_price * np.exp(np.cumsum(returns))
            
            data[(symbol, 'close')] = prices
            data[(symbol, 'open')] = prices * (1 + np.random.normal(0, 0.001, len(dates)))
            data[(symbol, 'high')] = prices * (1 + np.abs(np.random.normal(0, 0.01, len(dates))))
            data[(symbol, 'low')] = prices * (1 - np.abs(np.random.normal(0, 0.01, len(dates))))
            data[(symbol, 'volume')] = np.random.randint(1000000, 10000000, len(dates))
        
        return data