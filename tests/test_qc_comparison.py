"""
HQG vs QuantConnect Comparison Test Suite
==========================================
Runs each HQG strategy against the backtester API, then compares
every available metric to the static QuantConnect reference data.

Usage:
    python test_qc_comparison.py
    python test_qc_comparison.py --threshold 0.10        # 10% tolerance
    python test_qc_comparison.py --strategy 5             # run only strategy 5
    python test_qc_comparison.py --verbose                # show all fields, not just failures
"""

import requests
import time
import os
import re
import json
import sys
import argparse
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_URL = "http://localhost:8005/api/v1/backtest"
STRATEGY_DIR = os.path.join("test_strategies", "strats")
QC_REFERENCE_FILE = "test_strategies/QC_strats/qc_results.json"
INITIAL_CAPITAL = 10000
DEFAULT_THRESHOLD = 0.05  # 5 %

# ---------------------------------------------------------------------------
# Field mapping: QC reference field -> how to extract from HQG response
#
#   Each entry is (qc_field, hqg_path, comparison_mode)
#
#   hqg_path:  dot-separated path into HQG JSON response
#   comparison_mode:
#       "pct"       – relative % difference |a-b| / max(|a|,|b|) <= threshold
#       "abs"       – absolute difference (for values near zero)
#       "exact_int" – must match exactly (integers like total_orders)
#       "skip"      – log but don't fail (QC-only fields with no HQG equiv)
# ---------------------------------------------------------------------------

FIELD_MAP = [
    # ── Core ratios ──────────────────────────────────────────────────────────
    ("sharpe_ratio",              "metrics.sharpe_ratio",       "pct"),
    ("sortino",                   "metrics.sortino",            "pct"),
    ("alpha",                     "metrics.alpha",              "abs"),
    ("beta",                      "metrics.beta",               "pct"),
    ("psr",                       "metrics.psr",                "pct"),

    # ── Returns & drawdown ───────────────────────────────────────────────────
    ("total_return",              "metrics.total_return",       "pct"),
    ("compounding_annual_return", "metrics.annualized_return",  "pct"),
    ("max_drawdown",              "metrics.max_drawdown",       "pct"),

    # ── Trade statistics ─────────────────────────────────────────────────────
    ("win_rate",                  "metrics.win_rate",           "pct"),
    ("total_orders",              "metrics.total_orders",       "exact_int"),
    ("avg_win",                   "metrics.avg_win",            "pct"),
    ("avg_loss",                  "metrics.avg_loss",           "pct"),

    # ── Equity stats ─────────────────────────────────────────────────────────
    ("end_equity",                "equity_stats.equity",        "pct"),
    ("net_profit",                "equity_stats.net_profit",    "pct"),
    ("total_fees",                "equity_stats.fees",          "abs"),
    ("volume",                    "equity_stats.volume",        "pct"),

    # ── QC-only fields (TODO: implement more) ──────────────────────────────────
    ("loss_rate",                 None,                         "skip"),
    ("expectancy",                None,                         "skip"),
    ("profit_loss_ratio",         None,                         "skip"),
    ("holdings",                  None,                         "skip"),
    ("unrealized",                None,                         "skip"),
    ("annual_standard_deviation", None,                         "skip"),
    ("annual_variance",           None,                         "skip"),
    ("information_ratio",         None,                         "skip"),
    ("tracking_error",            None,                         "skip"),
    ("treynor_ratio",             None,                         "skip"),
    ("estimated_strategy_capacity", None,                       "skip"),
    ("lowest_capacity_asset",     None,                         "skip"),
    ("portfolio_turnover",        None,                         "skip"),
    ("drawdown_recovery",         None,                         "skip"),
    ("net_profit_pct",            None,                         "skip"),
]

# Absolute-mode tolerance (used when values are near zero)
ABS_TOLERANCE = 0.02


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_path(obj: dict, dotpath: str):
    """Resolve a dot-separated path like 'metrics.sharpe_ratio' in a dict."""
    parts = dotpath.split(".")
    current = obj
    for p in parts:
        if isinstance(current, dict) and p in current:
            current = current[p]
        else:
            return None
    return current


def extract_dates(code: str) -> tuple[str, str]:
    start_match = re.search(r'START_DATE\s*=\s*["\'](\d{4}-\d{2}-\d{2})["\']', code)
    end_match = re.search(r'END_DATE\s*=\s*["\'](\d{4}-\d{2}-\d{2})["\']', code)
    start = start_match.group(1) if start_match else "2010-01-01"
    end = end_match.group(1) if end_match else "2026-01-01"
    return f"{start}T00:00:00", f"{end}T00:00:00"


