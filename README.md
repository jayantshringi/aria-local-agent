# aria-local-agent

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React + Vite](https://img.shields.io/badge/frontend-React%20%2B%20Vite-61DAFB.svg)](https://vitejs.dev/)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-black.svg)](https://ollama.com/)

**aria-local-agent** is a fully private, local-first personal AI assistant that runs entirely on your own hardware. 

> **Hard Rule:** No user data ever leaves the owner's machines. No cloud LLM APIs, no telemetry, no third-party analytics.

---

## Key Features

1. **Local Text & Voice Chat:** Conversational assistant powered by Ollama (`qwen2.5:7b-instruct` or `llama3.1:8b`) with streaming WebSocket responses.
2. **Permanent Searchable History:** Every session and message is stored locally in SQLite with WAL mode, searchable by keyword (FTS5) and meaning (`sqlite-vec` + `nomic-embed-text`).
3. **Editable Profile Memory:** Remembers facts about you, with an owner-controlled approval gate (`pending` -> `approved` -> prompt injection).
4. **Guarded Agent Tools:** Can interact with notes, files, reminders, and applications with explicit risk levels (`low`, `medium`, `high`), approval queues, audit logging, and an instant kill switch.
5. **Multi-Device Mesh:** Responsive PWA client installable on phone and PC, connected via private Tailscale mesh VPN without exposing open ports to the internet.
6. **Proactive Automation:** Automated morning briefings and reminders powered by APScheduler.

---

## Technical Stack

| Component | Technology | Rationale |
|---|---|---|
| **LLM Runtime** | [Ollama](https://ollama.com/) | Local execution of chat models (`qwen2.5:7b-instruct` / `llama3.1:8b`) and embeddings (`nomic-embed-text`) |
| **Backend** | Python 3.11+, FastAPI | High-performance asynchronous API, WebSocket streaming |
| **Database** | SQLite (WAL mode) | `sqlite-vec` for dense vector search, FTS5 for full-text search |
| **Speech-to-Text** | `faster-whisper` | Low-latency on-device transcription |
| **Text-to-Speech** | `Piper` | Fast, lightweight local neural speech synthesis |
| **Web Frontend** | React, Vite, TypeScript | Installable Progressive Web App (PWA) for desktop and mobile |
| **Remote Access** | [Tailscale](https://tailscale.com/) | Secure private wireguard mesh networking, zero port-forwarding |
| **Scheduler** | APScheduler | Local background jobs and reminder triggers |
| **Quality & Tests** | `pytest`, `ruff`, `black`, `eslint` | Enforced linting and automated test coverage |

---

## Repository Structure

```
aria-local-agent/
├── AGENTS.md              # Antigravity agent build instructions & specifications
├── README.md              # Project documentation
├── LICENSE                # MIT License
├── .gitignore             # Git ignore definitions
├── .env.example           # Environment template
├── docs/                  # Architectural & operational documentation
│   ├── architecture.md    # System design & data flow
│   ├── security.md        # Privacy guarantees, threat model, safety controls
│   ├── tools.md           # Tool registry, schemas & permission tiers
│   └── setup-guide.md     # Installation & setup guide
├── backend/               # FastAPI backend
│   ├── pyproject.toml     # Python packaging & dependencies
│   ├── app/
│   │   ├── main.py        # App entry point
│   │   ├── config.py      # App configuration
│   │   ├── auth/          # Passkey/token auth
│   │   ├── db/            # Schema, migrations & SQLite queries
│   │   ├── llm/           # Ollama client & prompt management
│   │   ├── memory/        # Embeddings, hybrid retrieval, facts
│   │   ├── agent/         # Loop, safety controls, audit log, kill switch
│   │   ├── tools/         # Modular tool implementations
│   │   ├── voice/         # STT & TTS integration
│   │   ├── scheduler/     # APScheduler background tasks
│   │   └── api/           # REST & WebSocket endpoints
│   └── tests/             # Automated backend tests
├── web/                   # React PWA frontend
├── desktop/               # Optional Tauri wrapper (Phase 6)
├── scripts/               # Backup, export, and maintenance utilities
└── data/                  # Gitignored local data (actual data in ~/.aria/)
```

---

## Development Setup

### 1. Prerequisites
- **Ollama:** Installed and running locally (`http://localhost:11434`)
  ```bash
  ollama pull qwen2.5:7b-instruct
  ollama pull nomic-embed-text
  ```
- **Python:** 3.11+
- **Node.js:** 20+

### 2. Backend Setup
```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -e .
pytest tests/
```

### 3. Run Quality Checks
```bash
ruff check backend/
black --check backend/
```

---

## Project Status

- [x] **Phase 0: Setup & Tooling** (Baseline structure, documentation, linting, tests)
- [ ] **Phase 1: Private Chat MVP** (FastAPI, Ollama streaming, SQLite persistence, React chat UI)
- [ ] **Phase 2: Memory** (Hybrid search: sqlite-vec + FTS5, profile facts, idle summarizer)
- [ ] **Phase 3: Multi-Device** (PWA manifest, device pairing, Tailscale setup, sync)
- [ ] **Phase 4: Agent Tools & Safety** (Tool registry, approval gate, audit log, kill switch)
- [ ] **Phase 5: Voice & Proactivity** (faster-whisper, Piper, wake word, APScheduler briefing)
- [ ] **Phase 6: Hardening & Polish** (Encryption at rest, export/delete, Tauri desktop)

---

## License

This project is licensed under the [MIT License](LICENSE).
