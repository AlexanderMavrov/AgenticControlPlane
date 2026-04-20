#!/usr/bin/env python3
"""
scope_context.py — shared helper module for spec scoping.

Single source of truth for all scope operations:
- Resolving active scope (priority chain: CLI --scope → local file → project
  default → "generic" hard-coded fallback).
- Listing available scopes (from _scope-config.json + implicit "generic").
- Mapping scope + domain to spec directory path.
- Loading specs filtered by scope (active_scope + generic by default).
- Writing scope bookkeeping files (user-state, config).

The "generic" scope is RESERVED and always available regardless of config.

Design rules:
- Scope id must match `^[a-z][a-z0-9-]*$` (lowercase, digits, hyphens).
- Scope id IS the directory name under .agent/specs/. No mapping layer.
- _scope-config.json is optional — if absent, only "generic" is available.
- .agent/local/active-scope is gitignored; plain text, one line (the id).

This module has NO external dependencies beyond Python stdlib, so it can be
imported by hooks (fast path) and scripts (business logic) alike.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterable, Optional


# ── Constants ──

GENERIC_SCOPE = "generic"
"""The reserved, implicit scope. Always available. Loaded alongside every
active scope. Cannot be redefined in _scope-config.json."""

SPEC_ROOT = Path(".agent/specs")
"""Root directory for all specs. Files live at:
.agent/specs/<scope>/<domain>/<spec-id>.md"""

SCOPE_CONFIG_PATH = SPEC_ROOT / "_scope-config.json"
"""Project-level scope configuration. Optional; committed to git.
Schema: {"scopes": [{"id": str, "label": str}], "default_active_scope": str?}"""

USER_STATE_DIR = Path(".agent/local")
"""Per-developer state directory. Gitignored. Created on demand."""

ACTIVE_SCOPE_FILE = USER_STATE_DIR / "active-scope"
"""Plain text file containing the active scope id on a single line.
Created by /scope-set; removed by /scope-unset."""

SCOPE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
"""Valid scope id format: lowercase letter start, then lowercase/digits/hyphens.
Enforces 1:1 mapping between id and directory name without any path-escape
concerns (no slashes, no spaces, no uppercase)."""


# ── Exceptions ──

class ScopeError(Exception):
    """Base for all scope-related errors."""


class ScopeNotFoundError(ScopeError):
    """Raised when a scope id does not exist in the current project."""


class InvalidScopeIdError(ScopeError):
    """Raised when a scope id does not match SCOPE_ID_PATTERN."""


class ScopeConfigError(ScopeError):
    """Raised when _scope-config.json is malformed."""


# ── Config I/O ──

def load_scope_config(root: Path = Path(".")) -> dict:
    """Read _scope-config.json. Returns empty config if file is absent.

    Returned shape:
        {"scopes": [{"id": str, "label": str}, ...],
         "default_active_scope": str or None}
    """
    path = root / SCOPE_CONFIG_PATH
    if not path.is_file():
        return {"scopes": [], "default_active_scope": None}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ScopeConfigError(f"Cannot read {path}: {e}") from e
    if not isinstance(data, dict):
        raise ScopeConfigError(f"{path}: expected object, got {type(data).__name__}")
    scopes = data.get("scopes") or []
    if not isinstance(scopes, list):
        raise ScopeConfigError(f"{path}: 'scopes' must be a list")
    return {
        "scopes": scopes,
        "default_active_scope": data.get("default_active_scope"),
    }


def save_scope_config(config: dict, root: Path = Path(".")) -> None:
    """Write _scope-config.json atomically (write to tmp, rename)."""
    path = root / SCOPE_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


def config_exists(root: Path = Path(".")) -> bool:
    """Return True if _scope-config.json exists (project has declared scopes)."""
    return (root / SCOPE_CONFIG_PATH).is_file()


# ── Active scope resolution ──

def read_user_active_scope(root: Path = Path(".")) -> Optional[str]:
    """Read .agent/local/active-scope if it exists; return stripped scope id or None."""
    path = root / ACTIVE_SCOPE_FILE
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def write_user_active_scope(scope_id: str, root: Path = Path(".")) -> None:
    """Persist the user's active scope. Creates parent dir if needed."""
    validate_scope_id(scope_id)
    path = root / ACTIVE_SCOPE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(scope_id + "\n", encoding="utf-8")


