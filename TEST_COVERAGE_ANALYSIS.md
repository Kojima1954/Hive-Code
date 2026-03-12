# Test Coverage Analysis

## Current State

The codebase has **5 test files** with approximately **68-79 unit tests** covering **5 of 12 source modules** (excluding `__init__.py` files). All tests are marked `@pytest.mark.unit` — there are **zero integration tests** despite the `integration` marker being defined in `pytest.ini`.

### Coverage by Module

| Source Module | Test File | Test Count | Coverage Level |
|---|---|---|---|
| `core/security/input_validation.py` | `test_input_validation.py` | ~39 | **Good** |
| `core/node/node_manager.py` | `test_node_manager.py` | ~11 | **Moderate** |
| `core/federation/fediverse_integration.py` | `test_federation.py` | ~10 | **Moderate** |
| `core/memory/diffmem_integration.py` | `test_diffmem.py` | ~9 | **Moderate** |
| `ui/web/app.py` | `test_api.py` | ~9 | **Low** (models + basic endpoints only) |
| `core/monitoring/health_check.py` | — | 0 | **None** |
| `core/monitoring/metrics.py` | — | 0 | **None** |
| `core/monitoring/logging_config.py` | — | 0 | **None** |
| `core/security/rate_limiting.py` | — | 0 | **None** |
| `core/security/tls_config.py` | — | 0 | **None** |
| `main.py` | — | 0 | **None** |

---

## Priority 1: Modules with Zero Test Coverage

### 1. `core/security/rate_limiting.py` — Critical, Security-Sensitive

This module contains `RateLimiter`, `DDoSProtection`, and `RateLimitMiddleware` — all security-critical components with no tests at all.

**Recommended tests:**
- `RateLimiter.check_rate_limit` — verify requests are allowed within limits and blocked when exceeded
- `RateLimiter.check_rate_limit` — verify `ValueError` is raised for non-positive `limit` or `window`
- `RateLimiter` — verify fail-open vs fail-closed behavior when Redis is unavailable
- `DDoSProtection.is_banned` / `ban_ip` — verify IP banning and ban expiry
- `DDoSProtection.check_request` — verify that repeated violations trigger an automatic ban after `MAX_VIOLATIONS_BEFORE_BAN` (5)
- `RateLimitMiddleware.get_client_ip` — verify `X-Forwarded-For` header parsing
- `RateLimitMiddleware.dispatch` — verify health check endpoints bypass rate limiting
- `RateLimitMiddleware.dispatch` — verify correct rule matching by endpoint pattern

### 2. `core/monitoring/health_check.py` — Important for Operations

`HealthChecker` provides system health status relied upon by the `/health` endpoint.

**Recommended tests:**
- `check_redis` — healthy path (mock Redis ping + info)
- `check_redis` — disabled path (no Redis client configured)
- `check_redis` — timeout and connection error paths
- `check_system_metrics` — verify CPU/memory/disk metrics structure (mock `psutil`)
- `check_uptime` — verify uptime calculation and ISO format
- `get_health_status` — verify overall status is "degraded" when Redis is unhealthy
- `get_health_status` — verify warnings for high CPU/memory/disk usage (>90%)
- `is_healthy` — returns `True` for both "healthy" and "degraded" statuses

### 3. `core/security/tls_config.py` — Important for Security

`TLSManager` handles certificate generation, loading, and verification.

**Recommended tests:**
- `generate_self_signed_cert` — verify key and cert files are created with correct content
- `generate_self_signed_cert` — verify existing certs are reused (not overwritten)
- `load_certificate` — verify loading a valid PEM certificate
- `load_certificate` — verify `None` returned for missing file
- `verify_certificate` — verify valid cert returns `True`
- `verify_certificate` — verify expired cert returns `False`
- `get_tls_config` — verify dict structure with existing files, `None` when missing

### 4. `core/monitoring/metrics.py` — Lower Priority

Prometheus metric definitions and helper functions (`track_time`, `track_time_sync`, `increment_counter`, `set_gauge`).

