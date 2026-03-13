"""Ollama auto-detection, installation, and model bootstrapping."""

import asyncio
import logging
import os
import platform
import shutil
import subprocess
import sys
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
INSTALL_SCRIPT_URL = "https://ollama.com/install.sh"
MODEL_PULL_TIMEOUT = 600  # 10 minutes for large model pulls


async def is_ollama_running(host: str = DEFAULT_OLLAMA_HOST) -> bool:
    """Check if an Ollama instance is reachable."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{host}/api/version")
            return resp.status_code == 200
    except Exception:
        return False


def is_ollama_installed() -> bool:
    """Check if the ollama binary is available on PATH."""
    return shutil.which("ollama") is not None


async def install_ollama() -> bool:
    """Install Ollama using the official install script (Linux/macOS).

    Returns True if installation succeeded, False otherwise.
    """
    system = platform.system().lower()

    if system not in ("linux", "darwin"):
        logger.warning(
            f"Automatic Ollama installation is not supported on {system}. "
            "Please install manually: https://ollama.com/download"
        )
        return False

    logger.info("Ollama not found. Downloading and installing...")

    try:
        # Download the install script
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(INSTALL_SCRIPT_URL)
            resp.raise_for_status()
            install_script = resp.text

        # Run the install script
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["sh"],
                input=install_script,
                capture_output=True,
                text=True,
                timeout=300,
            ),
        )

        if result.returncode == 0:
            logger.info("Ollama installed successfully")
            return True
        else:
            logger.error(f"Ollama install script failed: {result.stderr}")
            return False

    except httpx.HTTPError as e:
        logger.error(f"Failed to download Ollama install script: {e}")
        return False
    except subprocess.TimeoutExpired:
        logger.error("Ollama installation timed out")
        return False
    except Exception as e:
        logger.error(f"Unexpected error installing Ollama: {e}")
        return False


async def start_ollama_server() -> bool:
    """Start the Ollama server as a background process.

    Returns True if the server started and is reachable.
    """
    if await is_ollama_running():
        logger.info("Ollama server already running")
        return True

    if not is_ollama_installed():
        logger.warning("Cannot start Ollama server: binary not found")
        return False

    logger.info("Starting Ollama server...")

    try:
        # Start ollama serve as a detached subprocess
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Wait for server to become ready (up to 30 seconds)
        for i in range(30):
            await asyncio.sleep(1)
            if await is_ollama_running():
                logger.info("Ollama server is ready")
                return True

        logger.error("Ollama server did not become ready within 30 seconds")
        return False

    except Exception as e:
        logger.error(f"Failed to start Ollama server: {e}")
        return False


async def pull_model(model: str, host: str = DEFAULT_OLLAMA_HOST) -> bool:
    """Pull a model if it isn't already available locally.

    Returns True if the model is available (already present or pulled).
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{host}/api/show",
                json={"name": model},
            )
            if resp.status_code == 200:
                logger.info(f"Model '{model}' is already available")
                return True
    except Exception:
        pass

    logger.info(f"Pulling model '{model}' (this may take several minutes)...")

    try:
        async with httpx.AsyncClient(timeout=MODEL_PULL_TIMEOUT) as client:
            resp = await client.post(
                f"{host}/api/pull",
                json={"name": model, "stream": False},
                timeout=MODEL_PULL_TIMEOUT,
            )
            if resp.status_code == 200:
                logger.info(f"Model '{model}' pulled successfully")
                return True
            else:
                logger.error(
                    f"Failed to pull model '{model}': {resp.status_code} {resp.text}"
                )
                return False
    except httpx.TimeoutException:
        logger.error(f"Model pull timed out for '{model}'")
        return False
    except Exception as e:
        logger.error(f"Error pulling model '{model}': {e}")
        return False


async def ensure_ollama(
    host: str = DEFAULT_OLLAMA_HOST,
    models: Optional[List[str]] = None,
    auto_install: bool = True,
) -> bool:
    """Ensure Ollama is installed, running, and required models are available.

    This is the main entry point for bootstrapping Ollama. It:
    1. Checks if Ollama is reachable
    2. If not, checks if the binary is installed
    3. If not installed and auto_install is True, installs it
    4. Starts the server if not running
    5. Pulls any requested models that are missing

    Args:
        host: Ollama API endpoint
        models: List of model names to ensure are pulled
        auto_install: Whether to attempt automatic installation

    Returns:
        True if Ollama is running and all models are available
    """
    models = models or []

    # Step 1: Check if already running
    if await is_ollama_running(host):
        logger.info("Ollama is already running")
    else:
        # Step 2: Check if installed
        if not is_ollama_installed():
            if not auto_install:
                logger.warning(
                    "Ollama is not installed and auto_install is disabled. "
                    "Install manually: https://ollama.com/download"
                )
                return False

            # Step 3: Install
            installed = await install_ollama()
            if not installed:
                return False

        # Step 4: Start server
        started = await start_ollama_server()
        if not started:
            return False

    # Step 5: Pull models
    all_pulled = True
    for model in models:
        pulled = await pull_model(model, host)
        if not pulled:
            logger.warning(f"Could not pull model '{model}', continuing anyway")
            all_pulled = False

    return all_pulled
