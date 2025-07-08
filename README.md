# Fix-overload-defaults

A tool and pre-commit hook to find some incorrect defaults in Python overloads.

## Usage

```console
$ fix-overload-defaults file.py
```

To run it over a directory of files (say, in a git repository):

```console
$ git ls-files | grep '\.py$' | xargs fix-overload-defaults
```
