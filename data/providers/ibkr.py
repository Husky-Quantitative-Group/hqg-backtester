from typing import List
import pandas as pd
from base import DataProvider

class IBKRProvider(DataProvider):
    def __init__(self, host: str | None = None, port: int | None = None, client_id: int | None = None):
        """Store IBKR connection params; defer connection until fetch."""
        pass

    def get_bars(self, symbols: List[str], start: str, end: str, resolution: str) -> pd.DataFrame:
        """Fetch raw OHLCV bars from IBKR; return canonical raw bars; no indicators."""
        pass


# NOTE:
# IBKR limits historical data per request → get_bars() must fetch in chunks
# and stitch results without gaps. Watch for rate limits: large backtests
# may be impractical. If so, swap in another provider (e.g. Alpaca).
# We keep OHLCV raw/decoupled so indicators are only added later.

# I will give you info to my person account for you to keep in your .env files. 
# IBKR Gateway will need to be running on your machine as well to establish a connection.