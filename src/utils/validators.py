from ..config.settings import settings
import ast

def validate_strategy_code(code: str) -> None:
    """Validate user-provided strategy code for security and correctness."""
    
    if not code or not code.strip():
        raise ValueError("Strategy code cannot be empty")
    
    if len(code) > settings.MAX_MEMORY_KB:
        raise ValueError(f"Strategy code too large (max {settings.MAX_MEMORY_KB}KB)")
    
    # parse code to AST
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Invalid Python syntax: {e}")
    
    # security (TODO: how long will this take?...)
    _check_forbidden_imports(tree)
    _check_forbidden_builtins(tree)
    _check_forbidden_attributes(tree)
    
    # verify Strategy class exists
    _check_strategy_class_exists(tree)


def _check_forbidden_imports(tree: ast.AST) -> None:
    """Check for forbidden import statements."""
    forbidden_modules = {
        'os', 'sys', 'subprocess', 'multiprocessing',
        'threading', 'socket', 'urllib', 'requests',
        'pickle', 'shelve', '__builtin__', 'builtins'
    }
    
    # TODO: add tools
    allowed_modules = {
        'numpy', 'pandas', 'math', 'datetime', 'typing',
        'hqg_algorithms', 'collections', 'itertools'
    }
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split('.')[0]
                if module in forbidden_modules:
                    raise ValueError(f"Import of '{module}' is not allowed")
                if module not in allowed_modules and module not in ['talib']:
                    raise ValueError(f"Import of '{module}' is not allowed. Allowed: {allowed_modules}")
        
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split('.')[0]
                if module in forbidden_modules:
                    raise ValueError(f"Import from '{module}' is not allowed")
                if module not in allowed_modules and module not in ['talib']:
                    raise ValueError(f"Import from '{module}' is not allowed. Allowed: {allowed_modules}")


def _check_forbidden_builtins(tree: ast.AST) -> None:
    """Check for forbidden builtin function calls."""
    forbidden_builtins = {
        'eval', 'exec', 'compile', '__import__',
        'open', 'input', 'breakpoint'
    }
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in forbidden_builtins:
                    raise ValueError(f"Use of '{node.func.id}()' is not allowed")


def _check_forbidden_attributes(tree: ast.AST) -> None:
    """Check for access to forbidden attributes."""
    forbidden_attrs = {
        '__globals__', '__locals__', '__code__',
        '__builtins__', '__dict__', '__class__'
    }
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr in forbidden_attrs:
                raise ValueError(f"Access to '{node.attr}' is not allowed")


def _check_strategy_class_exists(tree: ast.AST) -> None:
    """Verify that code defines a Strategy subclass."""
    has_strategy_class = False
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if it inherits from Strategy
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == 'Strategy':
                    has_strategy_class = True
                    break
                elif isinstance(base, ast.Attribute) and base.attr == 'Strategy':
                    has_strategy_class = True
                    break
    
    if not has_strategy_class:
        raise ValueError("Code must define a class that inherits from Strategy")