def pct_diff(a: float, b: float) -> float:
    """Symmetric relative difference. Returns 0.0 if both are zero."""
    denom = max(abs(a), abs(b))
    if denom < 1e-12:
        return 0.0
    return abs(a - b) / denom


@dataclass
class FieldResult:
    qc_field: str
    hqg_path: Optional[str]
    mode: str
    qc_value: object
    hqg_value: object = None
    diff: Optional[float] = None
    passed: Optional[bool] = None
    reason: str = ""


@dataclass
class StrategyResult:
    strategy_id: int
    name: str
    filename: str
    api_status: int = 0
    runtime: float = 0.0
    error: Optional[str] = None
    field_results: list = field(default_factory=list)

    @property
    def fields_tested(self):
        return [f for f in self.field_results if f.passed is not None]

    @property
    def fields_passed(self):
        return [f for f in self.field_results if f.passed is True]

    @property
    def fields_failed(self):
        return [f for f in self.field_results if f.passed is False]

    @property
    def fields_skipped(self):
        return [f for f in self.field_results if f.passed is None]


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def run_backtest(filepath: str) -> dict:
    with open(filepath, "r") as f:
        code = f.read()

    start_date, end_date = extract_dates(code)

    payload = {
        "strategy_code": code,
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": INITIAL_CAPITAL,
    }

    start = time.time()
    response = requests.post(API_URL, json=payload)
    elapsed = time.time() - start

    return {
        "status_code": response.status_code,
        "elapsed": elapsed,
        "result": response.json() if response.status_code == 200 else None,
        "error": response.text if response.status_code != 200 else None,
    }


def compare_strategy(
    hqg_response: dict,
    qc_data: dict,
    threshold: float,
) -> list[FieldResult]:
    """Compare all mapped fields between HQG response and QC reference."""
    results = []

    for qc_field, hqg_path, mode in FIELD_MAP:
        qc_val = qc_data.get(qc_field)
        fr = FieldResult(
            qc_field=qc_field,
            hqg_path=hqg_path,
            mode=mode,
            qc_value=qc_val,
        )

        # ── Skip mode ────────────────────────────────────────────────────
        if mode == "skip":
            fr.reason = "QC-only field (no HQG equivalent)"
            results.append(fr)
            continue

        # ── Resolve HQG value ────────────────────────────────────────────
        if hqg_path is None:
            fr.reason = "No HQG path defined"
            results.append(fr)
            continue

        hqg_val = resolve_path(hqg_response, hqg_path)
        fr.hqg_value = hqg_val

        if hqg_val is None:
            fr.passed = False
            fr.reason = "HQG field missing from response"
            results.append(fr)
            continue

        if qc_val is None:
            fr.reason = "QC reference value is null"
            results.append(fr)
            continue

        # ── exact_int ────────────────────────────────────────────────────
        if mode == "exact_int":
            fr.diff = abs(int(hqg_val) - int(qc_val))
            # Allow small tolerance on order count too (timing can differ)
            tolerance_orders = max(1, int(abs(qc_val) * threshold))
            fr.passed = fr.diff <= tolerance_orders
            if not fr.passed:
                fr.reason = f"Δ={fr.diff} (tolerance ±{tolerance_orders})"
            else:
                fr.reason = f"Δ={fr.diff}"
            results.append(fr)
            continue

        # ── abs ──────────────────────────────────────────────────────────
        if mode == "abs":
            fr.diff = abs(float(hqg_val) - float(qc_val))
            fr.passed = fr.diff <= ABS_TOLERANCE
            if not fr.passed:
                fr.reason = f"Δ={fr.diff:.6f} > abs tol {ABS_TOLERANCE}"
            else:
                fr.reason = f"Δ={fr.diff:.6f}"
            results.append(fr)
            continue

        # ── pct (default) ────────────────────────────────────────────────
        if mode == "pct":
            # If both near zero, fall back to absolute
            if max(abs(float(qc_val)), abs(float(hqg_val))) < 1e-6:
                fr.diff = 0.0
                fr.passed = True
                fr.reason = "Both ≈ 0"
            else:
                fr.diff = pct_diff(float(hqg_val), float(qc_val))
                fr.passed = fr.diff <= threshold
                pct_str = f"{fr.diff * 100:.2f}%"
                if not fr.passed:
                    fr.reason = f"{pct_str} > {threshold * 100:.0f}% threshold"
                else:
                    fr.reason = pct_str
            results.append(fr)
            continue

    return results


# ---------------------------------------------------------------------------
# Strategy file <-> QC reference matching
# ---------------------------------------------------------------------------

