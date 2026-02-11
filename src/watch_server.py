"""
Watch server for live-updating HTML view of a Claude Code JSONL session.

Usage:
    from watch_server import WatchServer
    WatchServer(path, port=8765).start()

Or via CLI:
    claude-extract -s {session_id} --watch [--port 8765]
"""

import json
import os
import platform
import queue
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, List, Optional

try:
    from .extract_claude_logs import ClaudeConversationExtractor
except ImportError:
    from extract_claude_logs import ClaudeConversationExtractor


# CSS shared with extract_claude_logs.py save_as_html (kept in sync manually)
_CSS = """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            margin: 0 0 10px 0;
        }
        .metadata {
            color: #666;
            font-size: 0.9em;
        }
        .message {
            background: white;
            padding: 15px 20px;
            margin-bottom: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .user { border-left: 4px solid #3498db; }
        .assistant { border-left: 4px solid #2ecc71; }
        .tool_use { border-left: 4px solid #f39c12; background: #fffbf0; }
        .tool_result { border-left: 4px solid #e74c3c; background: #fff5f5; }
        .system { border-left: 4px solid #95a5a6; background: #f8f9fa; }
        .subagent_user, .subagent_assistant {
            border-left: 4px solid #9b59b6;
            background: #f8f4ff;
        }
        .role {
            font-weight: bold;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
        }
        .content {
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .content-text { margin: 5px 0; }
        .content-thinking {
            background: #f0f7ff;
            border-left: 3px solid #4a90e2;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
        }
        .thinking-header {
            font-weight: bold;
            color: #2c5aa0;
            margin-bottom: 5px;
            font-size: 0.9em;
        }
        .thinking-content {
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            color: #333;
        }
        .content-tool-use {
            background: #fffbf0;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
        }
        .tool-name { font-weight: bold; color: #856404; margin-bottom: 5px; }
        .tool-input {
            background: #f4f4f4;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
            margin: 0;
        }
        .content-image { margin: 10px 0; text-align: center; }
        .content-image img {
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .content-image-placeholder {
            background: #f4f4f4;
            padding: 20px;
            border-radius: 4px;
            text-align: center;
            color: #666;
            font-style: italic;
        }
        .content-tool-reference {
            background: #fff9e6;
            padding: 8px;
            border-radius: 4px;
            margin: 5px 0;
        }
        .tool-ref-label { font-weight: bold; color: #856404; }
        .content-tool-result {
            background: #fff5f5;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
            border-left: 3px solid #e74c3c;
        }
        .tool-result-header {
            font-weight: bold;
            color: #c0392b;
            margin-bottom: 5px;
            font-size: 0.9em;
        }
        .tool-result-content {
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            color: #333;
        }
        pre {
            background: #f4f4f4;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
        }
        code {
            background: #f4f4f4;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        #status-bar {
            position: fixed;
            bottom: 12px;
            right: 16px;
            background: rgba(255,255,255,0.92);
            border: 1px solid #ddd;
            border-radius: 20px;
            padding: 4px 14px;
            font-size: 0.82em;
            color: #555;
            box-shadow: 0 1px 4px rgba(0,0,0,0.12);
            z-index: 1000;
        }
"""


def _open_url(url: str) -> None:
    """Open a URL in the default browser."""
    try:
        if platform.system() == "Windows":
            os.startfile(url)
        elif platform.system() == "Darwin":
            subprocess.run(["open", url])
        else:
            subprocess.run(["xdg-open", url])
    except Exception:
        pass


