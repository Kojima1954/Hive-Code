"""Tests for TLS/SSL configuration and certificate management."""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

from core.security.tls_config import TLSManager


@pytest.fixture
def tls_dir():
    """Create a temporary directory for TLS certs."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


@pytest.fixture
def tls_manager(tls_dir):
    """Create a TLSManager with a temp directory."""
    return TLSManager(cert_dir=tls_dir)


class TestGenerateSelfSignedCert:
    """Tests for generate_self_signed_cert."""

    @pytest.mark.unit
    def test_creates_key_and_cert_files(self, tls_manager, tls_dir):
        """Should create key and cert files on disk."""
        key_path, cert_path = tls_manager.generate_self_signed_cert("localhost")
        assert key_path.exists()
        assert cert_path.exists()
        assert key_path.stat().st_size > 0
        assert cert_path.stat().st_size > 0

    @pytest.mark.unit
    def test_returns_correct_paths(self, tls_manager, tls_dir):
        """Should return paths within the cert directory."""
        key_path, cert_path = tls_manager.generate_self_signed_cert("example.com")
        assert str(key_path).startswith(tls_dir)
        assert str(cert_path).startswith(tls_dir)
        assert key_path.name == "server.key"
        assert cert_path.name == "server.crt"

    @pytest.mark.unit
    def test_custom_filenames(self, tls_manager):
        """Should use custom filenames when specified."""
        key_path, cert_path = tls_manager.generate_self_signed_cert(
            "localhost", key_file="custom.key", cert_file="custom.crt"
        )
        assert key_path.name == "custom.key"
        assert cert_path.name == "custom.crt"

    @pytest.mark.unit
    def test_reuses_existing_cert(self, tls_manager):
        """Should reuse existing certs instead of regenerating."""
        key1, cert1 = tls_manager.generate_self_signed_cert("localhost")
        content1 = cert1.read_bytes()

        key2, cert2 = tls_manager.generate_self_signed_cert("localhost")
        content2 = cert2.read_bytes()

        assert content1 == content2

    @pytest.mark.unit
    def test_cert_contains_domain(self, tls_manager):
        """Generated cert should contain the specified domain."""
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.x509.oid import ExtensionOID

        tls_manager.generate_self_signed_cert("myapp.example.com")
        cert = tls_manager.load_certificate()
        assert cert is not None

        # Check SAN extension
        san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        dns_names = san.value.get_values_for_type(x509.DNSName)
        assert "myapp.example.com" in dns_names


class TestLoadCertificate:
    """Tests for load_certificate."""

    @pytest.mark.unit
    def test_loads_existing_cert(self, tls_manager):
        """Should load a valid PEM certificate."""
        tls_manager.generate_self_signed_cert("localhost")
        cert = tls_manager.load_certificate()
        assert cert is not None

    @pytest.mark.unit
    def test_returns_none_for_missing_file(self, tls_manager):
        """Should return None when cert file doesn't exist."""
        cert = tls_manager.load_certificate("nonexistent.crt")
        assert cert is None

    @pytest.mark.unit
    def test_loaded_cert_has_correct_cn(self, tls_manager):
        """Loaded cert should have the correct Common Name."""
        from cryptography.x509.oid import NameOID

        tls_manager.generate_self_signed_cert("test.local")
        cert = tls_manager.load_certificate()
        cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        assert cn == "test.local"


class TestVerifyCertificate:
    """Tests for verify_certificate."""

    @pytest.mark.unit
    def test_valid_cert_returns_true(self, tls_manager):
        """Should return True for a freshly generated valid cert."""
        tls_manager.generate_self_signed_cert("localhost", validity_days=365)
        assert tls_manager.verify_certificate() is True

    @pytest.mark.unit
    def test_missing_cert_returns_false(self, tls_manager):
        """Should return False when cert file doesn't exist."""
        assert tls_manager.verify_certificate("nonexistent.crt") is False

    @pytest.mark.unit
    def test_expired_cert_returns_false(self, tls_manager):
        """Should return False for an expired certificate."""
        # Generate cert with 0-day validity (effectively already expired)
        tls_manager.generate_self_signed_cert(
            "localhost",
            key_file="expired.key",
            cert_file="expired.crt",
            validity_days=0,
        )
        assert tls_manager.verify_certificate("expired.crt") is False


class TestGetTlsConfig:
    """Tests for get_tls_config."""

    @pytest.mark.unit
    def test_returns_config_with_existing_files(self, tls_manager):
        """Should return config dict when both files exist."""
        tls_manager.generate_self_signed_cert("localhost")
        config = tls_manager.get_tls_config()
        assert config is not None
        assert "ssl_keyfile" in config
        assert "ssl_certfile" in config
        assert config["ssl_keyfile"].endswith("server.key")
        assert config["ssl_certfile"].endswith("server.crt")

    @pytest.mark.unit
    def test_returns_none_when_missing_files(self, tls_manager):
        """Should return None when key or cert files are missing."""
        config = tls_manager.get_tls_config()
        assert config is None

    @pytest.mark.unit
    def test_returns_none_when_only_key_exists(self, tls_manager, tls_dir):
        """Should return None when only key file exists."""
        (Path(tls_dir) / "server.key").touch()
        config = tls_manager.get_tls_config()
        assert config is None