**Recommended tests:**
- `increment_counter` — verify counter increments with and without labels
- `increment_counter` — verify exception handling (no crash on failure)
- `set_gauge` — verify gauge sets value with and without labels
- `track_time` — verify async decorator records duration to histogram
- `track_time_sync` — verify sync decorator records duration to histogram

### 5. `core/monitoring/logging_config.py` — Lower Priority

JSON logging formatter and structured logger.

**Recommended tests:**
- `JSONFormatter.format` — verify JSON output structure (timestamp, level, message, etc.)
- `JSONFormatter.format` — verify exception info is included when present
- `setup_logging` — verify log directory creation and handler configuration
- `StructuredLogger` — verify extra fields are passed through to log records

---

## Priority 2: Existing Modules with Significant Gaps

### 6. `ui/web/app.py` — Only Pydantic Models Tested

The current `test_api.py` only tests Pydantic models (`MessageRequest`, `MessageResponse`, `TokenData`) and hits 3 basic GET endpoints. Major functionality is untested:

**Recommended tests:**
- **ConnectionManager**: `connect`, `disconnect`, `send_personal_message`, `broadcast` — verify WebSocket connection lifecycle and message routing
- **JWT authentication**: `create_token` / `verify_token` — verify token creation, expiry enforcement, and invalid token rejection
- **POST `/api/auth/login`**: verify username validation, token response structure, and invalid username rejection
- **POST `/api/messages`**: verify authenticated message sending, anonymous fallback, and validation error handling
- **GET `/api/messages/history`**: verify limit validation and response format
- **WebSocket `/ws/{user_id}`**: verify connection, message processing, broadcast, validation errors sent back to client, and disconnect cleanup

### 7. `core/node/node_manager.py` — Missing Error/Edge Cases

Current tests cover happy paths. Missing:

**Recommended tests:**
- Error handling when Redis is unavailable during message processing
- Adding duplicate participants
- Processing messages with invalid/empty content
- Removing non-existent participants
- AI agent creation with invalid parameters
- Large message handling

---

## Priority 3: Cross-Cutting Gaps

### 8. Integration Tests (None Exist)

The `pytest.ini` defines an `integration` marker but no tests use it. Key integration test scenarios:

- **Redis integration**: Full message flow through Redis pub/sub
- **End-to-end API flow**: Login → send message → retrieve history
- **WebSocket full lifecycle**: Connect → send messages → receive broadcasts → disconnect
- **Memory persistence**: Add memories → retrieve by similarity → consolidation cycle
- **Rate limiting integration**: Verify requests are actually throttled with a real (or test) Redis instance

### 9. Error Handling and Edge Cases

Across all modules, error paths and edge cases are undertested:

- Redis connection failures and reconnection behavior
- Concurrent access patterns (multiple simultaneous WebSocket clients)
- Input boundary values (max-length strings, empty inputs, Unicode edge cases)
- Graceful degradation when external services (Ollama, Redis) are unavailable

### 10. Security-Focused Tests

Given the security-sensitive nature of this application:

- JWT token tampering and algorithm confusion attacks
- Rate limiting bypass attempts (IP spoofing via `X-Forwarded-For`)
- Input validation bypass with encoded/escaped payloads
- Encryption with malformed or tampered ciphertext
- WebSocket connection exhaustion

---

## Summary of Recommendations (Ranked)

| Priority | Area | Reason |
|---|---|---|
| **P0** | `rate_limiting.py` | Security-critical, zero coverage |
| **P0** | `health_check.py` | Operational reliability, zero coverage |
| **P1** | `tls_config.py` | Security-critical, zero coverage |
| **P1** | `app.py` (WebSocket, JWT, API routes) | Core functionality, minimal coverage |
| **P2** | `metrics.py` | Helper functions untested |
| **P2** | `logging_config.py` | Infrastructure code untested |
| **P2** | Integration tests | No integration tests exist at all |
| **P3** | Security-focused tests | Missing adversarial/edge-case testing |
| **P3** | `node_manager.py` error paths | Happy-path-only coverage |
