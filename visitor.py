from __future__ import annotations
import ast
import sys
from typing import overload, Any, TypedDict
from collections import defaultdict


class NoMatch: ...


class Function(TypedDict):
    overloads: list[ast.FunctionDef]
    implementation: ast.FunctionDef | None


def extract_annotation_value(annotation: ast.expr) -> Any:
    """
    Extract the value from a type annotation node.

    TODO:
        - instead of extracting a single value, extract a set of values.
          then, check if the default is any of them.
    """
    if isinstance(annotation, ast.Constant):
        return annotation.value
    elif isinstance(annotation, ast.Name):
        return annotation.id
    elif isinstance(annotation, ast.Subscript):
        # Handle Literal[value] types
        if (
            isinstance(annotation.value, ast.Name) and annotation.value.id == "Literal"
        ) or (
            isinstance(annotation.value, ast.Attribute)
            and annotation.value.attr == "Literal"
        ):
            return extract_annotation_value(annotation.slice)
    return NoMatch()


def find_overload_default_mismatches(code: str) -> list[Any]:
    """Find overload functions where annotation matches default but missing '= ...'."""
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

    # todo: `implementation` could be fused by `.py` file, if this is a stub one?
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

            # Check positional args in overload
            for i, arg in enumerate(overload_args):
                arg_name = arg.arg
                if arg.annotation is None:
                    continue
                annotation_value = extract_annotation_value(arg.annotation)

                # Check if this arg has a default in the implementation
                if arg_name in impl_defaults:
                    impl_default = impl_defaults[arg_name]

                    if annotation_value == impl_default:
                        # Check if overload has a default for this arg
                        has_default = i >= len(overload_args) - len(overload_defaults)

                        if not has_default:
                            mismatches.append(
                                {
                                    "function": func_name,
                                    "arg": arg_name,
                                    "annotation_value": annotation_value,
                                    "impl_default": impl_default,
                                    "line": overload_func.lineno,
                                    "overload_func": overload_func,
                                }
                            )

            # Check keyword-only args in overload
            for i, arg in enumerate(overload_kwonlyargs):
                arg_name = arg.arg
                if arg.annotation is None:
                    continue
                annotation_value = extract_annotation_value(arg.annotation)

                if arg_name in impl_defaults:
                    impl_default = impl_defaults[arg_name]

                    # Check if annotation matches the default value
                    if annotation_value == impl_default:
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
                                    "annotation_value": annotation_value,
                                    "impl_default": impl_default,
                                    "line": overload_func.lineno,
                                    "overload_func": overload_func,
                                }
                            )

    return mismatches


if __name__ == "__main__":  # pragma: no cover
    for path in sys.argv[1:]:
        with open(path) as fd:
            content = fd.read()
        mismatches = find_overload_default_mismatches(content)

        if mismatches:
            for mismatch in mismatches:
                print(f"{path}:{mismatch['line']}")
                print(f"  Function '{mismatch['function']}' at line {mismatch['line']}")
                print(
                    f"    Arg '{mismatch['arg']}' has annotation {mismatch['annotation_value']}"
                )
                print(f"    but implementation default is {mismatch['impl_default']}")
                print()
