from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional


class Order:
    """Order representation."""
    
    def __init__(self, symbol: str, quantity: int, is_buy: bool, submitted_at: Optional[datetime] = None):
        self.symbol = symbol
        self.quantity = int(quantity)
        self.is_buy = bool(is_buy)
        self.submitted_at = submitted_at or datetime.utcnow()


class Holding:
    """Position holding representation."""
    
    def __init__(self, symbol: str, quantity: int, average_price: float):
        self.symbol = symbol
        self.quantity = int(quantity)
        self.average_price = float(average_price)


class Broker:
    """Execution interface (simple concrete class in v1)."""

    def submit(self, order: Dict[str, Any]) -> None:
        raise NotImplementedError

    def settle(self, symbol: str, close_price: float, when: datetime) -> None:
        raise NotImplementedError

    def cash(self) -> float:
        raise NotImplementedError

    def holdings(self) -> Dict[str, Holding]:
        raise NotImplementedError


class IBBroker(Broker):
    """Interactive Brokers-style broker with commission structure."""

    def __init__(self, commission_rate: float = 0.005) -> None:
        self._cash: float = 100_000.0
        self._holdings: Dict[str, Holding] = {}
        self._pending: List[Dict[str, Any]] = []
        self._orders: List[Dict[str, Any]] = []  # history
        self._fills: List[Dict[str, Any]] = []
        self._last_price: Dict[str, float] = {}
        self._commission_rate = commission_rate  # $0.005 per share
        self.logger = logging.getLogger(__name__)

    # engine may call to seed starting cash
    def set_starting_cash(self, amount: float) -> None:
        self._cash = float(amount)
        self.logger.info(f"Starting cash set to ${self._cash:,.2f}")

    def calculate_commission(self, symbol: str, quantity: int, price: float) -> float:
        """Calculate IB-style commission.
        
        US Stocks: $0.005 per share, minimum $1.00, maximum 1% of trade value
        """
        # Calculate base commission
        base_commission = quantity * self._commission_rate
        
        # Apply minimum and maximum
        min_commission = 1.00
        max_commission = 0.01 * quantity * price  # 1% of trade value
        
        commission = min(max_commission, max(min_commission, base_commission))
        
        return round(commission, 2)

    def submit(self, order: Dict[str, Any]) -> None:
        """Submit an order for execution."""
        order = dict(order)
        order.setdefault("submitted_at", datetime.now())
        order.setdefault("status", "Submitted")
        order.setdefault("commission", 0.0)
        
        # Validate order
        if order.get("quantity", 0) <= 0:
            raise ValueError("Order quantity must be positive")
        
        if not order.get("symbol"):
            raise ValueError("Order symbol is required")
        
        self._pending.append(order)
        self._orders.append(dict(order))
        
        self.logger.info(f"Order submitted: {order['symbol']} {order['quantity']} shares {'BUY' if order['is_buy'] else 'SELL'}")

    def settle(self, symbol: str, close_price: float, when: datetime) -> List[Dict[str, Any]]:
        """Settle pending orders for a symbol at current price.
        
        Returns list of filled orders.
        """
        self._last_price[symbol] = close_price
        
        if not self._pending:
            return []
        
        remaining: List[Dict[str, Any]] = []
        filled_orders: List[Dict[str, Any]] = []
        
        for order in self._pending:
            if order["symbol"] != symbol:
                remaining.append(order)
                continue
            
            should_fill = self._should_fill_order(order, close_price)
            
            if not should_fill:
                remaining.append(order)
                continue
            
            # Execute the order
            fill_result = self._execute_order(order, close_price, when)
            if fill_result:
                filled_orders.append(fill_result)
                order["status"] = "Filled"
                order["filled_at"] = when
                order["fill_price"] = close_price
        
        self._pending = remaining
        return filled_orders
    
    def _should_fill_order(self, order: Dict[str, Any], current_price: float) -> bool:
        """Determine if an order should be filled."""
        order_type = order.get("type", "market")
        
        if order_type == "market":
            return True
        elif order_type == "limit":
            limit_price = order.get("limit_price")
            if limit_price is None:
                return False
            
            is_buy = order.get("is_buy", False)
            
            # Buy orders fill when current price <= limit price
            if is_buy and current_price <= limit_price:
                return True
            # Sell orders fill when current price >= limit price
            elif not is_buy and current_price >= limit_price:
                return True
        
        return False
    
    def _execute_order(self, order: Dict[str, Any], price: float, when: datetime) -> Optional[Dict[str, Any]]:
        """Execute an order and update portfolio."""
        try:
            symbol = order["symbol"]
            quantity = int(order["quantity"])
            is_buy = order["is_buy"]
            
            # Calculate commission
            commission = self.calculate_commission(symbol, quantity, price)
            
            # Calculate total cost
            trade_value = quantity * price
            direction = 1 if is_buy else -1
            
            # Update cash (including commission)
            total_cost = trade_value * direction + commission
            self._cash -= total_cost
            
            # Update holdings
            holding = self._holdings.get(symbol)
            prev_qty = holding.quantity if holding else 0
            new_qty = prev_qty + quantity * direction
            
            if holding is None:
                avg_price = price
            else:
                if direction > 0:  # Buying
                    total_cost_shares = holding.average_price * prev_qty + trade_value
                    avg_price = total_cost_shares / (prev_qty + quantity) if (prev_qty + quantity) != 0 else price
                else:  # Selling
                    avg_price = holding.average_price  # Average price doesn't change on sell
            
            # Update or create holding
            if new_qty == 0:
                # Remove holding if position is closed
                if symbol in self._holdings:
                    del self._holdings[symbol]
            else:
                self._holdings[symbol] = Holding(
                    symbol=symbol,
                    quantity=new_qty,
                    average_price=avg_price
                )
            
            # Create fill record
            fill_record = {
                "symbol": symbol,
                "filled_qty": quantity,
                "fill_price": price,
                "commission": commission,
                "direction": "buy" if is_buy else "sell",
                "time": when,
                "order_ref": order,
                "trade_value": trade_value,
                "total_cost": total_cost,
            }
            
            self._fills.append(fill_record)
            
            self.logger.info(
                f"Order filled: {symbol} {quantity} shares @ ${price:.2f} "
                f"(${commission:.2f} commission)"
            )
            
            return fill_record
            
        except Exception as e:
            self.logger.error(f"Error executing order: {e}")
            return None

    def cash(self) -> float:
        """Get current cash balance."""
        return self._cash

    def holdings(self) -> Dict[str, Holding]:
        """Get current holdings."""
        return dict(self._holdings)

    def get_orders(self) -> List[Dict[str, Any]]:
        """Get order history."""
        return list(self._orders)
    
    def get_fills(self) -> List[Dict[str, Any]]:
        """Get fill history."""
        return list(self._fills)
    
    def get_pending_orders(self) -> List[Dict[str, Any]]:
        """Get pending orders."""
        return list(self._pending)

    # convenience for engine/analysis
    def snapshot(self) -> Dict[str, Any]:
        """Get portfolio snapshot."""
        equity = self._cash
        holdings_value = 0
        
        holdings_detail = {}
        for sym, h in self._holdings.items():
            last = self._last_price.get(sym, h.average_price)
            position_value = h.quantity * last
            holdings_value += position_value
            
            holdings_detail[sym] = {
                "quantity": h.quantity,
                "avg_price": h.average_price,
                "current_price": last,
                "position_value": position_value,
                "unrealized_pnl": position_value - (h.quantity * h.average_price),
            }
        
        total_equity = self._cash + holdings_value
        
        return {
            "cash": self._cash,
            "holdings_value": holdings_value,
            "total_equity": total_equity,
            "holdings": holdings_detail,
            "pending_orders": len(self._pending),
            "total_orders": len(self._orders),
            "total_fills": len(self._fills),
        }
    
    def get_equity_curve(self) -> List[Dict[str, Any]]:
        """Get equity curve from fill history."""
        equity_curve = []
        running_cash = self._cash
        
        # Sort fills by time
        sorted_fills = sorted(self._fills, key=lambda x: x["time"])
        
        for fill in sorted_fills:
            running_cash -= fill["total_cost"]
            
            # Calculate current equity
            holdings_value = 0
            for sym, h in self._holdings.items():
                if sym == fill["symbol"]:
                    # Use fill price for the symbol being traded
                    holdings_value += h.quantity * fill["fill_price"]
                else:
                    # Use last known price for other symbols
                    last = self._last_price.get(sym, h.average_price)
                    holdings_value += h.quantity * last
            
            equity = running_cash + holdings_value
            
            equity_curve.append({
                "time": fill["time"],
                "equity": equity,
                "cash": running_cash,
                "holdings_value": holdings_value,
            })
        
        return equity_curve


# Keep SimpleBroker as alias for backward compatibility
SimpleBroker = IBBroker


