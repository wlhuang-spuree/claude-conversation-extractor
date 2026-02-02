# Claude Conversation Extractor - Export Claude Code Conversations

## 🎮 Two Ways to Use

- **`claude-start`** - Interactive UI with ASCII art logo, real-time search, and menu-driven interface
- **`claude-extract`** - Plain CLI for command-line operations and scripting

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/claude-conversation-extractor.svg)](https://badge.fury.io/py/claude-conversation-extractor)
[![Downloads](https://pepy.tech/badge/claude-conversation-extractor)](https://pepy.tech/project/claude-conversation-extractor)

**Export Claude Code conversations with the #1 extraction tool.** Claude Code stores chats in ~/.claude/projects as JSONL files with no export button - this tool solves that.

## 🎯 Can't Export Claude Code Conversations? We Solved It.

**Claude Code has no export button.** Your conversations are trapped in `~/.claude/projects/` as undocumented JSONL files. You need:
- ❌ **Export Claude Code conversations** before they're deleted
- ❌ **Search Claude Code chat history** to find that solution from last week
- ❌ **Backup Claude Code logs** for documentation or sharing
- ❌ **Convert Claude JSONL to Markdown** for readable archives

## ✅ Claude Conversation Extractor: The First Export Tool for Claude Code

This is the **ONLY tool that exports Claude Code conversations**:
- ✅ **Finds Claude Code logs** automatically in ~/.claude/projects
- ✅ **Extracts Claude conversations** to clean Markdown files
- ✅ **Searches Claude chat history** with real-time results
- ✅ **Backs up all Claude sessions** with one command
- ✅ **Works on Windows, macOS, Linux** - wherever Claude Code runs

## ✨ Features for Claude Code Users

- **🔍 Real-Time Search**: Search Claude conversations as you type - no flags needed
- **📝 Claude JSONL to Markdown**: Clean export without terminal artifacts
- **⚡ Find Any Chat**: Search by content, date, or conversation name
- **📦 Bulk Export**: Extract all Claude Code conversations at once
- **🎯 Zero Config**: Just run `claude-extract` - we find everything automatically
- **🚀 No Dependencies**: Pure Python - no external packages required
- **🖥️ Cross-Platform**: Export Claude Code logs on any OS
- **📊 97% Test Coverage**: Reliable extraction you can trust

## 📦 Install Claude Conversation Extractor

### Quick Install


**Using pip:**
```bash
pip install git+https://github.com/wlhuang-spuree/claude-conversation-extractor.git
```

**Using uv:**
```bash
# Install uv first (if not already installed)
# macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install the extractor
uv tool install git+https://github.com/wlhuang-spuree/claude-conversation-extractor.git
```

## 🚀 How to Export Claude Code Conversations

### Quick Start - Directly From File
- Select from File 
   1. cd into `~\.claude\projects` or `%USERPROFILE%\.claude\projects`
   2. copy the fullpath of target file (`.jsonl`)
   3. command `claude-extract --format html --detailed --output ./claude_exports --input "C:\Users\alan\.claude\projects\E--spuree-misc\ea6be090-25d9-4950-a98b-8b426d1d8280.jsonl"`
    Quick snippet: `claude-extract --format html --detailed --output ./claude_exports --input $input`
- Select from session ID
   1. in Claude Code, enter target session and cmd `/status`:
   ```
   ❯ /status
    ─────────────────────────────────────────────
    Settings:  Status   Config   Usage  (←/→ or tab to cycle)

    Version: 2.1.29
    Session name: /rename to add a name
    >>> Session ID: ea6be090-25d9-4950-a98b-8b426d1d8280 <<<
    cwd: E:\spuree\misc
   ```
    2. `claude-extract --format html --detailed --output ./claude_exports --session $session_id`

### Quick Start - Realtime CLI
```bash
# Run the interactive UI with ASCII art logo and real-time search
claude-start

# Run the standard CLI interface
claude-extract

# Search for specific content directly
claude-search "API integration"
```
### Export Claude Code Logs - All Methods & Formats

**Basic Export Commands:**
```bash
# Interactive mode with UI - easiest way to export Claude conversations
claude-start

# CLI mode - command-line interface
claude-extract

# List all Claude Code conversations
claude-extract --list

# Export specific Claude chats by number
claude-extract --extract 1,3,5

# Export recent Claude Code sessions
claude-extract --recent 5

# Backup all Claude conversations at once
claude-extract --all

# Extract from a specific JSONL file (relative or absolute path)
claude-extract --input file.jsonl
claude-extract --input ~/.claude/projects/my-project/chat_123.jsonl
claude-extract --file ./conversations/session.jsonl

# Extract by session ID (searches automatically in ~/.claude/projects)
claude-extract --session-id ea6be090-25d9-4950-a98b-8b426d1d8280
claude-extract --session-id ea6be090-25d9-4950-a98b-8b426d1d8280 --format html --detailed

# Save Claude logs to custom location
claude-extract --output ~/my-claude-backups
```

**Export Formats (NEW in v1.1.1!):**
```bash
# Export as JSON for programmatic processing
claude-extract --format json --extract 1

# Export as HTML with beautiful formatting
claude-extract --format html --all

# Include tool use, MCP responses, and system messages
claude-extract --detailed --extract 1

# Combine options for complete exports
claude-extract --format html --detailed --recent 5

# Extract from a specific file with custom format
claude-extract --input file.jsonl --format html
claude-extract --input file.jsonl --format json --detailed
```

**Supported Formats:**
- **Markdown** (default) - Clean, readable text format
- **JSON** - Structured data for analysis and processing
- **HTML** - Beautiful web-viewable format with syntax highlighting

**Detailed Mode (`--detailed`):**
Includes complete conversation transcript with:
- Tool use invocations and parameters
- MCP server responses
- System messages and errors
- Terminal command outputs
- All metadata from the conversation

### 🔍 Search Claude Code Chat History

Search across all your Claude conversations:

```bash
# Method 1: Direct search command
claude-search                    # Prompts for search term
claude-search "zig build"        # Search for specific term
claude-search "error handling"   # Multi-word search

# Method 2: From interactive menu
claude-extract
# Select "Search conversations" for real-time search
```

**Search features:**
- Fast full-text search across all conversations
- Case-insensitive by default
- Finds exact matches, partial matches, and patterns
- Shows match previews and conversation context
- Option to extract matching sessions directly

## 📁 Where Are Claude Code Logs Stored?

### Claude Code Default Locations:
- **macOS/Linux**: `~/.claude/projects/*/chat_*.jsonl`
- **Windows**: `%USERPROFILE%\.claude\projects\*\chat_*.jsonl`
- **Format**: Undocumented JSONL with base64 encoded content

### Exported Claude Conversation Locations:
```text
~/Desktop/Claude logs/claude-conversation-2025-06-09-abc123.md
├── Metadata (session ID, timestamp)
├── User messages with 👤 prefix
├── Claude responses with 🤖 prefix
└── Clean Markdown formatting
```

## ❓ Frequently Asked Questions

### How do I export Claude Code conversations?
Install with `pip install git+https://github.com/wlhuang-spuree/claude-conversation-extractor.git` or `uv tool install git+https://github.com/wlhuang-spuree/claude-conversation-extractor.git` then run `claude-extract`. The tool automatically finds all conversations in ~/.claude/projects.

### How do I export the detailed transcript with tool use?
Use the `--detailed` flag to include tool invocations, MCP responses, terminal outputs, and system messages:
```bash
claude-extract --detailed --format html --extract 1
```
This gives you the complete conversation as seen in Claude's Ctrl+R view.

### Where does Claude Code store conversations?
Claude Code saves all chats in `~/.claude/projects/` as JSONL files. There's no built-in export feature - that's why this tool exists.

### Can I search my Claude Code history?
Yes! Run `claude-search` or select "Search conversations" from the menu. Type anything and see results instantly.

### How to backup all Claude Code sessions?
Run `claude-extract --all` to export every conversation at once, or use the interactive menu option "Export all conversations".

### Does this work with Claude.ai (web version)?
No, this tool specifically exports Claude Code (desktop app) conversations. Claude.ai has its own export feature in settings.

### Can I convert Claude JSONL to other formats?
Yes! Version 1.1.1 supports multiple export formats:
- **Markdown** - Default clean text format
- **JSON** - Structured data with timestamps and metadata  
- **HTML** - Beautiful web-viewable format with modern styling
Use `--format json` or `--format html` when extracting.

### Can I extract from a specific JSONL file?
Yes! You have two options:

1. **By file path** - Use the `--input` or `--file` parameter:
```bash
claude-extract --input file.jsonl --format html
claude-extract --file ~/.claude/projects/my-project/chat_123.jsonl
```

2. **By session ID** - Use the `--session-id` parameter (automatically searches in ~/.claude/projects):
```bash
claude-extract --session-id ea6be090-25d9-4950-a98b-8b426d1d8280 --format html
```

The `--session-id` option is useful when you know the session ID from Claude Code's `/status` command and want to extract without finding the file path manually.

### Is this tool official?
No, this is an independent open-source tool. It reads the local Claude Code files on your computer - no API or internet required.

### Optional: Advanced Search with spaCy
```bash
# For semantic search capabilities
pip install spacy
python -m spacy download en_core_web_sm
```

## 🤝 Contributing

Help make the best Claude Code export tool even better! See [CONTRIBUTING.md](docs/development/CONTRIBUTING.md).

### Development Setup

**Using pip:**
```bash
# Clone the repo
git clone https://github.com/wlhuang-spuree/claude-conversation-extractor.git
cd claude-conversation-extractor

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install in editable mode
pip install -e .

# Install dev dependencies
pip install -r requirements/dev.txt

# Run tests
pytest
```

**Using uv:**
```bash
# Clone the repo
git clone https://github.com/wlhuang-spuree/claude-conversation-extractor.git
cd claude-conversation-extractor

# Install in editable mode
uv pip install -e .

# Install dev dependencies
uv pip install -r requirements/dev.txt

# Run tests
pytest
```

## 🐛 Troubleshooting Claude Export Issues

### Can't find Claude Code conversations?
- Ensure Claude Code has been used at least once
- Check `~/.claude/projects/` exists and has .jsonl files
- Verify read permissions on the directory
- Try `ls -la ~/.claude/projects/` to see if files exist

### "No Claude sessions found" error
- Claude Code must be installed and used before exporting
- Check the correct user directory is being scanned
- Ensure you're running the tool as the same user who uses Claude Code

### Installation issues?
See [INSTALL.md](docs/user/INSTALL.md) for:
- Fixing "externally managed environment" errors
- PATH configuration help
- Platform-specific troubleshooting


## 📜 License

MIT License - see [LICENSE](LICENSE) for details.