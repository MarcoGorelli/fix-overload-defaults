# Fix-overload-defaults

A tool to find some incorrect defaults in Python overloads.

## Installation

For now, just

```console
pip install git+https://github.com/MarcoGorelli/fix-overload-defaults.git
```

## Usage

```console
fix-overload-defaults file.py
```

To run it over a directory of files (say, in a git repository):

```console
git ls-files | grep '\.py$' | xargs fix-overload-defaults
```
