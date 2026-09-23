"""`hqg` command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from hqg_algorithms import validate_strategy

from . import __version__
from .api import API_URL, BacktestClient
from .render import render_logs, render_result, render_validation_errors

def _read_strategy(path: Path) -> str:
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


def _build_payload(args: argparse.Namespace, source: str, name: str) -> dict[str, Any]:
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
    }


def cmd_run(args: argparse.Namespace) -> int:
    path = Path(args.strategy)
    source = _read_strategy(path)
    name = args.name or path.stem

    errors = validate_strategy(source)
    if errors:
        print(render_validation_errors(errors, path.name), file=sys.stderr)
        return 2

    payload = _build_payload(args, source, name)

    client = BacktestClient(API_URL)
    client.health()
    job_id = client.submit(payload)
    print(f"  job {job_id}", file=sys.stderr)

    if args.no_wait:
        print("  submitted; check it with: hqg status " + job_id, file=sys.stderr)
        return 0

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

    if args.json:
        # Raw response on stdout for piping; summary stays on stderr.
        print(summary, file=sys.stderr)
        print(json.dumps(result, indent=2))
    else:
        print(summary)
        if args.verbose and logs:
            print(render_logs(logs))

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    client = BacktestClient(API_URL)
    client.health()
    record = client.get_job(args.job_id)

    if record is None:
        raise RuntimeError(
            f"Job {args.job_id} no longer exists.\n"
            "The service keeps job state in memory; it may have restarted."
        )

    status = record.get("status", "UNKNOWN")
    print(f"  {args.job_id} {status.lower()}", file=sys.stderr)

    if status != "COMPLETED":
        if status in ("FAILED", "CANCELLED"):
            print(f"  {record.get('error') or 'did not complete'}", file=sys.stderr)
            return 1
        return 0

    result = record.get("result") or {}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        params = result.get("parameters", {})
        print(render_result(result, params.get("name", args.job_id), 0.0))
        logs: list[str] = record.get("logs") or []
        if args.verbose and logs:
            print(render_logs(logs))
    return 0


def cmd_cancel(args: argparse.Namespace) -> int:
    client = BacktestClient(API_URL)
    client.health()
    outcome = client.cancel(args.job_id)
    print(f"  job {args.job_id} {outcome}", file=sys.stderr)
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    BacktestClient(API_URL).health()
    print(f"  backtesting service is reachable at {API_URL}", file=sys.stderr)
    return 0


def _build_parser() -> argparse.ArgumentParser:
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
    run.add_argument("--json", action="store_true", help="print the raw result to stdout")
    run.add_argument("--verbose", action="store_true", help="include strategy log output")
    run.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="seconds to wait for the result (default: 600)",
    )
    run.add_argument("--no-wait", action="store_true", help="submit and exit without waiting")
    run.set_defaults(func=cmd_run)

    status = subparsers.add_parser("status", help="check a previously submitted backtest")
    status.add_argument("job_id")
    status.add_argument("--json", action="store_true", help="print the raw result to stdout")
    status.add_argument("--verbose", action="store_true", help="include strategy log output")
    status.set_defaults(func=cmd_status)

    cancel = subparsers.add_parser("cancel", help="cancel a queued backtest")
    cancel.add_argument("job_id")
    cancel.set_defaults(func=cmd_cancel)

    health = subparsers.add_parser("health", help="check that the service is reachable")
    health.set_defaults(func=cmd_health)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:        # the researcher's input was wrong
        print(f"\n  {exc}\n", file=sys.stderr)
        return 2
    except RuntimeError as exc:      # the run or the service failed
        print(f"\n  {exc}\n", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n  interrupted", file=sys.stderr)
        return 130
