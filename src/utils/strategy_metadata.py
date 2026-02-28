import ast
from dataclasses import dataclass
from hqg_algorithms import Cadence, BarSize, ExecutionTiming


BARSIZE_MAP = {attr: member for member in BarSize for attr in (member.name, member.value)}
EXECUTION_MAP = {attr: member for member in ExecutionTiming for attr in (member.name, member.value)}


@dataclass(frozen=True)
class StrategyMetadata:
    universe: list[str]
    cadence: Cadence


def extract_metadata(source: str) -> StrategyMetadata:
    """
    Parse strategy source code and extract universe + cadence
    from class variable assignments.

    Raises ValueError with message on failure.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise ValueError(f"Strategy has a syntax error: {e}")

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        universe = None
        cadence = None

        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            for target in item.targets:
                if not isinstance(target, ast.Name):
                    continue
                if target.id == "universe":
                    universe = _parse_universe(item.value, node.name)
                elif target.id == "cadence":
                    cadence = _parse_cadence(item.value, node.name)

        if universe is not None:
            return StrategyMetadata(
                universe=universe,
                cadence=cadence or Cadence(),
            )

    raise ValueError(
        "No strategy class with 'universe' found. "
        'Define it as a class variable: universe = ["SPY", "IEF"]'
    )


def _parse_universe(node: ast.expr, class_name: str) -> list[str]:
    """Extract universe from a list literal assignment."""
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError):
        raise ValueError(
            f"{class_name}.universe must be a list literal of ticker strings. "
            f'e.g. universe = ["SPY", "IEF"]'
        )

    if not isinstance(value, list) or not all(isinstance(s, str) for s in value):
        raise ValueError(
            f"{class_name}.universe must be a list of strings, "
            f"got {type(value).__name__}"
        )

    if len(value) == 0:
        raise ValueError(f"{class_name}.universe must not be empty")

    return value


def _parse_cadence(node: ast.expr, class_name: str) -> Cadence:
    """Extract cadence from a Cadence(...) call with keyword args."""
    if not isinstance(node, ast.Call):
        raise ValueError(
            f"{class_name}.cadence must be a Cadence(...) call. "
            f"e.g. cadence = Cadence(bar_size=BarSize.DAILY)"
        )

    func = node.func
    func_name = None
    if isinstance(func, ast.Name):
        func_name = func.id
    elif isinstance(func, ast.Attribute):
        func_name = func.attr

    if func_name != "Cadence":
        raise ValueError(
            f"{class_name}.cadence must be a Cadence(...) call, "
            f"got {func_name}(...)"
        )

    bar_size = BarSize.DAILY
    execution = ExecutionTiming.CLOSE_TO_CLOSE

    for kw in node.keywords:
        attr_str = _resolve_enum_attr(kw.value, class_name)

        if kw.arg == "bar_size":
            if attr_str not in BARSIZE_MAP:
                raise ValueError(
                    f"{class_name}.cadence: unknown bar_size '{attr_str}'. "
                    f"Valid: {', '.join(f'BarSize.{m.name}' for m in BarSize)}"
                )
            bar_size = BARSIZE_MAP[attr_str]

        elif kw.arg == "execution":
            if attr_str not in EXECUTION_MAP:
                raise ValueError(
                    f"{class_name}.cadence: unknown execution '{attr_str}'. "
                    f"Valid: {', '.join(f'ExecutionTiming.{m.name}' for m in ExecutionTiming)}"
                )
            execution = EXECUTION_MAP[attr_str]

    return Cadence(bar_size=bar_size, execution=execution)


def _resolve_enum_attr(node: ast.expr, class_name: str) -> str:
    """Resolve BarSize.DAILY or ExecutionTiming.CLOSE_TO_CLOSE to the attr name."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.attr

    raise ValueError(
        f"{class_name}.cadence: arguments must be BarSize.X or ExecutionTiming.Y, "
        f"not variables or function calls. "
        f"e.g. cadence = Cadence(bar_size=BarSize.DAILY, execution=ExecutionTiming.CLOSE_TO_NEXT_OPEN)"
    )