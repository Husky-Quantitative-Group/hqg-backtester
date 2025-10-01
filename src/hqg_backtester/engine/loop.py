from __future__ import annotations

from typing import Dict, Iterator, Tuple

from ..api.algorithm import Algorithm
from ..data.types import Slice, TradeBar


def run(algorithm: Algorithm, feed: Iterator[Tuple[object, Dict[str, TradeBar]]], broker) -> None:
    """Minimal event loop implementation.

    - Calls algorithm.Initialize()
    - For each bar in feed: builds Slice, calls algorithm.OnData(slice), settles broker
    """
    algorithm._attach_broker(broker)
    algorithm.Initialize()
    for when, bars in feed:
        data = Slice(bars)
        algorithm.OnData(data)
        for symbol, bar in bars.items():
            broker.settle(symbol, bar.close, bar.end_time)


