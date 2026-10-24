"""Проверить измеримые ограничения Python из перечня нарушений."""

import ast
import io
import re
import tokenize
from pathlib import Path

MAX_LINE = 80
MAX_TEXT_LINE = 120
MAX_FILE = 1000
MAX_FUNCTION = 40
MAX_ARGUMENTS = 7
MAX_COMPLEXITY = 10
SNAKE_CASE = re.compile(r"^_?[a-z][a-z0-9_]*$|^__[a-z]+__$")


class Complexity(ast.NodeVisitor):
    """Оценивать цикломатическую сложность без вложенных функций."""

    def __init__(self):
        """Начать подсчёт с одного линейного пути."""
        self.value = 1

    def visit(self, node):
        """Добавить ветвления, исключения и короткие логические операции."""
        branches = (ast.If, ast.For, ast.AsyncFor, ast.While,
                    ast.IfExp, ast.ExceptHandler)
        if isinstance(node, branches):
            self.value += 1
        if isinstance(node, ast.BoolOp):
            self.value += len(node.values) - 1
        if isinstance(node, ast.comprehension):
            self.value += 1 + len(node.ifs)
        if isinstance(node, ast.Match):
            self.value += max(0, len(node.cases) - 1)
        if not isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            super().visit(node)


def check_function(node, errors):
    """Проверить длину, параметры, имя и ветвления функции."""
    label = f"line {node.lineno}: {node.name}"
    if node.end_lineno - node.lineno + 1 > MAX_FUNCTION:
        errors.append(label + ": function too long")
    args = node.args
    count = len(args.posonlyargs + args.args + args.kwonlyargs)
    count += bool(args.vararg) + bool(args.kwarg)
    if count > MAX_ARGUMENTS:
        errors.append(label + ": too many arguments")
    if not SNAKE_CASE.fullmatch(node.name) and node.name != "setUp":
        errors.append(label + ": function name is not PEP 8")
    counter = Complexity()
    for statement in node.body:
        counter.visit(statement)
    if counter.value > MAX_COMPLEXITY:
        errors.append(label + f": complexity {counter.value}")
    return counter.value


def check_python(path):
    """Проверить документацию, размеры и отсутствие комментариев Python."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    errors, complexities = [], []
    lines = source.splitlines()
    if len(lines) > MAX_FILE:
        errors.append("file too long")
    for number, line in enumerate(lines, start=1):
        if len(line) > MAX_LINE:
            errors.append(f"line {number}: exceeds 80 characters")
    if not ast.get_docstring(tree):
        errors.append("module docstring missing")
    complexities = check_nodes(tree, errors)
    tokens = tokenize.tokenize(io.BytesIO(source.encode()).readline)
    if any(token.type == tokenize.COMMENT for token in tokens):
        errors.append("Python comments instead of docstrings")
    return errors, max(complexities, default=1)


def check_nodes(tree, errors):
    """Проверить документацию и ограничения всех функций и классов."""
    complexities = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if not ast.get_docstring(node):
                errors.append(f"line {node.lineno}: docstring missing")
        if isinstance(node, ast.FunctionDef):
            complexities.append(check_function(node, errors))
    return complexities


def check_text(root):
    """Проверить длины строк документации, JSON и сценариев ОС."""
    errors = []
    for folder in (root, root / "scripts", root / "examples"):
        if not folder.exists():
            continue
        for path in folder.iterdir():
            if path.suffix not in {".md", ".bat", ".sh", ".json", ".txt"}:
                continue
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if len(line) > MAX_TEXT_LINE:
                    errors.append(f"{path.name}:{number}: text line >120")
    return errors


def main():
    """Проверить исходники, тесты и длины текстовых файлов проекта."""
    root = Path(__file__).resolve().parents[1]
    failures, maximum = [], 1
    for folder in ("src", "tests"):
        for path in sorted((root / folder).glob("*.py")):
            errors, complexity = check_python(path)
            maximum = max(maximum, complexity)
            failures.extend(f"{path.relative_to(root)}: {e}" for e in errors)
    failures.extend(check_text(root))
    print("\n".join(failures) if failures else "Style checks passed")
    print(f"Maximum estimated cyclomatic complexity: {maximum}")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
