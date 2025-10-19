"""Main entry point for Conversational Swarm Intelligence Network."""

import asyncio
import os
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from core.monitoring.logging_config import setup_logging

# Load environment variables
load_dotenv()


def create_directories():
    """Create required directories if they don't exist."""
    directories = [
        "logs",
        "memory",
        "shared_memory",
        "keys",
        "certs",
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    
    print("✓ Created required directories")


def main():
    """Main entry point."""
    print("=" * 60)
    print("🐝 Conversational Swarm Intelligence Network")
    print("=" * 60)
    
    # Create directories
    create_directories()
    
    # Setup logging
    log_level = os.getenv("LOG_LEVEL", "INFO")
    setup_logging(log_level=log_level)
    print(f"✓ Logging configured at {log_level} level")
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    workers = int(os.getenv("WORKERS", "1"))
    
    # TLS configuration (optional)
    tls_enabled = os.getenv("TLS_ENABLED", "false").lower() == "true"
    ssl_keyfile = None
    ssl_certfile = None
    
    if tls_enabled:
        ssl_keyfile = os.getenv("TLS_KEY_PATH", "certs/server.key")
        ssl_certfile = os.getenv("TLS_CERT_PATH", "certs/server.crt")
        
        # Check if certificates exist
        if not (Path(ssl_keyfile).exists() and Path(ssl_certfile).exists()):
            print("⚠ TLS enabled but certificates not found. Generating self-signed certificate...")
            from core.security.tls_config import TLSManager
            tls_manager = TLSManager()
            domain = os.getenv("DOMAIN", "localhost")
            tls_manager.generate_self_signed_cert(domain)
            print(f"✓ Generated self-signed certificate for {domain}")
    
    print(f"\n📡 Starting server on {host}:{port}")
    print(f"   Workers: {workers}")
    print(f"   Reload: {reload}")
    print(f"   TLS: {'Enabled' if tls_enabled else 'Disabled'}")
    print("\n" + "=" * 60)
    print("🌐 Access the application:")
    protocol = "https" if tls_enabled else "http"
    print(f"   Web UI:    {protocol}://{host}:{port}/")
    print(f"   API Docs:  {protocol}://{host}:{port}/docs")
    print(f"   Health:    {protocol}://{host}:{port}/health")
    print(f"   Metrics:   {protocol}://{host}:{port}/metrics")
    print("=" * 60 + "\n")
    
    # Run server
    uvicorn.run(
        "ui.web.app:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile,
        log_level=log_level.lower(),
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
