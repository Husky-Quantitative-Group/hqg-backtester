"""Terminal formatting for backtest results."""

from __future__ import annotations
import asciichartpy
from datetime import datetime
from typing import Any

_LEFT_INDENT = 4
_LABEL_W = 18
_VALUE_W = 10
_GAP = 3
_COL_W = _LEFT_INDENT + _LABEL_W + _VALUE_W
_HEADER_INDENT = 2


def _pct(value: float | None, signed: bool = True, places: int = 1) -> str:
    """Format a decimal fraction as a percentage."""
    if value is None:
        return "—"
    scaled = value * 100.0
    sign = "+" if signed and scaled >= 0 else ""
    return f"{sign}{scaled:.{places}f}%"


def _ratio(value: float | None, places: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{places}f}"


def _money(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "—"
    if value < 0:
        return f"-${abs(value):,.0f}"
    return f"{'+' if signed else ''}${value:,.0f}"


def _headers(left: str, right: str) -> str:
    pad = _COL_W + _GAP - _HEADER_INDENT
    return f"{' ' * _HEADER_INDENT}{left:<{pad}}{right}".rstrip()


def _row(l_label: str, l_value: str, r_label: str = "", r_value: str = "") -> str:
    if l_label:
        left = f"{' ' * _LEFT_INDENT}{l_label:<{_LABEL_W}}{l_value:>{_VALUE_W}}"
    else:
        left = " " * _COL_W
    if not r_label:
        return left.rstrip()
    return f"{left}{' ' * _GAP}{r_label:<{_LABEL_W}}{r_value:>{_VALUE_W}}".rstrip()


def _date(value: Any) -> str:
    text = str(value)
    return text.split("T")[0] if "T" in text else text


def render_result(result: dict[str, Any], source_name: str, elapsed: float) -> str:
    """Build the metrics summary for a completed backtest."""
    metrics = result.get("metrics", {})
    params = result.get("parameters", {})

    header = " · ".join(
        [
            source_name,
            f"{_date(params.get('start_date'))} → {_date(params.get('end_date'))}",
            _money(params.get("starting_equity")),
            f"{elapsed:.1f}s",
        ]
    )

    drawdown = metrics.get("max_drawdown")
    drawdown_display = _pct(-abs(drawdown)) if drawdown is not None else "—"

    lines = [
        "",
        f"  {header}",
        "",
        _headers("Return", "Risk"),
        _row(
            "Total", _pct(metrics.get("total_pct_return")),
            "Max drawdown", drawdown_display,
        ),
        _row(
            "Annualized", _pct(metrics.get("annualized_return")),
            "Ann. volatility", _pct(metrics.get("ann_vol"), signed=False),
        ),
        _row(
            "Net profit", _money(metrics.get("net_profit"), signed=True),
            "VaR 95%", _pct(metrics.get("var_95")),
        ),
        _row(
            "Final equity", _money(metrics.get("final_portfolio_value")),
            "CVaR 95%", _pct(metrics.get("cvar_95")),
        ),
        _row("", "", "Drawdown (bars)", str(metrics.get("max_drawdown_duration", "—"))),
        "",
        _headers("Ratios", "Market"),
        _row(
            "Sharpe", _ratio(metrics.get("sharpe")),
            "Alpha", _pct(metrics.get("alpha")),
        ),
        _row(
            "Sortino", _ratio(metrics.get("sortino")),
            "Beta", _ratio(metrics.get("beta")),
        ),
        _row(
            "Calmar", _ratio(metrics.get("calmar")),
            "Orders", str(metrics.get("total_orders", "—")),
        ),
        _row(
            "PSR", _ratio(metrics.get("psr")),
            "Volume", _money(metrics.get("volume")),
        ),
        "",
    ]
    return "\n".join(lines)


def render_logs(logs: list[str]) -> str:
    if not logs:
        return ""
    body = "\n".join(f"    {line}" for line in logs)
    return f"  Logs\n{body}\n"


def render_equity_graph(candles: list[dict]) -> str:
    """Render ASCII equity curve from candle data."""
    if not candles:
        return ""

    # Extract close prices as equity curve
    closes = [c["close"] for c in candles]
    label_width = max(len(f"{min(closes):,.0f}"), len(f"{max(closes):,.0f}"))

    # Build plot with asciichartpy
    config = {
        "height": 12,
        "format": f"{{:>{label_width},.0f}}",
    }

    plot_str = asciichartpy.plot(closes, config)

    # Format with header and indentation (matching existing pattern)
    lines = ["", "  Equity Graph", ""]
    for line in plot_str.split("\n"):
        lines.append(f"    {line}")

    # x axis: plot body starts after the label and tick columns asciichartpy reserves
    width = len(closes)
    gutter = " " * (label_width + 1)
    first = datetime.fromtimestamp(candles[0]["time"]).strftime("%Y-%m-%d")
    last = datetime.fromtimestamp(candles[-1]["time"]).strftime("%Y-%m-%d")
    lines.append(f"    {gutter}└{'─' * width}")
    lines.append(f"    {gutter} {first} {last:>{max(width - len(first) - 1, 0)}}")
    lines.append("")

    return "\n".join(lines)


def render_validation_errors(errors: list[str], source_name: str) -> str:
    lines = [f"  {source_name} is not a valid strategy:", ""]
    lines.extend(f"    • {error}" for error in errors)
    lines.append("")
    return "\n".join(lines)
