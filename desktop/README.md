# Aria Desktop — Native Tauri Wrapper

This directory contains the native desktop wrapper for **Aria Local Agent** built with [Tauri v2](https://v2.tauri.app/).

## Features
- **Native OS Window:** Runs Aria with minimal resource overhead (~30-40 MB RAM compared to Electron's 200+ MB).
- **System Tray Integration:** Minimize to background system tray with single-click restore.
- **Local Isolated Webview:** Connects strictly to your local backend (`http://localhost:8000`) without any external internet traffic.
- **Cross-Platform:** Builds on Windows, macOS, and Linux.

## Prerequisites
1. **Rust & Cargo:** Install Rust via [rustup.rs](https://rustup.rs).
2. **Node.js:** v18+ for Vite compilation and Tauri CLI.

## Development & Building

1. Ensure the web client bundle is built:
   ```bash
   cd ../web
   npm run build
   ```

2. Run desktop app in development mode:
   ```bash
   cd ../desktop
   npm install
   npm run dev
   ```

3. Build production standalone executable:
   ```bash
   npm run build
   ```
   The compiled executable will be located in `src-tauri/target/release/`.
