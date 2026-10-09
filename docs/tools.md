# Agent Tool Specifications

## 1. Tool Registry Architecture

Each tool in `aria-local-agent` is implemented as an isolated, self-contained Python class inheriting from a base `BaseTool` interface in `backend/app/agent/base_tool.py`.

### Tool Contract
Every tool provides:
1. `name: str` - Unique dot-namespaced identifier (e.g., `files.read`).
2. `description: str` - Concise description for the LLM tool selector.
3. `parameters: dict` - Standard JSON Schema defining expected inputs.
4. `risk_level: RiskLevel` - Tier: `LOW`, `MEDIUM`, or `HIGH`.
5. `execute(args: dict, context: ExecutionContext) -> ToolResult` - Async execution function.

---

## 2. Initial Tool Catalog

### 2.1 Notes
- **`notes.search` (Risk: LOW)**
  - *Description:* Searches stored notes by keyword or tag.
  - *Parameters:* `query` (string), `limit` (integer, default 5).
- **`notes.create` (Risk: MEDIUM)**
  - *Description:* Creates a new note in the user's local notes repository.
  - *Parameters:* `title` (string), `content` (string), `tags` (array of strings).

### 2.2 Filesystem
- **`files.search` (Risk: LOW)**
  - *Description:* Searches for filenames matching a pattern inside whitelisted folders.
  - *Parameters:* `pattern` (string), `root_dir` (optional string within whitelist).
- **`files.read` (Risk: LOW)**
  - *Description:* Reads the content of a text or markdown file inside whitelisted folders.
  - *Parameters:* `path` (string).
- **`files.write` (Risk: MEDIUM)**
  - *Description:* Writes or appends text to a file inside whitelisted folders.
  - *Parameters:* `path` (string), `content` (string), `mode` ("overwrite" or "append").
- **`files.move` (Risk: MEDIUM)**
  - *Description:* Renames or moves a file within whitelisted folders.
  - *Parameters:* `source_path` (string), `target_path` (string).
- **`files.delete` (Risk: HIGH)**
  - *Description:* Safely moves a file to the system trash bin (never permanent deletion).
  - *Parameters:* `path` (string).

### 2.3 Reminders
- **`reminders.create` (Risk: LOW)**
  - *Description:* Creates a scheduled reminder.
  - *Parameters:* `text` (string), `due_at` (ISO 8601 timestamp), `repeat_rule` (optional string).
- **`reminders.list` (Risk: LOW)**
  - *Description:* Lists upcoming or active reminders.
  - *Parameters:* `status` ("pending" | "completed" | "all").

### 2.4 Applications
- **`apps.open` (Risk: MEDIUM)**
  - *Description:* Opens an application from the owner's configured allowlist.
  - *Parameters:* `app_name` (string).

### 2.5 Web Search (Optional / Disabled by Default)
- **`web.search` (Risk: MEDIUM)**
  - *Description:* Queries a local SearXNG instance or local offline index.
  - *Parameters:* `query` (string), `max_results` (integer).

### 2.6 Shell Execution (Disabled by Default)
- **`shell.run` (Risk: HIGH)**
  - *Description:* Executes an approved command from a strict allow-list. Always requires explicit approval.
  - *Parameters:* `command` (string), `args` (array of strings).

---

## 3. Whitelist Management

Filesystem tools are strictly restricted to paths defined in `ARIA_FOLDER_WHITELIST` in settings. Any attempt to traverse (`../`) or access directories outside the whitelist immediately fails and creates a security alert in `audit_log`.
