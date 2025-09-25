import pandas as pd

REQUIRED_COLS = ["open", "high", "low", "close", "volume"]

def validate_bars(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate raw bars as a tall table:
      - MultiIndex ROWS: ['timestamp','symbol'] (in that order)
      - Columns: at least ['open','high','low','close','volume']
    Check sorted and return the cleaned DataFrame. No indicator columns here.
    """
    pass
