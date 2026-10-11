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

## 6. Tailscale Multi-Device Access (Phone & Secondary PCs)

To access Aria securely on your phone, tablet, or laptop without opening ports on your home router or exposing anything to the public internet, Aria uses **Tailscale**, an encrypted peer-to-peer WireGuard mesh VPN.

### 6.1 Install & Connect Tailscale
1. **On your host machine (where Aria runs)**:
   - Download and install Tailscale from [tailscale.com/download](https://tailscale.com/download).
   - Log in and verify your machine appears in your tailnet:
     ```bash
     tailscale status
     ```
2. **On your mobile phone (iOS / Android)**:
   - Install Tailscale from the App Store or Google Play Store.
   - Sign in with the exact same account.
   - Enable the VPN connection toggle.

### 6.2 Host Binding & Network Configuration
By default, Aria listens on `127.0.0.1` (localhost only). To allow connections from your Tailscale devices:
1. In your `backend/.env` file, set:
   ```env
   ARIA_HOST=0.0.0.0
   ARIA_PORT=8000
   ```
2. Find your host machine's Tailscale IP or MagicDNS hostname (e.g. `100.102.45.67` or `aria-server.tailnet-xyz.ts.net`).
3. Add your Tailscale hostname to `CORS_ORIGINS`:
   ```env
   CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:8000","https://aria-server.tailnet-xyz.ts.net","http://100.102.45.67:8000"]
   ```

### 6.3 Secure HTTPS with Tailscale Serve / Certs (Recommended for PWA & Notifications)
Mobile browsers require HTTPS for Progressive Web App (PWA) installation, Service Workers, and Web Push notifications. Tailscale makes free HTTPS certificates automatic:

**Option A: Using `tailscale serve` (Easiest)**
Tailscale can automatically reverse-proxy your local port with valid TLS:
```bash
tailscale serve --bg 8000
```
This automatically gives you a secure URL like `https://aria-server.tailnet-xyz.ts.net` with an official Let's Encrypt TLS certificate trusted by iOS Safari and Android Chrome.

**Option B: Generating certificates directly**
```bash
tailscale cert aria-server.tailnet-xyz.ts.net
```
This downloads `aria-server.tailnet-xyz.ts.net.crt` and `aria-server.tailnet-xyz.ts.net.key` for use in your reverse proxy or uvicorn directly.

---

## 7. Device Pairing & PWA Installation Flow

Once connected over Tailscale HTTPS:

### 7.1 Pair Your Phone (Zero Password Needed)
1. On your authenticated desktop browser, open **Sidebar > Devices & Sync**.
2. Click **Pair New Device** to generate a one-time 8-character pairing code (e.g. `ARIA-84K2`) and a local QR code.
3. On your phone:
   - Point your phone camera at the QR code to open `https://<tailscale-host>/?pair=ARIA-84K2`.
   - Alternatively, open the site on your phone, select **Pair with Code**, and enter the code.
4. Tap **Connect Device**. The server automatically registers your phone with a dedicated random device token. Your master password is never typed or stored on your phone!

### 7.2 Install as a Native App (PWA)
- **On iOS (Safari)**:
  1. Open the URL in Safari.
  2. Tap the **Share** button (box with upward arrow).
  3. Scroll down and tap **Add to Home Screen**.
  4. Aria will now launch as a full-screen, standalone app with its own icon and splash screen.
- **On Android (Chrome)**:
  1. Open the URL in Chrome.
  2. Tap the **Install App** button in the sidebar, or tap the three dots menu > **Install app / Add to Home screen**.
- **On Desktop (Chrome / Edge)**:
  1. Click the **Install** icon in your browser address bar or click **Install App** in the sidebar.

### 7.3 Real-Time Multi-Device Sync
- Any message sent from your phone appears immediately on your desktop screen via the real-time WebSocket sync bus.
- If your phone is lost or stolen, open **Devices & Sync** on your PC and click **Revoke Access** on that device. It will be disconnected immediately and its token permanently invalidated.

---

## 8. Voice & Proactive Scheduler Configuration

### 8.1 Local Speech-to-Text (`faster-whisper`)
- Aria uses local `faster-whisper` for offline audio transcription.
- By default, the `base.en` (or `small`) quantized INT8 model is automatically downloaded into `~/.aria/models/whisper/` on first use.
- The web app records 16kHz linear PCM directly using the browser's Web Audio API—no system `ffmpeg` installation is required!
- In your browser or PWA, grant microphone permissions when prompted after pressing the microphone button.

### 8.2 Local Text-to-Speech (`Piper`)
- Aria utilizes local Piper neural voice models for ultra-fast, offline spoken responses.
- To use Piper, place any Piper ONNX model and JSON config into `~/.aria/models/piper/` (e.g. `en_US-lessac-medium.onnx` and `en_US-lessac-medium.onnx.json`).
- If no Piper model is installed, text-to-speech gracefully falls back to synthesized audio or browser speech synthesis without throwing errors.
- Toggle spoken replies on/off using the speaker icon next to the theme toggle in the chat header, or click the speaker button on any individual assistant message.

### 8.3 Background Reminders & Morning Briefings
- The background `APScheduler` engine automatically polls for due reminders every 30 seconds.
- Overdue and newly triggered reminders are broadcast across WebSocket to all connected devices with audio alerts and notification toasts.
- A morning briefing cron runs daily at the configured briefing time (`ARIA_BRIEFING_HOUR=8`, `ARIA_BRIEFING_MINUTE=0`), generating an agenda of today's schedule, pending tasks, and yesterday's activity. You can also trigger it manually at any time via the **Morning Briefing** button in the sidebar.

