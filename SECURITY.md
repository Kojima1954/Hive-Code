# Security Recommendations and Best Practices

This document outlines the security measures implemented in this codebase and recommendations for production deployment.

## Implemented Security Measures

### 1. Input Validation and Sanitization
- **Username validation**: Alphanumeric, underscore, and hyphen only (max 64 chars)
- **User ID validation**: Alphanumeric, underscore, and hyphen only (max 128 chars)
- **Message content validation**: Length limits (max 10,000 chars), null byte removal
- **Tag validation**: Format and count restrictions
- **Redis key sanitization**: Prevents injection attacks

### 2. Encryption
- **Hybrid encryption**: RSA-4096 for key exchange, AES-256-GCM for data
- **TLS/SSL support**: 4096-bit keys for production certificates
- **Message encryption**: Optional end-to-end encryption for messages

### 3. Rate Limiting and DDoS Protection
- **Redis-based sliding window**: Prevents API abuse
- **IP banning**: Automatic banning after repeated violations
- **Configurable fail modes**: Choose between availability (fail-open) or security (fail-closed)
- **Per-endpoint limits**: Different limits for API, WebSocket, and metrics endpoints

### 4. Authentication
- **JWT tokens**: With issued-at (iat) and expiration (exp) claims
- **Token validation**: Proper expiration checking

### 5. Modern Python Practices
- **Timezone-aware datetime**: Using `datetime.now(timezone.utc)` instead of deprecated `utcnow()`
- **Type hints**: Comprehensive type annotations throughout
- **Structured logging**: JSON-formatted logs with proper error context

## Production Security Checklist

### Critical (Must Do Before Production)

- [ ] **Change JWT_SECRET**: Replace default with a strong random string (min 32 chars)
  ```bash
  # Generate strong secret
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

- [ ] **Implement real authentication**: Replace demo login with proper user authentication
  - Use password hashing (bcrypt/argon2)
  - Implement account lockout after failed attempts
  - Add CAPTCHA for brute force protection
  - Store credentials securely (never in code or environment variables)

- [ ] **Configure CORS properly**: Replace `ALLOWED_ORIGINS=*` with specific domains
  ```bash
  ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
  ```

- [ ] **Enable TLS/SSL**: Always use HTTPS in production
  ```bash
  TLS_ENABLED=true
  ```
  - Use valid certificates (not self-signed) from Let's Encrypt or a CA
  - Configure proper certificate validation

- [ ] **Secure Redis**: 
  - Enable Redis authentication (requirepass)
  - Use TLS for Redis connections
  - Restrict Redis network access
  ```bash
  REDIS_PASSWORD=your-strong-password
  ```

### High Priority

- [ ] **Configure rate limiting**: Adjust based on your use case
  ```bash
  RATE_LIMIT_FAIL_OPEN=false  # Fail closed for better security
  RATE_LIMIT_REQUESTS=100      # Per endpoint
  RATE_LIMIT_WINDOW=60         # In seconds
  ```

- [ ] **Set up monitoring and alerting**:
  - Configure Prometheus/Grafana
  - Set up alerts for security events
  - Monitor rate limit violations and bans
  - Track authentication failures

- [ ] **Implement audit logging**:
  - Log all authentication attempts
  - Log security-relevant events
  - Store logs securely with retention policy

- [ ] **Database security** (if added):
  - Use parameterized queries (prevent SQL injection)
  - Implement least privilege access
  - Encrypt sensitive data at rest

### Medium Priority

- [ ] **Add security headers**:
  - Content-Security-Policy
  - X-Frame-Options
  - X-Content-Type-Options
  - Strict-Transport-Security

- [ ] **Implement session management**:
  - Session timeout
  - Session invalidation on logout
  - Concurrent session limits

- [ ] **Add input length limits to Pydantic models**:
  ```python
  class MessageRequest(BaseModel):
      content: str = Field(..., max_length=10000)
  ```

- [ ] **Implement CSRF protection** for state-changing operations

- [ ] **Add webhook signature verification** for federated communications

### Infrastructure Security

- [ ] **Container security**:
  - Use minimal base images
  - Scan for vulnerabilities regularly
  - Run as non-root user
  - Implement resource limits

- [ ] **Network security**:
  - Use firewalls to restrict access
  - Implement VPN for internal services
  - Use private networks for Redis/database

- [ ] **Secrets management**:
  - Use secret management service (AWS Secrets Manager, HashiCorp Vault, etc.)
  - Never commit secrets to version control
  - Rotate secrets regularly

## Security Configuration

### Environment Variables for Security

```bash
# Critical Security Settings
JWT_SECRET=your-strong-random-secret-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# TLS/SSL
TLS_ENABLED=true
TLS_CERT_PATH=/path/to/cert.crt
TLS_KEY_PATH=/path/to/key.key

