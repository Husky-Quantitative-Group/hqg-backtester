from .base_provider import BaseDataProvider
from datetime import datetime
from hqg_algorithms import BarSize
from typing import Any, Dict, List, Optional
import logging
import time

import pandas as pd
import requests


logger = logging.getLogger(__name__)


class DataFeedClient(BaseDataProvider):
    """
    Client for the internal historical data feed service.

    POST http://{host}:{port}/data/historical with a small retry budget; 
    fall back to yfinance provider on error.
    """

    _MAX_ATTEMPTS = 3
    _REQUEST_TIMEOUT = 30     # seconds

    def __init__(self, port: int = 6767, host: str = "datafeed-api"):
        self.port = port
        self.host = host
        self._base_url = f"http://{host}:{port}"

    def get_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        bar_size: BarSize = BarSize.DAILY,
    ) -> pd.DataFrame:

        payload = {
            "symbols": symbols,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "bar_size": getattr(bar_size, "value", str(bar_size)),
        }
 
        try:
            body = self._post_with_retry("/data/historical", payload)
            return self._parse_response(body)
        except Exception as exc:
            # lagoon down
            logger.warning(
                "DataFeed %s returned error (%s); falling back to yfinance.",
                self._base_url,
                exc,
            )
            return self._fallback(symbols, start_date, end_date, bar_size)


    def _post_with_retry(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._base_url}{path}"
        last_err: Optional[Exception] = None

        for attempt in range(1, self._MAX_ATTEMPTS + 1):
            try:
                resp = requests.post(url, json=payload, timeout=self._REQUEST_TIMEOUT)
            except requests.RequestException as e:
                last_err = e
            else:
                if 400 <= resp.status_code < 500:
                    # data unavailable or malformed request, don't retry
                    raise requests.HTTPError(
                        f"{resp.status_code} from {path}: {resp.text}"
                    )

                if resp.ok:
                    try:
                        return resp.json()
                    except ValueError as e:
                        last_err = e
                else:
                    last_err = requests.HTTPError(
                        f"{resp.status_code} from {path}: {resp.text}"
                    )

            if attempt < self._MAX_ATTEMPTS:
                time.sleep(attempt)   # increase backoff by 1 sec each try

        raise last_err


    @staticmethod
    def _parse_response(body: Dict[str, Any]) -> pd.DataFrame:
        """
        Expects a symbol-grouped payload:

            {
              "bars": {
                "AAPL": {
                  "timestamps": ["2024-01-02", "2024-01-03", ...],
                  "open":   [...],
                  "high":   [...],
                  "low":    [...],
                  "close":  [...],
                  "volume": [...]
                },
                "MSFT": { ... }
              }
            }
        """
        bars = body.get("bars") or body.get("data") or {}
        if not bars:
            return pd.DataFrame()

        per_symbol: Dict[str, pd.DataFrame] = {}
        for symbol, series in bars.items():
            index = pd.to_datetime(series["timestamps"])
            fields = {k: v for k, v in series.items() if k != "timestamps"}
            per_symbol[symbol] = pd.DataFrame(fields, index=index)

        df = pd.concat(per_symbol, axis=1)
        df.columns.names = ["symbol", "field"]
        df.index.name = "timestamp"
        df.sort_index(inplace=True)
        return df


    def _fallback(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        bar_size: BarSize,
    ) -> pd.DataFrame:
        from .yf_provider import YFDataProvider

        provider = YFDataProvider()
        return provider.get_data(symbols, start_date, end_date, bar_size)