def match_strategy_file_to_qc(filename: str, qc_strategies: list[dict]) -> Optional[dict]:
    """
    Match a strategy filename like 'strategy_07_sector_rotation_monthly.py'
    to the QC reference entry by extracting the numeric ID.
    """
    m = re.match(r"strategy_(\d+)", filename)
    if not m:
        return None
    sid = int(m.group(1))
    for s in qc_strategies:
        if s["id"] == sid:
            return s
    return None


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_field_table(field_results: list[FieldResult], verbose: bool):
    """Print a table of field comparisons."""
    # Determine which fields to show
    if verbose:
        rows = field_results
    else:
        # Show failures + a count of passes/skips
        rows = [f for f in field_results if f.passed is False]

    if rows:
        hdr = f"    {'Field':<35} {'QC':>14} {'HQG':>14} {'Diff':>10} {'Status':>6}  Reason"
        print(hdr)
        print("    " + "-" * (len(hdr) - 4))
        for fr in rows:
            qc_str = format_val(fr.qc_value)
            hqg_str = format_val(fr.hqg_value)
            diff_str = format_diff(fr.diff, fr.mode)
            status = "PASS" if fr.passed else ("FAIL" if fr.passed is False else "SKIP")
            status_colored = status
            print(f"    {fr.qc_field:<35} {qc_str:>14} {hqg_str:>14} {diff_str:>10} {status_colored:>6}  {fr.reason}")