# CORS
ALLOWED_ORIGINS=https://yourdomain.com

# Rate Limiting
RATE_LIMIT_FAIL_OPEN=false
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Redis Security
REDIS_PASSWORD=your-redis-password
REDIS_URL=rediss://username:password@redis:6379  # Use rediss:// for TLS
```

## Known Limitations and Warnings

### Current Demo Features (NOT FOR PRODUCTION)

1. **Demo Authentication**: The `/api/auth/login` endpoint accepts any credentials
   - **Risk**: Anyone can authenticate
   - **Fix**: Implement proper user authentication

2. **Default JWT Secret**: Uses weak default if not configured
   - **Risk**: JWT tokens can be forged
   - **Fix**: Set strong JWT_SECRET

3. **Wildcard CORS**: Allows all origins by default
   - **Risk**: CSRF attacks possible
   - **Fix**: Configure specific allowed origins

4. **Self-signed certificates**: Generated automatically
   - **Risk**: Man-in-the-middle attacks, browser warnings
   - **Fix**: Use proper CA-signed certificates

## Incident Response

### If Security Breach Suspected

1. **Immediate Actions**:
   - Rotate JWT_SECRET immediately
   - Ban suspicious IPs
   - Review audit logs
   - Invalidate all sessions

2. **Investigation**:
   - Check logs for unauthorized access
   - Review rate limit violations
   - Check for data exfiltration
   - Identify attack vector

3. **Remediation**:
   - Patch vulnerabilities
   - Update dependencies
   - Strengthen security controls
   - Document lessons learned

## Dependency Security

### Regular Maintenance

```bash
# Check for security vulnerabilities
pip install safety
safety check -r requirements.txt

# Update dependencies (test thoroughly)
pip list --outdated
pip install --upgrade <package>
```

### Critical Dependencies to Monitor

- cryptography: Security vulnerabilities can be critical
- fastapi/uvicorn: Web framework security
- redis: Connection security
- pyjwt: Token validation
- ollama: AI model security

## Reporting Security Issues

If you discover a security vulnerability:

1. **DO NOT** open a public issue
2. Email security contact (configure this)
3. Include:
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Security Testing

### Regular Security Testing

- [ ] Run dependency vulnerability scans weekly
- [ ] Perform penetration testing before major releases
- [ ] Review audit logs regularly
- [ ] Test disaster recovery procedures
- [ ] Conduct security training for team

### Automated Security Checks

- CodeQL (GitHub Advanced Security)
- Dependency scanning (Dependabot, Snyk)
- SAST (Static Application Security Testing)
- DAST (Dynamic Application Security Testing)

## Compliance Considerations

Depending on your use case, you may need to comply with:

- **GDPR**: Data privacy and protection
- **HIPAA**: Healthcare data security
- **PCI DSS**: Payment card data
- **SOC 2**: Security, availability, confidentiality

Consult with legal counsel for specific requirements.

---

**Last Updated**: 2025-10-31
**Security Review Recommended**: Quarterly or after major changes
