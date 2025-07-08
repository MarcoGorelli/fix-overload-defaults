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


def find_overload_default_mismatches(code: str, stub_code: str | None = None) -> list[Any]:
    """Find overload functions where annotation matches default but missing '= ...'."""
    if stub_code:
        stub_tree: ast.Module | None = ast.parse(stub_code)
    else:
        stub_tree = None

    tree = ast.parse(code)

    function_groups: dict[str, Function] = defaultdict(
        lambda: {"overloads": [], "implementation": None}
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            is_overload = any(
                isinstance(decorator, ast.Name) and decorator.id == "overload"
                for decorator in node.decorator_list
            )
            if is_overload:
                function_groups[node.name]["overloads"].append(node)
            else:
                function_groups[node.name]["implementation"] = node

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

    mismatches: list[dict[str, Any]] = []

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
                arg_name = arg.arg
                if arg.annotation is None:
                    continue
                annotation_values = extract_annotation_value(arg.annotation, literal_alias)
                is_last_positional_arg_without_default = i == len(overload_args) - len(overload_defaults) -1
                has_default = i >= len(overload_args) - len(overload_defaults)

                if arg_name in impl_defaults:
                    impl_default = impl_defaults[arg_name]

                    # We can only report a mismatch if this is the last argument which doesn't have a default,
                    # as python doesn't allow for non-default args to follow default ones.
                    # e.g.:
                    #     @overload
                    #     def foo(a: int, b: str)
                    # here we can add a default for `b`, but not for `a`.

                    if impl_default in annotation_values and is_last_positional_arg_without_default:
                        mismatches.append(
                            {
                                "function": func_name,
                                "arg": arg_name,
                                "impl_default": impl_default,
                                "line": overload_func.lineno,
                            }
                        )
                elif has_default and i < len(impl.args.args) - len(impl.args.defaults):
                    mismatches.append(
                        {
                            "function": func_name,
                            "arg": arg_name,
                            "impl_default": '<none>',
                            "line": overload_func.lineno,
                        }
                    )


            # Check keyword-only args in overload
            for i, arg in enumerate(overload_kwonlyargs):
                arg_name = arg.arg
                if arg.annotation is None:
                    continue
                annotation_values = extract_annotation_value(arg.annotation, literal_alias)

                if arg_name in impl_defaults:
                    impl_default = impl_defaults[arg_name]

                    # Check if annotation matches the default value
                    if impl_default in annotation_values:
                        has_default = (
                            overload_kw_defaults
                            and i < len(overload_kw_defaults)
                            and overload_kw_defaults[i] is not None
                        )

                        if not has_default:
                            mismatches.append(
                                {
                                    "function": func_name,
                                    "arg": arg_name,
                                    "impl_default": impl_default,
                                    "line": overload_func.lineno,
                                }
                            )

    return mismatches


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

        mismatches = find_overload_default_mismatches(content, stub_content)

        if mismatches:
            for mismatch in mismatches:
                print(f"{path}:{mismatch['line']} {mismatch['function']}: Arg '{mismatch['arg']}' is missing a default value in the annotation. Hint: add `= ...`")
