from datetime import datetime
from typing import List

import pandas as pd
from datafeed import Config, DataFeed


class DataFeedAltProvider:
    """Adapter for raw alternative data from hqg-datafeed."""

    def __init__(self, feed: DataFeed | None = None):
        self.feed = feed or DataFeed(Config())

    def get_data(
        self,
        series: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, pd.DataFrame]:
        if not series:
            return {}

        market_data = self.feed.get_data(
            securities=[],
            alt_data=series,
            start=start_date,
            end=end_date,
        )
        return market_data.alt_data
