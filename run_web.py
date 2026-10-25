#!/usr/bin/env python3
"""
Launcher script for Groww App Review Pulse Agent Web Dashboard & Backend API.
Starts the FastAPI server with static frontend files on http://localhost:8000.
"""

import argparse
import os
import socket
import sys
import uvicorn


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def main():
    parser = argparse.ArgumentParser(description="Start Groww Pulse Agent Web Dashboard & API")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
    env_port = os.environ.get("PORT")
    default_port = int(env_port) if env_port else 8000
    parser.add_argument("--port", type=int, default=default_port, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    port = args.port
    if not env_port and is_port_in_use(port, "127.0.0.1"):
        print(f"Warning: Port {port} is currently in use.")
        # Find next available port
        for candidate in range(port + 1, port + 20):
            if not is_port_in_use(candidate, "127.0.0.1"):
                print(f"Switching to available port {candidate}...")
                port = candidate
                break

    print("=" * 60)
    print("📈 GROWW APP REVIEW PULSE AGENT — DASHBOARD & BACKEND API")
    print("=" * 60)
    print(f"🌐 Access Dashboard UI : http://localhost:{port}")
    print(f"📑 Interactive OpenAPI  : http://localhost:{port}/docs")
    print(f"⚡ Backend API Base     : http://localhost:{port}/api/status")
    print("=" * 60)
    print("Press Ctrl+C to stop the server.\n")

    uvicorn.run("src.web.app:app", host=args.host, port=port, reload=args.reload)


if __name__ == "__main__":
    main()
