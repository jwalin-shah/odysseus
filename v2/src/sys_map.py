"""sys-map: stateless AST repo map CLI (pure stdlib)."""
import argparse
import ast
import json
import os
import sys

def extract_signatures_from_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            content = f.read()
            tree = ast.parse(content, filename=filepath)
        except (SyntaxError, UnicodeDecodeError):
            return None

    classes = {}
    functions = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(item.name)
            classes[node.name] = {"methods": methods}
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)

    return {"classes": classes, "functions": functions}

def map_directory(directory_path):
    result = {}
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                signatures = extract_signatures_from_file(filepath)
                if signatures is not None:
                    # Use relative path as key for better usability
                    rel_path = os.path.relpath(filepath, directory_path)
                    result[rel_path] = signatures
    return result

def main(argv=None):
    parser = argparse.ArgumentParser(prog="sys-map")
    parser.add_argument("--dir", required=True, help="Directory to map")
    parser.add_argument("--format", choices=["json"], default="json")
    args = parser.parse_args(argv)

    tree = map_directory(args.dir)
    print(json.dumps(tree, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
