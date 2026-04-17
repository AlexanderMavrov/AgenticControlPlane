#!/usr/bin/env python3
"""Transform JSON data. Script tool for workflow use.

Usage (via tool server):
  Called with --input=<path> [--operation=enrich|summarize]
  Returns JSON with transformed data.

Operations:
  enrich (default): adds _enriched=true and _field_count
  summarize: returns {"summary": "N fields", "keys": [...]}
"""
import json
import sys


def main():
    input_path = None
    operation = "enrich"
    for arg in sys.argv[1:]:
        if arg.startswith("--input="):
            input_path = arg.split("=", 1)[1]
        elif arg.startswith("--operation="):
            operation = arg.split("=", 1)[1]

    if not input_path:
        print(json.dumps({"error": "Missing --input argument"}))
        sys.exit(1)

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

    if operation == "enrich":
        data["_enriched"] = True
        data["_field_count"] = len(data)
    elif operation == "summarize":
        data = {"summary": f"{len(data)} fields", "keys": list(data.keys())[:10]}

    print(json.dumps(data))


if __name__ == "__main__":
    main()
