from abc import ABC, abstractmethod
from typing import List
import pandas as pd

class DataProvider(ABC):
    @abstractmethod
    def get_bars(self, symbols: List[str], start: str, end: str, resolution: str) -> pd.DataFrame:
        """
        Return raw OHLCV bars as a DataFrame with MultiIndex ROWS:
            index.names == ['timestamp','symbol']
            columns == ['open','high','low','close','volume']
        Clipped to [start,end]. No indicators here.
        """
        pass
