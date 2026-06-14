#!/usr/bin/env python3
"""Review implementations in specified module directories.

For each Python file in the target directories, this script:
  1. Imports the module and runs it as __main__ to execute any self-test.
  2. Counts the public (non-underscore) top-level functions.
  3. Checks whether a corresponding test file exists under tests/.

It then prints a small table summarising the findings.
"""

import importlib.util
import inspect
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

DIRECTORIES = ['bit_ops', 'bit_manipulation', 'number_theory', 'date_math']
TESTS_DIR = 'tests'


def find_python_files(directory):
    """Return sorted list of module names (without .py) found in *directory*."""
    if not os.path.isdir(directory):
        return []
    names = []
    for entry in sorted(os.listdir(directory)):
        if entry.endswith('.py') and entry != '__init__.py':
            names.append(entry[:-3])
    return names


def count_public_functions(module):
    """Count public top-level functions defined in *module*."""
    count = 0
    for name, obj in vars(module).items():
        if name.startswith('_'):
            continue
        if inspect.isfunction(obj):
            count += 1
    return count


def has_test_file(module_name):
    """Return True if tests/test_<module_name>.py exists."""
    return os.path.isfile(os.path.join(TESTS_DIR, f'test_{module_name}.py'))


def run_as_main(file_path):
    """Execute the file as the __main__ module.

    Returns True if the file loaded and ran without raising a real
    exception (SystemExit is treated as success).
    """
    spec = importlib.util.spec_from_file_location('__main__', file_path)
    if spec is None or spec.loader is None:
        return False
    module = importlib.util.module_from_spec(spec)
    sys.modules['__main__'] = module
    try:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            spec.loader.exec_module(module)
    except SystemExit:
        return True
    except Exception:
        return False
    return True


def load_module(directory, module_name):
    """Import a module by file path and return the loaded module object."""
    file_path = os.path.join(directory, f'{module_name}.py')
    full_name = f'{directory}.{module_name}'
    spec = importlib.util.spec_from_file_location(full_name, file_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def main():
    rows = []
    for directory in DIRECTORIES:
        for module_name in find_python_files(directory):
            file_path = os.path.join(directory, f'{module_name}.py')
            module = load_module(directory, module_name)
            functions = count_public_functions(module) if module is not None else 0
            has_tests = has_test_file(module_name)
            self_test_ok = run_as_main(file_path)
            rows.append((
                f'{directory}/{module_name}',
                functions,
                has_tests,
                self_test_ok,
            ))

    headers = ('module', 'functions', 'has_tests', 'self_test_ok')
    if not rows:
        print(' | '.join(headers))
        print('No modules found.')
        return

    str_rows = [(r[0], r[1], r[2], r[3]) for r in rows]
    widths = [
        max(len(headers[0]), max(len(str(r[0])) for r in str_rows)),
        max(len(headers[1]), max(len(str(r[1])) for r in str_rows)),
        max(len(headers[2]), max(len(str(r[2])) for r in str_rows)),
        max(len(headers[3]), max(len(str(r[3])) for r in str_rows)),
    ]

    def fmt(values):
        return ' | '.join(f'{str(v):<{w}}' for v, w in zip(values, widths))

    print(fmt(headers))
    print('-+-'.join('-' * w for w in widths))
    for row in str_rows:
        print(fmt(row))


if __name__ == '__main__':
    main()