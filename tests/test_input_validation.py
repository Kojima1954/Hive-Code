"""Tests for input validation and sanitization utilities."""

import pytest

from core.security.input_validation import (
    ValidationError,
    sanitize_redis_key,
    validate_username,
    validate_user_id,
    validate_message_content,
    validate_tag,
    validate_tags,
    validate_importance,
    validate_limit,
    MAX_MESSAGE_LENGTH,
    MAX_USERNAME_LENGTH,
    MAX_USER_ID_LENGTH,
    MAX_TAG_LENGTH,
    MAX_TAGS_COUNT,
)


class TestSanitizeRedisKey:
    """Tests for sanitize_redis_key."""

    @pytest.mark.unit
    def test_valid_simple_key(self):
        assert sanitize_redis_key("mykey") == "mykey"

    @pytest.mark.unit
    def test_valid_key_with_colons(self):
        assert sanitize_redis_key("ratelimit:user:123") == "ratelimit:user:123"

    @pytest.mark.unit
    def test_valid_key_with_dots_and_slashes(self):
        """IP addresses and URL paths must be allowed (C1 fix)."""
        key = "ratelimit:192.168.1.1:/api/messages"
        assert sanitize_redis_key(key) == key

    @pytest.mark.unit
    def test_valid_key_with_ipv4(self):
        assert sanitize_redis_key("banned:10.0.0.1") == "banned:10.0.0.1"

    @pytest.mark.unit
    def test_valid_key_with_hyphens_and_underscores(self):
        assert sanitize_redis_key("my-key_name:123") == "my-key_name:123"

    @pytest.mark.unit
    def test_empty_key_raises(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            sanitize_redis_key("")

    @pytest.mark.unit
    def test_too_long_key_raises(self):
        with pytest.raises(ValidationError, match="too long"):
            sanitize_redis_key("a" * 257)

    @pytest.mark.unit
    def test_max_length_key_valid(self):
        key = "a" * 256
        assert sanitize_redis_key(key) == key

    @pytest.mark.unit
    def test_invalid_characters_raise(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            sanitize_redis_key("key with spaces")

    @pytest.mark.unit
    def test_newline_injection_raises(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            sanitize_redis_key("key\ninjection")

    @pytest.mark.unit
    def test_null_byte_injection_raises(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            sanitize_redis_key("key\x00injection")


class TestValidateUsername:
    """Tests for validate_username."""

    @pytest.mark.unit
    def test_valid_username(self):
        assert validate_username("alice") == "alice"

    @pytest.mark.unit
    def test_valid_username_with_numbers(self):
        assert validate_username("user123") == "user123"

    @pytest.mark.unit
    def test_valid_username_with_hyphens_underscores(self):
        assert validate_username("my_user-name") == "my_user-name"

    @pytest.mark.unit
    def test_empty_username_raises(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_username("")

    @pytest.mark.unit
    def test_too_long_username_raises(self):
        with pytest.raises(ValidationError, match="too long"):
            validate_username("a" * (MAX_USERNAME_LENGTH + 1))

    @pytest.mark.unit
    def test_username_with_spaces_raises(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_username("user name")

    @pytest.mark.unit
    def test_username_with_special_chars_raises(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_username("user@name!")


class TestValidateUserId:
    """Tests for validate_user_id."""

    @pytest.mark.unit
    def test_valid_user_id(self):
        assert validate_user_id("user_123") == "user_123"

    @pytest.mark.unit
    def test_empty_user_id_raises(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_user_id("")

    @pytest.mark.unit
    def test_too_long_user_id_raises(self):
        with pytest.raises(ValidationError, match="too long"):
            validate_user_id("a" * (MAX_USER_ID_LENGTH + 1))


class TestValidateMessageContent:
    """Tests for validate_message_content."""

    @pytest.mark.unit
    def test_valid_content(self):
        assert validate_message_content("Hello, world!") == "Hello, world!"

    @pytest.mark.unit
    def test_empty_content_raises(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_message_content("")

    @pytest.mark.unit
    def test_too_long_content_raises(self):
        with pytest.raises(ValidationError, match="too long"):
            validate_message_content("a" * (MAX_MESSAGE_LENGTH + 1))

    @pytest.mark.unit
    def test_null_bytes_stripped(self):
        result = validate_message_content("hello\x00world")
        assert result == "helloworld"


class TestValidateTag:
    """Tests for validate_tag."""

    @pytest.mark.unit
    def test_valid_simple_tag(self):
        assert validate_tag("message") == "message"

    @pytest.mark.unit
    def test_valid_tag_with_colon(self):
        """Tags with colons must be allowed (H1 fix)."""
        assert validate_tag("sender:user_123") == "sender:user_123"

    @pytest.mark.unit
    def test_valid_tag_with_hyphen_underscore(self):
        assert validate_tag("my-tag_name") == "my-tag_name"

    @pytest.mark.unit
    def test_empty_tag_raises(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_tag("")

    @pytest.mark.unit
    def test_too_long_tag_raises(self):
        with pytest.raises(ValidationError, match="too long"):
            validate_tag("a" * (MAX_TAG_LENGTH + 1))

    @pytest.mark.unit
    def test_tag_with_spaces_raises(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_tag("bad tag")


class TestValidateTags:
    """Tests for validate_tags."""

    @pytest.mark.unit
    def test_valid_tags_list(self):
        result = validate_tags(["message", "sender:user_1"])
        assert result == ["message", "sender:user_1"]

    @pytest.mark.unit
    def test_too_many_tags_raises(self):
        with pytest.raises(ValidationError, match="Too many tags"):
            validate_tags(["tag"] * (MAX_TAGS_COUNT + 1))

    @pytest.mark.unit
    def test_non_list_raises(self):
        with pytest.raises(ValidationError, match="must be a list"):
            validate_tags("not-a-list")

    @pytest.mark.unit
    def test_empty_list_valid(self):
        assert validate_tags([]) == []


class TestValidateImportance:
    """Tests for validate_importance."""

    @pytest.mark.unit
    def test_valid_importance(self):
        assert validate_importance(5.0) == 5.0

    @pytest.mark.unit
    def test_clamps_high_value(self):
        assert validate_importance(15.0) == 10.0

    @pytest.mark.unit
    def test_clamps_low_value(self):
        assert validate_importance(-5.0) == 0.0

    @pytest.mark.unit
    def test_accepts_integer(self):
        assert validate_importance(3) == 3.0

    @pytest.mark.unit
    def test_non_number_raises(self):
        with pytest.raises(ValidationError, match="must be a number"):
            validate_importance("high")


class TestValidateLimit:
    """Tests for validate_limit."""

    @pytest.mark.unit
    def test_valid_limit(self):
        assert validate_limit(50) == 50

    @pytest.mark.unit
    def test_zero_limit_raises(self):
        with pytest.raises(ValidationError, match="at least 1"):
            validate_limit(0)

    @pytest.mark.unit
    def test_negative_limit_raises(self):
        with pytest.raises(ValidationError, match="at least 1"):
            validate_limit(-1)

    @pytest.mark.unit
    def test_over_max_limit_raises(self):
        with pytest.raises(ValidationError, match="too high"):
            validate_limit(200, max_limit=100)

    @pytest.mark.unit
    def test_non_integer_raises(self):
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_limit(5.5)

    @pytest.mark.unit
    def test_exact_max_limit_valid(self):
        assert validate_limit(100, max_limit=100) == 100
