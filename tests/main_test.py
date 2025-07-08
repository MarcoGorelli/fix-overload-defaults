from visitor import find_overload_default_mismatches
import pytest


@pytest.mark.parametrize(
    "content",
    [
        "from typing import Literal\n"
        "@overload\n"
        "def foo(a: Literal[True]) -> None: ...\n"
        "@overload\n"
        "def foo(a: Literal[False]) -> int: ...\n"
        "def foo(a: bool = False) -> None | int: ...\n",
        "from typing import Literal\n"
        "@overload\n"
        "def foo(*, a: Literal[True]) -> None: ...\n"
        "@overload\n"
        "def foo(*, a: Literal[False]) -> int: ...\n"
        "def foo(*, a: bool = False) -> None | int: ...\n",
        "from typing import Literal as L\n"
        "@overload\n"
        "def foo(a: L[True]) -> None: ...\n"
        "@overload\n"
        "def foo(a: L[False]) -> int: ...\n"
        "def foo(a: bool = False) -> None | int: ...\n",
        "from typing import Literal as L\n"
        "@overload\n"
        "def foo(a: L[True]) -> None: ...\n"
        "@overload\n"
        "def foo(a: L[False]) -> int: ...\n"
        "def foo(a: bool = False) -> None | int: ...\n",
        "from typing import Literal\n"
        "@overload\n"
        "def foo(a: Literal[True] = ...) -> None: ...\n"
        "@overload\n"
        "def foo(a: Literal[False]) -> int: ...\n"
        "def foo(a: bool = False) -> None | int: ...\n",
        "@overload\n"
        "def foo(a: bool) -> None: ...\n"
        "@overload\n"
        "def foo(a: None) -> int: ...\n"
        "def foo(a: bool | None = None) -> None | int: ...\n",
        "@overload\n"
        "def foo(*, a: bool) -> None: ...\n"
        "@overload\n"
        "def foo(*, a: None) -> int: ...\n"
        "def foo(*, a: bool | None = None) -> None | int: ...\n",
        "@overload\n"
        "def foo(*, a: bool, b: typing.Optional[int]) -> None: ...\n"
        "@overload\n"
        "def foo(*, a: None, b: typing.Optional[int]) -> int: ...\n"
        "def foo(*, a: bool | None = None, b: typing.Optional[int]) -> None | int: ...\n",
        "@overload\n"
        "def foo(*, a: bool, b: typing.Optional[int]) -> None: ...\n"
        "@overload\n"
        "def foo(*, a: int | None, b: typing.Optional[int]) -> int: ...\n"
        "def foo(*, a: int | bool | None = None, b: typing.Optional[int]) -> None | int: ...\n",
        "from typing import Literal\n"
        "@overload\n"
        "def foo(a: Literal[True] = ...) -> None: ...\n"
        "@overload\n"
        "def foo(a: Literal[False] = ...) -> int: ...\n"
        "def foo(a: bool = False) -> None | int: ...\n",
        "from typing import Literal\n"
        "@overload\n"
        "def foo(a: Literal[True] = ...) -> None: ...\n"
        "@overload\n"
        "def foo(a: Literal[False] = ...) -> int: ...\n"
        "def foo(a: bool = True) -> None | int: ...\n",
        "from typing import Literal\n"
        "@overload\n"
        "def foo(a: Literal[True] = ...) -> None: ...\n"
        "@overload\n"
        "def foo(a: Literal[False] = ...) -> int: ...\n"
        "def foo(a: bool | None = None) -> None | int: ...\n",
    ],
)
def test_violations(content: str) -> None:
    result = find_overload_default_mismatches(content)
    assert result


@pytest.mark.parametrize(
    "content",
    [
        "@overload\n"
        "def foo(a: Literal[True]) -> None: ...\n"
        "@overload\n"
        "def foo(a: Literal[False] = ...) -> int: ...\n"
        "def foo(a: bool = False) -> None | int: ...\n",
        "@overload\n"
        "def foo(a: bool) -> None: ...\n"
        "@overload\n"
        "def foo(a: None = ...) -> int: ...\n"
        "def foo(a: bool | None = None) -> None | int: ...\n",
        'def foo(a): return 1',
        "from typing import Literal\n"
        "@overload\n"
        "def foo(a: Literal[True]) -> None: ...\n"
        "@overload\n"
        "def foo(a: Literal[False]) -> int: ...\n"
        "def foo(a: bool = False) -> None | int: ...\n"
        "def foo(b: bool = False) -> None | int: ...\n",
        "from typing import Literal\n"
        "@overload\n"
        "def foo(a: Literal[True]) -> None: ...\n"
        "@overload\n"
        "def foo(a) -> int: ...\n"
        "def foo(a: bool = False) -> None | int: ...\n",
        "from typing import Literal\n"
        "@overload\n"
        "def foo(*, a: Literal[True]) -> None: ...\n"
        "@overload\n"
        "def foo(*, a) -> int: ...\n"
        "def foo(*, a: bool = False) -> None | int: ...\n",
    ],
)
def test_passing(content: str) -> None:
    result = find_overload_default_mismatches(content)
    assert not result
