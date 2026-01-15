
from hqg_algorithms.types import Cadence, Slice, PortfolioView
from hqg_algorithms.strategy import Strategy
import numpy as np
import pandas as pd
import cvxpy as cp
from datetime import timedelta
from collections import deque
from src.models.response import PerformanceMetrics


class MeanVar(Strategy):
    
    def __init__(self):
        self.qc_metrics = PerformanceMetrics(
            total_return=0,
            annualized_return=0,
            sharpe_ratio=0,
            max_drawdown=0,
            win_rate=0,
            total_orders=0,
            sortino=0,
            alpha=0,
            beta=0,
            psr=0,
            avg_win=0,
            avg_loss=0,
            annualized_variance=0,
            annualized_std=0
        )

        
        # Strategy parameters
        self.lookback_days = 126  # ~6 months of history
        self.weight_cap = 0.25    # max 25% in any single asset
        self.min_obs = 60         # require ~3 months of data minimum
        self.gamma = 20           # risk aversion parameter
        
        # Store price history internally
        # Structure: {"SPY": deque([price1, price2, ...], maxlen=lookback_days+2), ...}
        self.price_history: dict[str, deque] = {}
        
    def universe(self) -> list[str]:
        return [
            "SPY",  # US large-cap
            "IWM",  # US small-cap
            "EFA",  # Developed ex-US
            "EEM",  # Emerging markets
            "QQQ",  # US large-cap growth tilt
            "VNQ",  # US REITs
            "GLD",  # Gold
            "DBC",  # Broad commodities
            "AGG",  # US aggregate bonds
            "LQD",  # Investment-grade corporates
            "HYG",  # High yield
            "TLT",  # Long Treasuries
            "TIP",  # Treasury inflation protected securities
            #"BTC"   # Bitcoin
        ]
    
    def cadence(self) -> Cadence:
        """
            Rebalance daily at bar close with 1-bar execution lag.
            Signal generated on bar close
            Orders executed at next bar's open (30min after in QC)
        """
        return Cadence(
            bar_size=timedelta(days=1),
            call_phase="on_bar_close",
            exec_lag_bars=1
        )
    
    def on_data(self, data: Slice, portfolio: PortfolioView) -> dict[str, float] | None:
        self._update_history(data)
        
        tradable = [sym for sym in self.universe() if data.has(sym) and data.close(sym) is not None]
        
        if len(tradable) < 3:
            return None
        
        # Build price DataFrame from history
        price_df = self._build_price_dataframe(tradable)
        
        if price_df is None or price_df.shape[0] < self.min_obs:
            return None  # Insufficient history
        
        # Calculate expected returns and covariance
        mu = self._get_mu(price_df)
        Sigma = self._get_sigma(price_df)
        
        # Optimize portfolio weights
        weights = self._allocate(mu, Sigma)
        
        if weights is None or len(weights) == 0:
            return None
        
        # Convert to weight dictionary, filtering negligible weights
        weight_dict = {}
        for sym, w in zip(tradable, weights):
            if w > 1e-6:  # Filter out effectively zero weights
                weight_dict[sym] = float(w)
        
        return weight_dict
    
    def _update_history(self, data: Slice) -> None:
        for symbol in self.universe():
            close_price = data.close(symbol)
            if close_price is not None:
                if symbol not in self.price_history:
                    self.price_history[symbol] = deque(maxlen=self.lookback_days + 2)
                self.price_history[symbol].append(close_price)
    
    def _build_price_dataframe(self, symbols: list[str]) -> pd.DataFrame | None:
        histories = {}
        for sym in symbols:
            if sym in self.price_history and len(self.price_history[sym]) >= self.min_obs:
                histories[sym] = list(self.price_history[sym])
        
        if len(histories) < 3:
            return None
        
        # Find minimum length across all symbols
        min_len = min(len(hist) for hist in histories.values())
        
        # Build DataFrame with aligned histories (take last min_len observations)
        aligned = {sym: hist[-min_len:] for sym, hist in histories.items()}
        df = pd.DataFrame(aligned)
        
        return df if not df.empty else None
    
    def _get_mu(self, price_df: pd.DataFrame) -> np.ndarray:
        rets = price_df.pct_change().dropna(how="all").fillna(0.0)
        if rets.shape[0] == 0:
            return np.ones(price_df.shape[1]) / max(1, price_df.shape[1])
        mu = rets.mean(axis=0).values
        return mu
    
    def _get_sigma(self, price_df: pd.DataFrame) -> np.ndarray:
        rets = price_df.pct_change().dropna(how="all").fillna(0.0)
        if rets.shape[0] == 0 or rets.shape[1] == 0:
            return np.eye(price_df.shape[1])
        Sigma = np.cov(rets.values, rowvar=False, ddof=1)
        return Sigma
    
    def _allocate(self, mu: np.ndarray, Sigma: np.ndarray) -> np.ndarray | None:
        N = len(mu)
        if N == 0:
            return None
        
        w = cp.Variable(N)
        objective = cp.Maximize(mu @ w - self.gamma * cp.quad_form(w, Sigma))
        
        constraints = [
            cp.sum(w) == 1,          # Fully invested
            w >= 0,                  # Long-only (no shorts)
            w <= self.weight_cap     # Position size limits
        ]
        
        prob = cp.Problem(objective, constraints)
        
        try:
            prob.solve(solver=cp.ECOS, verbose=False)
        except Exception:
            return np.ones(N) / N
        
        if w.value is None or np.any(np.isnan(w.value)):
            return np.ones(N) / N
        
        return np.asarray(w.value, dtype=float).ravel()
    

