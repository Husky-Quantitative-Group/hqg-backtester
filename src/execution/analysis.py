import ast
import builtins

from ..models.request import BacktestRequest
from . import whitelists


class StaticAnalyzer:
    """
    Static analyzer using Python's AST module to validate user strategy code.
    """

    @classmethod
    def analyze(cls, request: BacktestRequest) -> BacktestRequest:
        """
        Perform static analysis on strategy code.

        """
        code = request.strategy_code

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            request.errors.add(f"Syntax error: {e.msg}", line=e.lineno)
            return request  # can't continue without valid AST

        cls._validate_nodes(tree, request)
        cls._validate_imports(tree, request)
        cls._validate_builtins(tree, request)
        cls._validate_attributes(tree, request)
        cls._validate_strategy_class(tree, request)

        return request

    @classmethod
    def _validate_nodes(cls, tree: ast.AST, request: BacktestRequest) -> None:
        """Ensure all AST nodes are in our whitelist."""
        for node in ast.walk(tree):
            if type(node) not in whitelists.ALLOWED_NODES:
                request.errors.add(
                    f"Disallowed syntax: {type(node).__name__}",
                    line=getattr(node, "lineno", None)
                )

    @classmethod
    def _validate_imports(cls, tree: ast.AST, request: BacktestRequest) -> None:
        """Validate all imports are from allowed modules."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_root = alias.name.split(".")[0]
                    if module_root not in whitelists.ALLOWED_MODULES:
                        request.errors.add(
                            f"Import of '{alias.name}' is not allowed",
                            line=node.lineno
                        )

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_root = node.module.split(".")[0]
                    if module_root not in whitelists.ALLOWED_MODULES:
                        request.errors.add(
                            f"Import from '{node.module}' is not allowed",
                            line=node.lineno
                        )

    @classmethod
    def _validate_builtins(cls, tree: ast.AST, request: BacktestRequest) -> None:
        """Validate builtin function calls."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                name = node.func.id
                if name in whitelists.FORBIDDEN_BUILTINS:
                    request.errors.add(f"Use of '{name}()' is forbidden", line=node.lineno)
                elif name in dir(builtins):
                    if name not in whitelists.ALLOWED_BUILTINS:
                        request.errors.add(f"Builtin '{name}()' is not allowed", line=node.lineno)

    @classmethod
    def _validate_attributes(cls, tree: ast.AST, request: BacktestRequest) -> None:
        """Check for forbidden attribute access."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if node.attr in whitelists.FORBIDDEN_ATTRIBUTES:
                    request.errors.add(
                        f"Access to '{node.attr}' is forbidden",
                        line=node.lineno
                    )

    @classmethod
    def _validate_strategy_class(cls, tree: ast.AST, request: BacktestRequest) -> None:
        """Verify that the code defines a class inheriting from Strategy."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    # class MyStrategy(Strategy)
                    if isinstance(base, ast.Name) and base.id == "Strategy":
                        return
                    # class MyStrategy(hqg_algorithms.Strategy)
                    if isinstance(base, ast.Attribute) and base.attr == "Strategy":
                        return
        request.errors.add("Code must define a class that inherits from Strategy")
