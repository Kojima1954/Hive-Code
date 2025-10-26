"""TLS/SSL configuration and certificate management."""

import os
import logging
from pathlib import Path
from typing import Optional, Tuple

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TLSManager:
    """TLS/SSL certificate manager for secure communications."""

    def __init__(self, cert_dir: str = "certs"):
        """
        Initialize TLS manager.

        Args:
            cert_dir: Directory to store certificates
        """
        self.cert_dir = Path(cert_dir)
        self.cert_dir.mkdir(exist_ok=True)

    def generate_self_signed_cert(
        self,
        domain: str,
        key_file: str = "server.key",
        cert_file: str = "server.crt",
        validity_days: int = 365
    ) -> Tuple[Path, Path]:
        """
        Generate a self-signed certificate for development/testing.

        Args:
            domain: Domain name for the certificate
            key_file: Filename for private key
            cert_file: Filename for certificate
            validity_days: Certificate validity in days

        Returns:
            Tuple of (key_path, cert_path)
        """
        key_path = self.cert_dir / key_file
        cert_path = self.cert_dir / cert_file

        # Check if certificate already exists
        if key_path.exists() and cert_path.exists():
            logger.info(f"Using existing certificate: {cert_path}")
            return key_path, cert_path

        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Swarm Network"),
            x509.NameAttribute(NameOID.COMMON_NAME, domain),
        ])

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=validity_days))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName(domain),
                    x509.DNSName(f"*.{domain}"),
                    x509.DNSName("localhost"),
                ]),
                critical=False,
            )
            .sign(private_key, hashes.SHA256(), default_backend())
        )

        # Write private key
        with open(key_path, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption()
                )
            )

        # Write certificate
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        logger.info(f"Generated self-signed certificate: {cert_path}")
        return key_path, cert_path

    def load_certificate(
        self,
        cert_file: str = "server.crt"
    ) -> Optional[x509.Certificate]:
        """
        Load an X.509 certificate.

        Args:
            cert_file: Certificate filename

        Returns:
            X.509 Certificate object or None if not found
        """
        cert_path = self.cert_dir / cert_file
        if not cert_path.exists():
            logger.warning(f"Certificate not found: {cert_path}")
            return None

        try:
            with open(cert_path, "rb") as f:
                cert_data = f.read()
                cert = x509.load_pem_x509_certificate(cert_data, default_backend())
                return cert
        except Exception as e:
            logger.error(f"Failed to load certificate: {e}")
            return None

    def verify_certificate(self, cert_file: str = "server.crt") -> bool:
        """
        Verify certificate validity.

        Args:
            cert_file: Certificate filename

        Returns:
            bool: True if certificate is valid, False otherwise
        """
        cert = self.load_certificate(cert_file)
        if not cert:
            return False

        try:
            # Check if certificate is expired
            now = datetime.utcnow()
            if now < cert.not_valid_before or now > cert.not_valid_after:
                logger.warning("Certificate is expired or not yet valid")
                return False

            logger.info("Certificate is valid")
            return True
        except Exception as e:
            logger.error(f"Certificate verification failed: {e}")
            return False

    def get_tls_config(
        self,
        key_file: str = "server.key",
        cert_file: str = "server.crt"
    ) -> Optional[dict]:
        """
        Get TLS configuration for uvicorn.

        Args:
            key_file: Private key filename
            cert_file: Certificate filename

        Returns:
            dict: TLS configuration or None if files don't exist
        """
        key_path = self.cert_dir / key_file
        cert_path = self.cert_dir / cert_file

        if not key_path.exists() or not cert_path.exists():
            logger.warning("TLS certificate or key not found")
            return None

        return {
            "ssl_keyfile": str(key_path),
            "ssl_certfile": str(cert_path),
        }