def clear_user_active_scope(root: Path = Path(".")) -> bool:
    """Delete .agent/local/active-scope. Returns True if it existed."""
    path = root / ACTIVE_SCOPE_FILE
    if path.is_file():
        path.unlink()
        return True
    return False


def resolve_active_scope(
    cli_scope: Optional[str] = None, root: Path = Path(".")
) -> tuple[str, str]:
    """Resolve the active scope via priority chain.

    Returns (scope_id, source) where source describes where the value came
    from for user-facing display:
      - "cli"                      (CLI --scope flag)
      - "user"                     (.agent/local/active-scope override)
      - "project-default"          (_scope-config.json default_active_scope)
      - "fallback"                 (hard-coded "generic")

    Does NOT validate that the returned scope exists — callers that need
    that guarantee should call validate_scope_exists() afterwards. This
    allows /scope-set to report useful errors ("scope 'foo' does not exist")
    on resolved values too.
    """
    if cli_scope:
        return cli_scope, "cli"

    user_scope = read_user_active_scope(root)
    if user_scope:
        return user_scope, "user"

    config = load_scope_config(root)
    default = config.get("default_active_scope")
    if default:
        return default, "project-default"

    return GENERIC_SCOPE, "fallback"


# ── Scope id validation and existence ──

def validate_scope_id(scope_id: str) -> None:
    """Raise InvalidScopeIdError if scope_id does not match the required format."""
    if not isinstance(scope_id, str) or not SCOPE_ID_PATTERN.match(scope_id):
        raise InvalidScopeIdError(
            f"Invalid scope id '{scope_id}'. "
            f"Must match {SCOPE_ID_PATTERN.pattern} "
            f"(lowercase letter start, then lowercase/digits/hyphens only)."
        )


def get_available_scopes(root: Path = Path(".")) -> list[dict]:
    """Return all available scopes as a list of {id, label, source} dicts.

    Always includes the implicit "generic" scope first. Additional scopes
    come from _scope-config.json.

    `source` is either "implicit" (for generic) or "config" (for declared
    scopes).
    """
    result = [{
        "id": GENERIC_SCOPE,
        "label": "Cross-integration invariants (implicit; always available)",
        "source": "implicit",
    }]
    config = load_scope_config(root)
    seen = {GENERIC_SCOPE}
    for entry in config.get("scopes", []):
        if not isinstance(entry, dict):
            continue
        sid = entry.get("id")
        if not isinstance(sid, str) or sid in seen:
            continue
        result.append({
            "id": sid,
            "label": entry.get("label") or sid,
            "source": "config",
        })
        seen.add(sid)
    return result


def scope_exists(scope_id: str, root: Path = Path(".")) -> bool:
    """Return True if scope_id is available (generic or declared in config)."""
    return any(s["id"] == scope_id for s in get_available_scopes(root))


def validate_scope_exists(scope_id: str, root: Path = Path(".")) -> None:
    """Raise ScopeNotFoundError if scope_id is not available."""
    if not scope_exists(scope_id, root):
        available = ", ".join(s["id"] for s in get_available_scopes(root))
        raise ScopeNotFoundError(
            f"Scope '{scope_id}' not found. Available: {available}."
        )


# ── Scope directory operations ──

def scope_dir(scope_id: str, root: Path = Path(".")) -> Path:
    """Return the path .agent/specs/<scope>/ for a given scope id."""
    validate_scope_id(scope_id)
    return root / SPEC_ROOT / scope_id


