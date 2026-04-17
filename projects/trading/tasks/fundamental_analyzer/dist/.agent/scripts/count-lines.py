#!/usr/bin/env python3
"""Count lines in a file. Script tool for workflow use.

Usage (via tool server):
  Called with --file_path=<path>
  Returns JSON: {"file": "...", "line_count": N, "char_count": N}
"""
import json
import sys


def main():
    file_path = None
    for arg in sys.argv[1:]:
        if arg.startswith("--file_path="):
            file_path = arg.split("=", 1)[1]

    if not file_path:
        print(json.dumps({"error": "Missing --file_path argument"}))
        sys.exit(1)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        print(json.dumps({
            "file": file_path,
            "line_count": len(lines),
            "char_count": sum(len(l) for l in lines),
        }))
    except FileNotFoundError:
        print(json.dumps({"error": f"File not found: {file_path}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
