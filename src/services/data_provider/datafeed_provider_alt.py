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
    ) -> pd.DataFrame:
        if not series:
            return pd.DataFrame(
                index=pd.DatetimeIndex([], name="date"),
                columns=pd.MultiIndex.from_tuples([], names=["series_id", "field"]),
            )

        market_data = self.feed.get_data(
            securities=[],
            alt_data=series,
            start=start_date,
            end=end_date,
        )
        return market_data.alt_data