def spec_dir_for(scope_id: str, domain: str, root: Path = Path(".")) -> Path:
    """Return the path .agent/specs/<scope>/<domain>/ for a given scope+domain."""
    validate_scope_id(scope_id)
    if not isinstance(domain, str) or not domain:
        raise ValueError(f"Invalid domain: {domain!r}")
    return scope_dir(scope_id, root) / domain


def ensure_scope_dir(scope_id: str, root: Path = Path(".")) -> Path:
    """Create .agent/specs/<scope>/ with empty _index.json and _registry.json.

    Idempotent — if the directory or files already exist, does not overwrite.
    Returns the scope directory path.
    """
    validate_scope_id(scope_id)
    sdir = scope_dir(scope_id, root)
    sdir.mkdir(parents=True, exist_ok=True)

    index_path = sdir / "_index.json"
    if not index_path.is_file():
        with index_path.open("w", encoding="utf-8") as f:
            json.dump({"scope": scope_id, "specs": []}, f, indent=2)
            f.write("\n")

    registry_path = sdir / "_registry.json"
    if not registry_path.is_file():
        with registry_path.open("w", encoding="utf-8") as f:
            json.dump({"scope": scope_id, "mappings": []}, f, indent=2)
            f.write("\n")

    return sdir


# ── Path → scope extraction (for hooks) ──

def scope_from_path(path: str | Path, root: Path = Path(".")) -> Optional[str]:
    """Extract the scope id from a path pointing into .agent/specs/<scope>/...

    Returns None if the path is not under .agent/specs/ or does not have a
    scope segment. Used by scope-write-validator hook to identify the scope
    of a write target.
    """
    try:
        p = Path(path).resolve()
        spec_root_abs = (root / SPEC_ROOT).resolve()
        rel = p.relative_to(spec_root_abs)
    except (ValueError, OSError):
        return None
    parts = rel.parts
    if not parts:
        return None
    candidate = parts[0]
    # The candidate must be a valid scope id. Management files like
    # _scope-config.json live directly under SPEC_ROOT and are not scopes.
    if candidate.startswith("_"):
        return None
    return candidate if SCOPE_ID_PATTERN.match(candidate) else None


# ── Spec loading (scope-aware) ──

def iter_spec_files(
    scopes: Iterable[str], root: Path = Path(".")
) -> Iterable[Path]:
    """Yield all .md spec files under the given scopes' directories.

    Skips management files (names starting with "_"). Includes files at any
    depth under <scope>/ (scopes are typically organized by domain:
    <scope>/<domain>/<id>.md).
    """
    for scope_id in scopes:
        if not scope_exists(scope_id, root):
            continue
        sdir = scope_dir(scope_id, root)
        if not sdir.is_dir():
            continue
        for path in sdir.rglob("*.md"):
            if path.name.startswith("_"):
                continue
            yield path


def resolve_read_scopes(
    active_scope: str, include_generic: bool = True
) -> list[str]:
    """Return the list of scopes to load when reading specs.

    By convention: active scope + generic (unless active IS generic, in which
    case just [generic]). The generic inclusion is what makes cross-integration
    rules applicable in every context.

    For cross-scope queries, callers pass "all" or a comma-separated list at
    a higher level (CLI parsing); this helper handles the normal case.
    """
    if active_scope == GENERIC_SCOPE or not include_generic:
        return [active_scope]
    return [active_scope, GENERIC_SCOPE]


# ── CLI support for skills ──

def format_scope_table(scopes: list[dict]) -> str:
    """Format a list of scope dicts as a human-readable table."""
    if not scopes:
        return "(no scopes)"
    width_id = max(len(s["id"]) for s in scopes)
    width_src = max(len(s.get("source", "")) for s in scopes)
    lines = []
    for s in scopes:
        lines.append(
            f"  {s['id']:<{width_id}}  "
            f"[{s.get('source', ''):<{width_src}}]  "
            f"{s.get('label', '')}"
        )
    return "\n".join(lines)