'''
QuantConnect:

# region imports
from AlgorithmImports import *
import numpy as np
import pandas as pd
import cvxpy as cp
# endregion

class MeanVarBaseline(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2019, 1, 1)
        self.SetCash(100_000)
        self.UniverseSettings.Resolution = Resolution.DAILY

        # base; we also add equities daily
        tickers = [
            "SPY",  # US large-cap
            "IWM",  # US small-cap
            "EFA",  # Developed ex-US
            "EEM",  # Emerging markets
            "QQQ",  # US large-cap growth tilt
            "VNQ",  # US REITs
            "GLD",  # Gold
            "DBC",  # Broad commodities
            "AGG",  # US aggregate bonds
            "LQD",  # Investment-grade corporates
            "HYG",  # High yield
            "TLT",  # Long Treasuries
            "TIP",  # Treasury inflation protected securities
            "BTC"   # Bitcoin
        ]
        

        self.my_universe = []
        for t in tickers:
            try:
                sec = self.add_equity(t, Resolution.DAILY)
                self.my_universe.append(sec.symbol)
                self.log(f"Added {t} -> {sec.symbol}")
            except Exception as e:
                self.log(f"Failed adding {t}: {e}")
        
        self.lookback_days = 126  # ~6 mo
        self.weight_cap = 0.25  # max 25% in any single asset
        self.min_obs = 60   # require ~3 months of data
        self.gamma = 20 # risk aversion

        # Daily at 30 min after market open
        self.Schedule.On(
            self.date_rules.every_day(self.my_universe[0]),
            self.time_rules.after_market_open(self.my_universe[0], 30),
            self.Rebalance
        )

        self.SetBenchmark("SPY")


    # estimations
    def get_mu(self, price_df: pd.DataFrame):
        """
            Intuition: ast averages approximate future returns
        """
        rets = price_df.pct_change().dropna(how="all").fillna(0.0)
        if rets.shape[0] == 0:
            return np.ones(rets.shape[1]) / max(1, rets.shape[1])   # if nada assume equal
        mu = rets.mean(axis=0).values  # simple average daily return
        return mu

    def get_sigma(self, price_df: pd.DataFrame):
        """
            Intution: past covariance approximates future covariance
        """
        rets = price_df.pct_change().dropna(how="all").fillna(0.0)
        if rets.shape[0] == 0 or rets.shape[1] == 0:
            return np.eye(price_df.shape[1])    # nxn Identity mtx
        Sigma = np.cov(rets.values, rowvar=False, ddof=1)
        return Sigma


    def allocate(self, mu: np.ndarray, Sigma: np.ndarray):
        """
        Mean-variance optimization using cvxpy.
        Maximize: mu.T @ w - gamma * w.T @ Sigma @ w
        Subject to: sum(w) == 1, 0 <= w <= weight_cap
        ie, which w maximizes (expected return - expected variance)
        """
        N = len(mu)
        if N == 0:
            return np.array([])

        # TODO (robustness): add in semidef check for Sigma

        w = cp.Variable(N)
        gamma = self.gamma

        objective = cp.Maximize(mu @ w - gamma * cp.quad_form(w, Sigma))

        # fully invested, long-only, capped weights
        constraints = [
            cp.sum(w) == 1,
            w >= 0,
            w <= self.weight_cap
        ]

        prob = cp.Problem(objective, constraints)
        prob.solve(solver=cp.ECOS, verbose=False)

        # equal weights if failed
        if w.value is None or np.any(np.isnan(w.value)):
            return np.ones(N) / N

        # TODO: might want to round down OR make weight threshold (continuous, ~0)
        return np.asarray(w.value, dtype=float).ravel()


    def Rebalance(self):
        cur_universe = [s for s in self.my_universe if self.Securities[s].IsTradable]
        if len(cur_universe) < 3:
            return

        hist = self.History(cur_universe, self.lookback_days + 2, Resolution.Daily)
        if hist.empty:
            return

        price_df = hist.close.unstack(level=0).sort_index()
        #price_df = hist["close"].unstack(0).sort_index()

        # Align to current universe order
        cols = [s for s in cur_universe if s in price_df.columns]
        price_df = price_df[cols].dropna(how="all")
        if price_df.shape[0] < self.min_obs:
            return

        # mu & sigma & allocate
        mu = self.get_mu(price_df.copy())
        Sigma = self.get_sigma(price_df.copy())
        w = self.allocate(mu, Sigma)

        for sym, wi in zip(cols, w):
            self.set_holdings(sym, float(wi))

        current = {h.Symbol for h in self.Portfolio.Values if h.Invested}
        keep = set(cols)
        liquidated = 0
        for sym in current - keep:
            self.liquidate(sym)
            liquidated += 1

        self.Debug(f"[{self.Time.date()}] Current {len(keep)}; Liquidated {liquidated} assets.")

'''