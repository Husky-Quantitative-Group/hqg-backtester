from typing import Type
from hqg_algorithms import Strategy


class StrategyLoader:
    """Safely loads user-defined Strategy classes from code strings."""

    @classmethod
    def load_code(cls, strategy_code: str) -> Type[Strategy]:
        """Load a Strategy class from a code string without writing to disk."""
        namespace: dict = {}
        try:
            exec(strategy_code, namespace)
        except Exception as e:
            raise ValueError(f"Failed to execute strategy code: {e}")

        for obj in namespace.values():
            if isinstance(obj, type) and issubclass(obj, Strategy) and obj is not Strategy:
                return obj

        raise ValueError("No Strategy subclass found in code")
