import ast

# ─────────────────────────────────────────────────────────────────────────────
# WHITELISTS
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_MODULES: set[str] = {
    # Math & data
    "numpy",
    "pandas",
    "math",
    "statistics",
    # Technical analysis
    "talib",
    # HQG framework
    "hqg_algorithms",
    # Standard library (safe)
    "datetime",
    "typing",
    "collections",
    "itertools",
    "functools",
    "dataclasses",
    "enum",
    "decimal",
    "fractions",
    "abc",
}

ALLOWED_BUILTINS: set[str] = {
    # Types & constructors
    "int", "float", "str", "bool", "list", "dict", "set", "tuple", "frozenset",
    "bytes", "bytearray", "complex",
    # Iteration & ranges
    "range", "enumerate", "zip", "map", "filter", "reversed", "sorted",
    # Aggregations
    "len", "sum", "min", "max", "abs", "round", "pow",
    "all", "any",
    # Type checking
    "isinstance", "issubclass", "type", "callable",
    "hasattr", "getattr", "setattr", "delattr",
    # Object utilities
    "id", "hash", "repr", "str", "format",
    "iter", "next",
    # Misc safe
    "print", "slice", "object", "super", "property", "staticmethod", "classmethod",
    "divmod", "ord", "chr", "bin", "hex", "oct",
}

ALLOWED_NODES: set[type] = {
    # Module structure
    ast.Module, ast.Interactive, ast.Expression,
    # Statements
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Return,
    ast.Delete, ast.Assign, ast.AugAssign, ast.AnnAssign,
    ast.For, ast.AsyncFor, ast.While, ast.If, ast.With, ast.AsyncWith,
    ast.Raise, ast.Try, ast.Assert, ast.Pass, ast.Break, ast.Continue,
    ast.Expr,
    # Imports (validated separately)
    ast.Import, ast.ImportFrom, ast.alias,
    # Expressions
    ast.BoolOp, ast.NamedExpr, ast.BinOp, ast.UnaryOp, ast.Lambda,
    ast.IfExp, ast.Dict, ast.Set, ast.ListComp, ast.SetComp, ast.DictComp,
    ast.GeneratorExp, ast.Await, ast.Yield, ast.YieldFrom,
    ast.Compare, ast.Call, ast.FormattedValue, ast.JoinedStr,
    ast.Constant, ast.Attribute, ast.Subscript, ast.Starred, ast.Name,
    ast.List, ast.Tuple, ast.Slice,
    # Expression context
    ast.Load, ast.Store, ast.Del,
    # Boolean operators
    ast.And, ast.Or,
    # Binary operators
    ast.Add, ast.Sub, ast.Mult, ast.MatMult, ast.Div, ast.Mod, ast.Pow,
    ast.LShift, ast.RShift, ast.BitOr, ast.BitXor, ast.BitAnd, ast.FloorDiv,
    # Unary operators
    ast.Invert, ast.Not, ast.UAdd, ast.USub,
    # Comparison operators
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot, ast.In, ast.NotIn,
    # Comprehension helpers
    ast.comprehension,
    # Exception handling
    ast.ExceptHandler,
    # Arguments & parameters
    ast.arguments, ast.arg, ast.keyword,
    # Match statement (Python 3.10+)
    ast.Match, ast.match_case, ast.MatchValue, ast.MatchSingleton,
    ast.MatchSequence, ast.MatchMapping, ast.MatchClass, ast.MatchStar,
    ast.MatchAs, ast.MatchOr,
}

# Python 3.12+ nodes
if hasattr(ast, "TypeAlias"):
    ALLOWED_NODES.add(ast.TypeAlias)

# ─────────────────────────────────────────────────────────────────────────────
# BLOCKLISTS
# ─────────────────────────────────────────────────────────────────────────────

FORBIDDEN_ATTRIBUTES: set[str] = {
    # Introspection / code execution
    "__globals__", "__locals__", "__code__", "__builtins__",
    "__dict__", "__class__", "__bases__", "__mro__", "__subclasses__",
    "__init_subclass__", "__set_name__",
    # Frame access
    "__frame__", "__traceback__", "f_globals", "f_locals", "f_code",
    "gi_frame", "gi_code", "cr_frame", "cr_code",
    # Import machinery
    "__loader__", "__spec__", "__path__", "__file__", "__cached__",
    # Dangerous descriptor methods
    "__reduce__", "__reduce_ex__", "__getstate__", "__setstate__",
}

FORBIDDEN_BUILTINS: set[str] = {
    # Code execution
    "eval", "exec", "compile", "__import__",
    # I/O
    "open", "input",
    # Debugging
    "breakpoint", "help",
    # Globals access
    "globals", "locals", "vars", "dir",
    # Memory/object internals
    "memoryview",
}
