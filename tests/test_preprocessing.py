from pathlib import Path

import pytest

from cli.preprocessing import inline_imports


def _run(tmp_path: Path, strategy: str, files: dict[str, str]) -> dict:
    for name, content in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    path = tmp_path / "strategy.py"
    path.write_text(strategy, encoding="utf-8")
    source = inline_imports(path, strategy)

    namespace: dict = {}
    exec(compile(source, str(path), "exec"), namespace)
    return namespace


def test_single_file_is_returned_unchanged(tmp_path):
    strategy = "from math import sqrt\nvalue = sqrt(4)"
    path = tmp_path / "strategy.py"
    path.write_text(strategy, encoding="utf-8")

    assert inline_imports(path, strategy) == strategy


def test_inlines_local_import(tmp_path):
    namespace = _run(
        tmp_path,
        "from helper import foo\nresult = foo()",
        {"helper.py": "def foo():\n    return 42"},
    )
    assert namespace["result"] == 42


def test_inlines_transitive_imports(tmp_path):
    namespace = _run(
        tmp_path,
        "from helper import foo\nresult = foo()",
        {
            "helper.py": "from utils import z\n\ndef foo():\n    return z",
            "utils.py": "z = 7",
        },
    )
    assert namespace["result"] == 7


def test_plain_import_binds_module_namespace(tmp_path):
    namespace = _run(
        tmp_path,
        "import helper\nresult = helper.foo()",
        {"helper.py": "def foo():\n    return 5"},
    )
    assert namespace["result"] == 5


def test_plain_import_alias(tmp_path):
    namespace = _run(
        tmp_path,
        "import helper as h\nresult = h.foo()",
        {"helper.py": "def foo():\n    return 6"},
    )
    assert namespace["result"] == 6


def test_duplicate_imports_are_inlined_once(tmp_path):
    strategy = "from helper import foo\nfrom helper import bar\nresult = foo() + bar()"
    files = {"helper.py": "def foo():\n    return 1\n\ndef bar():\n    return 2"}
    namespace = _run(tmp_path, strategy, files)
    assert namespace["result"] == 3


def test_circular_imports_terminate(tmp_path):
    namespace = _run(
        tmp_path,
        "from a import g\nresult = g()",
        {
            "a.py": "from b import f\n\ndef g():\n    return f()",
            "b.py": "from a import g\n\ndef f():\n    return 11",
        },
    )
    assert namespace["result"] == 11


def test_missing_local_module_is_left_alone(tmp_path):
    strategy = "from hqg_algorithms import Strategy\nvalue = 1"
    path = tmp_path / "strategy.py"
    path.write_text(strategy, encoding="utf-8")

    assert inline_imports(path, strategy) == strategy


def test_empty_strategy_rejected(tmp_path):
    with pytest.raises(ValueError):
        inline_imports(tmp_path / "strategy.py", "   ")


def test_syntax_error_in_helper_reports_path(tmp_path):
    strategy = "from helper import foo"
    (tmp_path / "helper.py").write_text("def foo(:", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid Python syntax:"):
        inline_imports(tmp_path / "strategy.py", strategy)

