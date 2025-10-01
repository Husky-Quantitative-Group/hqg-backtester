from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..data.types import Slice, Resolution


class Algorithm:
    """QuantConnect-style user algorithm base.

    Users subclass this and implement Initialize() and OnData(slice).
    """

    def __init__(self) -> None:
        self._cash: float = 100_000.0
        self._subscriptions: Set[str] = set()
        self._broker = None  # set by engine
        self._events: List[Dict[str, Any]] = []  # simple logger sink
        self.portfolio = self  # Simple portfolio interface
        self._current_time = None  # Track current time in backtest

    def Initialize(self) -> None:
        """Called once before the event loop starts."""
        pass

    def OnData(self, data: "Slice") -> None:
        """Called for each bar with a Slice of data for subscribed symbols."""
        pass

    def SetCash(self, amount: float) -> None:
        """Set starting cash for the algorithm portfolio."""
        self._cash = float(amount)

    def AddEquity(self, symbol: str, resolution: "Resolution | None" = None) -> None:
        """Subscribe to an equity symbol at the given resolution (default daily)."""
        self._subscriptions.add(symbol)

    # --- Runtime wiring (engine will call these) ---
    def _attach_broker(self, broker) -> None:
        self._broker = broker
        # give broker initial cash
        if hasattr(self._broker, "set_starting_cash"):
            self._broker.set_starting_cash(self._cash)
    
    def _set_broker(self, broker) -> None:
        """Set the broker for this algorithm (alias for _attach_broker)."""
        self._attach_broker(broker)
    
    def _set_data_loader(self, data_loader) -> None:
        """Set the data loader for this algorithm."""
        self._data_loader = data_loader
    
    def _set_symbols(self, symbols) -> None:
        """Set the symbols for this algorithm."""
        self._symbols = symbols
    
    def _set_current_time(self, time) -> None:
        """Set the current time in the backtest."""
        self._current_time = time

    # --- User-callable convenience ---
    def place_order(
        self,
        symbol: str,
        quantity: int,
        direction: Optional[str] = None,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        tag: Optional[str] = None,
        is_buy: Optional[bool] = None,
    ) -> None:
        """Submit an order via the attached broker.

        - direction: "long" to buy, "short" to sell/short (deprecated, use is_buy)
        - is_buy: True to buy, False to sell
        - order_type: "market" or "limit"
        """
        if self._broker is None:
            raise RuntimeError("Broker not attached")
        if order_type not in ("market", "limit"):
            raise ValueError("order_type must be 'market' or 'limit'")
        
        # Handle both direction and is_buy parameters for backward compatibility
        if is_buy is not None:
            buy_flag = is_buy
        elif direction is not None:
            buy_flag = True if direction == "long" else False
        else:
            raise ValueError("Either 'direction' or 'is_buy' parameter must be provided")
        order: Dict[str, Any] = {
            "type": order_type,
            "symbol": symbol,
            "quantity": int(quantity),
            "is_buy": buy_flag,
            "limit_price": float(limit_price) if limit_price is not None else None,
            "tag": tag,
        }
        self._broker.submit(order)

    def log(self, msg: str, **context: Any) -> None:
        event = {"level": "INFO", "msg": msg, **context}
        self._events.append(event)
    
    @property
    def total_portfolio_value(self) -> float:
        """Get total portfolio value (simplified implementation)."""
        return self._cash  # Simplified - in real implementation would include positions


