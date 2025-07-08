# The other part of it is...we could find where there's defaults but there shouldn't be?
# That's...a bit harder.
from __future__ import annotations
import os
import ast
import sys
from typing import Any, TypedDict
from collections import defaultdict



class Function(TypedDict):
    overloads: list[ast.FunctionDef]
    implementation: ast.FunctionDef | None


def extract_annotation_value(annotation: ast.expr, literal_alias: str | None) -> set[Any]:
    if isinstance(annotation, ast.Constant):
        return {annotation.value}
    elif isinstance(annotation, ast.Name):
        return {annotation.id}
    elif isinstance(annotation, ast.Subscript):
        # e.g. `a: Literal[True]`
        if (
            isinstance(annotation.value, ast.Name) and annotation.value.id == literal_alias
        ) or (
            isinstance(annotation.value, ast.Attribute)
            and annotation.value.attr == literal_alias
        ):
            return extract_annotation_value(annotation.slice, literal_alias)
    elif isinstance(annotation, ast.BinOp):
        # e.g. `a: True | None`
        return {*extract_annotation_value(annotation.left, literal_alias), *extract_annotation_value(annotation.right, literal_alias)}
    return set()

def find_literal_alias(module: ast.Module) -> str | None:
    for node in ast.walk(module):
        if isinstance(node, ast.ImportFrom) and node.module == 'typing':
            for name in node.names:
                if name.name == 'Literal':
                    return name.asname or 'Literal'
    return None

def report_missing_default(func_name: str, arg: ast.arg, literal_alias: str | None, impl_default: Any) -> dict[str, Any] | None:
    assert arg.annotation is not None
    arg_name = arg.arg
    annotation_values = extract_annotation_value(arg.annotation, literal_alias)

    if impl_default in annotation_values:
        return {
                "function": func_name,
                "arg": arg_name,
                "impl_default": impl_default,
                "line": arg.lineno,
            }
    return None

def report_wrong_default(func_name: str, arg: ast.arg, literal_alias: str | None, impl_default: Any) -> dict[str, Any] | None:
    assert arg.annotation is not None
    arg_name = arg.arg
    annotation_values = extract_annotation_value(arg.annotation, literal_alias)

    # Some hand-written simple cases of incorrect defaults which we can detect.
    if impl_default is False and len(annotation_values) == 1 and list(annotation_values)[0] in {True, None}:
        return { "function": func_name, "arg": arg_name, "impl_default": impl_default, "line": arg.lineno, }
    elif impl_default is True and len(annotation_values) == 1 and list(annotation_values)[0] in {False, None}:
        return {
                "function": func_name,
                "arg": arg_name,
                "impl_default": impl_default,
                "line": arg.lineno,
            }
    elif impl_default is None and len(annotation_values) == 1 and list(annotation_values)[0] in {False, True}:
        return {
                "function": func_name,
                "arg": arg_name,
                "impl_default": impl_default,
                "line": arg.lineno,
            }
    return None


