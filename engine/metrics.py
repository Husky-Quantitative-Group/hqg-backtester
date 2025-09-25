from typing import Dict, Any
import pandas as pd

def compute_metrics(equity: pd.Series) -> Dict[str, Any]:
    """Return basic stats (e.g., total return, max drawdown, volatility, simple sharpe)."""
    pass

def drawdown_series(equity: pd.Series) -> pd.Series:
    """Return equity / cummax - 1.0 as a time-aligned Series."""
    pass
