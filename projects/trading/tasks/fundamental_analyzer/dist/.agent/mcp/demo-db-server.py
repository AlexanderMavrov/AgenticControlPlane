#!/usr/bin/env python3
"""Demo MCP server: fake database with query and status tools.

Used by the tools-demo example workflow to demonstrate MCP tool
dependencies. Not a real database — returns canned data.

Transport: stdio (JSON-RPC 2.0, newline-delimited)
"""

import json
import sys

# Fake data
TABLES = {
    "users": [
        {"id": 1, "name": "Alice", "role": "admin"},
        {"id": 2, "name": "Bob", "role": "developer"},
        {"id": 3, "name": "Carol", "role": "tester"},
    ],
    "projects": [
        {"id": 1, "name": "Alpha", "status": "active"},
        {"id": 2, "name": "Beta", "status": "planning"},
    ],
}

TOOLS = [
    {
        "name": "query_table",
        "description": "Query a database table. Returns rows as JSON array.",
        "inputSchema": {
            "type": "object",
            "required": ["table"],
            "properties": {
                "table": {"type": "string", "description": "Table name (users, projects)"},
                "limit": {"type": "integer", "description": "Max rows to return (default: all)"},
            },
        },
    },
    {
        "name": "get_status",
        "description": "Get database server status and available tables.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def handle_tool_call(name, arguments):
    if name == "query_table":
        table = arguments.get("table", "")
        limit = arguments.get("limit")
        rows = TABLES.get(table, [])
        if limit and isinstance(limit, int):
            rows = rows[:limit]
        if not rows and table not in TABLES:
            return {"error": f"Unknown table: {table}. Available: {list(TABLES.keys())}"}
        return {"table": table, "rows": rows, "count": len(rows)}
    if name == "get_status":
        return {"status": "ok", "server": "demo-db", "tables": list(TABLES.keys()),
                "total_rows": sum(len(v) for v in TABLES.values())}
    return {"error": f"Unknown tool: {name}"}


def handle_message(msg):
    method = msg.get("method", "")
    msg_id = msg.get("id")
    params = msg.get("params", {})

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "demo-db-server", "version": "1.0.0"},
        }}

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        result = handle_tool_call(name, arguments)
        text = json.dumps(result, indent=2, ensure_ascii=False)
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "content": [{"type": "text", "text": text}],
        }}

    if msg_id is not None:
        return {"jsonrpc": "2.0", "id": msg_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"}}
    return None


def main():
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle_message(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