def find_overload_default_mismatches(code: str, stub_code: str | None = None) -> tuple[list[Any], list[Any]]:
    """Find overload functions where annotation matches default but missing '= ...'."""
    if stub_code:
        stub_tree: ast.Module | None = ast.parse(stub_code)
    else:
        stub_tree = None

    tree = ast.parse(code)

    function_groups: dict[str, Function] = defaultdict(
        lambda: {"overloads": [], "implementation": None}
    )

    ambiguous: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            is_overload = any(
                isinstance(decorator, ast.Name) and decorator.id == "overload"
                for decorator in node.decorator_list
            )
            if is_overload:
                function_groups[node.name]["overloads"].append(node)
            else:
                if function_groups[node.name]['implementation'] is not None:
                    ambiguous.add(node.name)
                function_groups[node.name]["implementation"] = node
        
    # If a function is defined multiple times in the same file, don't guess, just
    # ignore it. Keep it safe.
    for name in ambiguous:
        function_groups.pop(name)

    if stub_tree:
        for node in ast.walk(stub_tree):
            if isinstance(node, ast.FunctionDef):
                is_overload = any(
                    isinstance(decorator, ast.Name) and decorator.id == "overload"
                    for decorator in node.decorator_list
                )
                if is_overload:
                    function_groups[node.name]["overloads"].append(node)
        literal_alias = find_literal_alias(stub_tree)
    else:
        literal_alias = find_literal_alias(tree)

    missing_defaults: list[dict[str, Any]] = []
    wrong_defaults: list[dict[str, Any]] = []

    for func_name, group in function_groups.items():
        if not group["overloads"] or not group["implementation"]:
            continue

        impl = group["implementation"]

        impl_defaults: dict[str, Any] = {}
        args = impl.args.args
        defaults = impl.args.defaults

        # ast stores defaults and args in separate lists, so we need
        # to do some gymnastics to match them up...
        if defaults:
            for i, default in enumerate(defaults):
                arg_index = len(args) - len(defaults) + i
                if 0 <= arg_index < len(args):
                    arg_name = args[arg_index].arg
                    if isinstance(default, ast.Constant):
                        impl_defaults[arg_name] = default.value
        
        kwonlyargs = impl.args.kwonlyargs
        kw_defaults = impl.args.kw_defaults
        if kw_defaults:
            for i, default in enumerate(kw_defaults):
                if default is not None:
                    arg_name = kwonlyargs[i].arg
                    if isinstance(default, ast.Constant):
                        impl_defaults[arg_name] = default.value

        for overload_func in group["overloads"]:
            overload_args = overload_func.args.args
            overload_defaults = overload_func.args.defaults
            overload_kwonlyargs = overload_func.args.kwonlyargs
            overload_kw_defaults = overload_func.args.kw_defaults

            for i, arg in enumerate(overload_args):
                if arg.annotation is None:
                    continue
                arg_name = arg.arg
                if arg_name not in impl_defaults:
                    continue

                is_missing_default =  i < len(overload_args) - len(overload_defaults)
                is_last_positional_without_default =  i == len(overload_args) - len(overload_defaults) -1
                if is_last_positional_without_default:
                    if missing_default := report_missing_default(func_name, arg, literal_alias, impl_defaults[arg_name]):
                        missing_defaults.append(missing_default)
                elif not is_missing_default:
                    if wrong_default := report_wrong_default(func_name, arg, literal_alias, impl_defaults[arg_name]):
                        wrong_defaults.append(wrong_default)

            # Check keyword-only args in overload
            for i, arg in enumerate(overload_kwonlyargs):
                arg_name = arg.arg
                if arg.annotation is None:
                    continue
                if arg_name not in impl_defaults:
                    continue

                is_missing_default = i < len(overload_kw_defaults) and overload_kw_defaults[i] is None
                if is_missing_default:
                    if missing_default := report_missing_default(func_name, arg, literal_alias, impl_defaults[arg_name]):
                        missing_defaults.append(missing_default)
                else:
                    if wrong_default := report_wrong_default(func_name, arg, literal_alias, impl_defaults[arg_name]):
                        wrong_defaults.append(wrong_default)

    return missing_defaults, wrong_defaults


if __name__ == "__main__":  # pragma: no cover
    for path in sys.argv[1:]:
        with open(path) as fd:
            content = fd.read()
        stub_file = path.removesuffix('.py') + '.pyi'
        if os.path.exists(stub_file):
            with open(stub_file) as fd:
                stub_content = fd.read()
            path = stub_file
        else:
            stub_content = None

        missing_defaults, wrong_defaults = find_overload_default_mismatches(content, stub_content)

        if missing_defaults:
            for mismatch in missing_defaults:
                print(f"{path}:{mismatch['line']} {mismatch['function']}: Arg '{mismatch['arg']}' is missing a default value in the annotation. Hint: add `= ...`")
        if wrong_defaults:
            for mismatch in wrong_defaults:
                print(f"{path}:{mismatch['line']} {mismatch['function']}: Arg '{mismatch['arg']}' incorrect default values.")
