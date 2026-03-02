import ast
from dataclasses import dataclass
from hqg_algorithms import Cadence, BarSize, ExecutionTiming


BARSIZE_MAP = {member.name: member for member in BarSize}
EXECUTION_MAP = {member.name: member for member in ExecutionTiming}

MAX_TICKER_LEN = 12
MAX_UNIVERSE_SIZE = 200


@dataclass(frozen=True)
class StrategyMetadata:
    universe: list[str]
    cadence: Cadence


def extract_metadata(source: str) -> StrategyMetadata:
    """
    Parse strategy source code and extract universe + cadence
    from class variable assignments. No code is executed.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise ValueError(f"Strategy has a syntax error on line {e.lineno}: {e.msg}")

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        universe_node = None
        cadence_node = None

        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            for target in item.targets:
                if not isinstance(target, ast.Name):
                    continue
                if target.id == "universe":
                    universe_node = item.value
                elif target.id == "cadence":
                    cadence_node = item.value

        if universe_node is None:
            continue

        universe = _parse_and_clean_universe(universe_node, node.name)
        cadence = _parse_cadence(cadence_node, node.name) if cadence_node else Cadence()

        return StrategyMetadata(universe=universe, cadence=cadence)

    raise ValueError(
        "No strategy class with 'universe' found. "
        'Define it as a class variable: universe = ["SPY", "IEF"]'
    )


def _parse_and_clean_universe(node: ast.expr, class_name: str) -> list[str]:
    """Extract, validate, and normalize universe from a list literal."""
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError):
        raise ValueError(
            f"{class_name}.universe must be a list literal of ticker strings. "
            f'e.g. universe = ["SPY", "IEF"]'
        )

    if not isinstance(value, list):
        raise ValueError(
            f"{class_name}.universe must be a list, got {type(value).__name__}"
        )

    if len(value) == 0:
        raise ValueError(f"{class_name}.universe must not be empty")

    # validate and normalize
    cleaned = []
    seen = set()
    errors = []

    for i, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(f"  universe[{i}]: expected string, got {type(item).__name__} ({item!r})")
            continue

        ticker = item.strip().upper()

        if not ticker:
            errors.append(f"  universe[{i}]: empty or whitespace-only ticker")
        elif len(ticker) > MAX_TICKER_LEN:
            errors.append(f"  universe[{i}]: '{ticker}' exceeds {MAX_TICKER_LEN} characters")
        elif ticker in seen:
            continue
        else:
            seen.add(ticker)
            cleaned.append(ticker)

    if errors:
        raise ValueError(
            f"{class_name}.universe has invalid tickers:\n" + "\n".join(errors)
        )

    if len(cleaned) > MAX_UNIVERSE_SIZE:
        raise ValueError(
            f"{class_name}.universe has {len(cleaned)} tickers (max {MAX_UNIVERSE_SIZE})"
        )

    return cleaned


def _parse_cadence(node: ast.expr, class_name: str) -> Cadence:
    """Extract cadence from a Cadence(...) call with keyword args."""
    if not isinstance(node, ast.Call):
        raise ValueError(
            f"{class_name}.cadence must be a Cadence(...) call. "
            f"e.g. cadence = Cadence(bar_size=BarSize.DAILY)"
        )

    func = node.func
    func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else None)

    if func_name != "Cadence":
        raise ValueError(
            f"{class_name}.cadence must be a Cadence(...) call, got {func_name}(...)"
        )

    bar_size = BarSize.DAILY
    execution = ExecutionTiming.CLOSE_TO_CLOSE

    for kw in node.keywords:
        attr_str = _resolve_enum_attr(kw.value, class_name)

        if kw.arg == "bar_size":
            if attr_str not in BARSIZE_MAP:
                valid = ", ".join(f"BarSize.{m.name}" for m in BarSize)
                raise ValueError(f"{class_name}.cadence: unknown bar_size '{attr_str}'. Valid: {valid}")
            bar_size = BARSIZE_MAP[attr_str]

        elif kw.arg == "execution":
            if attr_str not in EXECUTION_MAP:
                valid = ", ".join(f"ExecutionTiming.{m.name}" for m in ExecutionTiming)
                raise ValueError(f"{class_name}.cadence: unknown execution '{attr_str}'. Valid: {valid}")
            execution = EXECUTION_MAP[attr_str]

        else:
            raise ValueError(
                f"{class_name}.cadence: unknown argument '{kw.arg}'. "
                f"Valid arguments: bar_size, execution"
            )

    return Cadence(bar_size=bar_size, execution=execution)


def _resolve_enum_attr(node: ast.expr, class_name: str) -> str:
    """Resolve BarSize.DAILY or ExecutionTiming.CLOSE_TO_CLOSE to the attr name."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.attr

    raise ValueError(
        f"{class_name}.cadence arguments must be BarSize.X or ExecutionTiming.Y, "
        f"not variables or function calls. "
        f"e.g. cadence = Cadence(bar_size=BarSize.DAILY, execution=ExecutionTiming.CLOSE_TO_NEXT_OPEN)"
    )