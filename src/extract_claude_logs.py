#!/usr/bin/env python3
"""
Extract clean conversation logs from Claude Code's internal JSONL files

This tool parses the undocumented JSONL format used by Claude Code to store
conversations locally in ~/.claude/projects/ and exports them as clean,
readable markdown files.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any


class ClaudeConversationExtractor:
    """Extract and convert Claude Code conversations from JSONL to markdown."""

    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize the extractor with Claude's directory and output location."""
        self.claude_dir = Path.home() / ".claude" / "projects"

        if output_dir:
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
        else:
            # Try multiple possible output directories
            possible_dirs = [
                Path.home() / "Desktop" / "Claude logs",
                Path.home() / "Documents" / "Claude logs",
                Path.home() / "Claude logs",
                Path.cwd() / "claude-logs",
            ]

            # Use the first directory we can create
            for dir_path in possible_dirs:
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    # Test if we can write to it
                    test_file = dir_path / ".test"
                    test_file.touch()
                    test_file.unlink()
                    self.output_dir = dir_path
                    break
                except Exception:
                    continue
            else:
                # Fallback to current directory
                self.output_dir = Path.cwd() / "claude-logs"
                self.output_dir.mkdir(exist_ok=True)

        print(f"📁 Saving logs to: {self.output_dir}")

    def find_sessions(self, project_path: Optional[str] = None) -> List[Path]:
        """Find all JSONL session files, sorted by most recent first."""
        if project_path:
            search_dir = self.claude_dir / project_path
        else:
            search_dir = self.claude_dir

        sessions = []
        if search_dir.exists():
            for jsonl_file in search_dir.rglob("*.jsonl"):
                sessions.append(jsonl_file)
        return sorted(sessions, key=lambda x: x.stat().st_mtime, reverse=True)

    def find_session_by_id(self, session_id: str) -> Optional[Path]:
        """Find a session file by session ID.
        
        Args:
            session_id: Session ID (without .jsonl extension)
        
        Returns:
            Path to the JSONL file if found, None otherwise
        """
        if not self.claude_dir.exists():
            return None
        
        # Search for {session_id}.jsonl
        matches = list(self.claude_dir.rglob(f"{session_id}.jsonl"))
        return matches[0] if matches else None

    def extract_conversation(self, jsonl_path: Path, detailed: bool = False) -> List[Dict[str, str]]:
        """Extract conversation messages from a JSONL file.
        
        Args:
            jsonl_path: Path to the JSONL file
            detailed: If True, include tool use, MCP responses, and system messages
        """
        conversation = []
        # Map tool_use_id to subagent_type for tracking subagent types
        tool_use_to_subagent_type = {}
        # Map tool_use_id to tool name for displaying tool results
        tool_use_to_name = {}

        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())

                        # Extract user messages
                        if entry.get("type") == "user" and "message" in entry:
                            msg = entry["message"]
                            if isinstance(msg, dict) and msg.get("role") == "user":
                                content = msg.get("content", "")
                                rich_content = self._extract_rich_content(content, detailed=detailed)
                                # Fill tool_name in tool_result parts
                                rich_content = self._fill_tool_names(rich_content, tool_use_to_name)
                                
                                # Check if there's actual content
                                if isinstance(rich_content, dict):
                                    text = rich_content.get("text", "")
                                else:
                                    text = str(rich_content)
                                
                                if text and text.strip():
                                    conversation.append(
                                        {
                                            "role": "user",
                                            "content": rich_content,
                                            "timestamp": entry.get("timestamp", ""),
                                        }
                                    )

                        # Extract assistant messages
                        elif entry.get("type") == "assistant" and "message" in entry:
                            msg = entry["message"]
                            if isinstance(msg, dict) and msg.get("role") == "assistant":
                                content = msg.get("content", [])
                                
                                # Track tool uses to extract subagent_type and tool names
                                if isinstance(content, list):
                                    for item in content:
                                        if isinstance(item, dict) and item.get("type") == "tool_use":
                                            tool_id = item.get("id", "")
                                            tool_name = item.get("name", "")
                                            # Map tool_use_id to tool name
                                            if tool_id and tool_name:
                                                tool_use_to_name[tool_id] = tool_name
                                            # Track Task tool for subagent_type
                                            if tool_name == "Task":
                                                tool_input = item.get("input", {})
                                                subagent_type = tool_input.get("subagent_type", "")
                                                if subagent_type:
                                                    tool_use_to_subagent_type[tool_id] = subagent_type
                                
                                rich_content = self._extract_rich_content(content, detailed=detailed)
                                # Fill tool_name in tool_result parts
                                rich_content = self._fill_tool_names(rich_content, tool_use_to_name)
                                
                                # Check if there's actual content
                                if isinstance(rich_content, dict):
                                    text = rich_content.get("text", "")
                                else:
                                    text = str(rich_content)
                                
                                if text and text.strip():
                                    conversation.append(
                                        {
                                            "role": "assistant",
                                            "content": rich_content,
                                            "timestamp": entry.get("timestamp", ""),
                                        }
                                    )
                        
                        # Extract progress entries (subagent output)
                        elif entry.get("type") == "progress":
                            data = entry.get("data", {})
                            progress_type = data.get("type")
                            
                            if progress_type == "agent_progress":
                                # Extract subagent messages
                                message_data = data.get("message", {})
                                if message_data:
                                    msg_type = message_data.get("type")  # "user" or "assistant"
                                    msg = message_data.get("message", {})
                                    agent_id = data.get("agentId", "unknown")
                                    parent_tool_use_id = entry.get("parentToolUseID", "")
                                    
                                    # Get subagent_type from the tool_use mapping
                                    subagent_type = tool_use_to_subagent_type.get(parent_tool_use_id, "")
                                    
                                    if msg_type == "user" and msg.get("role") == "user":
                                        content = msg.get("content", [])
                                        
                                        # Track tool_use in subagent messages
                                        if isinstance(content, list):
                                            for item in content:
                                                if isinstance(item, dict) and item.get("type") == "tool_use":
                                                    tool_id = item.get("id", "")
                                                    tool_name = item.get("name", "")
                                                    if tool_id and tool_name:
                                                        tool_use_to_name[tool_id] = tool_name
                                        
                                        rich_content = self._extract_rich_content(content, detailed=detailed)
                                        # Fill tool_name in tool_result parts
                                        rich_content = self._fill_tool_names(rich_content, tool_use_to_name)
                                        
                                        if isinstance(rich_content, dict):
                                            text = rich_content.get("text", "")
                                        else:
                                            text = str(rich_content)
                                        
                                        if text and text.strip():
                                            conversation.append({
                                                "role": "subagent_user",
                                                "content": rich_content,
                                                "metadata": {
                                                    "agent_id": agent_id,
                                                    "agent_type": "subagent",
                                                    "subagent_type": subagent_type,
                                                    "parent_tool_use_id": parent_tool_use_id
                                                },
                                                "timestamp": message_data.get("timestamp", entry.get("timestamp", ""))
                                            })
                                    elif msg_type == "assistant" and msg.get("role") == "assistant":
                                        content = msg.get("content", [])
                                        
                                        # Track tool_use in subagent messages
                                        if isinstance(content, list):
                                            for item in content:
                                                if isinstance(item, dict) and item.get("type") == "tool_use":
                                                    tool_id = item.get("id", "")
                                                    tool_name = item.get("name", "")
                                                    if tool_id and tool_name:
                                                        tool_use_to_name[tool_id] = tool_name
                                        
                                        rich_content = self._extract_rich_content(content, detailed=detailed)
                                        # Fill tool_name in tool_result parts
                                        rich_content = self._fill_tool_names(rich_content, tool_use_to_name)
                                        
                                        if isinstance(rich_content, dict):
                                            text = rich_content.get("text", "")
                                        else:
                                            text = str(rich_content)
                                        
                                        if text and text.strip():
                                            conversation.append({
                                                "role": "subagent_assistant",
                                                "content": rich_content,
                                                "metadata": {
                                                    "agent_id": agent_id,
                                                    "agent_type": "subagent",
                                                    "subagent_type": subagent_type,
                                                    "parent_tool_use_id": parent_tool_use_id
                                                },
                                                "timestamp": message_data.get("timestamp", entry.get("timestamp", ""))
                                            })
                        
                        # Include tool use and system messages if detailed mode
                        elif detailed:
                            # Extract tool use events
                            if entry.get("type") == "tool_use":
                                tool_data = entry.get("tool", {})
                                tool_name = tool_data.get("name", "unknown")
                                tool_input = tool_data.get("input", {})
                                conversation.append(
                                    {
                                        "role": "tool_use",
                                        "content": f"🔧 Tool: {tool_name}\nInput: {json.dumps(tool_input, indent=2)}",
                                        "timestamp": entry.get("timestamp", ""),
                                    }
                                )
                            
                            # Extract tool results
                            elif entry.get("type") == "tool_result":
                                result = entry.get("result", {})
                                output = result.get("output", "") or result.get("error", "")
                                conversation.append(
                                    {
                                        "role": "tool_result",
                                        "content": f"📤 Result:\n{output}",
                                        "timestamp": entry.get("timestamp", ""),
                                    }
                                )
                            
                            # Extract system messages
                            elif entry.get("type") == "system" and "message" in entry:
                                msg = entry.get("message", "")
                                if msg:
                                    conversation.append(
                                        {
                                            "role": "system",
                                            "content": f"ℹ️ System: {msg}",
                                            "timestamp": entry.get("timestamp", ""),
                                        }
                                    )

                    except json.JSONDecodeError:
                        continue
                    except Exception:
                        # Silently skip problematic entries
                        continue

        except Exception as e:
            print(f"❌ Error reading file {jsonl_path}: {e}")

        return conversation

    def _fill_tool_names(self, content: Union[str, Dict[str, Any]], tool_use_to_name: Dict[str, str]) -> Union[str, Dict[str, Any]]:
        """Fill tool_name in tool_result parts using tool_use_id mapping.
        
        Args:
            content: Content dict or string
            tool_use_to_name: Mapping from tool_use_id to tool name
        
        Returns:
            Content with tool_name filled in tool_result parts
        """
        if isinstance(content, str) or not isinstance(content, dict):
            return content
        
        parts = content.get("parts", [])
        if parts:
            for part in parts:
                if part.get("type") == "tool_result":
                    tool_use_id = part.get("tool_use_id", "")
                    if tool_use_id and not part.get("tool_name"):
                        tool_name = tool_use_to_name.get(tool_use_id, "")
                        if tool_name:
                            part["tool_name"] = tool_name
        
        return content
    
    def _extract_text_content(self, content, detailed: bool = False) -> str:
        """Extract text from various content formats Claude uses (legacy method).
        
        Args:
            content: The content to extract from
            detailed: If True, include tool use blocks and other metadata
        
        Returns:
            Plain text string for backward compatibility
        """
        rich_content = self._extract_rich_content(content, detailed=detailed)
        if isinstance(rich_content, dict):
            return rich_content.get("text", "")
        return str(rich_content)
    
    def _extract_rich_content(self, content, detailed: bool = False) -> Union[str, Dict[str, Any]]:
        """Extract structured content from various formats Claude uses.
        
        Args:
            content: The content to extract from (string, list, or dict)
            detailed: If True, include tool use blocks and other metadata
        
        Returns:
            Either a string (for simple text) or a dict with structure:
            {
                "type": "text" | "rich",
                "text": str,  # Plain text representation for backward compatibility
                "parts": [
                    {"type": "text", "text": str} |
                    {"type": "thinking", "thinking": str} |
                    {"type": "tool_use", "name": str, "input": dict} |
                    {"type": "image", "source": dict, ...} |
                    {"type": "tool_reference", "tool_name": str}
                ]
            }
        """
        if isinstance(content, str):
            return {
                "type": "text",
                "text": content,
                "parts": [{"type": "text", "text": content}]
            }
        elif isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    item_type = item.get("type")
                    if item_type == "text":
                        parts.append({
                            "type": "text",
                            "text": item.get("text", "")
                        })
                    elif item_type == "thinking":
                        parts.append({
                            "type": "thinking",
                            "thinking": item.get("thinking", "")
                        })
                    elif item_type == "tool_use":
                        if detailed:
                            parts.append({
                                "type": "tool_use",
                                "name": item.get("name", "unknown"),
                                "input": item.get("input", {})
                            })
                    elif item_type == "image":
                        source = item.get("source", {})
                        image_data = {
                            "type": "image",
                            "source_type": source.get("type", "unknown")
                        }
                        
                        # Process base64 data
                        if "data" in source:
                            image_data["source"] = source  # Save full source for HTML rendering
                            image_data["has_full_data"] = True
                        
                        # Process dataUrl
                        if "dataUrl" in source:
                            image_data["data_url"] = source["dataUrl"]
                        
                        parts.append(image_data)
                    elif item_type == "tool_reference":
                        parts.append({
                            "type": "tool_reference",
                            "tool_name": item.get("tool_name", "unknown")
                        })
                    elif item_type == "tool_result":
                        # Recursively extract content from tool_result
                        tool_result_content = item.get("content", [])
                        tool_result_extracted = self._extract_rich_content(tool_result_content, detailed=detailed)
                        tool_use_id = item.get("tool_use_id", "")
                        
                        if isinstance(tool_result_extracted, dict):
                            # Extract parts from the tool_result content
                            tool_result_inner_parts = tool_result_extracted.get("parts", [])
                            # Add tool_result wrapper for each inner part
                            for inner_part in tool_result_inner_parts:
                                parts.append({
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "tool_name": None,  # Will be filled later if mapping available
                                    "content": inner_part
                                })
                        else:
                            # Fallback: treat as text
                            parts.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "tool_name": None,  # Will be filled later if mapping available
                                "content": {"type": "text", "text": str(tool_result_extracted)}
                            })
            
            # If only one text part, return simplified format for backward compatibility
            if len(parts) == 1 and parts[0]["type"] == "text":
                return {
                    "type": "text",
                    "text": parts[0]["text"],
                    "parts": parts
                }
            elif len(parts) == 0:
                return {
                    "type": "text",
                    "text": "",
                    "parts": []
                }
            else:
                # Build combined text for backward compatibility
                text_parts = []
                for part in parts:
                    if part["type"] == "text":
                        text_parts.append(part["text"])
                    elif part["type"] == "thinking":
                        text_parts.append(f"\n[Thinking] {part['thinking']}\n")
                    elif part["type"] == "tool_use":
                        text_parts.append(f"\n🔧 Using tool: {part['name']}\n")
                        text_parts.append(f"Input: {json.dumps(part['input'], indent=2, ensure_ascii=False)}\n")
                    elif part["type"] == "image":
                        text_parts.append("\n[Image]\n")
                    elif part["type"] == "tool_reference":
                        text_parts.append(f"\n[Tool Reference] {part['tool_name']}\n")
                    elif part["type"] == "tool_result":
                        tool_use_id = part.get("tool_use_id", "")
                        tool_name = part.get("tool_name", "")
                        tool_display = tool_name if tool_name else f"{tool_use_id[:8]}..."
                        content_part = part.get("content", {})
                        if isinstance(content_part, dict):
                            if content_part.get("type") == "text":
                                text_parts.append(f"\n[Tool Result: {tool_display}]\n{content_part.get('text', '')}\n")
                            elif content_part.get("type") == "image":
                                text_parts.append(f"\n[Tool Result: {tool_display}]\n[Image]\n")
                            else:
                                text_parts.append(f"\n[Tool Result: {tool_display}]\n")
                        else:
                            text_parts.append(f"\n[Tool Result: {tool_display}]\n{str(content_part)}\n")
                
                return {
                    "type": "rich",
                    "text": "\n".join(text_parts),
                    "parts": parts
                }
        else:
            return {
                "type": "text",
                "text": str(content),
                "parts": [{"type": "text", "text": str(content)}]
            }

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters"""
        return (text.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace('"', "&quot;")
                   .replace("'", "&#x27;"))
    
    def _render_content_to_html(self, content: Union[str, Dict[str, Any]]) -> str:
        """Render content to HTML format.
        
        Args:
            content: Can be a string (backward compatible) or structured content dict
        
        Returns:
            HTML formatted string
        """
        if isinstance(content, str):
            # Backward compatible: plain text content
            return self._escape_html(content)
        
        # Structured content
        parts = content.get("parts", [])
        html_parts = []
        
        for part in parts:
            part_type = part.get("type")
            if part_type == "text":
                html_parts.append(f'<div class="content-text">{self._escape_html(part["text"])}</div>')
            elif part_type == "thinking":
                html_parts.append(
                    f'<div class="content-thinking">'
                    f'<div class="thinking-header">Thinking Process</div>'
                    f'<div class="thinking-content">{self._escape_html(part["thinking"])}</div>'
                    f'</div>'
                )
            elif part_type == "tool_use":
                tool_input_json = json.dumps(part["input"], indent=2, ensure_ascii=False)
                html_parts.append(
                    f'<div class="content-tool-use">'
                    f'<div class="tool-name">🔧 {self._escape_html(part["name"])}</div>'
                    f'<pre class="tool-input">{self._escape_html(tool_input_json)}</pre>'
                    f'</div>'
                )
            elif part_type == "image":
                source = part.get("source", {})
                if "data" in source and part.get("has_full_data"):
                    # Display base64 image
                    data_url = f"data:image/jpeg;base64,{source['data']}"
                    html_parts.append(
                        f'<div class="content-image">'
                        f'<img src="{data_url}" alt="Screenshot" style="max-width: 100%; height: auto;" />'
                        f'</div>'
                    )
                elif part.get("data_url"):
                    html_parts.append(
                        f'<div class="content-image">'
                        f'<img src="{self._escape_html(part["data_url"])}" alt="Screenshot" style="max-width: 100%; height: auto;" />'
                        f'</div>'
                    )
                else:
                    html_parts.append('<div class="content-image-placeholder">[Image Data]</div>')
            elif part_type == "tool_reference":
                html_parts.append(
                    f'<div class="content-tool-reference">'
                    f'<span class="tool-ref-label">Tool Reference:</span> '
                    f'<code>{self._escape_html(part["tool_name"])}</code>'
                    f'</div>'
                )
            elif part_type == "tool_result":
                tool_use_id = part.get("tool_use_id", "")
                tool_name = part.get("tool_name", "")
                tool_display = tool_name if tool_name else f"{tool_use_id[:8]}..."
                content_part = part.get("content", {})
                
                html_parts.append(f'<div class="content-tool-result">')
                html_parts.append(f'<div class="tool-result-header">📤 Tool Result: {self._escape_html(tool_display)}</div>')
                
                if isinstance(content_part, dict):
                    content_type = content_part.get("type")
                    if content_type == "text":
                        html_parts.append(f'<div class="tool-result-content">{self._escape_html(content_part.get("text", ""))}</div>')
                    elif content_type == "image":
                        source = content_part.get("source", {})
                        if "data" in source and content_part.get("has_full_data"):
                            data_url = f"data:image/jpeg;base64,{source['data']}"
                            html_parts.append(
                                f'<div class="content-image">'
                                f'<img src="{data_url}" alt="Screenshot" style="max-width: 100%; height: auto;" />'
                                f'</div>'
                            )
                        elif content_part.get("data_url"):
                            html_parts.append(
                                f'<div class="content-image">'
                                f'<img src="{self._escape_html(content_part["data_url"])}" alt="Screenshot" style="max-width: 100%; height: auto;" />'
                                f'</div>'
                            )
                        else:
                            html_parts.append('<div class="content-image-placeholder">[Image Data]</div>')
                    else:
                        html_parts.append(f'<div class="tool-result-content">{self._escape_html(str(content_part))}</div>')
                else:
                    html_parts.append(f'<div class="tool-result-content">{self._escape_html(str(content_part))}</div>')
                
                html_parts.append(f'</div>')
        
        return "\n".join(html_parts) if html_parts else self._escape_html(content.get("text", ""))
    
    def _render_content_to_markdown(self, content: Union[str, Dict[str, Any]]) -> str:
        """Render content to Markdown format.
        
        Args:
            content: Can be a string (backward compatible) or structured content dict
        
        Returns:
            Markdown formatted string
        """
        if isinstance(content, str):
            return content
        
        # Structured content
        parts = content.get("parts", [])
        markdown_parts = []
        
        for part in parts:
            part_type = part.get("type")
            if part_type == "text":
                markdown_parts.append(part["text"])
            elif part_type == "thinking":
                markdown_parts.append(f"\n**Thinking Process:**\n\n```\n{part['thinking']}\n```\n")
            elif part_type == "tool_use":
                markdown_parts.append(f"\n**🔧 Using Tool:** `{part['name']}`\n\n```json\n{json.dumps(part['input'], indent=2, ensure_ascii=False)}\n```\n")
            elif part_type == "image":
                markdown_parts.append("\n**📷 Image**\n\n*[Image data included in conversation]*\n")
            elif part_type == "tool_reference":
                markdown_parts.append(f"\n**Tool Reference:** `{part['tool_name']}`\n")
            elif part_type == "tool_result":
                tool_use_id = part.get("tool_use_id", "")
                tool_name = part.get("tool_name", "")
                tool_display = tool_name if tool_name else f"{tool_use_id[:8]}..."
                content_part = part.get("content", {})
                markdown_parts.append(f"\n**📤 Tool Result: {tool_display}**\n\n")
                
                if isinstance(content_part, dict):
                    content_type = content_part.get("type")
                    if content_type == "text":
                        markdown_parts.append(f"{content_part.get('text', '')}\n")
                    elif content_type == "image":
                        markdown_parts.append("*[Image data included in conversation]*\n")
                    else:
                        markdown_parts.append(f"{str(content_part)}\n")
                else:
                    markdown_parts.append(f"{str(content_part)}\n")
        
        return "\n".join(markdown_parts) if markdown_parts else content.get("text", "")
    
    def display_conversation(self, jsonl_path: Path, detailed: bool = False) -> None:
        """Display a conversation in the terminal with pagination.
        
        Args:
            jsonl_path: Path to the JSONL file
            detailed: If True, include tool use and system messages
        """
        try:
            # Extract conversation
            messages = self.extract_conversation(jsonl_path, detailed=detailed)
            
            if not messages:
                print("❌ No messages found in conversation")
                return
            
            # Get session info
            session_id = jsonl_path.stem
            
            # Clear screen and show header
            print("\033[2J\033[H", end="")  # Clear screen
            print("=" * 60)
            print(f"📄 Viewing: {jsonl_path.parent.name}")
            print(f"Session: {session_id[:8]}...")
            
            # Get timestamp from first message
            first_timestamp = messages[0].get("timestamp", "")
            if first_timestamp:
                try:
                    dt = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))
                    print(f"Date: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                except Exception:
                    pass
            
            print("=" * 60)
            print("↑↓ to scroll • Q to quit • Enter to continue\n")
            
            # Display messages with pagination
            lines_shown = 8  # Header lines
            lines_per_page = 30
            
            for i, msg in enumerate(messages):
                role = msg["role"]
                content = msg["content"]
                
                # Handle structured content
                if isinstance(content, dict):
                    display_content = content.get("text", "")
                else:
                    display_content = str(content)
                
                # Format role display
                if role == "user" or role == "human":
                    print(f"\n{'─' * 40}")
                    print(f"👤 HUMAN:")
                    print(f"{'─' * 40}")
                elif role == "assistant":
                    print(f"\n{'─' * 40}")
                    print(f"🤖 CLAUDE:")
                    print(f"{'─' * 40}")
                elif role == "subagent_user":
                    metadata = msg.get("metadata", {})
                    agent_id = metadata.get("agent_id", "unknown")
                    subagent_type = metadata.get("subagent_type", "")
                    subagent_display = f"{subagent_type.upper()}" if subagent_type else f"{agent_id[:8]}..."
                    print(f"\n{'─' * 40}")
                    print(f"🤖 SUBAGENT ({subagent_display}) USER:")
                    print(f"{'─' * 40}")
                elif role == "subagent_assistant":
                    metadata = msg.get("metadata", {})
                    agent_id = metadata.get("agent_id", "unknown")
                    subagent_type = metadata.get("subagent_type", "")
                    subagent_display = f"{subagent_type.upper()}" if subagent_type else f"{agent_id[:8]}..."
                    print(f"\n{'─' * 40}")
                    print(f"🤖 SUBAGENT ({subagent_display}) ASSISTANT:")
                    print(f"{'─' * 40}")
                elif role == "tool_use":
                    print(f"\n🔧 TOOL USE:")
                elif role == "tool_result":
                    print(f"\n📤 TOOL RESULT:")
                elif role == "system":
                    print(f"\nℹ️ SYSTEM:")
                else:
                    print(f"\n{role.upper()}:")
                
                # Display content (limit very long messages)
                lines = display_content.split('\n')
                max_lines_per_msg = 50
                
                for line_idx, line in enumerate(lines[:max_lines_per_msg]):
                    # Wrap very long lines
                    if len(line) > 100:
                        line = line[:97] + "..."
                    print(line)
                    lines_shown += 1
                    
                    # Check if we need to paginate
                    if lines_shown >= lines_per_page:
                        response = input("\n[Enter] Continue • [Q] Quit: ").strip().upper()
                        if response == "Q":
                            print("\n👋 Stopped viewing")
                            return
                        # Clear screen for next page
                        print("\033[2J\033[H", end="")
                        lines_shown = 0
                
                if len(lines) > max_lines_per_msg:
                    print(f"... [{len(lines) - max_lines_per_msg} more lines truncated]")
                    lines_shown += 1
            
            print("\n" + "=" * 60)
            print("📄 End of conversation")
            print("=" * 60)
            input("\nPress Enter to continue...")
            
        except Exception as e:
            print(f"❌ Error displaying conversation: {e}")
            input("\nPress Enter to continue...")

    def save_as_markdown(
        self, conversation: List[Dict[str, str]], session_id: str
    ) -> Optional[Path]:
        """Save conversation as clean markdown file."""
        if not conversation:
            return None

        # Get timestamp from first message
        first_timestamp = conversation[0].get("timestamp", "")
        if first_timestamp:
            try:
                # Parse ISO timestamp
                dt = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M:%S")
            except Exception:
                date_str = datetime.now().strftime("%Y-%m-%d")
                time_str = ""
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")
            time_str = ""

        filename = f"claude-conversation-{date_str}-{session_id[:8]}.md"
        output_path = self.output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# Claude Conversation Log\n\n")
            f.write(f"Session ID: {session_id}\n")
            f.write(f"Date: {date_str}")
            if time_str:
                f.write(f" {time_str}")
            f.write("\n\n---\n\n")

            for msg in conversation:
                role = msg["role"]
                content = msg["content"]
                
                # Handle structured content
                if isinstance(content, dict):
                    display_content = self._render_content_to_markdown(content)
                else:
                    display_content = str(content)
                
                if role == "user":
                    f.write("## 👤 User\n\n")
                    f.write(f"{display_content}\n\n")
                elif role == "assistant":
                    f.write("## 🤖 Claude\n\n")
                    f.write(f"{display_content}\n\n")
                elif role == "subagent_user":
                    metadata = msg.get("metadata", {})
                    agent_id = metadata.get("agent_id", "unknown")
                    subagent_type = metadata.get("subagent_type", "")
                    subagent_display = f"{subagent_type.upper()}" if subagent_type else f"{agent_id[:8]}..."
                    f.write(f"## 🤖 Subagent ({subagent_display}) - User\n\n")
                    f.write(f"{display_content}\n\n")
                elif role == "subagent_assistant":
                    metadata = msg.get("metadata", {})
                    agent_id = metadata.get("agent_id", "unknown")
                    subagent_type = metadata.get("subagent_type", "")
                    subagent_display = f"{subagent_type.upper()}" if subagent_type else f"{agent_id[:8]}..."
                    f.write(f"## 🤖 Subagent ({subagent_display}) - Assistant\n\n")
                    f.write(f"{display_content}\n\n")
                elif role == "tool_use":
                    f.write("### 🔧 Tool Use\n\n")
                    f.write(f"{display_content}\n\n")
                elif role == "tool_result":
                    f.write("### 📤 Tool Result\n\n")
                    f.write(f"{display_content}\n\n")
                elif role == "system":
                    f.write("### ℹ️ System\n\n")
                    f.write(f"{display_content}\n\n")
                else:
                    f.write(f"## {role}\n\n")
                    f.write(f"{display_content}\n\n")
                f.write("---\n\n")

        return output_path
    
    def save_as_json(
        self, conversation: List[Dict[str, str]], session_id: str
    ) -> Optional[Path]:
        """Save conversation as JSON file."""
        if not conversation:
            return None

        # Get timestamp from first message
        first_timestamp = conversation[0].get("timestamp", "")
        if first_timestamp:
            try:
                dt = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = datetime.now().strftime("%Y-%m-%d")
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")

        filename = f"claude-conversation-{date_str}-{session_id[:8]}.json"
        output_path = self.output_dir / filename

        # Create JSON structure
        output = {
            "session_id": session_id,
            "date": date_str,
            "message_count": len(conversation),
            "messages": conversation
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        return output_path
    
    def save_as_html(
        self, conversation: List[Dict[str, str]], session_id: str
    ) -> Optional[Path]:
        """Save conversation as HTML file with syntax highlighting."""
        if not conversation:
            return None

        # Get timestamp from first message
        first_timestamp = conversation[0].get("timestamp", "")
        if first_timestamp:
            try:
                dt = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M:%S")
            except Exception:
                date_str = datetime.now().strftime("%Y-%m-%d")
                time_str = ""
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")
            time_str = ""

        filename = f"claude-conversation-{date_str}-{session_id[:8]}.html"
        output_path = self.output_dir / filename

        # HTML template with modern styling
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Conversation - {session_id[:8]}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            margin: 0 0 10px 0;
        }}
        .metadata {{
            color: #666;
            font-size: 0.9em;
        }}
        .message {{
            background: white;
            padding: 15px 20px;
            margin-bottom: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .user {{
            border-left: 4px solid #3498db;
        }}
        .assistant {{
            border-left: 4px solid #2ecc71;
        }}
        .tool_use {{
            border-left: 4px solid #f39c12;
            background: #fffbf0;
        }}
        .tool_result {{
            border-left: 4px solid #e74c3c;
            background: #fff5f5;
        }}
        .system {{
            border-left: 4px solid #95a5a6;
            background: #f8f9fa;
        }}
        .subagent_user, .subagent_assistant {{
            border-left: 4px solid #9b59b6;
            background: #f8f4ff;
        }}
        .role {{
            font-weight: bold;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
        }}
        .content {{
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .content-text {{
            margin: 5px 0;
        }}
        .content-thinking {{
            background: #f0f7ff;
            border-left: 3px solid #4a90e2;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .thinking-header {{
            font-weight: bold;
            color: #2c5aa0;
            margin-bottom: 5px;
            font-size: 0.9em;
        }}
        .thinking-content {{
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            color: #333;
        }}
        .content-tool-use {{
            background: #fffbf0;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .tool-name {{
            font-weight: bold;
            color: #856404;
            margin-bottom: 5px;
        }}
        .tool-input {{
            background: #f4f4f4;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
            margin: 0;
        }}
        .content-image {{
            margin: 10px 0;
            text-align: center;
        }}
        .content-image img {{
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .content-image-placeholder {{
            background: #f4f4f4;
            padding: 20px;
            border-radius: 4px;
            text-align: center;
            color: #666;
            font-style: italic;
        }}
        .content-tool-reference {{
            background: #fff9e6;
            padding: 8px;
            border-radius: 4px;
            margin: 5px 0;
        }}
        .tool-ref-label {{
            font-weight: bold;
            color: #856404;
        }}
        .content-tool-result {{
            background: #fff5f5;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
            border-left: 3px solid #e74c3c;
        }}
        .tool-result-header {{
            font-weight: bold;
            color: #c0392b;
            margin-bottom: 5px;
            font-size: 0.9em;
        }}
        .tool-result-content {{
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            color: #333;
        }}
        pre {{
            background: #f4f4f4;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Claude Conversation Log</h1>
        <div class="metadata">
            <p>Session ID: {session_id}</p>
            <p>Date: {date_str} {time_str}</p>
            <p>Messages: {len(conversation)}</p>
        </div>
    </div>
"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            
            for msg in conversation:
                role = msg["role"]
                content = msg["content"]
                
                # Render content to HTML
                rendered_content = self._render_content_to_html(content)
                
                # Determine role display
                if role == "subagent_user":
                    metadata = msg.get("metadata", {})
                    agent_id = metadata.get("agent_id", "unknown")
                    subagent_type = metadata.get("subagent_type", "")
                    subagent_display = f"{subagent_type.upper()}" if subagent_type else f"{agent_id[:8]}..."
                    role_display = f"🤖 Subagent ({subagent_display}) - User"
                elif role == "subagent_assistant":
                    metadata = msg.get("metadata", {})
                    agent_id = metadata.get("agent_id", "unknown")
                    subagent_type = metadata.get("subagent_type", "")
                    subagent_display = f"{subagent_type.upper()}" if subagent_type else f"{agent_id[:8]}..."
                    role_display = f"🤖 Subagent ({subagent_display}) - Assistant"
                else:
                    role_display = {
                        "user": "👤 User",
                        "assistant": "🤖 Claude",
                        "tool_use": "🔧 Tool Use",
                        "tool_result": "📤 Tool Result",
                        "system": "ℹ️ System"
                    }.get(role, role)
                
                f.write(f'    <div class="message {role}">\n')
                f.write(f'        <div class="role">{role_display}</div>\n')
                f.write(f'        <div class="content">{rendered_content}</div>\n')
                f.write(f'    </div>\n')
            
            f.write("\n</body>\n</html>")

        return output_path

    def save_conversation(
        self, conversation: List[Dict[str, str]], session_id: str, format: str = "markdown"
    ) -> Optional[Path]:
        """Save conversation in the specified format.
        
        Args:
            conversation: The conversation data
            session_id: Session identifier
            format: Output format ('markdown', 'json', 'html')
        """
        if format == "markdown":
            return self.save_as_markdown(conversation, session_id)
        elif format == "json":
            return self.save_as_json(conversation, session_id)
        elif format == "html":
            return self.save_as_html(conversation, session_id)
        else:
            print(f"❌ Unsupported format: {format}")
            return None

    def get_conversation_preview(self, session_path: Path) -> Tuple[str, int]:
        """Get a preview of the conversation's first real user message and message count."""
        try:
            first_user_msg = ""
            msg_count = 0
            
            with open(session_path, 'r', encoding='utf-8') as f:
                for line in f:
                    msg_count += 1
                    if not first_user_msg:
                        try:
                            data = json.loads(line)
                            # Check for user message
                            if data.get("type") == "user" and "message" in data:
                                msg = data["message"]
                                if msg.get("role") == "user":
                                    content = msg.get("content", "")
                                    
                                    # Handle list content (common format in Claude JSONL)
                                    if isinstance(content, list):
                                        for item in content:
                                            if isinstance(item, dict) and item.get("type") == "text":
                                                text = item.get("text", "").strip()
                                                
                                                # Skip tool results
                                                if text.startswith("tool_use_id"):
                                                    continue
                                                
                                                # Skip interruption messages
                                                if "[Request interrupted" in text:
                                                    continue
                                                
                                                # Skip Claude's session continuation messages
                                                if "session is being continued" in text.lower():
                                                    continue
                                                
                                                # Remove XML-like tags (command messages, etc)
                                                import re
                                                text = re.sub(r'<[^>]+>', '', text).strip()
                                                
                                                # Skip command outputs  
                                                if "is running" in text and "…" in text:
                                                    continue
                                                
                                                # Handle image references - extract text after them
                                                if text.startswith("[Image #"):
                                                    parts = text.split("]", 1)
                                                    if len(parts) > 1:
                                                        text = parts[1].strip()
                                                
                                                # If we have real user text, use it
                                                if text and len(text) > 3:  # Lower threshold to catch "hello"
                                                    first_user_msg = text[:100].replace('\n', ' ')
                                                    break
                                    
                                    # Handle string content (less common but possible)
                                    elif isinstance(content, str):
                                        import re
                                        content = content.strip()
                                        
                                        # Remove XML-like tags
                                        content = re.sub(r'<[^>]+>', '', content).strip()
                                        
                                        # Skip command outputs
                                        if "is running" in content and "…" in content:
                                            continue
                                        
                                        # Skip Claude's session continuation messages
                                        if "session is being continued" in content.lower():
                                            continue
                                        
                                        # Skip tool results and interruptions
                                        if not content.startswith("tool_use_id") and "[Request interrupted" not in content:
                                            if content and len(content) > 3:  # Lower threshold to catch short messages
                                                first_user_msg = content[:100].replace('\n', ' ')
                        except json.JSONDecodeError:
                            continue
                            
            return first_user_msg or "No preview available", msg_count
        except Exception as e:
            return f"Error: {str(e)[:30]}", 0

    def list_recent_sessions(self, limit: int = None) -> List[Path]:
        """List recent sessions with details."""
        sessions = self.find_sessions()

        if not sessions:
            print("❌ No Claude sessions found in ~/.claude/projects/")
            print("💡 Make sure you've used Claude Code and have conversations saved.")
            return []

        print(f"\n📚 Found {len(sessions)} Claude sessions:\n")
        print("=" * 80)

        # Show all sessions if no limit specified
        sessions_to_show = sessions[:limit] if limit else sessions
        for i, session in enumerate(sessions_to_show, 1):
            # Clean up project name (remove hyphens, make readable)
            project = session.parent.name.replace('-', ' ').strip()
            if project.startswith("Users"):
                project = "~/" + "/".join(project.split()[2:]) if len(project.split()) > 2 else "Home"
            
            session_id = session.stem
            modified = datetime.fromtimestamp(session.stat().st_mtime)

            # Get file size
            size = session.stat().st_size
            size_kb = size / 1024
            
            # Get preview and message count
            preview, msg_count = self.get_conversation_preview(session)

            # Print formatted info
            print(f"\n{i}. 📁 {project}")
            print(f"   📄 Session: {session_id[:8]}...")
            print(f"   📅 Modified: {modified.strftime('%Y-%m-%d %H:%M')}")
            print(f"   💬 Messages: {msg_count}")
            print(f"   💾 Size: {size_kb:.1f} KB")
            print(f"   📝 Preview: \"{preview}...\"")

        print("\n" + "=" * 80)
        return sessions[:limit]

    def extract_multiple(
        self, sessions: List[Path], indices: List[int], 
        format: str = "markdown", detailed: bool = False
    ) -> Tuple[int, int]:
        """Extract multiple sessions by index.
        
        Args:
            sessions: List of session paths
            indices: Indices to extract
            format: Output format ('markdown', 'json', 'html')
            detailed: If True, include tool use and system messages
        """
        success = 0
        total = len(indices)

        for idx in indices:
            if 0 <= idx < len(sessions):
                session_path = sessions[idx]
                conversation = self.extract_conversation(session_path, detailed=detailed)
                if conversation:
                    output_path = self.save_conversation(conversation, session_path.stem, format=format)
                    success += 1
                    msg_count = len(conversation)
                    print(
                        f"✅ {success}/{total}: {output_path.name} "
                        f"({msg_count} messages)"
                    )
                else:
                    print(f"⏭️  Skipped session {idx + 1} (no conversation)")
            else:
                print(f"❌ Invalid session number: {idx + 1}")

        return success, total


