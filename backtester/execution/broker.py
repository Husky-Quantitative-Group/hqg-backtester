from datetime import datetime


class Order:
    def __init__(self, symbol, quantity, is_buy, submitted_at=None):
        self.symbol = symbol
        self.quantity = int(quantity)
        self.is_buy = bool(is_buy)
        self.submitted_at = submitted_at or datetime.utcnow()


class Holding:
    def __init__(self, symbol, quantity, average_price):
        self.symbol = symbol
        self.quantity = int(quantity)
        self.average_price = float(average_price)


class Broker:
    def submit(self, order):
        raise NotImplementedError

    def settle(self, symbol, close_price, when):
        raise NotImplementedError

    def cash(self):
        raise NotImplementedError

    def holdings(self):
        raise NotImplementedError


class IBBroker(Broker):
    def __init__(self, commission_rate=0.005):
        self._cash = 10000.0
        self._holdings = {}
        self._pending = []
        self._orders = []
        self._fills = []
        self._last_price = {}
        self._commission_rate = commission_rate

    def set_starting_cash(self, amount):
        self._cash = float(amount)

    def calculate_commission(self, symbol, quantity, price):
        if self._commission_rate == 0.0:
            return 0.0
            
        base_commission = quantity * self._commission_rate
        min_commission = 1.00
        max_commission = 0.01 * quantity * price
        
        commission = min(max_commission, max(min_commission, base_commission))
        return round(commission, 2)

    def submit(self, order):
        order = dict(order)
        order.setdefault("submitted_at", datetime.now())
        order.setdefault("status", "Submitted")

        if order.get("quantity", 0) <= 0:
            raise ValueError("Order quantity must be positive")
        
        if not order.get("symbol"):
            raise ValueError("Order symbol is required")
        
        self._pending.append(order)
        self._orders.append(dict(order))

    def settle(self, symbol, close_price, when):
        self._last_price[symbol] = close_price
        
        if not self._pending:
            return []
        
        remaining = []
        filled_orders = []
        
        for order in self._pending:
            if order["symbol"] != symbol:
                remaining.append(order)
                continue
            
            should_fill = self._should_fill_order(order, close_price)
            
            if not should_fill:
                remaining.append(order)
                continue
            
            fill_result = self._execute_order(order, close_price, when)
            if fill_result:
                filled_orders.append(fill_result)
                order["status"] = "Filled"
                order["filled_at"] = when
                order["fill_price"] = close_price
        
        self._pending = remaining
        return filled_orders
    
    def _should_fill_order(self, order, current_price):
        order_type = order.get("type", "market")
        
        if order_type == "market":
            return True

        elif order_type == "limit":
            limit_price = order.get("limit_price")
            if limit_price is None:
                return False
            
            is_buy = order.get("is_buy", False)
            
            if is_buy and current_price <= limit_price:
                return True
            elif not is_buy and current_price >= limit_price:
                return True
        
        return False
    
    def _execute_order(self, order, price, when):
        try:
            symbol = order["symbol"]
            quantity = int(order["quantity"])
            is_buy = order["is_buy"]
            
            commission = self.calculate_commission(symbol, quantity, price)
            trade_value = quantity * price
            direction = 1 if is_buy else -1
            total_cost = trade_value * direction + commission
            self._cash -= total_cost
            
            holding = self._holdings.get(symbol)
            prev_qty = holding.quantity if holding else 0
            new_qty = prev_qty + (quantity * direction)
            
            if holding is None:
                avg_price = price
            else:
                if direction > 0:
                    total_cost_shares = holding.average_price * prev_qty + trade_value
                    avg_price = total_cost_shares / (prev_qty + quantity) if (prev_qty + quantity) != 0 else price
                else:
                    avg_price = holding.average_price
            
            if new_qty == 0:
                if symbol in self._holdings:
                    del self._holdings[symbol]
            else:
                self._holdings[symbol] = Holding(
                    symbol=symbol,
                    quantity=new_qty,
                    average_price=avg_price
                )
            
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
            return fill_record
            
        except Exception as e:
            return None

    def cash(self):
        return self._cash

    def holdings(self):
        return dict(self._holdings)

    def get_orders(self):
        return list(self._orders)
    
    def get_fills(self):
        return list(self._fills)
    
    def get_pending_orders(self):
        return list(self._pending)

    def snapshot(self):
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
    
    def get_equity_curve(self):
        equity_curve = []
        running_cash = self._cash
        sorted_fills = sorted(self._fills, key=lambda x: x["time"])
        
        for fill in sorted_fills:
            running_cash -= fill["total_cost"]
            holdings_value = 0
            
            for sym, h in self._holdings.items():
                if sym == fill["symbol"]:
                    holdings_value += h.quantity * fill["fill_price"]
                else:
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


