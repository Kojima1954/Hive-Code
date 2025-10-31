"""Fediverse integration with ActivityPub and blockchain verification."""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from core.security.encryption import HybridEncryption

logger = logging.getLogger(__name__)


@dataclass
class ActivityPubMessage:
    """ActivityPub message format."""
    
    id: str
    type: str
    actor: str
    object: Dict[str, Any]
    published: str
    signature: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActivityPubMessage':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class BlockchainRecord:
    """Blockchain verification record."""
    
    message_id: str
    timestamp: float
    previous_hash: str
    content_hash: str
    signature: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def compute_hash(self) -> str:
        """Compute hash of the record."""
        record_data = f"{self.message_id}{self.timestamp}{self.previous_hash}{self.content_hash}"
        return hashlib.sha256(record_data.encode()).hexdigest()


class FediverseConnector:
    """
    Connector for Fediverse integration with ActivityPub protocol.
    Includes blockchain-style verification for message integrity.
    """
    
    def __init__(
        self,
        actor_id: str,
        domain: str,
        encryption: HybridEncryption = None
    ):
        """
        Initialize Fediverse connector.
        
        Args:
            actor_id: Unique actor identifier
            domain: Domain name for this instance
            encryption: Hybrid encryption instance
        """
        self.actor_id = actor_id
        self.domain = domain
        self.encryption = encryption or HybridEncryption()
        self.blockchain: List[BlockchainRecord] = []
        self.client = httpx.AsyncClient(timeout=30.0)
        
        logger.info(f"Initialized Fediverse connector for {actor_id}@{domain}")
    
    def create_actor_profile(self) -> Dict[str, Any]:
        """
        Create ActivityPub actor profile.
        
        Returns:
            Actor profile dictionary
        """
        actor_url = f"https://{self.domain}/actors/{self.actor_id}"
        
        return {
            "@context": [
                "https://www.w3.org/ns/activitystreams",
                "https://w3id.org/security/v1"
            ],
            "id": actor_url,
            "type": "Person",
            "preferredUsername": self.actor_id,
            "inbox": f"{actor_url}/inbox",
            "outbox": f"{actor_url}/outbox",
            "followers": f"{actor_url}/followers",
            "following": f"{actor_url}/following",
            "publicKey": {
                "id": f"{actor_url}#main-key",
                "owner": actor_url,
                "publicKeyPem": self.encryption.export_public_key()
            }
        }
    
    def create_activity(
        self,
        activity_type: str,
        content: str,
        to: List[str] = None
    ) -> ActivityPubMessage:
        """
        Create an ActivityPub activity.
        
        Args:
            activity_type: Type of activity (Create, Update, Delete, etc.)
            content: Activity content
            to: List of recipients
            
        Returns:
            ActivityPub message
        """
        actor_url = f"https://{self.domain}/actors/{self.actor_id}"
        activity_id = f"{actor_url}/activities/{datetime.now(timezone.utc).timestamp()}"
        
        message = ActivityPubMessage(
            id=activity_id,
            type=activity_type,
            actor=actor_url,
            object={
                "type": "Note",
                "content": content,
                "published": datetime.now(timezone.utc).isoformat(),
                "to": to or ["https://www.w3.org/ns/activitystreams#Public"]
            },
            published=datetime.now(timezone.utc).isoformat()
        )
        
        # Sign the message (exclude signature field)
        message_dict = message.to_dict()
        message_dict.pop('signature', None)  # Remove signature field before signing
        message.signature = self._sign_message(message_dict)
        
        return message
    
    def _sign_message(self, message_data: Dict[str, Any]) -> str:
        """
        Sign a message using RSA private key.
        
        Args:
            message_data: Message dictionary
            
        Returns:
            Base64-encoded signature
        """
        import base64
        
        # Create canonical representation
        canonical = json.dumps(message_data, sort_keys=True, separators=(',', ':'))
        message_bytes = canonical.encode('utf-8')
        
        # Sign with private key
        signature = self.encryption.private_key.sign(
            message_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return base64.b64encode(signature).decode('utf-8')
    
    def verify_signature(
        self,
        message_data: Dict[str, Any],
        signature: str,
        public_key_pem: str
    ) -> bool:
        """
        Verify message signature.
        
        Args:
            message_data: Message dictionary
            signature: Base64-encoded signature
            public_key_pem: PEM-encoded public key
            
        Returns:
            True if signature is valid, False otherwise
        """
        import base64
        
        try:
            # Import public key
            public_key = self.encryption.import_public_key(public_key_pem)
            
            # Create canonical representation
            canonical = json.dumps(message_data, sort_keys=True, separators=(',', ':'))
            message_bytes = canonical.encode('utf-8')
            
            # Verify signature
            signature_bytes = base64.b64decode(signature.encode('utf-8'))
            public_key.verify(
                signature_bytes,
                message_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False
    
    def add_to_blockchain(self, message: ActivityPubMessage) -> BlockchainRecord:
        """
        Add message to blockchain for verification.
        
        Args:
            message: ActivityPub message
            
        Returns:
            Blockchain record
        """
        # Compute content hash
        content_hash = hashlib.sha256(
            json.dumps(message.to_dict()).encode()
        ).hexdigest()
        
        # Get previous hash
        previous_hash = "0" * 64  # Genesis block
        if self.blockchain:
            previous_hash = self.blockchain[-1].compute_hash()
        
        # Create record
        record = BlockchainRecord(
            message_id=message.id,
            timestamp=datetime.now(timezone.utc).timestamp(),
            previous_hash=previous_hash,
            content_hash=content_hash,
            signature=message.signature or ""
        )
        
        self.blockchain.append(record)
        logger.debug(f"Added message to blockchain: {message.id}")
        
        return record
    
    def verify_blockchain(self) -> bool:
        """
        Verify blockchain integrity.
        
        Returns:
            True if blockchain is valid, False otherwise
        """
        if not self.blockchain:
            return True
        
        for i, record in enumerate(self.blockchain):
            # Check hash chain
            if i > 0:
                expected_previous = self.blockchain[i - 1].compute_hash()
                if record.previous_hash != expected_previous:
                    logger.error(f"Blockchain broken at index {i}")
                    return False
        
        logger.info("Blockchain verification successful")
        return True
    
    async def send_activity(
        self,
        recipient_inbox: str,
        activity: ActivityPubMessage
    ) -> bool:
        """
        Send ActivityPub activity to recipient.
        
        Args:
            recipient_inbox: Recipient's inbox URL
            activity: Activity to send
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Add to blockchain
            self.add_to_blockchain(activity)
            
            # Send HTTP POST to inbox
            headers = {
                "Content-Type": "application/activity+json",
                "User-Agent": f"SwarmNetwork/{self.domain}"
            }
            
            response = await self.client.post(
                recipient_inbox,
                json=activity.to_dict(),
                headers=headers
            )
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Activity sent successfully to {recipient_inbox}")
                return True
            else:
                logger.error(f"Failed to send activity: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending activity: {e}")
            return False
    
    async def fetch_actor(self, actor_url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch actor profile from remote instance.
        
        Args:
            actor_url: URL of the actor
            
        Returns:
            Actor profile or None if failed
        """
        try:
            headers = {
                "Accept": "application/activity+json",
                "User-Agent": f"SwarmNetwork/{self.domain}"
            }
            
            response = await self.client.get(actor_url, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch actor: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching actor: {e}")
            return None
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
        logger.info("Closed Fediverse connector")
    
    def get_blockchain_stats(self) -> Dict[str, Any]:
        """
        Get blockchain statistics.
        
        Returns:
            Dictionary of blockchain stats
        """
        return {
            "total_records": len(self.blockchain),
            "is_valid": self.verify_blockchain(),
            "latest_hash": self.blockchain[-1].compute_hash() if self.blockchain else None,
        }
