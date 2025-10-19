"""Hybrid encryption module using RSA and AES-GCM."""

import base64
import os
from typing import Tuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class HybridEncryption:
    """Hybrid encryption using RSA-4096 for key exchange and AES-GCM for data encryption."""

    def __init__(self):
        """Initialize hybrid encryption with RSA key pair generation."""
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()

    def export_public_key(self) -> str:
        """
        Export the public key in PEM format.

        Returns:
            str: Base64-encoded PEM public key
        """
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return base64.b64encode(pem).decode('utf-8')

    def import_public_key(self, public_key_b64: str) -> rsa.RSAPublicKey:
        """
        Import a public key from base64-encoded PEM format.

        Args:
            public_key_b64: Base64-encoded PEM public key

        Returns:
            RSAPublicKey: The imported public key
        """
        pem = base64.b64decode(public_key_b64.encode('utf-8'))
        return serialization.load_pem_public_key(pem, backend=default_backend())

    def encrypt(self, data: bytes, recipient_public_key: rsa.RSAPublicKey) -> Tuple[bytes, bytes, bytes]:
        """
        Encrypt data using hybrid encryption (AES-GCM + RSA).

        For messages larger than 470 bytes, uses AES-GCM encryption with RSA-encrypted key.
        For smaller messages, uses RSA directly.

        Args:
            data: Data to encrypt
            recipient_public_key: Recipient's RSA public key

        Returns:
            Tuple of (encrypted_data, encrypted_key, nonce)
        """
        if len(data) > 470:  # Use hybrid encryption for large messages
            # Generate random AES key
            aes_key = AESGCM.generate_key(bit_length=256)
            aesgcm = AESGCM(aes_key)
            nonce = os.urandom(12)

            # Encrypt data with AES-GCM
            encrypted_data = aesgcm.encrypt(nonce, data, None)

            # Encrypt AES key with RSA
            encrypted_key = recipient_public_key.encrypt(
                aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

            return encrypted_data, encrypted_key, nonce
        else:
            # Use RSA directly for small messages
            encrypted_data = recipient_public_key.encrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return encrypted_data, b'', b''

    def decrypt(self, encrypted_data: bytes, encrypted_key: bytes, nonce: bytes) -> bytes:
        """
        Decrypt data using hybrid encryption.

        Args:
            encrypted_data: Encrypted data
            encrypted_key: RSA-encrypted AES key (empty for small messages)
            nonce: Nonce used for AES-GCM (empty for small messages)

        Returns:
            bytes: Decrypted data
        """
        if encrypted_key:  # Hybrid encryption was used
            # Decrypt AES key with RSA
            aes_key = self.private_key.decrypt(
                encrypted_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

            # Decrypt data with AES-GCM
            aesgcm = AESGCM(aes_key)
            data = aesgcm.decrypt(nonce, encrypted_data, None)
            return data
        else:
            # RSA direct decryption
            data = self.private_key.decrypt(
                encrypted_data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return data
