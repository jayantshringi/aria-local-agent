# System Setup & Installation Guide

This guide walks you through setting up all components required for `aria-local-agent`.

---

## 1. Prerequisites Overview

| Tool | Minimum Version | Purpose |
|---|---|---|
| **Ollama** | Latest | Local LLM and embedding runtime |
| **Python** | 3.11+ | Backend server and agent runtime |
| **Node.js** | 20.x+ | Frontend Vite development and build |
| **Tailscale** | Latest | Secure multi-device mesh networking |

---

## 2. Installing Ollama

### Windows
1. Download the Windows installer from [ollama.com/download/windows](https://ollama.com/download/windows)
2. Run `OllamaSetup.exe`
3. Verify Ollama is running in your taskbar or terminal:
   ```powershell
   ollama --version
   ```

### macOS
1. Download the macOS installer from [ollama.com/download/mac](https://ollama.com/download/mac) or install via Homebrew:
   ```bash
   brew install ollama
   ```
2. Launch Ollama from Applications or run:
   ```bash
   ollama serve
   ```

### Linux
Run the official install script:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

---

## 3. Pulling Required Local Models

Once Ollama is installed and running, pull the chat model and embedding model:

```bash
# Pull embedding model (768-dim, fast and accurate)
ollama pull nomic-embed-text

# Pull chat model (choose based on your hardware)
# For 16GB+ RAM / 8GB+ VRAM:
ollama pull qwen2.5:7b-instruct
# Alternatively:
ollama pull llama3.1:8b
```

Verify models are present:
```bash
ollama list
```

---

## 4. Python Environment Setup

We recommend using `uv` or Python's standard `venv` with Python 3.11+.

### Using `uv` (Recommended for speed and clean version pinning)
```powershell
# Navigate to the backend directory
cd backend

# Create virtual environment pinned to Python 3.11
uv venv --python 3.11 .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install development dependencies
uv pip install -e ".[dev]"
```

### Using Standard Python `venv`
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

---

## 5. Web Frontend Setup

```bash
cd web
npm install
npm run dev
```
The web interface will be available at `http://localhost:5173`.

---

## 6. Tailscale Multi-Device Access

To use `aria-local-agent` securely on your phone without exposing any ports to the public internet:

1. Install Tailscale on your host machine from [tailscale.com/download](https://tailscale.com/download).
2. Install Tailscale on your mobile device (iOS App Store / Google Play).
3. Log in with the same account on both devices.
4. Note your host machine's Tailscale IP or MagicDNS hostname (e.g., `http://my-pc.tailscale.net:8000`).
5. Configure `CORS_ORIGINS` in `.env` to allow your Tailscale hostname.
6. Open your browser on your phone and navigate to your Tailscale host URL. Add to Home Screen to install as a PWA!
