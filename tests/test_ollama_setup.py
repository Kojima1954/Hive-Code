"""Tests for Ollama auto-detection, installation, and bootstrapping."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from core.utils.ollama_setup import (
    is_ollama_running,
    is_ollama_installed,
    install_ollama,
    start_ollama_server,
    pull_model,
    ensure_ollama,
)


# --- is_ollama_running ---

@pytest.mark.unit
async def test_is_ollama_running_returns_true_when_reachable():
    """Test detection when Ollama is reachable."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("core.utils.ollama_setup.httpx.AsyncClient", return_value=mock_client):
        result = await is_ollama_running()
    assert result is True


@pytest.mark.unit
async def test_is_ollama_running_returns_false_on_error():
    """Test detection when Ollama is not reachable."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("core.utils.ollama_setup.httpx.AsyncClient", return_value=mock_client):
        result = await is_ollama_running()
    assert result is False


# --- is_ollama_installed ---

@pytest.mark.unit
def test_is_ollama_installed_true():
    """Test when ollama binary is on PATH."""
    with patch("shutil.which", return_value="/usr/local/bin/ollama"):
        assert is_ollama_installed() is True


@pytest.mark.unit
def test_is_ollama_installed_false():
    """Test when ollama binary is NOT on PATH."""
    with patch("shutil.which", return_value=None):
        assert is_ollama_installed() is False


# --- install_ollama ---

@pytest.mark.unit
async def test_install_ollama_unsupported_platform():
    """Test install fails gracefully on unsupported platform."""
    with patch("platform.system", return_value="Windows"):
        result = await install_ollama()
    assert result is False


@pytest.mark.unit
async def test_install_ollama_success_linux():
    """Test successful install on Linux."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "echo installed"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stderr = ""

    with (
        patch("platform.system", return_value="Linux"),
        patch("core.utils.ollama_setup.httpx.AsyncClient", return_value=mock_client),
        patch("subprocess.run", return_value=mock_proc),
    ):
        result = await install_ollama()
    assert result is True


@pytest.mark.unit
async def test_install_ollama_script_failure():
    """Test install when script returns non-zero."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "exit 1"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stderr = "some error"

    with (
        patch("platform.system", return_value="Linux"),
        patch("core.utils.ollama_setup.httpx.AsyncClient", return_value=mock_client),
        patch("subprocess.run", return_value=mock_proc),
    ):
        result = await install_ollama()
    assert result is False


# --- start_ollama_server ---

@pytest.mark.unit
async def test_start_ollama_server_already_running():
    """Test no-op when server is already running."""
    with patch("core.utils.ollama_setup.is_ollama_running", return_value=True):
        result = await start_ollama_server()
    assert result is True


@pytest.mark.unit
async def test_start_ollama_server_binary_not_found():
    """Test failure when binary is not installed."""
    with (
        patch("core.utils.ollama_setup.is_ollama_running", return_value=False),
        patch("core.utils.ollama_setup.is_ollama_installed", return_value=False),
    ):
        result = await start_ollama_server()
    assert result is False


# --- pull_model ---

@pytest.mark.unit
async def test_pull_model_already_available():
    """Test when model is already present."""
    mock_show = MagicMock()
    mock_show.status_code = 200

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_show)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("core.utils.ollama_setup.httpx.AsyncClient", return_value=mock_client):
        result = await pull_model("phi3:mini")
    assert result is True


@pytest.mark.unit
async def test_pull_model_downloads_successfully():
    """Test successful model pull when not present."""
    mock_show = MagicMock()
    mock_show.status_code = 404  # not present

    mock_pull = MagicMock()
    mock_pull.status_code = 200

    call_count = 0

    async def mock_post(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if "show" in url:
            return mock_show
        return mock_pull

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("core.utils.ollama_setup.httpx.AsyncClient", return_value=mock_client):
        result = await pull_model("phi3:mini")
    assert result is True


# --- ensure_ollama ---

@pytest.mark.unit
async def test_ensure_ollama_already_running_no_models():
    """Test ensure_ollama when server is already running, no models requested."""
    with patch("core.utils.ollama_setup.is_ollama_running", return_value=True):
        result = await ensure_ollama(models=[])
    assert result is True


@pytest.mark.unit
async def test_ensure_ollama_not_installed_auto_install_disabled():
    """Test ensure_ollama when not installed and auto_install=False."""
    with (
        patch("core.utils.ollama_setup.is_ollama_running", return_value=False),
        patch("core.utils.ollama_setup.is_ollama_installed", return_value=False),
    ):
        result = await ensure_ollama(auto_install=False)
    assert result is False


@pytest.mark.unit
async def test_ensure_ollama_installs_starts_and_pulls():
    """Test full bootstrap: install, start, pull models."""
    with (
        patch("core.utils.ollama_setup.is_ollama_running", side_effect=[False, True]),
        patch("core.utils.ollama_setup.is_ollama_installed", return_value=False),
        patch("core.utils.ollama_setup.install_ollama", return_value=True),
        patch("core.utils.ollama_setup.start_ollama_server", return_value=True),
        patch("core.utils.ollama_setup.pull_model", return_value=True) as mock_pull,
    ):
        result = await ensure_ollama(models=["phi3:mini", "llama2"])
    assert result is True
    assert mock_pull.call_count == 2
