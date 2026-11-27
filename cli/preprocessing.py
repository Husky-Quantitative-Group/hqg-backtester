import ast
from pathlib import Path

class PrependImports(ast.NodeTransformer):
    def __init__(self, working_dir: str) -> None:
        self.working_dir = str(working_dir)
        self.files_seen = set()

    def _should_replace_import(self, node: ast.Import | ast.ImportFrom) -> str | None:
        """ Returns the code for the import, if it exists, otherwise None """
        if isinstance(node, ast.Import):
            # Note: using names[0] means that you can't use a comma separated
            # list to import other files
            p = Path(self.working_dir + '/' + node.names[0].name + '.py')
        elif isinstance(node, ast.ImportFrom):
            p = Path(self.working_dir + '/' + node.module + '.py')
        else:
            return None

        if (p.exists() and p.is_file()):
            if str(p) in self.files_seen:
                # return an newline char because it is non-None, so it will
                # replace the import statement which has already been seen
                return "\n"
            else:
                self.files_seen.add(str(p))

            code = p.read_text().strip()
            return code

        return None

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """
        Replaces ImportFrom with the source code of the file being imported from.
        Note, this will import the entire file, not just the code that is imported.

        i.e.
            from helper import a

        Will inline all of the code in helper.py which may cause visibility issues.
        """
        if (code := self._should_replace_import(node)):

            # parse code to AST
            try:
                # Recursively replaces imports
                tree = ast.parse(code)
                self.visit(tree)
                ast.fix_missing_locations(tree)
            except SyntaxError as e:
                raise ValueError(f"Invalid Python syntax: {e}")

            return tree
        else:
            return node

    def visit_Import(self, node: ast.Import):
        """ Replaces Import with the source code of the file being imported """
        if (code := self._should_replace_import(node)):
            # parse code to AST
            try:
                # Recursively replaces imports
                tree = ast.parse(code)
                self.visit(tree)
                ast.fix_missing_locations(tree)
            except SyntaxError as e:
                raise ValueError(f"Invalid Python syntax: {e}")

            # Note: This means that you can't use a comma separated list to
            # import other files
            class_node = ast.ClassDef(
                name=node.names[0].asname if node.names[0].asname else node.names[0].name,
                bases=[],
                keywords=[],
                body=[tree.body],
                decorator_list=[],
            )
            return class_node
        else:
            return node


def inline_imports(path: Path, code: str) -> str:
    """ Takes code and inlines all files that are imported """
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

