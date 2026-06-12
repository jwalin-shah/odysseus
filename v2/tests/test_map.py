import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.sys_map import map_directory, extract_signatures_from_file

def test_extract_signatures_from_file():
    content = """
class MyClass:
    def my_method(self):
        pass

def my_func(a, b):
    pass
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(content)
        f_path = f.name

    try:
        result = extract_signatures_from_file(f_path)
        assert result == {
            "classes": {
                "MyClass": {"methods": ["my_method"]}
            },
            "functions": ["my_func"]
        }
    finally:
        os.remove(f_path)

def test_map_directory():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, 'test1.py'), 'w') as f:
            f.write("def func1(): pass")
        
        with open(os.path.join(d, 'test2.py'), 'w') as f:
            f.write("class A:\n    def m(self): pass")
            
        result = map_directory(d)
        assert 'test1.py' in result
        assert result['test1.py'] == {'classes': {}, 'functions': ['func1']}
        assert 'test2.py' in result
        assert result['test2.py'] == {'classes': {'A': {'methods': ['m']}}, 'functions': []}
