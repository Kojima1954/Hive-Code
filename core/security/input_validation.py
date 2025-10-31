"""Input validation and sanitization utilities."""

import re
import logging
from typing import Optional, Pattern

logger = logging.getLogger(__name__)

# Constants
MAX_MESSAGE_LENGTH = 10000
MAX_USERNAME_LENGTH = 64
MAX_USER_ID_LENGTH = 128
MAX_TAG_LENGTH = 50
MAX_TAGS_COUNT = 20

# Regex patterns for validation
USERNAME_PATTERN: Pattern = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')
USER_ID_PATTERN: Pattern = re.compile(r'^[a-zA-Z0-9_-]{1,128}$')
TAG_PATTERN: Pattern = re.compile(r'^[a-zA-Z0-9_-]{1,50}$')
REDIS_KEY_PATTERN: Pattern = re.compile(r'^[a-zA-Z0-9:_-]{1,256}$')


class ValidationError(ValueError):
    """Custom exception for validation errors."""
    pass


def sanitize_redis_key(key: str) -> str:
    """
    Sanitize Redis key to prevent injection attacks.
    
    Args:
        key: Redis key to sanitize
        
    Returns:
        Sanitized key
        
    Raises:
        ValidationError: If key contains invalid characters
    """
    if not key:
        raise ValidationError("Redis key cannot be empty")
    
    if len(key) > 256:
        raise ValidationError("Redis key too long (max 256 characters)")
    
    # Only allow alphanumeric, colon, underscore, and hyphen
    if not REDIS_KEY_PATTERN.match(key):
        raise ValidationError("Redis key contains invalid characters")
    
    return key


def validate_username(username: str) -> str:
    """
    Validate and sanitize username.
    
    Args:
        username: Username to validate
        
    Returns:
        Validated username
        
    Raises:
        ValidationError: If username is invalid
    """
    if not username:
        raise ValidationError("Username cannot be empty")
    
    if len(username) > MAX_USERNAME_LENGTH:
        raise ValidationError(f"Username too long (max {MAX_USERNAME_LENGTH} characters)")
    
    if not USERNAME_PATTERN.match(username):
        raise ValidationError("Username contains invalid characters (only alphanumeric, underscore, and hyphen allowed)")
    
    return username


def validate_user_id(user_id: str) -> str:
    """
    Validate and sanitize user ID.
    
    Args:
        user_id: User ID to validate
        
    Returns:
        Validated user ID
        
    Raises:
        ValidationError: If user ID is invalid
    """
    if not user_id:
        raise ValidationError("User ID cannot be empty")
    
    if len(user_id) > MAX_USER_ID_LENGTH:
        raise ValidationError(f"User ID too long (max {MAX_USER_ID_LENGTH} characters)")
    
    if not USER_ID_PATTERN.match(user_id):
        raise ValidationError("User ID contains invalid characters (only alphanumeric, underscore, and hyphen allowed)")
    
    return user_id


def validate_message_content(content: str) -> str:
    """
    Validate message content.
    
    Args:
        content: Message content to validate
        
    Returns:
        Validated content
        
    Raises:
        ValidationError: If content is invalid
    """
    if not content:
        raise ValidationError("Message content cannot be empty")
    
    if len(content) > MAX_MESSAGE_LENGTH:
        raise ValidationError(f"Message content too long (max {MAX_MESSAGE_LENGTH} characters)")
    
    # Remove null bytes which can cause issues
    content = content.replace('\x00', '')
    
    return content


def validate_tag(tag: str) -> str:
    """
    Validate a single tag.
    
    Args:
        tag: Tag to validate
        
    Returns:
        Validated tag
        
    Raises:
        ValidationError: If tag is invalid
    """
    if not tag:
        raise ValidationError("Tag cannot be empty")
    
    if len(tag) > MAX_TAG_LENGTH:
        raise ValidationError(f"Tag too long (max {MAX_TAG_LENGTH} characters)")
    
    if not TAG_PATTERN.match(tag):
        raise ValidationError("Tag contains invalid characters (only alphanumeric, underscore, and hyphen allowed)")
    
    return tag


def validate_tags(tags: list) -> list:
    """
    Validate a list of tags.
    
    Args:
        tags: List of tags to validate
        
    Returns:
        List of validated tags
        
    Raises:
        ValidationError: If tags are invalid
    """
    if not isinstance(tags, list):
        raise ValidationError("Tags must be a list")
    
    if len(tags) > MAX_TAGS_COUNT:
        raise ValidationError(f"Too many tags (max {MAX_TAGS_COUNT})")
    
    return [validate_tag(tag) for tag in tags]


def validate_importance(importance: float) -> float:
    """
    Validate importance score.
    
    Args:
        importance: Importance score to validate
        
    Returns:
        Validated importance (clamped to 0.0-10.0)
    """
    if not isinstance(importance, (int, float)):
        raise ValidationError("Importance must be a number")
    
    # Clamp to valid range
    return max(0.0, min(10.0, float(importance)))


def validate_limit(limit: int, max_limit: int = 100) -> int:
    """
    Validate pagination limit.
    
    Args:
        limit: Limit value to validate
        max_limit: Maximum allowed limit
        
    Returns:
        Validated limit
        
    Raises:
        ValidationError: If limit is invalid
    """
    if not isinstance(limit, int):
        raise ValidationError("Limit must be an integer")
    
    if limit < 1:
        raise ValidationError("Limit must be at least 1")
    
    if limit > max_limit:
        raise ValidationError(f"Limit too high (max {max_limit})")
    
    return limit
