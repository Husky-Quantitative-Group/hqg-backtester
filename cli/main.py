"""`hqg` command line entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
from typing import Any

from hqg_algorithms import validate_strategy

from . import __version__
from .api import BacktestClient
from .auth import load_token, save_token
from .render import (
    render_logs,
    render_result,
    render_validation_errors,
    save_equity_graph,
    save_portfolio_allocation_graph,
    save_weight_graph,
)
from .settings import HQG_HOME, settings

from src.models.request import BacktestRequest


def make_request(
    strategy_code: str,
    start_date: datetime = datetime(2023, 1, 1),
    end_date: datetime = datetime(2024, 1, 1),
    initial_capital: float = 10000.0,
    commission: float = 0.001,
    slippage: float = 0.001,
    name: str = "Dashboard Backtest",
    config: dict = None
) -> BacktestRequest:
    """
    Simulate a real request from the dashboard.

    This mirrors what the frontend would send to /api/v1/backtest.
    """
    return BacktestRequest(
        strategy_code=strategy_code,
        name=name,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        commission=commission,
        slippage=slippage,
        config_params=config,
    )


def NewClient() -> BacktestClient:
    """Build a client carrying whatever credentials the researcher has."""
    return BacktestClient(settings.API_URL, load_token())

def read_strategy(path: Path) -> str:
    if not path.exists():
        raise ValueError(f"No such file: {path}")
    if path.is_dir():
        raise ValueError(f"{path} is a directory; point at a strategy file.")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Could not read {path}: {exc}") from exc


def _parse_date(value: str, flag: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"{flag} must be a date in YYYY-MM-DD form, got {value!r}") from None

def _parse_config_file(path: Path) -> dict:
    if path is None:
        return {}

    if not path.exists():
        raise ValueError(f"No such file: {path}")
    if path.is_dir():
        raise ValueError(f"{path} is a directory; point at a configuration file.")
    try:
        output = json.loads(path.read_text())

        if len(output.keys()) == 0:
            return {}
        else:
            return output

    except OSError as exc:
        raise ValueError(f"Could not read {path}: {exc}") from exc


def build_payload(args: argparse.Namespace, source: str, name: str, backtest_params: dict) -> dict[str, Any]:
    capital = args.capital # this has a default value
    if args.start is None:
        args.start = "2000-01-01"
    if args.end is None:
        args.end = "2026-01-01"
    start = _parse_date(args.start, "--start")
    end = _parse_date(args.end, "--end")

    if end <= start:
        raise ValueError("--end must be after --start")
    if capital <= 0:
        raise ValueError("--capital must be greater than 0")

    # TODO: commission & slippage
    return {
        "strategy_code": source,
        "name": name,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "initial_capital": capital,
        "profile": args.profile,
        "config_params": backtest_params,
    }


def cmd_run(args: argparse.Namespace) -> int:
    if args.config:
        config_path = Path(args.config)
    else:
        config_path = None
    config = _parse_config_file(config_path)
    backtest_params = None

    # If there is no config file or it isn't proper json, an empty dict
    # will be returned so this loop will never run
    for key, value in config.items():
        match key:
            case "start":
                args.start = str(config.get("start"))
            case "end":
                args.end = str(config.get("end"))
            case "name":
                args.name = str(config.get("name"))
            case "capital":
                args.capital = float(config.get("capital"))
            case "profile":
                args.profile = bool(config.get("profile"))
            case "verbose":
                args.verbose = bool(config.get("verbose"))
            case "graph":
                args.graph = bool(config.get("graph"))
            case "params":
                backtest_params = config.get("params")

    path = Path(args.strategy)
    source = read_strategy(path)
    name = args.name or path.stem

    errors = validate_strategy(source)
    if errors:
        print(render_validation_errors(errors, path.name), file=sys.stderr)
        return 2

    payload = build_payload(args, source, name, backtest_params)

    from src.api.handlers import BacktestHandler

    handler = BacktestHandler()

    started = time.monotonic()

    try:
        response = asyncio.run(
            handler.run_backtest(
                make_request(
                    strategy_code=payload['strategy_code'],
                    start_date=payload['start_date'],
                    end_date=payload['end_date'],
                    initial_capital=payload['initial_capital'],
                    commission=0,
                    slippage=0,
                    name=payload['name'],
                    config=payload['config_params'],
                )
            )
        )
    except KeyboardInterrupt:
        print("\n  interrupted", file=sys.stderr)
        return 130

    elapsed = time.monotonic() - started

    if response is None:
        raise RuntimeError("The job completed but returned no result.")

    result = response.model_dump(mode="json")

    summary = render_result(result, path.name, elapsed)
    logs: list[str] = []
    candles = result.get("candles", [])
    orders = result.get("orders", [])
    weights = result.get("holding_weights", [])

    print(summary)
    if args.verbose and logs:
        print(render_logs(logs))
    if args.profile and result.get("profile"):
        print(f"  Profile\n{result['profile']}")

    stem = f"{name}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"

    graph_dir = HQG_HOME / "graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)

    if args.graph and candles:
        graph = graph_dir / f"{stem}-equity.png"
        save_equity_graph(candles, graph)
        print(f"  equity graph saved to {graph}", file=sys.stderr)

    if args.graph and weights:
        graph = graph_dir / f"{stem}-allocation.png"
        save_portfolio_allocation_graph(weights, graph)
        print(f"  portfolio allocation graph saved to {graph}", file=sys.stderr)

    if args.graph and candles:
        graph = graph_dir / f"{stem}-weights.png"
        parameters = result.get("parameters") or {}
        starting_equity = parameters.get("starting_equity", args.capital)
        save_weight_graph(candles, orders, starting_equity, graph)
        print(f"  weight graph saved to {graph}", file=sys.stderr)

    if args.graph:
        log_dir = HQG_HOME / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        out = log_dir / f"{stem}.json"
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"  saved to {out}", file=sys.stderr)

    return 0

def cmd_health(args: argparse.Namespace) -> int:
    NewClient().health()
    print(f"  backtesting service is reachable at {settings.API_URL}", file=sys.stderr)
    return 0

def cmd_login(args: argparse.Namespace) -> int:
    # paste in by hand
    if sys.stdin.isatty():
        token = getpass("  paste your dashboard token: ")
    # pipe in to terminal
    else:
        token = sys.stdin.readline()

    path = save_token(token)
    print(f"  saved to {path}", file=sys.stderr)
    
    NewClient().health()
    print(f"  signed in to {settings.API_URL}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hqg",
        description="Run backtests against the HQG backtesting service.",
    )
    parser.add_argument("--version", action="version", version=f"hqg {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="run a backtest on a strategy file")
    run.add_argument("strategy", help="path to a Python file defining a Strategy subclass")
    run.add_argument("--start", metavar="YYYY-MM-DD", help="backtest start date")
    run.add_argument("--end", metavar="YYYY-MM-DD", help="backtest end date")
    run.add_argument(
        "--capital", type=float, default=10000.0, help="starting capital (default: 10000)"
    )
    run.add_argument("--name", help="name for this run (default: the file name)")
    run.add_argument("--graph", action="store_true", help="save the raw result to ~/.hqg/logs and the equity, portfolio allocation & weight graphs to ~/.hqg/graphs")
    run.add_argument("--verbose", action="store_true", help="include strategy log output")
    run.add_argument(
        "--profile", action="store_true", help="profile the backtest on the server (HQG_PROFILE)"
    )
    run.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="seconds to wait for the result (default: 600)",
    )
    run.add_argument("--config", help="path to a json configuration file")
    run.set_defaults(func=cmd_run)

    health = subparsers.add_parser("health", help="check that the service is reachable")
    health.set_defaults(func=cmd_health)

    login = subparsers.add_parser("login", help="save your dashboard token")
    login.set_defaults(func=cmd_login)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:        # input was wrong
        print(f"\n  {exc}\n", file=sys.stderr)
        return 2
    except RuntimeError as exc:      # the run or the service failed
        print(f"\n  {exc}\n", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n  interrupted", file=sys.stderr)
        return 130
