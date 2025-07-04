from __future__ import annotations
import ast
import sys
from typing import overload, Any

class NoMatch:
    ...

def extract_annotation_value(annotation: ast.expr) -> Any:
    """Extract the value from a type annotation node."""
    if isinstance(annotation, ast.Constant):
        return annotation.value
    elif isinstance(annotation, ast.Name):
        return annotation.id
    elif isinstance(annotation, ast.Subscript):
        # Handle Literal[value] types
        if (isinstance(annotation.value, ast.Name) and annotation.value.id == 'Literal') or \
           (isinstance(annotation.value, ast.Attribute) and annotation.value.attr == 'Literal'):
            # Extract the literal value
            return extract_annotation_value(annotation.slice)
    return NoMatch()

def find_overload_default_mismatches(code: str) -> list[Any]:
    """Find overload functions where annotation matches default but missing '= ...'."""
    tree = ast.parse(code)
    
    # Dictionary to store function groups by name
    function_groups = {}
    
    # Collect all functions grouped by name
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name not in function_groups:
                function_groups[node.name] = {'overloads': [], 'implementation': None}
            
            # Check if this is an overload
            is_overload = any(
                isinstance(decorator, ast.Name) and decorator.id == 'overload'
                for decorator in node.decorator_list
            )
            
            if is_overload:
                function_groups[node.name]['overloads'].append(node)
            else:
                function_groups[node.name]['implementation'] = node
    
    mismatches = []
    
    # Check each function group
    for func_name, group in function_groups.items():
        if not group['overloads'] or not group['implementation']:
            continue
            
        impl = group['implementation']
        
        # Build mapping of arg_name -> default_value from implementation
        impl_defaults = {}
        args = impl.args.args
        defaults = impl.args.defaults
        
        # Map positional args with defaults
        if defaults:
            for i, default in enumerate(defaults):
                arg_index = len(args) - len(defaults) + i
                if arg_index >= 0 and arg_index < len(args):
                    arg_name = args[arg_index].arg
                    if isinstance(default, ast.Constant):
                        impl_defaults[arg_name] = default.value
        
        # Map keyword-only args with defaults
        kwonlyargs = impl.args.kwonlyargs
        kw_defaults = impl.args.kw_defaults
        if kw_defaults:
            for i, default in enumerate(kw_defaults):
                if default is not None and i < len(kwonlyargs):
                    arg_name = kwonlyargs[i].arg
                    if isinstance(default, ast.Constant):
                        impl_defaults[arg_name] = default.value
        
        # Check each overload
        for overload_func in group['overloads']:
            overload_args = overload_func.args.args
            overload_defaults = overload_func.args.defaults
            overload_kwonlyargs = overload_func.args.kwonlyargs
            overload_kw_defaults = overload_func.args.kw_defaults
            
            # Check positional args in overload
            for i, arg in enumerate(overload_args):
                arg_name = arg.arg
                annotation_value = extract_annotation_value(arg.annotation)
                
                # Check if this arg has a default in the implementation
                if arg_name in impl_defaults:
                    impl_default = impl_defaults[arg_name]
                    
                    # Check if annotation matches the default value
                    if annotation_value == impl_default:
                        # Check if overload has a default for this arg
                        has_default = i >= len(overload_args) - len(overload_defaults)
                        
                        if not has_default:
                            mismatches.append({
                                'function': func_name,
                                'arg': arg_name,
                                'annotation_value': annotation_value,
                                'impl_default': impl_default,
                                'line': overload_func.lineno,
                                'overload_func': overload_func
                            })
            # Check keyword-only args in overload
            for i, arg in enumerate(overload_kwonlyargs):
                arg_name = arg.arg
                annotation_value = extract_annotation_value(arg.annotation)
                
                # Check if this arg has a default in the implementation
                if arg_name in impl_defaults:
                    impl_default = impl_defaults[arg_name]
                    
                    # Check if annotation matches the default value
                    if annotation_value == impl_default:
                        # Check if overload has a default for this kwonly arg
                        has_default = (overload_kw_defaults and i < len(overload_kw_defaults) 
                                     and overload_kw_defaults[i] is not None)
                        
                        if not has_default:
                            mismatches.append({
                                'function': func_name,
                                'arg': arg_name,
                                'annotation_value': annotation_value,
                                'impl_default': impl_default,
                                'line': overload_func.lineno,
                                'overload_func': overload_func
                            })
    
    return mismatches


if __name__ == "__main__":  # pragma: no cover
    for path in sys.argv[1:]:
        with open(path) as fd:
            content = fd.read()
        mismatches = find_overload_default_mismatches(content)

        if mismatches:
            print(f"Found overload mismatches in {path}:")
            for mismatch in mismatches:
                print(f"{path}:{mismatch['line']}")
                print(f"  Function '{mismatch['function']}' at line {mismatch['line']}")
                print(f"    Arg '{mismatch['arg']}' has annotation {mismatch['annotation_value']}")
                print(f"    but implementation default is {mismatch['impl_default']}")
                print()