class WatchServer:
    """
    HTTP server that serves a live-updating HTML view of a JSONL session.

    - GET /       → full initial HTML with existing messages
    - GET /events → SSE stream; pushes new message HTML as JSON-encoded strings
    """

    def __init__(self, jsonl_path: Path, port: int = 8765):
        self.jsonl_path = Path(jsonl_path)
        self.port = port

        # Create extractor without triggering __init__ side-effects (mkdir, print)
        self._extractor: ClaudeConversationExtractor = (
            ClaudeConversationExtractor.__new__(ClaudeConversationExtractor)
        )

        # Incremental parse state – maintained across polls
        self._tool_use_to_name: Dict[str, str] = {}
        self._tool_use_to_subagent_type: Dict[str, str] = {}
        self._last_offset: int = 0
        self._last_size: int = 0

        # SSE subscriber queues
        self._subscribers: List[queue.Queue] = []
        self._subscribers_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # SSE pub/sub helpers
    # ------------------------------------------------------------------ #

    def _subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._subscribers_lock:
            self._subscribers.append(q)
        return q

    def _unsubscribe(self, q: queue.Queue) -> None:
        with self._subscribers_lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def _broadcast(self, html_fragment: str) -> None:
        """Push a JSON-encoded HTML fragment to all connected SSE clients."""
        payload = json.dumps(html_fragment)
        with self._subscribers_lock:
            for q in self._subscribers:
                q.put(payload)

    # ------------------------------------------------------------------ #
    # Incremental JSONL parsing
    # ------------------------------------------------------------------ #

    def _parse_entry(self, entry: dict) -> Optional[dict]:
        """
        Parse one JSONL entry and return a message dict (or None).

        Side-effect: updates _tool_use_to_name / _tool_use_to_subagent_type
        so subsequent entries can resolve tool names correctly.
        """
        entry_type = entry.get("type")

        if entry_type == "user" and "message" in entry:
            msg = entry["message"]
            if isinstance(msg, dict) and msg.get("role") == "user":
                content = msg.get("content", "")
                rich = self._extractor._extract_rich_content(content, detailed=True)
                rich = self._extractor._fill_tool_names(rich, self._tool_use_to_name)
                text = rich.get("text", "") if isinstance(rich, dict) else str(rich)
                if text and text.strip():
                    return {
                        "role": "user",
                        "content": rich,
                        "timestamp": entry.get("timestamp", ""),
                    }

        elif entry_type == "assistant" and "message" in entry:
            msg = entry["message"]
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                content = msg.get("content", [])
                # Track tool uses for name/subagent resolution
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "tool_use":
                            tool_id = item.get("id", "")
                            tool_name = item.get("name", "")
                            if tool_id and tool_name:
                                self._tool_use_to_name[tool_id] = tool_name
                            if tool_name == "Task":
                                subagent_type = item.get("input", {}).get("subagent_type", "")
                                if subagent_type and tool_id:
                                    self._tool_use_to_subagent_type[tool_id] = subagent_type
                rich = self._extractor._extract_rich_content(content, detailed=True)
                rich = self._extractor._fill_tool_names(rich, self._tool_use_to_name)
                text = rich.get("text", "") if isinstance(rich, dict) else str(rich)
                if text and text.strip():
                    return {
                        "role": "assistant",
                        "content": rich,
                        "timestamp": entry.get("timestamp", ""),
                    }

        elif entry_type == "progress":
            data = entry.get("data", {})
            if data.get("type") == "agent_progress":
                message_data = data.get("message", {})
                if message_data:
                    msg_type = message_data.get("type")  # "user" or "assistant"
                    msg = message_data.get("message", {})
                    agent_id = data.get("agentId", "unknown")
                    parent_tool_use_id = entry.get("parentToolUseID", "")
                    subagent_type = self._tool_use_to_subagent_type.get(parent_tool_use_id, "")

                    if msg_type in ("user", "assistant"):
                        expected_role = msg_type  # "user" or "assistant"
                        role_key = "subagent_user" if msg_type == "user" else "subagent_assistant"

                        if msg.get("role") == expected_role:
                            content = msg.get("content", [])
                            # Track tool_use in subagent messages
                            if isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict) and item.get("type") == "tool_use":
                                        tool_id = item.get("id", "")
                                        tool_name = item.get("name", "")
                                        if tool_id and tool_name:
                                            self._tool_use_to_name[tool_id] = tool_name
                            rich = self._extractor._extract_rich_content(content, detailed=True)
                            rich = self._extractor._fill_tool_names(rich, self._tool_use_to_name)
                            text = rich.get("text", "") if isinstance(rich, dict) else str(rich)
                            if text and text.strip():
                                return {
                                    "role": role_key,
                                    "content": rich,
                                    "metadata": {
                                        "agent_id": agent_id,
                                        "agent_type": "subagent",
                                        "subagent_type": subagent_type,
                                        "parent_tool_use_id": parent_tool_use_id,
                                    },
                                    "timestamp": message_data.get(
                                        "timestamp", entry.get("timestamp", "")
                                    ),
                                }

        return None

    def _render_message_html(self, msg: dict) -> str:
        """Render a single message dict to an HTML <div> string."""
        role = msg["role"]
        content = msg["content"]
        rendered = self._extractor._render_content_to_html(content)

        if role == "subagent_user":
            metadata = msg.get("metadata", {})
            subagent_type = metadata.get("subagent_type", "")
            agent_id = metadata.get("agent_id", "unknown")
            subagent_display = subagent_type.upper() if subagent_type else f"{agent_id[:8]}..."
            role_display = f"🤖 Subagent ({subagent_display}) - User"
        elif role == "subagent_assistant":
            metadata = msg.get("metadata", {})
            subagent_type = metadata.get("subagent_type", "")
            agent_id = metadata.get("agent_id", "unknown")
            subagent_display = subagent_type.upper() if subagent_type else f"{agent_id[:8]}..."
            role_display = f"🤖 Subagent ({subagent_display}) - Assistant"
        else:
            role_display = {
                "user": "👤 User",
                "assistant": "🤖 Claude",
                "tool_use": "🔧 Tool Use",
                "tool_result": "📤 Tool Result",
                "system": "ℹ️ System",
            }.get(role, role)

        return (
            f'    <div class="message {role}">\n'
            f"        <div class=\"role\">{role_display}</div>\n"
            f'        <div class="content">{rendered}</div>\n'
            f"    </div>\n"
        )

    # ------------------------------------------------------------------ #
    # File loading
    # ------------------------------------------------------------------ #

    def _load_initial(self) -> list:
        """
        Read the whole JSONL file, build conversation list, and set
        _last_offset/_last_size so the poll loop only sees new content.
        """
        conversation = []
        self._tool_use_to_name = {}
        self._tool_use_to_subagent_type = {}

        try:
            with open(self.jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        entry = json.loads(stripped)
                        msg = self._parse_entry(entry)
                        if msg:
                            conversation.append(msg)
                    except Exception:
                        continue
                self._last_offset = f.tell()
        except Exception as e:
            print(f"❌ Error reading {self.jsonl_path}: {e}")

        try:
            self._last_size = self.jsonl_path.stat().st_size
        except Exception:
            self._last_size = self._last_offset

        return conversation

    # ------------------------------------------------------------------ #
    # HTML building
    # ------------------------------------------------------------------ #

    def _build_initial_html(self, conversation: list) -> str:
        session_id = self.jsonl_path.stem
        messages_html = "".join(self._render_message_html(m) for m in conversation)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Watch \u2014 {session_id[:8]}</title>
    <style>{_CSS}
    </style>
</head>
<body>
    <div class="header">
        <h1>Claude Conversation \u2014 Live View</h1>
        <div class="metadata">
            <p>Session: {session_id}</p>
            <p>File: {self.jsonl_path}</p>
            <p>Messages at load: {len(conversation)}</p>
        </div>
    </div>
    <div id="messages">
{messages_html}
    </div>
    <div id="status-bar">\U0001f7e2 Connected</div>
    <script>
        const es = new EventSource('/events');
        const statusBar = document.getElementById('status-bar');
        es.onmessage = function(e) {{
            const html = JSON.parse(e.data);
            document.getElementById('messages').insertAdjacentHTML('beforeend', html);
            window.scrollTo(0, document.body.scrollHeight);
        }};
        es.onerror = function() {{
            statusBar.textContent = '\U0001f534 Disconnected \u2014 reload to reconnect';
        }};
        es.onopen = function() {{
            statusBar.textContent = '\U0001f7e2 Connected';
        }};
    </script>
</body>
</html>"""

    # ------------------------------------------------------------------ #
    # Background poll loop
    # ------------------------------------------------------------------ #

    def _poll_loop(self) -> None:
        while True:
            time.sleep(0.5)
            try:
                stat = self.jsonl_path.stat()
                if stat.st_size != self._last_size:
                    self._process_new_content()
            except Exception:
                pass

    def _process_new_content(self) -> None:
        """Read newly appended lines, parse them, broadcast HTML fragments."""
        try:
            with open(self.jsonl_path, "r", encoding="utf-8") as f:
                f.seek(self._last_offset)
                new_lines = f.readlines()
                self._last_offset = f.tell()
            self._last_size = self.jsonl_path.stat().st_size

            for line in new_lines:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                    msg = self._parse_entry(entry)
                    if msg:
                        self._broadcast(self._render_message_html(msg))
                except Exception:
                    continue
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Server entry point
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Load initial content, start HTTP server and poll thread, open browser."""
        print(f"\U0001f441  Loading: {self.jsonl_path}")
        conversation = self._load_initial()
        initial_html = self._build_initial_html(conversation)

        server_self = self  # closure reference

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/":
                    body = initial_html.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                elif self.path == "/events":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("X-Accel-Buffering", "no")
                    self.end_headers()

                    sub_q = server_self._subscribe()
                    try:
                        while True:
                            try:
                                data = sub_q.get(timeout=15)
                                self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                                self.wfile.flush()
                            except queue.Empty:
                                # Keep-alive comment to prevent proxy timeouts
                                self.wfile.write(b": keepalive\n\n")
                                self.wfile.flush()
                    except Exception:
                        pass
                    finally:
                        server_self._unsubscribe(sub_q)

                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):  # noqa: A002
                pass  # Suppress HTTP access log noise

        httpd = HTTPServer(("", self.port), _Handler)

        poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        poll_thread.start()

        url = f"http://localhost:{self.port}"
        print(f"\U0001f310 Watch server: {url}")
        print(f"   Messages loaded: {len(conversation)}")
        print("Press Ctrl+C to stop...")
        _open_url(url)

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\U0001f44b Watch server stopped")
            httpd.shutdown()
