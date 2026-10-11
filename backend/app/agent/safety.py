"""Deterministic safety checks, folder whitelisting, and prompt-injection defense."""

import html
import re
from pathlib import Path
from typing import Any


class SecurityViolationError(Exception):
    """Raised when an operation violates agent security constraints."""

    pass


def verify_path_allowed(path_input: str | Path, whitelisted_roots: list[Path]) -> Path:
    """
    Verify that the target path resolves within one of the whitelisted directory roots.
    Protects against directory traversal ('../'), symbolic link escaping, and unauthorized root access.
    """
    if not whitelisted_roots:
        raise SecurityViolationError(
            "No folder whitelist configured. All filesystem access is blocked."
        )

    # Convert to Path and resolve fully (resolves symlinks and '..' components)
    target = Path(path_input).expanduser().resolve()

    for root in whitelisted_roots:
        resolved_root = root.expanduser().resolve()
        try:
            target.relative_to(resolved_root)
            return target
        except ValueError:
            continue

    roots_str = ", ".join(str(r) for r in whitelisted_roots)
    raise SecurityViolationError(
        f"Access denied: path '{target}' is outside whitelisted directories ({roots_str})."
    )


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal or control characters."""
    clean = re.sub(r'[\\/*?:"<>|]', "", filename).strip()
    if clean in ("", ".", ".."):
        raise SecurityViolationError(f"Invalid filename: '{filename}'")
    return clean


def wrap_untrusted_data(
    tool_name: str,
    data: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Wrap untrusted content (files, web results, notes) in explicit XML delimiters.
    Prevents prompt injection attacks from overriding system instructions.
    Neutralizes attempts to close the delimiter within the content itself.
    """
    # Escape any nested closing tags to prevent delimiter escape
    safe_data = data.replace("</untrusted_tool_data>", "&lt;/untrusted_tool_data&gt;")

    meta_attrs = f' source="{tool_name}"'
    if metadata:
        for k, v in metadata.items():
            meta_attrs += f' {k}="{html.escape(str(v))}"'

    return f"<untrusted_tool_data{meta_attrs}>\n" f"{safe_data}\n" f"</untrusted_tool_data>"
