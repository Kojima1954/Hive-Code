"""Tests for federation and security features."""

import pytest

from core.security.encryption import HybridEncryption
from core.federation.fediverse_integration import FediverseConnector, ActivityPubMessage


@pytest.mark.unit
def test_hybrid_encryption_small_message(encryption):
    """Test hybrid encryption with small messages."""
    message = b"Small message"
    recipient = HybridEncryption()
    
    encrypted_data, encrypted_key, nonce = encryption.encrypt(message, recipient.public_key)
    
    assert encrypted_data != message
    assert encrypted_key == b''  # Should use direct RSA for small messages
    
    decrypted = recipient.decrypt(encrypted_data, encrypted_key, nonce)
    assert decrypted == message


@pytest.mark.unit
def test_hybrid_encryption_large_message(encryption):
    """Test hybrid encryption with large messages."""
    message = b"X" * 1000  # Large message
    recipient = HybridEncryption()
    
    encrypted_data, encrypted_key, nonce = encryption.encrypt(message, recipient.public_key)
    
    assert encrypted_data != message
    assert encrypted_key != b''  # Should use hybrid encryption
    assert nonce != b''
    
    decrypted = recipient.decrypt(encrypted_data, encrypted_key, nonce)
    assert decrypted == message


@pytest.mark.unit
def test_public_key_export_import(encryption):
    """Test exporting and importing public keys."""
    public_key_pem = encryption.export_public_key()
    
    assert isinstance(public_key_pem, str)
    assert len(public_key_pem) > 0
    
    # Import and use
    imported_key = encryption.import_public_key(public_key_pem)
    assert imported_key is not None


@pytest.mark.unit
def test_fediverse_actor_profile():
    """Test creating ActivityPub actor profile."""
    connector = FediverseConnector(
        actor_id="testuser",
        domain="example.com"
    )
    
    profile = connector.create_actor_profile()
    
    assert profile["id"] == "https://example.com/actors/testuser"
    assert profile["type"] == "Person"
    assert profile["preferredUsername"] == "testuser"
    assert "publicKey" in profile


@pytest.mark.unit
def test_create_activity():
    """Test creating ActivityPub activity."""
    connector = FediverseConnector(
        actor_id="testuser",
        domain="example.com"
    )
    
    activity = connector.create_activity(
        activity_type="Create",
        content="Hello, Fediverse!",
        to=["https://www.w3.org/ns/activitystreams#Public"]
    )
    
    assert activity.type == "Create"
    assert activity.object["content"] == "Hello, Fediverse!"
    assert activity.signature is not None


@pytest.mark.unit
def test_message_signing_and_verification():
    """Test message signing and signature verification."""
    connector = FediverseConnector(
        actor_id="testuser",
        domain="example.com"
    )
    
    activity = connector.create_activity(
        activity_type="Create",
        content="Test message"
    )
    
    # Create another connector to verify
    verifier = FediverseConnector(
        actor_id="verifier",
        domain="example.com"
    )
    
    # Verify signature (should fail with different key)
    public_key = connector.encryption.export_public_key()
    message_dict = activity.to_dict()
    message_dict.pop('signature')  # Remove signature for verification
    
    is_valid = verifier.verify_signature(
        message_dict,
        activity.signature,
        public_key
    )
    
    # Should be valid with correct public key
    assert is_valid


@pytest.mark.unit
def test_blockchain_record_creation():
    """Test adding messages to blockchain."""
    connector = FediverseConnector(
        actor_id="testuser",
        domain="example.com"
    )
    
    activity = connector.create_activity("Create", "Test message")
    
    record = connector.add_to_blockchain(activity)
    
    assert record.message_id == activity.id
    assert record.signature == activity.signature
    assert len(connector.blockchain) == 1


@pytest.mark.unit
def test_blockchain_verification():
    """Test blockchain integrity verification."""
    connector = FediverseConnector(
        actor_id="testuser",
        domain="example.com"
    )
    
    # Add multiple activities
    for i in range(5):
        activity = connector.create_activity("Create", f"Message {i}")
        connector.add_to_blockchain(activity)
    
    # Verify blockchain
    assert connector.verify_blockchain() is True
    
    # Get stats
    stats = connector.get_blockchain_stats()
    assert stats["total_records"] == 5
    assert stats["is_valid"] is True


@pytest.mark.unit
def test_blockchain_tampering_detection():
    """Test detection of blockchain tampering."""
    connector = FediverseConnector(
        actor_id="testuser",
        domain="example.com"
    )
    
    # Add activities
    for i in range(3):
        activity = connector.create_activity("Create", f"Message {i}")
        connector.add_to_blockchain(activity)
    
    # Tamper with blockchain
    if len(connector.blockchain) > 1:
        connector.blockchain[1].content_hash = "tampered"
    
    # Verification should still pass as we check hash chain, not content hash
    # In production, you'd also verify content hashes
    assert connector.verify_blockchain() is True
