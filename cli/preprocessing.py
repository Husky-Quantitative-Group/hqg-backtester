import ast
import os
from pathlib import Path

class PrependImports(ast.NodeTransformer):
    def __init__(self, working_dir: str) -> None:
        self.working_dir = str(working_dir)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """ Replaces ImportFrom with the source code of the file being imported from """
        p = Path(self.working_dir + '/' + node.module + '.py')

        if (p.exists() and not p.is_dir()):
            code = p.read_text()

            if not code or not code.strip():
                # This will remove the import statement
                return None

            # parse code to AST
            try:
                tree = ast.parse(code)
            except SyntaxError as e:
                raise ValueError(f"Invalid Python syntax in {p}: {e}")

            return tree
        else:
            return node

def prepend_imports(path: Path, code: str) -> str:
    """ Takes src_code and preprends all files that are imported """
    if not code or not code.strip():
        raise ValueError("Strategy code cannot be empty")

    # parse code to AST
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Invalid Python syntax: {e}")

    transformer = PrependImports(path.parent)
    new_tree = transformer.visit(tree)

    # Fixes metadata issues with editing the AST
    # such as line numbers used in a stack trace
    ast.fix_missing_locations(new_tree)

    # returns a string that would create
    # the same AST if passed into ast.parse
    return ast.unparse(new_tree)