def main():
    parser = argparse.ArgumentParser(
        description="Extract Claude Code conversations to clean markdown files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list                    # List all available sessions
  %(prog)s --extract 1               # Extract the most recent session
  %(prog)s --extract 1,3,5           # Extract specific sessions
  %(prog)s --recent 5                # Extract 5 most recent sessions
  %(prog)s --all                     # Extract all sessions
  %(prog)s --input file.jsonl        # Extract specified JSONL file
  %(prog)s --output ~/my-logs        # Specify output directory
  %(prog)s --search "python error"   # Search conversations
  %(prog)s --search-regex "import.*" # Search with regex
  %(prog)s --format json --all       # Export all as JSON
  %(prog)s --format html --extract 1 # Export session 1 as HTML
  %(prog)s --detailed --extract 1    # Include tool use & system messages
  %(prog)s --input file.jsonl --format html  # Extract file as HTML
        """,
    )
    parser.add_argument("--list", action="store_true", help="List recent sessions")
    parser.add_argument(
        "--extract",
        type=str,
        help="Extract specific session(s) by number (comma-separated)",
    )
    parser.add_argument(
        "--all", "--logs", action="store_true", help="Extract all sessions"
    )
    parser.add_argument(
        "--recent", type=int, help="Extract N most recent sessions", default=0
    )
    parser.add_argument(
        "--output", type=str, help="Output directory for markdown files"
    )
    parser.add_argument(
        "--limit", type=int, help="Limit for --list command (default: show all)", default=None
    )
    parser.add_argument(
        "--interactive",
        "-i",
        "--start",
        "-s",
        action="store_true",
        help="Launch interactive UI for easy extraction",
    )
    parser.add_argument(
        "--export",
        type=str,
        help="Export mode: 'logs' for interactive UI",
    )

    # Search arguments
    parser.add_argument(
        "--search", type=str, help="Search conversations for text (smart search)"
    )
    parser.add_argument(
        "--search-regex", type=str, help="Search conversations using regex pattern"
    )
    parser.add_argument(
        "--search-date-from", type=str, help="Filter search from date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--search-date-to", type=str, help="Filter search to date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--search-speaker",
        choices=["human", "assistant", "both"],
        default="both",
        help="Filter search by speaker",
    )
    parser.add_argument(
        "--case-sensitive", action="store_true", help="Make search case-sensitive"
    )
    
    # Export format arguments
    parser.add_argument(
        "--format",
        choices=["markdown", "json", "html"],
        default="markdown",
        help="Output format for exported conversations (default: markdown)"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Include tool use, MCP responses, and system messages in export"
    )
    parser.add_argument(
        "--input",
        "--file",
        type=str,
        dest="input_file",
        help="Specify input JSONL file path directly (supports relative and absolute paths)"
    )
    parser.add_argument(
        "--session-id",
        "--session",
        type=str,
        dest="session_id",
        help="Find and extract session by session ID (searches in ~/.claude/projects)"
    )

    args = parser.parse_args()

    # Handle interactive mode
    if args.interactive or (args.export and args.export.lower() == "logs"):
        from interactive_ui import main as interactive_main

        interactive_main()
        return

    # Handle --input parameter (highest priority)
    if args.input_file:
        # Validate input file
        input_path = Path(args.input_file)
        
        # Check if file exists
        if not input_path.exists():
            print(f"❌ Error: File not found: {input_path}")
            print(f"   Please check the file path and try again.")
            return
        
        # Check if it's a file (not a directory)
        if not input_path.is_file():
            print(f"❌ Error: Path is not a file: {input_path}")
            return
        
        # Check file extension (optional but recommended)
        if input_path.suffix.lower() != ".jsonl":
            print(f"⚠️  Warning: File extension is '{input_path.suffix}', expected '.jsonl'")
            response = input("Continue anyway? (y/N): ").strip().lower()
            if response != 'y':
                print("👋 Cancelled")
                return
        
        # Initialize extractor with optional output directory
        extractor = ClaudeConversationExtractor(args.output)
        
        # Extract conversation from the specified file
        print(f"\n📤 Extracting from: {input_path}")
        print(f"   Format: {args.format.upper()}")
        if args.detailed:
            print("   📋 Including detailed tool use and system messages")
        
        conversation = extractor.extract_conversation(input_path, detailed=args.detailed)
        
        if not conversation:
            print("❌ No conversation found in the file")
            return
        
        # Get session ID from filename
        session_id = input_path.stem
        
        # Save in the requested format
        output_path = extractor.save_conversation(
            conversation, 
            session_id, 
            format=args.format
        )
        
        if output_path:
            print(f"✅ Successfully extracted {len(conversation)} messages")
            print(f"   Saved to: {output_path}")
        else:
            print("❌ Failed to save conversation")
        
        return

    # Handle --session-id parameter (second priority after --input)
    if args.session_id:
        # Initialize extractor with optional output directory
        extractor = ClaudeConversationExtractor(args.output)
        
        # Find session file by ID
        session_path = extractor.find_session_by_id(args.session_id)
        
        if not session_path:
            print(f"❌ Error: Session not found: {args.session_id}")
            print(f"   Searched in: {extractor.claude_dir}")
            print(f"   Please check the session ID and try again.")
            return
        
        # Extract conversation from the found file
        print(f"\n📤 Extracting from: {session_path}")
        print(f"   Session ID: {args.session_id}")
        print(f"   Format: {args.format.upper()}")
        if args.detailed:
            print("   📋 Including detailed tool use and system messages")
        
        conversation = extractor.extract_conversation(session_path, detailed=args.detailed)
        
        if not conversation:
            print("❌ No conversation found in the file")
            return
        
        # Save in the requested format
        output_path = extractor.save_conversation(
            conversation, 
            args.session_id, 
            format=args.format
        )
        
        if output_path:
            print(f"✅ Successfully extracted {len(conversation)} messages")
            print(f"   Saved to: {output_path}")
        else:
            print("❌ Failed to save conversation")
        
        return

    # Initialize extractor with optional output directory
    extractor = ClaudeConversationExtractor(args.output)

    # Handle search mode
    if args.search or args.search_regex:
        from datetime import datetime

        from search_conversations import ConversationSearcher

        searcher = ConversationSearcher()

        # Determine search mode and query
        if args.search_regex:
            query = args.search_regex
            mode = "regex"
        else:
            query = args.search
            mode = "smart"

        # Parse date filters
        date_from = None
        date_to = None
        if args.search_date_from:
            try:
                date_from = datetime.strptime(args.search_date_from, "%Y-%m-%d")
            except ValueError:
                print(f"❌ Invalid date format: {args.search_date_from}")
                return

        if args.search_date_to:
            try:
                date_to = datetime.strptime(args.search_date_to, "%Y-%m-%d")
            except ValueError:
                print(f"❌ Invalid date format: {args.search_date_to}")
                return

        # Speaker filter
        speaker_filter = None if args.search_speaker == "both" else args.search_speaker

        # Perform search
        print(f"🔍 Searching for: {query}")
        results = searcher.search(
            query=query,
            mode=mode,
            date_from=date_from,
            date_to=date_to,
            speaker_filter=speaker_filter,
            case_sensitive=args.case_sensitive,
            max_results=30,
        )

        if not results:
            print("❌ No matches found.")
            return

        print(f"\n✅ Found {len(results)} matches across conversations:")

        # Group and display results
        results_by_file = {}
        for result in results:
            if result.file_path not in results_by_file:
                results_by_file[result.file_path] = []
            results_by_file[result.file_path].append(result)

        # Store file paths for potential viewing
        file_paths_list = []
        for file_path, file_results in results_by_file.items():
            file_paths_list.append(file_path)
            print(f"\n{len(file_paths_list)}. 📄 {file_path.parent.name} ({len(file_results)} matches)")
            # Show first match preview
            first = file_results[0]
            print(f"   {first.speaker}: {first.matched_content[:100]}...")

        # Offer to view conversations
        if file_paths_list:
            print("\n" + "=" * 60)
            try:
                view_choice = input("\nView a conversation? Enter number (1-{}) or press Enter to skip: ".format(
                    len(file_paths_list))).strip()
                
                if view_choice.isdigit():
                    view_num = int(view_choice)
                    if 1 <= view_num <= len(file_paths_list):
                        selected_path = file_paths_list[view_num - 1]
                        extractor.display_conversation(selected_path, detailed=args.detailed)
                        
                        # Offer to extract after viewing
                        extract_choice = input("\n📤 Extract this conversation? (y/N): ").strip().lower()
                        if extract_choice == 'y':
                            conversation = extractor.extract_conversation(selected_path, detailed=args.detailed)
                            if conversation:
                                session_id = selected_path.stem
                                if args.format == "json":
                                    output = extractor.save_as_json(conversation, session_id)
                                elif args.format == "html":
                                    output = extractor.save_as_html(conversation, session_id)
                                else:
                                    output = extractor.save_as_markdown(conversation, session_id)
                                print(f"✅ Saved: {output.name}")
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Cancelled")
        
        return

    # Default action is to list sessions
    if args.list or (
        not args.extract
        and not args.all
        and not args.recent
        and not args.search
        and not args.search_regex
    ):
        sessions = extractor.list_recent_sessions(args.limit)

        if sessions and not args.list:
            print("\nTo extract conversations:")
            print("  claude-extract --extract <number>      # Extract specific session")
            print("  claude-extract --recent 5              # Extract 5 most recent")
            print("  claude-extract --all                   # Extract all sessions")

    elif args.extract:
        sessions = extractor.find_sessions()

        # Parse comma-separated indices
        indices = []
        for num in args.extract.split(","):
            try:
                idx = int(num.strip()) - 1  # Convert to 0-based index
                indices.append(idx)
            except ValueError:
                print(f"❌ Invalid session number: {num}")
                continue

        if indices:
            print(f"\n📤 Extracting {len(indices)} session(s) as {args.format.upper()}...")
            if args.detailed:
                print("📋 Including detailed tool use and system messages")
            success, total = extractor.extract_multiple(
                sessions, indices, format=args.format, detailed=args.detailed
            )
            print(f"\n✅ Successfully extracted {success}/{total} sessions")

    elif args.recent:
        sessions = extractor.find_sessions()
        limit = min(args.recent, len(sessions))
        print(f"\n📤 Extracting {limit} most recent sessions as {args.format.upper()}...")
        if args.detailed:
            print("📋 Including detailed tool use and system messages")

        indices = list(range(limit))
        success, total = extractor.extract_multiple(
            sessions, indices, format=args.format, detailed=args.detailed
        )
        print(f"\n✅ Successfully extracted {success}/{total} sessions")

    elif args.all:
        sessions = extractor.find_sessions()
        print(f"\n📤 Extracting all {len(sessions)} sessions as {args.format.upper()}...")
        if args.detailed:
            print("📋 Including detailed tool use and system messages")

        indices = list(range(len(sessions)))
        success, total = extractor.extract_multiple(
            sessions, indices, format=args.format, detailed=args.detailed
        )
        print(f"\n✅ Successfully extracted {success}/{total} sessions")


def launch_interactive():
    """Launch the interactive UI directly, or handle search if specified."""
    import sys
    
    # If no arguments provided, launch interactive UI
    if len(sys.argv) == 1:
        try:
            from .interactive_ui import main as interactive_main
        except ImportError:
            from interactive_ui import main as interactive_main
        interactive_main()
    # Check if 'search' was passed as an argument
    elif len(sys.argv) > 1 and sys.argv[1] == 'search':
        # Launch real-time search with viewing capability
        try:
            from .realtime_search import RealTimeSearch, create_smart_searcher
            from .search_conversations import ConversationSearcher
        except ImportError:
            from realtime_search import RealTimeSearch, create_smart_searcher
            from search_conversations import ConversationSearcher
        
        # Initialize components
        extractor = ClaudeConversationExtractor()
        searcher = ConversationSearcher()
        smart_searcher = create_smart_searcher(searcher)
        
        # Run search
        rts = RealTimeSearch(smart_searcher, extractor)
        selected_file = rts.run()
        
        if selected_file:
            # View the selected conversation
            extractor.display_conversation(selected_file)
            
            # Offer to extract
            try:
                extract_choice = input("\n📤 Extract this conversation? (y/N): ").strip().lower()
                if extract_choice == 'y':
                    conversation = extractor.extract_conversation(selected_file)
                    if conversation:
                        session_id = selected_file.stem
                        output = extractor.save_as_markdown(conversation, session_id)
                        print(f"✅ Saved: {output.name}")
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Cancelled")
    else:
        # If other arguments are provided, run the normal CLI
        main()


if __name__ == "__main__":
    main()