def format_val(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        if abs(v) >= 1000:
            return f"{v:,.2f}"
        return f"{v:.6f}"
    return str(v)


def format_diff(d, mode) -> str:
    if d is None:
        return "—"
    if mode == "exact_int":
        return f"{int(d)}"
    if mode == "abs":
        return f"{d:.6f}"
    return f"{d * 100:.2f}%"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="HQG vs QC comparison test suite")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help=f"Relative tolerance (default {DEFAULT_THRESHOLD})")
    parser.add_argument("--strategy", type=int, default=None,
                        help="Run only a single strategy by ID")
    parser.add_argument("--verbose", action="store_true",
                        help="Show all fields, not just failures")
    parser.add_argument("--qc-ref", default=QC_REFERENCE_FILE,
                        help=f"Path to QC reference JSON (default {QC_REFERENCE_FILE})")
    parser.add_argument("--strategy-dir", default=STRATEGY_DIR,
                        help=f"Path to HQG strategy files (default {STRATEGY_DIR})")
    parser.add_argument("--api-url", default=API_URL,
                        help=f"Backtest API URL (default {API_URL})")
    args = parser.parse_args()

    threshold = args.threshold
    api_url = args.api_url
    strategy_dir = args.strategy_dir

    # ── Load QC reference ────────────────────────────────────────────────
    if not os.path.isfile(args.qc_ref):
        print(f"ERROR: QC reference file not found: {args.qc_ref}")
        sys.exit(1)

    with open(args.qc_ref) as f:
        qc_data = json.load(f)
    qc_strategies = qc_data["strategies"]

    # ── Discover strategy files ──────────────────────────────────────────
    if not os.path.isdir(strategy_dir):
        print(f"ERROR: Strategy directory not found: {strategy_dir}")
        sys.exit(1)

    files = sorted(f for f in os.listdir(strategy_dir) if f.endswith(".py"))
    if not files:
        print(f"No .py files found in '{strategy_dir}'.")
        sys.exit(1)

    # Filter to single strategy if requested
    if args.strategy is not None:
        files = [f for f in files if re.match(rf"strategy_0*{args.strategy}_", f)]
        if not files:
            print(f"ERROR: No file found for strategy {args.strategy}")
            sys.exit(1)

    # ── Header ───────────────────────────────────────────────────────────
    print()
    print("=" * 95)
    print("  HQG vs QuantConnect  —  Backtest Comparison Test Suite")
    print("=" * 95)
    print(f"  Threshold       : {threshold * 100:.1f}%")
    print(f"  Abs tolerance   : {ABS_TOLERANCE}")
    print(f"  API URL         : {api_url}")
    print(f"  Strategy dir    : {strategy_dir}")
    print(f"  QC reference    : {args.qc_ref}")
    print(f"  Strategies found: {len(files)}")
    print("=" * 95)

    all_results: list[StrategyResult] = []
    total_start = time.time()

    for i, filename in enumerate(files, 1):
        filepath = os.path.join(strategy_dir, filename)
        qc_entry = match_strategy_file_to_qc(filename, qc_strategies)

        if qc_entry is None:
            print(f"\n[{i}/{len(files)}] {filename}  — SKIPPED (no QC reference match)")
            continue

        sid = qc_entry["id"]
        sname = qc_entry["name"]
        sr = StrategyResult(strategy_id=sid, name=sname, filename=filename)

        print(f"\n[{i}/{len(files)}] Strategy {sid}: {sname}")
        print(f"  File   : {filename}")
        print(f"  Period : {qc_entry['start_date']} → {qc_entry['end_date']}")
        print(f"  Cadence: {qc_entry['cadence']}")

        # ── Run HQG backtest ─────────────────────────────────────────────
        try:
            bt = run_backtest(filepath)
        except Exception as e:
            sr.error = str(e)
            print(f"  ERROR  : API request failed: {e}")
            all_results.append(sr)
            continue

        sr.api_status = bt["status_code"]
        sr.runtime = bt["elapsed"]

        print(f"  Status : {bt['status_code']}  ({bt['elapsed']:.2f}s)")

        if bt["result"] is None:
            sr.error = bt["error"][:200] if bt["error"] else "Unknown"
            print(f"  ERROR  : {sr.error}")
            all_results.append(sr)
            continue

        # ── Compare fields ───────────────────────────────────────────────
        sr.field_results = compare_strategy(
            bt["result"], qc_entry["quantconnect"], threshold
        )

        n_tested = len(sr.fields_tested)
        n_pass = len(sr.fields_passed)
        n_fail = len(sr.fields_failed)
        n_skip = len(sr.fields_skipped)

        status_label = "PASS" if n_fail == 0 else "FAIL"
        print(f"  Result : {status_label}  ({n_pass}/{n_tested} passed, {n_fail} failed, {n_skip} skipped)")

        if n_fail > 0 or args.verbose:
            print_field_table(sr.field_results, args.verbose)

        all_results.append(sr)

    # ── Final summary ────────────────────────────────────────────────────
    total_elapsed = time.time() - total_start

    print("\n")
    print("=" * 95)
    print("  FINAL SUMMARY")
    print("=" * 95)

    total_strategies = len(all_results)
    strategies_passed = 0
    strategies_failed = 0
    strategies_error = 0
    total_fields_tested = 0
    total_fields_passed = 0
    total_fields_failed = 0

    hdr = f"  {'ID':<4} {'Name':<40} {'Status':<7} {'Pass':>5} {'Fail':>5} {'Skip':>5} {'Time':>7}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))

    for sr in all_results:
        if sr.error:
            strategies_error += 1
            print(f"  {sr.strategy_id:<4} {sr.name:<40} {'ERROR':<7} {'—':>5} {'—':>5} {'—':>5} {sr.runtime:>6.2f}s")
            continue

        n_pass = len(sr.fields_passed)
        n_fail = len(sr.fields_failed)
        n_skip = len(sr.fields_skipped)
        n_tested = len(sr.fields_tested)

        total_fields_tested += n_tested
        total_fields_passed += n_pass
        total_fields_failed += n_fail

        if n_fail == 0:
            strategies_passed += 1
            status = "PASS"
        else:
            strategies_failed += 1
            status = "FAIL"

        print(f"  {sr.strategy_id:<4} {sr.name:<40} {status:<7} {n_pass:>5} {n_fail:>5} {n_skip:>5} {sr.runtime:>6.2f}s")

    print("  " + "-" * (len(hdr) - 2))
    print(f"  Strategies : {strategies_passed} passed, {strategies_failed} failed, {strategies_error} errors  ({total_strategies} total)")
    print(f"  Fields     : {total_fields_passed}/{total_fields_tested} passed, {total_fields_failed} failed")
    print(f"  Threshold  : {threshold * 100:.1f}%")
    print(f"  Total time : {total_elapsed:.2f}s")
    print()

    # ── Failure detail recap ─────────────────────────────────────────────
    any_failures = [sr for sr in all_results if len(sr.fields_failed) > 0]
    if any_failures:
        print("=" * 95)
        print("  FAILURE DETAILS")
        print("=" * 95)
        for sr in any_failures:
            print(f"\n  Strategy {sr.strategy_id}: {sr.name}")
            for fr in sr.fields_failed:
                qc_str = format_val(fr.qc_value)
                hqg_str = format_val(fr.hqg_value)
                diff_str = format_diff(fr.diff, fr.mode)
                print(f"    {fr.qc_field:<35} QC={qc_str:<14} HQG={hqg_str:<14} diff={diff_str:<10} {fr.reason}")
        print()

    # ── Exit code ────────────────────────────────────────────────────────
    if strategies_failed > 0 or strategies_error > 0:
        sys.exit(1)
    else:
        print("  ALL STRATEGIES WITHIN TOLERANCE ✓")
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()