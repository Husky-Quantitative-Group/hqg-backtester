from typing import Dict, List, Optional, Any
from engine.backtest import run as _engine_run

class Algorithm:
    """
    Base class for researchers.
    """
    # -------- lifecycle (user overrides) --------
    def Initialize(self):
        raise NotImplementedError

    def OnData(self, data: Dict[str, Any]):
        raise NotImplementedError

    def __init__(self) -> None:
        # Config set in initialize()
        self._universe: List[str] = []
        self._start: Optional[str] = None
        self._end: Optional[str] = None
        self._resolution: str = "Daily"  # V1 Daily only
        self._indicator_reqs: List[tuple[str, str, Dict[str, Any]]] = []

        # Engine-injected services
        self._broker = None
        self._portfolio = None

        self._initialized = False

    # -------- config helpers --------
    def set_universe(self, symbols: List[str]) -> None:
        self._universe = list(symbols)

    def set_timeframe(self, start: str, end: str) -> None:
        # Expect "YYYY-MM-DD" strings in V1
        self._start, self._end = start, end

    def set_resolution(self, resolution: str) -> None:
        if resolution != "Daily":
            raise ValueError("V1 supports 'Daily' resolution only.")
        self._resolution = resolution

    def add_indicator(self, symbol: str, name: str, customName:str, **params: Any) -> None:
        # [AAPL, RSI, RSI_20, 20]
        self._indicator_reqs.append((symbol, name, customName, params))

    @property
    def broker(self):
        assert self._broker is not None
        return self._broker

    @property
    def portfolio(self):
        assert self._portfolio is not None
        return self._portfolio

    def buy(self, symbol: str, qty: int) -> None:
        self.broker.submit_order("BUY", symbol, int(qty))

    def sell(self, symbol: str, qty: int) -> None:
        self.broker.submit_order("SELL", symbol, int(qty))

    def liquidate(self, symbol: Optional[str] = None) -> None:
        self.broker.submit_order("LIQUIDATE", symbol, 0)

    # -------- entry points --------
    def _backtest(self) -> str:
        self._ensure_initialized()
        return _engine_run(self)

    @classmethod
    def backtest(cls) -> str:
        """Convenience: CustomAlgo.backtest()"""
        return cls()._backtest()

    # -------- internal --------
    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        if type(self).Initialize is not Algorithm.Initialize:
            self.Initialize()
        else:
            raise NotImplementedError("Provide Initialize() in your Algorithm subclass.")
        # sanity checks
        if not self._universe:
            raise ValueError("Universe is empty. Call set_universe([...]) in Initialize().")
        if not (self._start and self._end):
            raise ValueError("Timeframe not set. Call set_timeframe('YYYY-MM-DD','YYYY-MM-DD').")
        self._initialized = True
