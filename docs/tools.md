# Agent Tool Specifications & Safety Architecture

## 1. Tool Registry Architecture

Each tool in `aria-local-agent` is implemented as an isolated, self-contained Python module inheriting from the `BaseTool` abstract base class (`backend/app/agent/base_tool.py`).

### Tool Contract
Every tool defines:
1. `name: str` - Unique dot-namespaced identifier (e.g., `files.read`).
2. `description: str` - Concise description for LLM prompting and user display.
3. `risk_level: RiskLevel` - Tier: `LOW`, `MEDIUM`, or `HIGH`.
4. `parameters: dict[str, Any]` - JSON Schema defining input parameters and types.
5. `execute(args: dict, context: ExecutionContext) -> ToolResult` - Safe async execution method.

---

## 2. Risk Tiers & Approval State Machine

| Risk Tier | Policy | Default Execution Flow |
|---|---|---|
| **LOW** | Safe, read-only or low-impact creation | Auto-executed immediately. Logged to `audit_log`. |
| **MEDIUM** | State mutations, file writes, opening apps | Intercepted into `pending_actions`. Broadcast via WebSocket. Requires explicit owner approval before execution. |
| **HIGH** | File deletion, shell execution | Strict approval required. Cannot be bypassed. Logged with full audit trail. |

### Pending Actions Flow
1. Model or client proposes an action via `dispatch_tool_call()`.
2. Low-risk tools execute automatically and wrap their output with `<untrusted_tool_data>`.
3. Medium- and high-risk tools insert a row in `pending_actions` (`status = 'pending'`) and broadcast a `pending_action_created` event to all connected devices.
4. The owner approves (`POST /api/v1/agent/actions/{id}/approve`) or rejects (`POST /api/v1/agent/actions/{id}/reject`).
5. On approval, the tool executes with an approved `ExecutionContext` and emits `pending_action_resolved`.
6. On rejection, the status is marked `'rejected'` and logged to `audit_log`.

---

## 3. Tool Catalog

### 3.1 Notes
- **`notes.create` (Risk: LOW)**
  - *Description:* Create a local markdown note in SQLite.
  - *Parameters:* `title` (str, required), `content` (str, required), `tags` (array of str).
- **`notes.search` (Risk: LOW)**
  - *Description:* Search local notes by title, content, or tag.
  - *Parameters:* `query` (str, required), `limit` (int, default 5).

### 3.2 Filesystem
- **`files.search` (Risk: LOW)**
  - *Description:* Search for files inside whitelisted directories using glob patterns.
  - *Parameters:* `query` (str, required), `path` (str, optional relative or absolute whitelisted directory).
- **`files.read` (Risk: LOW)**
  - *Description:* Read text or markdown contents up to `max_bytes` within whitelisted directories.
  - *Parameters:* `path` (str, required), `max_bytes` (int, default 65536).
- **`files.write` (Risk: MEDIUM, Requires Approval)**
  - *Description:* Create, overwrite, or append content to a file inside whitelisted folders.
  - *Parameters:* `path` (str, required), `content` (str, required), `mode` ("overwrite" | "append", default "overwrite").
- **`files.move` (Risk: MEDIUM, Requires Approval)**
  - *Description:* Move or rename files within whitelisted folders.
  - *Parameters:* `source` (str, required), `destination` (str, required).
- **`files.delete` (Risk: HIGH, Requires Approval)**
  - *Description:* Soft-delete file into `.trash/<filename>_<timestamp>`. Permanent unrecoverable deletion is forbidden.
  - *Parameters:* `path` (str, required).

### 3.3 Reminders
- **`reminders.create` (Risk: LOW)**
  - *Description:* Schedule a reminder with text, due date/time (ISO 8601), and optional repeat rule.
  - *Parameters:* `text` (str, required), `due_at` (str, required), `repeat_rule` (str, optional).
- **`reminders.list` (Risk: LOW)**
  - *Description:* List reminders filtered by status (`pending`, `completed`, `all`).
  - *Parameters:* `status` (str, default "pending"), `limit` (int, default 20).

### 3.4 Applications
- **`apps.open` (Risk: MEDIUM, Requires Approval)**
  - *Description:* Launch an application explicitly listed in `ARIA_APPS_ALLOWLIST`. Executed without shell interpolation.
  - *Parameters:* `app_name` (str, required).

### 3.5 Web Search
- **`web.search` (Risk: MEDIUM, Requires Approval, Disabled by Default)**
  - *Description:* Query local self-hosted SearXNG instance (`http://localhost:8080`).
  - *Parameters:* `query` (str, required), `limit` (int, default 5).

### 3.6 Shell Execution
- **`shell.run` (Risk: HIGH, Requires Approval, Disabled by Default)**
  - *Description:* Execute a command strictly allowlisted in `ARIA_SHELL_ALLOWLIST`. Runs in sandboxed subprocess with timeouts.
  - *Parameters:* `command` (str, required), `args` (array of str).

---

## 4. Safety Controls & Prompt Injection Defense

### 4.1 Folder Whitelist Sandboxing
- All file operations are checked via `verify_path_allowed()` in `backend/app/agent/safety.py`.
- Path traversal sequences (`../`, `..\\`) and symlink escapes outside `ARIA_FOLDER_WHITELIST` raise `SecurityViolationError` immediately and are logged.

### 4.2 Reversible Deletions
- In adherence to `AGENTS.md` Section 6, `files.delete` never deletes files permanently. Files are timestamped and moved into `.trash/` inside the primary whitelisted root.

### 4.3 Prompt Injection Defense
- Untrusted tool outputs (file contents, notes, search queries) are wrapped in `<untrusted_tool_data>` delimiters via `wrap_untrusted_data()`.
- Nested escape sequences (e.g. `</untrusted_tool_data>`) inside tool output are sanitized to prevent jailbreaks and instruction override attempts.

---

## 5. Emergency Kill Switch

- **Trigger API:** `POST /api/v1/agent/kill`
- **Reset API:** `POST /api/v1/agent/kill/reset`
- **Status API:** `GET /api/v1/agent/kill/status`
- **Behavior:**
  1. Sets global kill switch state to `active = True`.
  2. Cancels all in-flight asyncio agent tasks immediately.
  3. Updates all `pending` actions in SQLite to `status = 'killed'`.
  4. Broadcasts `agent_killed` WebSocket event across all connected thin clients.
  5. Intercepts and rejects any subsequent tool execution requests until explicitly reset.
