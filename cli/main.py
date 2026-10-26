"""`hqg` command line entry point."""

from __future__ import annotations

import argparse
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
from .render import render_logs, render_result, render_validation_errors, save_equity_graph
from .settings import HQG_HOME, settings


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


def build_payload(args: argparse.Namespace, source: str, name: str) -> dict[str, Any]:
    start = _parse_date(args.start, "--start")
    end = _parse_date(args.end, "--end")
    if end <= start:
        raise ValueError("--end must be after --start")
    if args.capital <= 0:
        raise ValueError("--capital must be greater than 0")

    # TODO: commission & slippage
    return {
        "strategy_code": source,
        "name": name,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "initial_capital": args.capital,
        "profile": args.profile,
    }


def cmd_run(args: argparse.Namespace) -> int:
    path = Path(args.strategy)
    source = read_strategy(path)
    name = args.name or path.stem

    errors = validate_strategy(source)
    if errors:
        print(render_validation_errors(errors, path.name), file=sys.stderr)
        return 2

    payload = build_payload(args, source, name)

    client = NewClient()
    client.health()
    job_id = client.submit(payload)
    print(f"  job {job_id}", file=sys.stderr)

    started = time.monotonic()
    try:
        record = client.wait_for_result(
            job_id,
            timeout=args.timeout,
            on_status=lambda status: print(f"  {status.lower()}", file=sys.stderr),
        )
    except KeyboardInterrupt:
        outcome = client.cancel(job_id)
        print(f"\n  interrupted; job {job_id} {outcome}", file=sys.stderr)
        return 130

    elapsed = time.monotonic() - started

    if record.get("status") != "COMPLETED":
        print(f"  {record.get('error') or 'did not complete'}", file=sys.stderr)
        return 1

    result = record.get("result")
    if not result:
        raise RuntimeError("The job completed but returned no result.")

    summary = render_result(result, path.name, elapsed)
    logs: list[str] = record.get("logs") or []
    candles = result.get("candles", [])

    print(summary)
    if args.verbose and logs:
        print(render_logs(logs))
    if args.profile and result.get("profile"):
        print(f"  Profile\n{result['profile']}")

    stem = f"{name}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"

    if args.json and candles:
        graph_dir = HQG_HOME / "graphs"
        graph_dir.mkdir(parents=True, exist_ok=True)
        graph = graph_dir / f"{stem}.png"
        save_equity_graph(candles, graph)
        print(f"  equity graph saved to {graph}", file=sys.stderr)

    if args.json:
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
    run.add_argument("--start", required=True, metavar="YYYY-MM-DD", help="backtest start date")
    run.add_argument("--end", required=True, metavar="YYYY-MM-DD", help="backtest end date")
    run.add_argument(
        "--capital", type=float, default=10000.0, help="starting capital (default: 10000)"
    )
    run.add_argument("--name", help="name for this run (default: the file name)")
    run.add_argument("--json", action="store_true", help="save the raw result to ~/.hqg/logs and the equity graph to ~/.hqg/graphs")
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
