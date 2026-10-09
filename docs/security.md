# Security Model & Safety Architecture

## 1. Zero Cloud Exposure Principle

The foundational axiom of `aria-local-agent` is absolute privacy:
- **Zero External API Calls:** No cloud LLM providers (OpenAI, Anthropic, Google), telemetry endpoints, or external third-party analytics are permitted.
- **Local-Only Runtime:** All inference (chat, embeddings, STT, TTS) is executed strictly on the owner's hardware.
- **Isolated Network Topology:** The server daemon binds only to `127.0.0.1` (or Tailscale interface). No ports are ever forwarded on home routers.

---

## 2. Authentication & Device Trust

- **Single-User Architecture:** Designed exclusively for the device owner.
- **Device Tokens:** High-entropy random tokens generated cryptographically (`secrets.token_urlsafe(32)`).
- **Hashed Storage:** Tokens are hashed (using SHA-256 or Argon2) before storage in the `devices` table.
- **Instant Revocation:** Any device can be individually revoked by the owner via the settings panel.

---

## 3. Tool Permissions & Risk Tiers

Every agent tool must declare an explicit `risk_level`:

| Risk Tier | Definition | Examples | Approval Requirement |
|---|---|---|---|
| **Low** | Read-only operations, non-destructive data access, internal state manipulation | `notes.search`, `files.read` (whitelisted), `reminders.create` | Executed automatically; logged to `audit_log` |
| **Medium** | Modifications to existing resources, opening external apps, web searches | `notes.create`, `files.write` (whitelisted), `apps.open` | Requires owner approval via UI |
| **High** | Deletions, external script execution, filesystem structure changes | `files.delete` (moves to trash), `shell.run` | Requires explicit owner confirmation with arguments preview |

---

## 4. Prompt Injection Defense (Untrusted Data Isolation)

AI agents that ingest external data (files, emails, web pages) are vulnerable to prompt injection attacks where untrusted content contains adversarial directives.

### Countermeasures:
1. **Strict Data Delimitation:** All tool outputs are wrapped inside distinct untrusted data blocks:
   ```markdown
   <untrusted_tool_data source="files.read" path="...">
   ... content ...
   </untrusted_tool_data>
   ```
2. **Instruction Disregard Directive:** The system prompt explicitly instructs the LLM that content within `<untrusted_tool_data>` must never override instructions, grant permissions, or alter system behavior.
3. **Deterministic Permission Checking:** The model **cannot** grant itself permissions. Execution permissions are enforced deterministically in Python code before any tool executes.

---

## 5. Audit Logging & Kill Switch

- **Comprehensive Audit Trail:** All tool calls—successful, rejected, or failed—are recorded in `audit_log` with timestamp, tool name, serialized arguments, risk level, approver, and outcome.
- **Kill Switch:** A dedicated hardware/UI interrupt button and API endpoint (`POST /api/v1/agent/kill`):
  - Halts any actively executing agent task immediately.
  - Aborts in-flight child processes.
  - Flushes the `pending_actions` queue to `rejected`.
  - Disconnects active WebSocket generation streams.

---

## 6. Storage Encryption

- The database file is located in the user directory (`~/.aria/aria.db`).
- Where supported, encrypted at rest using SQLCipher or an encrypted OS disk volume (e.g., BitLocker / LUKS / FileVault).
- Encrypted export and backup scripts (`scripts/backup.py`) ensure safe portability.
