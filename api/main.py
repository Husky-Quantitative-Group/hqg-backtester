from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import os
import re
import math
from datetime import datetime
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtester.runner import run as run_backtest_engine

app = FastAPI(
    title="HQG Backtester API",
    description="REST API for running quantitative trading strategy backtests",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BacktestRequest(BaseModel):
    code: str
    startDate: str = None
    endDate: str = None
    initialCash: float = 100000.0


@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


def parse_strategy_code(code: str):
    from hqg_algorithms import Strategy, Cadence
    
    namespace = {'Strategy': Strategy, 'Cadence': Cadence}
    exec(code, namespace)
    
    for name, obj in namespace.items():
        if isinstance(obj, type) and issubclass(obj, Strategy) and obj is not Strategy:
            if not hasattr(obj, 'cadence') or obj.cadence is Strategy.cadence:
                original_class = obj
                class StrategyWithCadence(original_class):
                    def cadence(self):
                        return Cadence()
                StrategyWithCadence.__name__ = original_class.__name__
                return StrategyWithCadence
            return obj
    
    raise ValueError("No Strategy subclass found in the provided code")


def extract_universe_from_code(code: str):
    universe_match = re.search(r'def universe\(self\).*?return\s*\[(.*?)\]', code, re.DOTALL)
    if universe_match:
        ticker_str = universe_match.group(1)
        found_tickers = re.findall(r'["\']([A-Z]+)["\']', ticker_str)
        if found_tickers:
            return found_tickers
    return ["SPY"]


@app.post("/backtest")
def run_backtest(request: BacktestRequest):
    try:
        code = request.code or ""
        initial_cash = request.initialCash or 100000.0
        
        if request.startDate:
            try:
                start_date = datetime.strptime(request.startDate, "%Y-%m-%d")
            except ValueError:
                start_date = datetime(2020, 1, 3)
        else:
            start_date = datetime(2020, 1, 3)
        
        if request.endDate:
            try:
                end_date = datetime.strptime(request.endDate, "%Y-%m-%d")
            except ValueError:
                end_date = datetime(2024, 1, 3)
        else:
            end_date = datetime(2024, 1, 3)
        
        try:
            strategy_class = parse_strategy_code(code)
        except Exception as e:
            return {"success": False, "error": f"Failed to parse strategy code: {str(e)}"}
        
        try:
            temp_instance = strategy_class()
            universe = temp_instance.universe()
        except Exception:
            universe = extract_universe_from_code(code)
        
        results = run_backtest_engine(
            algorithm_class=strategy_class,
            universe=universe,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            verbose=False
        )
        
        equity_curve = results.get('equity_curve', [])
        fills = results.get('fills', [])
        performance = results.get('performance_report', {})
        final_snapshot = results.get('final_snapshot', {})
        
        formatted_equity_curve = []
        for point in equity_curve:
            timestamp = point['time']
            if isinstance(timestamp, datetime):
                timestamp = int(timestamp.timestamp())
            equity = point['equity']
            formatted_equity_curve.append({
                "time": timestamp,
                "open": round(equity, 2),
                "high": round(equity * 1.001, 2),
                "low": round(equity * 0.999, 2),
                "close": round(equity, 2),
            })
        
        orders = []
        for i, fill in enumerate(fills):
            fill_time = fill.get('time') or fill.get('filled_at') or fill.get('submitted_at')
            if fill_time is None:
                timestamp_str = start_date.strftime("%b %d, %Y, %I:%M %p")
            elif isinstance(fill_time, datetime):
                timestamp_str = fill_time.strftime("%b %d, %Y, %I:%M %p")
            elif hasattr(fill_time, 'strftime'):
                timestamp_str = fill_time.strftime("%b %d, %Y, %I:%M %p")
            else:
                try:
                    parsed = datetime.fromisoformat(str(fill_time).replace('Z', '+00:00'))
                    timestamp_str = parsed.strftime("%b %d, %Y, %I:%M %p")
                except:
                    timestamp_str = start_date.strftime("%b %d, %Y, %I:%M %p")
            
            quantity = fill.get('filled_qty') or fill.get('quantity', 0)
            direction = fill.get('direction', 'buy')
            is_buy = direction == 'buy' if isinstance(direction, str) else fill.get('is_buy', True)
            
            orders.append({
                "id": str(i + 1),
                "timestamp": timestamp_str,
                "ticker": fill.get('symbol', 'UNKNOWN'),
                "type": "Buy" if is_buy else "Sell",
                "price": round(fill.get('fill_price', 0), 2),
                "amount": int(quantity),
            })
        
        final_equity = final_snapshot.get('total_equity', initial_cash)
        net_profit = final_equity - initial_cash
        total_return_pct = (final_equity - initial_cash) / initial_cash
        total_volume = sum(o["price"] * o["amount"] for o in orders)
        fees = sum(fill.get('commission', 0) for fill in fills)
        
        summary = performance.get('summary', {})
        trade_metrics = performance.get('trade_metrics', {})
        risk_metrics = performance.get('risk_metrics', {})
        
        def to_python(val, default=0):
            if val is None:
                return default
            if hasattr(val, 'item'):
                val = float(val.item())
            else:
                val = float(val)
            if math.isinf(val) or math.isnan(val):
                return default
            return val
        
        return {
            "success": True,
            "data": {
                "summary": {
                    "initialCash": float(initial_cash),
                    "finalEquity": round(float(final_equity), 2),
                    "totalReturn": round(float(total_return_pct) * 100, 2),
                    "totalReturnPct": round(float(total_return_pct), 4),
                    "numTrades": int(len(orders)),
                    "netProfit": round(float(net_profit), 2),
                    "fees": round(float(fees), 2),
                    "volume": round(float(total_volume), 2),
                },
                "metrics": {
                    "sharpeRatio": round(to_python(summary.get('sharpe_ratio', 0)), 2),
                    "sortinoRatio": round(to_python(summary.get('sortino_ratio', 0)), 2),
                    "alpha": round(to_python(risk_metrics.get('alpha', 0)), 2),
                    "beta": round(to_python(risk_metrics.get('beta', 1), 1), 2),
                    "maxDrawdown": round(abs(to_python(summary.get('max_drawdown', 0))) * 100, 2),
                    "winRate": round(to_python(summary.get('win_rate', 0)) * 100, 2),
                    "profitFactor": round(to_python(trade_metrics.get('profit_factor', 0)), 2),
                    "psr": round(to_python(performance.get('psr', 0)), 2),
                    "avgWinPct": round(to_python(trade_metrics.get('avg_win_pct', 0)) * 100, 2),
                    "avgLossPct": round(abs(to_python(trade_metrics.get('avg_loss_pct', 0))) * 100, 2),
                    "linearityError": round(to_python(performance.get('linearity_error', 0)), 2),
                    "rateDrift": round(to_python(performance.get('rate_drift', 0)), 2),
                    "volatility": round(to_python(summary.get('annualized_volatility', 0)), 4),
                },
                "equityCurve": formatted_equity_curve,
                "orders": orders,
            },
        }
        
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
