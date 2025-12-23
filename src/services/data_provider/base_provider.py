from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List
import pandas as pd


class BaseDataProvider(ABC):

    @abstractmethod
    async def get_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        bar_size: timedelta = timedelta(days=1),
    ) -> pd.DataFrame:
        """
        Fetch historical market data.

        Args:
            symbols: List of ticker symbols
            start_date: Start datetime (inclusive)
            end_date: End datetime (inclusive)
            bar_size: Bar duration

        Returns:
            pandas DataFrame with:
              - DatetimeIndex
              - MultiIndex columns (symbol, field)
        """
        raise NotImplementedError
