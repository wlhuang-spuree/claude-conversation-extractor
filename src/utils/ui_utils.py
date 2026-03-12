"""Shared UI utilities for HTML generation and navigation."""

from typing import List, Dict, Any, Optional
from .html_utils import escape_html


def is_human_user_message(entry: dict) -> bool:
    """Detect if user message is from human input (not system injection)."""
    if entry.get("type") != "user":
        return False
    content = entry.get("message", {}).get("content")
    if "permissionMode" in entry:
        return True
    if isinstance(content, str):
        return True
    return False


def format_subagent_display(metadata: dict) -> str:
    """Format subagent type/id for display. Returns e.g. 'EXPLORE' or 'a1f2b4f8...'"""
    subagent_type = metadata.get("subagent_type", "")
    agent_id = metadata.get("agent_id", "unknown")
    return subagent_type.upper() if subagent_type else f"{agent_id[:8]}..."


def get_nav_label(msg: dict) -> str:
    """Get sidebar nav label for a message."""
    role = msg.get("role", "")
    metadata = msg.get("metadata", {})

    if role == "user" and metadata.get("is_human"):
        return "👤 User"
    if role == "assistant" and metadata.get("subagent_start"):
        return "🤖 Claude → Subagent"
    if role == "subagent_user":
        disp = format_subagent_display(metadata)
        return f"🤖 Subagent ({disp}) - User"
    if role == "subagent_assistant":
        disp = format_subagent_display(metadata)
        return f"🤖 Subagent ({disp}) - Assistant"

    return {
        "user": "👤 User",
        "assistant": "🤖 Claude",
        "tool_use": "🔧 Tool",
        "tool_result": "📤 Result",
        "system": "ℹ️ System"
    }.get(role, role)


def build_sidebar_nav(conversation: List[Dict]) -> str:
    """
    Build sidebar nav HTML. Filters for: human messages + subagent starts + first assistant per segment.
    Single-pass implementation for efficiency.
    """
    include_first_assistant = True

    parts = []
    expect_first_assistant = False

    # Single-pass: build indices AND HTML simultaneously
    for i, msg in enumerate(conversation):
        role = msg.get("role", "")
        metadata = msg.get("metadata", {})

        # Determine if this message should appear in sidebar
        should_include = False
        if role == "user" and metadata.get("is_human"):
            should_include = True
            expect_first_assistant = include_first_assistant
        elif role == "assistant" and metadata.get("subagent_start"):
            should_include = True
            expect_first_assistant = False
        elif include_first_assistant and role == "assistant" and expect_first_assistant:
            should_include = True
            expect_first_assistant = False

        if should_include:
            label = get_nav_label(msg)
            extra_class = ""
            if role == "user" and metadata.get("is_human"):
                extra_class = " human"
            elif role == "assistant" and metadata.get("subagent_start"):
                extra_class = " subagent-start"

            content = msg.get("content", {})
            text = content.get("text", "") if isinstance(content, dict) else str(content)
            preview = (text or "")[:25].replace("\n", " ").strip()
            display = f"{label} {preview}..." if preview else label

            parts.append(f'<a href="#msg-{i}" class="nav-link{extra_class}" data-msg="msg-{i}">{escape_html(display)}</a>')

    return "\n            ".join(parts)
